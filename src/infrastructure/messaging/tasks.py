"""
Celery Background Tasks

All async background tasks for ETL imports, analytics calculations,
scheduled reports, and notification delivery.
"""

import asyncio
import io
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from celery import shared_task

from .celery_app import celery_app

logger = logging.getLogger(__name__)

# ─── Async helper ────────────────────────────────────────────────────────────
# Celery workers are sync; we need a helper to run async DB operations.


def _run_async(coro):
    """Run an async coroutine in a new event loop (for Celery workers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_session_factory():
    """Get async session factory for use in tasks."""
    from src.infrastructure.database.session import get_session_factory
    return get_session_factory()


def _normalize_phone(raw: str) -> str | None:
    """Normalize Iranian phone number. Delegates to core utility."""
    from src.core.utils import normalize_phone_strict
    return normalize_phone_strict(raw)


def _parse_duration(raw) -> int:
    """Parse duration from text like '366 sec' or '2 min 30 sec' to integer seconds."""
    import re
    if not raw or (hasattr(raw, '__class__') and raw.__class__.__name__ == 'float' and str(raw) == 'nan'):
        return 0
    text = str(raw).strip().lower()
    match = re.match(r"(\d+)\s*sec", text)
    if match:
        return int(match.group(1))
    match = re.match(r"(\d+)\s*min(?:\s+(\d+)\s*sec)?", text)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2) or 0)
    try:
        return int(float(text.replace(",", "")))
    except (ValueError, TypeError):
        return 0


def _notify_ws(event_type: str, payload: dict[str, Any]) -> None:
    """Publish a WebSocket event through Redis pub/sub."""
    try:
        import redis as redis_lib
        from src.core.config import settings
        r = redis_lib.Redis.from_url(settings.redis.url)
        message = json.dumps({
            "type": event_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat(),
        }, default=str)
        r.publish("funnelier:ws:events", message)
        r.close()
    except Exception as e:
        logger.warning(f"WebSocket notification failed: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# ETL Import Tasks
# ═════════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.import_leads_excel")
def import_leads_excel(self, file_content_b64: str, filename: str,
                       tenant_id: str, category: str | None = None):
    """
    Import leads from an uploaded Excel file (base64-encoded content).
    """
    import base64
    tenant_uuid = UUID(tenant_id)
    content = base64.b64decode(file_content_b64)

    _notify_ws("import_started", {
        "task_id": self.request.id,
        "file": filename,
        "type": "leads",
        "tenant_id": tenant_id,
    })

    async def _do_import():
        import pandas as pd
        from src.modules.leads.infrastructure.repositories import ContactRepository
        from src.modules.leads.domain.entities import Contact
        from src.core.domain.entities import PhoneNumber

        df = pd.read_excel(io.BytesIO(content))

        if not category:
            cat = Path(filename).stem
        else:
            cat = category

        # Find phone column
        phone_col = _find_phone_column(df)
        if not phone_col:
            return {"error": f"No phone column found. Columns: {list(df.columns)}"}

        name_col = _find_name_column(df)
        session_factory = _get_session_factory()
        imported = 0
        duplicates = 0
        errors = 0
        error_details = []

        async with session_factory() as session:
            repo = ContactRepository(session, tenant_uuid)

            for idx, row in df.iterrows():
                try:
                    phone = _normalize_phone(str(row[phone_col]))
                    if not phone:
                        errors += 1
                        continue

                    name = (str(row[name_col]).strip()
                            if name_col and pd.notna(row.get(name_col))
                            else "")

                    existing = await repo.get_by_phone(phone)
                    if existing:
                        duplicates += 1
                        continue

                    contact = Contact(
                        id=uuid4(),
                        tenant_id=tenant_uuid,
                        phone_number=PhoneNumber.from_string(phone),
                        name=name,
                        source_name=f"excel:{filename}",
                        category_name=cat,
                        tags=[cat] if cat else [],
                    )
                    await repo.add(contact)
                    imported += 1

                    # Report progress every 100 rows
                    if imported % 100 == 0:
                        self.update_state(state="PROGRESS", meta={
                            "current": idx + 1,
                            "total": len(df),
                            "imported": imported,
                        })

                except Exception as e:
                    errors += 1
                    if len(error_details) < 10:
                        error_details.append(f"Row {idx}: {str(e)[:80]}")

            await session.commit()

        return {
            "file_name": filename,
            "category": cat,
            "total_records": len(df),
            "imported": imported,
            "duplicates": duplicates,
            "errors": errors,
            "error_details": error_details,
        }

    result = _run_async(_do_import())

    _notify_ws("import_completed", {
        "task_id": self.request.id,
        "file": filename,
        "type": "leads",
        "result": result,
    })

    return result


@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.import_call_logs_csv")
def import_call_logs_csv(self, file_content_b64: str, filename: str,
                         tenant_id: str, salesperson: str | None = None):
    """Import call logs from a CSV file (base64-encoded content)."""
    import base64
    tenant_uuid = UUID(tenant_id)
    content = base64.b64decode(file_content_b64)

    _notify_ws("import_started", {
        "task_id": self.request.id,
        "file": filename,
        "type": "call_logs",
    })

    async def _do_import():
        import pandas as pd
        from src.modules.communications.infrastructure.repositories import CallLogRepository
        from src.modules.communications.domain.entities import CallLog as CallLogEntity
        from src.core.domain import CallType, CallSource

        # Try multiple encodings
        df = None
        for enc in ["utf-8-sig", "utf-8", "cp1256", "latin1"]:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except Exception:
                continue
        if df is None:
            return {"error": "Cannot decode CSV file"}

        sp = salesperson or _extract_salesperson(filename)

        phone_col = _find_phone_column(df)
        if not phone_col:
            return {"error": f"No phone column found. Columns: {list(df.columns)}"}

        duration_col = _find_column(df, [
            "duration", "مدت", "طول مکالمه", "Duration"])
        type_col = _find_column(df, [
            "type", "نوع", "Type", "Direction"])

        session_factory = _get_session_factory()
        imported = 0
        errors = 0

        async with session_factory() as session:
            repo = CallLogRepository(session, tenant_uuid)

            for idx, row in df.iterrows():
                try:
                    phone = _normalize_phone(str(row[phone_col]))
                    if not phone:
                        errors += 1
                        continue

                    duration = _parse_duration(
                        row.get(duration_col) if duration_col else None)

                    # Determine direction from call type
                    call_type = str(row.get(type_col, "")).strip().lower() if type_col else ""
                    if call_type in ("outgoing",):
                        ct = CallType.OUTGOING
                    elif call_type in ("incomming", "incoming"):
                        ct = CallType.INCOMING
                    elif call_type in ("missed",):
                        ct = CallType.MISSED
                    else:
                        ct = CallType.OUTGOING

                    is_successful = call_type not in ("missed", "rejected") and duration >= 90

                    call_log = CallLogEntity(
                        id=uuid4(),
                        tenant_id=tenant_uuid,
                        phone_number=phone,
                        call_type=ct,
                        source=CallSource.MOBILE,
                        duration_seconds=duration,
                        call_time=datetime.utcnow(),
                        salesperson_name=sp or "unknown",
                        is_successful=is_successful,
                        metadata={"source_file": filename},
                    )
                    await repo.add(call_log)
                    imported += 1
                except Exception:
                    errors += 1

            await session.commit()

        return {
            "file_name": filename,
            "category": sp,
            "total_records": len(df),
            "imported": imported,
            "errors": errors,
        }

    result = _run_async(_do_import())

    _notify_ws("import_completed", {
        "task_id": self.request.id,
        "file": filename,
        "type": "call_logs",
        "result": result,
    })

    return result


@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.import_sms_logs_csv")
def import_sms_logs_csv(self, file_content_b64: str, filename: str,
                        tenant_id: str):
    """Import SMS delivery logs from CSV (base64-encoded content)."""
    import base64
    tenant_uuid = UUID(tenant_id)
    content = base64.b64decode(file_content_b64)

    async def _do_import():
        import pandas as pd
        from src.modules.communications.infrastructure.repositories import SMSLogRepository
        from src.modules.communications.domain.entities import SMSLog as SMSLogEntity
        from src.core.domain import SMSDirection, SMSStatus

        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")

        phone_col = _find_phone_column(df)
        if not phone_col:
            return {"error": f"No phone column found. Columns: {list(df.columns)}"}

        status_col = _find_column(df, [
            "status", "وضعیت", "StatusText", "delivery"])
        content_col = _find_column(df, [
            "message", "متن", "content", "body", "Message"])

        session_factory = _get_session_factory()
        imported = 0
        errors = 0

        async with session_factory() as session:
            repo = SMSLogRepository(session, tenant_uuid)
            for idx, row in df.iterrows():
                try:
                    phone = _normalize_phone(str(row[phone_col]))
                    if not phone:
                        errors += 1
                        continue

                    status = SMSStatus.DELIVERED
                    if status_col and pd.notna(row.get(status_col)):
                        raw_status = str(row[status_col]).lower()
                        if "deliver" in raw_status or "تحویل" in raw_status:
                            status = SMSStatus.DELIVERED
                        elif "fail" in raw_status or "خطا" in raw_status:
                            status = SMSStatus.FAILED
                        else:
                            status = SMSStatus.SENT

                    sms_log = SMSLogEntity(
                        id=uuid4(),
                        tenant_id=tenant_uuid,
                        phone_number=phone,
                        direction=SMSDirection.OUTBOUND,
                        content=str(row.get(content_col, ""))[:500] if content_col else "",
                        status=status,
                        provider_name="kavenegar",
                        metadata={"source_file": filename},
                    )
                    await repo.add(sms_log)
                    imported += 1
                except Exception:
                    errors += 1

            await session.commit()

        return {
            "file_name": filename,
            "total_records": len(df),
            "imported": imported,
            "errors": errors,
        }

    result = _run_async(_do_import())

    _notify_ws("import_completed", {
        "task_id": self.request.id,
        "file": filename,
        "type": "sms_logs",
        "result": result,
    })

    return result


@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.import_voip_json")
def import_voip_json(self, file_content_b64: str, filename: str,
                     tenant_id: str):
    """Import VoIP call logs from JSON (Asterisk CDR format)."""
    import base64
    tenant_uuid = UUID(tenant_id)
    content = base64.b64decode(file_content_b64)

    async def _do_import():
        from src.modules.communications.infrastructure.repositories import CallLogRepository
        from src.modules.communications.domain.entities import CallLog as CallLogEntity
        from src.core.domain import CallType, CallSource

        records = json.loads(content)
        if isinstance(records, dict):
            records = records.get("records", records.get("calls", [records]))
        if not isinstance(records, list):
            records = [records]

        session_factory = _get_session_factory()
        imported = 0
        errors = 0

        async with session_factory() as session:
            repo = CallLogRepository(session, tenant_uuid)
            for rec in records:
                try:
                    phone = _normalize_phone(
                        str(rec.get("dst", rec.get("destination",
                            rec.get("phone", "")))))
                    if not phone:
                        errors += 1
                        continue

                    duration = int(rec.get("billsec",
                                           rec.get("duration", 0)))
                    direction = rec.get("direction", "outbound")
                    ct = CallType.INCOMING if direction == "inbound" else CallType.OUTGOING

                    call_log = CallLogEntity(
                        id=uuid4(),
                        tenant_id=tenant_uuid,
                        phone_number=phone,
                        call_type=ct,
                        source=CallSource.VOIP,
                        duration_seconds=duration,
                        call_time=datetime.utcnow(),
                        salesperson_name=str(rec.get("src",
                            rec.get("caller", "voip"))),
                        voip_call_id=rec.get("uniqueid", rec.get("call_id")),
                        voip_extension=rec.get("channel", rec.get("extension")),
                        is_successful=duration >= 90,
                        metadata={"source_file": filename},
                    )
                    await repo.add(call_log)
                    imported += 1
                except Exception:
                    errors += 1

            await session.commit()

        return {
            "file_name": filename,
            "total_records": len(records),
            "imported": imported,
            "errors": errors,
        }

    result = _run_async(_do_import())

    _notify_ws("import_completed", {
        "task_id": self.request.id,
        "file": filename,
        "type": "voip",
        "result": result,
    })

    return result


@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.import_leads_batch")
def import_leads_batch(self, tenant_id: str):
    """
    Batch import all Excel files from the leads-numbers folder.
    Reports progress per file.
    """
    tenant_uuid = UUID(tenant_id)
    folder = Path(__file__).parent.parent.parent.parent / "leads-numbers"

    if not folder.exists():
        return {"error": f"Folder not found: {folder}"}

    xlsx_files = sorted(folder.glob("*.xlsx"))
    total_files = len(xlsx_files)

    results = []
    total_imported = 0
    total_dupes = 0
    total_errors = 0

    for file_idx, xlsx in enumerate(xlsx_files):
        self.update_state(state="PROGRESS", meta={
            "current_file": file_idx + 1,
            "total_files": total_files,
            "file_name": xlsx.name,
        })

        try:
            with open(xlsx, "rb") as f:
                import base64
                content_b64 = base64.b64encode(f.read()).decode()

            # Run individual import (inline, not as sub-task)
            result = import_leads_excel(
                content_b64, xlsx.name, tenant_id,
                category=Path(xlsx.name).stem)

            results.append(result)
            total_imported += result.get("imported", 0)
            total_dupes += result.get("duplicates", 0)
            total_errors += result.get("errors", 0)

        except Exception as e:
            results.append({
                "file_name": xlsx.name,
                "errors": 1,
                "error_details": [str(e)[:200]],
            })
            total_errors += 1

    summary = {
        "files_processed": len(results),
        "total_imported": total_imported,
        "total_duplicates": total_dupes,
        "total_errors": total_errors,
        "results": results,
    }

    _notify_ws("batch_import_completed", {
        "task_id": self.request.id,
        "type": "leads_batch",
        "summary": summary,
    })

    return summary


# ═════════════════════════════════════════════════════════════════════════════
# Analytics Calculation Tasks
# ═════════════════════════════════════════════════════════════════════════════

@celery_app.task(name="src.infrastructure.messaging.tasks.calculate_daily_funnel_snapshot")
def calculate_daily_funnel_snapshot(tenant_id: str | None = None):
    """
    Calculate and store daily funnel snapshot.
    If tenant_id is None, runs for all tenants.
    """
    async def _calculate():
        from sqlalchemy import select
        from src.infrastructure.database.models.tenants import TenantModel

        session_factory = _get_session_factory()

        async with session_factory() as session:
            if tenant_id:
                tenant_ids = [UUID(tenant_id)]
            else:
                stmt = select(TenantModel.id)
                result = await session.execute(stmt)
                tenant_ids = [row[0] for row in result.fetchall()]

        snapshots = []
        for tid in tenant_ids:
            try:
                snapshot = await _compute_funnel_snapshot(tid)
                # Persist snapshot to database
                await _persist_funnel_snapshot(tid, snapshot)
                snapshots.append(snapshot)
            except Exception as e:
                logger.error(f"Funnel snapshot failed for tenant {tid}: {e}")

        return {
            "tenants_processed": len(snapshots),
            "date": datetime.utcnow().date().isoformat(),
            "snapshots": snapshots,
        }

    result = _run_async(_calculate())

    _notify_ws("funnel_snapshot_completed", {
        "date": datetime.utcnow().date().isoformat(),
        "result": result,
    })

    return result


async def _persist_funnel_snapshot(tenant_id: UUID, snapshot: dict) -> None:
    """Persist a computed funnel snapshot to the database."""
    from src.modules.analytics.infrastructure.repositories import FunnelSnapshotRepository

    session_factory = _get_session_factory()
    async with session_factory() as session:
        repo = FunnelSnapshotRepository(session, tenant_id)

        class SnapshotData:
            pass

        data = SnapshotData()
        data.snapshot_date = datetime.utcnow().date()
        data.stage_counts = snapshot.get("stages", {})
        data.new_leads = snapshot.get("stages", {}).get("lead_acquired", 0)
        data.new_conversions = snapshot.get("stages", {}).get("payment_received", 0)
        data.daily_revenue = 0
        data.conversion_rates = snapshot.get("conversions", {})
        data.conversion_rate = snapshot.get("conversions", {}).get("overall", 0.0) / 100
        data.stage_transitions = []
        data.new_sms_sent = snapshot.get("stages", {}).get("sms_sent", 0)
        data.new_sms_delivered = snapshot.get("stages", {}).get("sms_delivered", 0)
        data.new_calls = snapshot.get("stages", {}).get("call_attempted", 0)
        data.new_answered_calls = snapshot.get("stages", {}).get("call_answered", 0)
        data.new_successful_calls = snapshot.get("stages", {}).get("call_answered", 0)
        data.new_invoices = snapshot.get("stages", {}).get("invoice_issued", 0)
        data.new_payments = snapshot.get("stages", {}).get("payment_received", 0)

        await repo.save(data)
        await session.commit()


async def _compute_funnel_snapshot(tenant_id: UUID) -> dict[str, Any]:
    """Compute funnel snapshot for a single tenant."""
    from sqlalchemy import select, func
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.communications import (
        SMSLogModel, CallLogModel,
    )
    from src.infrastructure.database.models.sales import (
        InvoiceModel, PaymentModel,
    )

    session_factory = _get_session_factory()
    today = datetime.utcnow().date()

    async with session_factory() as session:
        # Stage 1: Total leads
        leads_count = (await session.execute(
            select(func.count(ContactModel.id)).where(
                ContactModel.tenant_id == tenant_id)
        )).scalar() or 0

        # Stage 2: SMS sent
        sms_sent = (await session.execute(
            select(func.count(SMSLogModel.id)).where(
                SMSLogModel.tenant_id == tenant_id)
        )).scalar() or 0

        # Stage 3: SMS delivered
        sms_delivered = (await session.execute(
            select(func.count(SMSLogModel.id)).where(
                SMSLogModel.tenant_id == tenant_id,
                SMSLogModel.status == "delivered",
            )
        )).scalar() or 0

        # Stage 4: Call attempted
        calls_attempted = (await session.execute(
            select(func.count(CallLogModel.id)).where(
                CallLogModel.tenant_id == tenant_id)
        )).scalar() or 0

        # Stage 5: Call answered (≥90 seconds)
        calls_answered = (await session.execute(
            select(func.count(CallLogModel.id)).where(
                CallLogModel.tenant_id == tenant_id,
                CallLogModel.is_successful == True,
            )
        )).scalar() or 0

        # Stage 6: Invoice issued
        invoices_issued = (await session.execute(
            select(func.count(InvoiceModel.id)).where(
                InvoiceModel.tenant_id == tenant_id)
        )).scalar() or 0

        # Stage 7: Payment received
        payments_received = (await session.execute(
            select(func.count(PaymentModel.id)).where(
                PaymentModel.tenant_id == tenant_id)
        )).scalar() or 0

    snapshot = {
        "tenant_id": str(tenant_id),
        "date": today.isoformat(),
        "stages": {
            "lead_acquired": leads_count,
            "sms_sent": sms_sent,
            "sms_delivered": sms_delivered,
            "call_attempted": calls_attempted,
            "call_answered": calls_answered,
            "invoice_issued": invoices_issued,
            "payment_received": payments_received,
        },
        "conversions": {
            "lead_to_sms": (sms_sent / leads_count * 100) if leads_count else 0,
            "sms_to_delivered": (sms_delivered / sms_sent * 100) if sms_sent else 0,
            "delivered_to_call": (calls_attempted / sms_delivered * 100) if sms_delivered else 0,
            "call_to_answered": (calls_answered / calls_attempted * 100) if calls_attempted else 0,
            "answered_to_invoice": (invoices_issued / calls_answered * 100) if calls_answered else 0,
            "invoice_to_payment": (payments_received / invoices_issued * 100) if invoices_issued else 0,
            "overall": (payments_received / leads_count * 100) if leads_count else 0,
        },
    }

    return snapshot


@celery_app.task(name="src.infrastructure.messaging.tasks.calculate_rfm_segments")
def calculate_rfm_segments(tenant_id: str | None = None):
    """
    Recalculate RFM segments for all contacts.
    If tenant_id is None, runs for all tenants.
    """
    async def _calculate():
        from sqlalchemy import select, func
        from src.infrastructure.database.models.tenants import TenantModel
        from src.infrastructure.database.models.leads import ContactModel
        from src.infrastructure.database.models.sales import (
            InvoiceModel, PaymentModel,
        )
        from src.modules.segmentation.domain.services import RFMSegmentationService
        from src.core.config import settings

        session_factory = _get_session_factory()

        async with session_factory() as session:
            if tenant_id:
                tenant_ids = [UUID(tenant_id)]
            else:
                stmt = select(TenantModel.id)
                result = await session.execute(stmt)
                tenant_ids = [row[0] for row in result.fetchall()]

        results = []
        now = datetime.utcnow()

        for tid in tenant_ids:
            try:
                async with session_factory() as session:
                    # Get contacts with payment data
                    contacts_stmt = (
                        select(ContactModel)
                        .where(ContactModel.tenant_id == tid)
                    )
                    contacts_result = await session.execute(contacts_stmt)
                    contacts = contacts_result.scalars().all()

                    # Get payment data grouped by phone
                    payments_stmt = (
                        select(
                            PaymentModel.phone_number,
                            func.count(PaymentModel.id).label("frequency"),
                            func.sum(PaymentModel.amount).label("monetary"),
                            func.max(PaymentModel.paid_at).label("last_payment"),
                        )
                        .where(PaymentModel.tenant_id == tid)
                        .group_by(PaymentModel.phone_number)
                    )
                    payments_result = await session.execute(payments_stmt)
                    payment_data = {
                        row.phone_number: {
                            "frequency": row.frequency,
                            "monetary": float(row.monetary or 0),
                            "last_payment": row.last_payment,
                        }
                        for row in payments_result.fetchall()
                    }

                rfm_service = RFMSegmentationService()
                segment_counts = {}

                # Update contacts with RFM scores
                async with session_factory() as session:
                    from sqlalchemy import update as sa_update

                    for contact in contacts:
                        pdata = payment_data.get(contact.phone_number, {})
                        frequency = pdata.get("frequency", 0)
                        monetary = pdata.get("monetary", 0)
                        last_payment = pdata.get("last_payment")

                        recency_days = (
                            (now - last_payment).days
                            if last_payment else 999
                        )

                        profile = rfm_service.calculate_rfm(
                            recency_days=recency_days,
                            frequency=frequency,
                            monetary=monetary,
                        )

                        segment_name = profile.segment.value
                        segment_counts[segment_name] = segment_counts.get(
                            segment_name, 0) + 1

                        # Persist RFM scores back to contact
                        stmt = (
                            sa_update(ContactModel)
                            .where(ContactModel.id == contact.id)
                            .values(
                                rfm_segment=segment_name,
                                rfm_score=f"{profile.recency_score}{profile.frequency_score}{profile.monetary_score}",
                                recency_score=profile.recency_score,
                                frequency_score=profile.frequency_score,
                                monetary_score=profile.monetary_score,
                                last_rfm_update=now,
                            )
                        )
                        await session.execute(stmt)

                    await session.commit()

                results.append({
                    "tenant_id": str(tid),
                    "total_contacts": len(contacts),
                    "segments": segment_counts,
                })

            except Exception as e:
                logger.error(f"RFM calculation failed for tenant {tid}: {e}")
                results.append({
                    "tenant_id": str(tid),
                    "error": str(e),
                })

        return {
            "tenants_processed": len(results),
            "results": results,
        }

    result = _run_async(_calculate())

    _notify_ws("rfm_calculation_completed", {
        "result": result,
    })

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Report Generation Tasks
# ═════════════════════════════════════════════════════════════════════════════

@celery_app.task(name="src.infrastructure.messaging.tasks.generate_daily_report")
def generate_daily_report(tenant_id: str | None = None):
    """Generate daily summary report."""
    async def _generate():
        from sqlalchemy import select, func
        from src.infrastructure.database.models.tenants import TenantModel

        session_factory = _get_session_factory()

        async with session_factory() as session:
            if tenant_id:
                tenant_ids = [UUID(tenant_id)]
            else:
                stmt = select(TenantModel.id)
                result = await session.execute(stmt)
                tenant_ids = [row[0] for row in result.fetchall()]

        reports = []
        for tid in tenant_ids:
            try:
                snapshot = await _compute_funnel_snapshot(tid)
                reports.append({
                    "tenant_id": str(tid),
                    "date": datetime.utcnow().date().isoformat(),
                    "funnel": snapshot,
                    "generated_at": datetime.utcnow().isoformat(),
                })
            except Exception as e:
                logger.error(f"Daily report failed for tenant {tid}: {e}")

        return {
            "reports_generated": len(reports),
            "reports": reports,
        }

    result = _run_async(_generate())

    _notify_ws("daily_report_generated", {
        "result": result,
    })

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Alert & Notification Tasks
# ═════════════════════════════════════════════════════════════════════════════

@celery_app.task(name="src.infrastructure.messaging.tasks.check_alerts")
def check_alerts(tenant_id: str | None = None):
    """
    Check alert rules and trigger notifications for any violations.
    """
    async def _check():
        from sqlalchemy import select
        from src.infrastructure.database.models.tenants import TenantModel

        session_factory = _get_session_factory()

        async with session_factory() as session:
            if tenant_id:
                tenant_ids = [UUID(tenant_id)]
            else:
                stmt = select(TenantModel.id)
                result = await session.execute(stmt)
                tenant_ids = [row[0] for row in result.fetchall()]

        triggered_alerts = []
        for tid in tenant_ids:
            try:
                snapshot = await _compute_funnel_snapshot(tid)
                conversions = snapshot.get("conversions", {})

                # Check conversion drop alerts
                if conversions.get("sms_to_delivered", 100) < 70:
                    triggered_alerts.append({
                        "tenant_id": str(tid),
                        "type": "delivery_rate_low",
                        "severity": "warning",
                        "message": f"SMS delivery rate is {conversions['sms_to_delivered']:.1f}% (below 70%)",
                        "value": conversions["sms_to_delivered"],
                    })

                if conversions.get("call_to_answered", 100) < 30:
                    triggered_alerts.append({
                        "tenant_id": str(tid),
                        "type": "call_answer_rate_low",
                        "severity": "warning",
                        "message": f"Call answer rate is {conversions['call_to_answered']:.1f}% (below 30%)",
                        "value": conversions["call_to_answered"],
                    })

                if conversions.get("overall", 100) < 1:
                    triggered_alerts.append({
                        "tenant_id": str(tid),
                        "type": "conversion_drop",
                        "severity": "critical",
                        "message": f"Overall conversion rate is {conversions['overall']:.2f}% (below 1%)",
                        "value": conversions["overall"],
                    })

            except Exception as e:
                logger.error(f"Alert check failed for tenant {tid}: {e}")

        return {
            "tenants_checked": len(tenant_ids),
            "alerts_triggered": len(triggered_alerts),
            "alerts": triggered_alerts,
        }

    result = _run_async(_check())

    if result.get("alerts_triggered", 0) > 0:
        _notify_ws("alerts_triggered", {
            "alerts": result["alerts"],
        })

    return result


@celery_app.task(name="src.infrastructure.messaging.tasks.send_sms_notification")
def send_sms_notification(phone: str, message: str):
    """Send an SMS notification via Kavenegar (or configured provider)."""
    from src.core.config import settings

    if not settings.kavenegar.api_key:
        logger.warning("Kavenegar API key not configured; SMS not sent")
        return {"status": "skipped", "reason": "api_key_not_configured"}

    try:
        import httpx
        url = f"https://api.kavenegar.com/v1/{settings.kavenegar.api_key}/sms/send.json"
        response = httpx.post(url, data={
            "receptor": phone,
            "message": message,
            "sender": settings.kavenegar.sender,
        }, timeout=30)
        return {"status": "sent", "response": response.json()}
    except Exception as e:
        logger.error(f"SMS send failed: {e}")
        return {"status": "failed", "error": str(e)}


# ═════════════════════════════════════════════════════════════════════════════
# Data Source Sync Tasks
# ═════════════════════════════════════════════════════════════════════════════

@celery_app.task(bind=True, name="src.infrastructure.messaging.tasks.sync_mongodb_invoices")
def sync_mongodb_invoices(self, tenant_id: str, connection_string: str,
                          database_name: str, collection_name: str = "invoices"):
    """Sync invoices from a tenant's MongoDB database."""
    tenant_uuid = UUID(tenant_id)

    async def _sync():
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.modules.sales.infrastructure.repositories import InvoiceRepository

        client = AsyncIOMotorClient(connection_string)
        db = client[database_name]
        collection = db[collection_name]

        cursor = collection.find({})
        session_factory = _get_session_factory()
        imported = 0
        errors = 0

        async with session_factory() as session:
            repo = InvoiceRepository(session, tenant_uuid)

            async for doc in cursor:
                try:
                    phone = _normalize_phone(
                        str(doc.get("phone", doc.get("customer_phone", ""))))
                    if not phone:
                        errors += 1
                        continue

                    from src.modules.sales.domain.entities import Invoice, InvoiceLineItem
                    from src.core.domain import InvoiceStatus

                    invoice = Invoice(
                        id=uuid4(),
                        tenant_id=tenant_uuid,
                        invoice_number=str(doc.get("invoice_number",
                            doc.get("_id", ""))),
                        phone_number=phone,
                        total_amount=int(float(doc.get("total",
                            doc.get("amount", 0)))),
                        subtotal=int(float(doc.get("subtotal",
                            doc.get("total", 0)))),
                        status=InvoiceStatus.ISSUED,
                        external_id=str(doc.get("_id", "")),
                        metadata={"source": f"mongodb:{database_name}.{collection_name}"},
                    )
                    await repo.add(invoice)
                    imported += 1
                except Exception:
                    errors += 1

            await session.commit()

        client.close()
        return {
            "imported": imported,
            "errors": errors,
        }

    result = _run_async(_sync())

    _notify_ws("sync_completed", {
        "task_id": self.request.id,
        "type": "mongodb_invoices",
        "result": result,
    })

    return result


# ═════════════════════════════════════════════════════════════════════════════
# Helper Functions (duplicated from ETL routes for task independence)
# ═════════════════════════════════════════════════════════════════════════════

def _find_phone_column(df) -> str | None:
    """Find the phone number column in a DataFrame."""
    import pandas as pd
    candidates = [
        "phone", "phone_number", "mobile", "شماره", "شماره تلفن",
        "شماره موبایل", "تلفن", "موبایل", "Phone", "Mobile", "Number",
        "شماره تماس", "Destination", "dst", "number", "tel",
    ]
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for c in candidates:
            if c.lower() in col_lower:
                return col
    # Heuristic: check for phone-like data
    for col in df.columns:
        sample = df[col].dropna().head(10).astype(str)
        phone_count = sum(1 for v in sample if _normalize_phone(v) is not None)
        if phone_count >= 5:
            return col
    return None


def _find_name_column(df) -> str | None:
    """Find the name column in a DataFrame."""
    candidates = ["name", "نام", "نام و نام خانوادگی", "full_name", "Name"]
    for col in df.columns:
        for c in candidates:
            if c.lower() in str(col).lower():
                return col
    return None


def _find_column(df, candidates: list[str]) -> str | None:
    """Find a column matching any candidate name."""
    for col in df.columns:
        for c in candidates:
            if c.lower() in str(col).lower():
                return col
    return None


def _extract_salesperson(filename: str) -> str:
    """Extract salesperson name from call log filename."""
    name = Path(filename).stem
    if " - " in name:
        return name.split(" - ")[-1].strip()
    return name.strip()

