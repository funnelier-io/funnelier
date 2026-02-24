"""
ETL / Data Import API Routes

Upload and import data files (Excel leads, CSV call logs, JSON VoIP logs).
Supports both synchronous (inline) and asynchronous (Celery) processing.
"""

import base64
import io
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from pydantic import BaseModel

from src.api.dependencies import get_current_tenant_id

router = APIRouter(prefix="/import", tags=["import"])


class ImportResult(BaseModel):
    file_name: str
    category: str | None = None
    total_records: int = 0
    imported: int = 0
    duplicates: int = 0
    errors: int = 0
    error_details: list[str] = []


class ImportSummary(BaseModel):
    files_processed: int
    total_imported: int
    total_duplicates: int
    total_errors: int
    results: list[ImportResult]


class AsyncTaskResponse(BaseModel):
    """Response for async (background) import requests."""
    task_id: str
    status: str = "queued"
    message: str = ""


# ============================================================================
# Lead Import (Excel)
# ============================================================================

@router.post("/leads/upload", response_model=ImportResult)
async def import_leads_excel(
    file: UploadFile = File(...),
    category: str = Query(None, description="Override category (default: from filename)"),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Import leads from an Excel file (.xlsx).
    Phone numbers are normalized and deduplicated.
    Category is extracted from filename if not provided.
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx/.xls files accepted")

    try:
        import pandas as pd
        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(400, f"Cannot read Excel file: {e}")

    # Extract category from filename if not provided
    if not category:
        category = _extract_category(file.filename)

    # Normalize and import
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.repositories.leads import ContactRepository

    session_factory = get_session_factory()
    imported = 0
    duplicates = 0
    errors = 0
    error_details = []

    # Find phone column
    phone_col = _find_phone_column(df)
    if not phone_col:
        raise HTTPException(400, f"No phone column found. Columns: {list(df.columns)}")

    name_col = _find_name_column(df)

    async with session_factory() as session:
        repo = ContactRepository(session)

        for idx, row in df.iterrows():
            try:
                phone = _normalize_phone(str(row[phone_col]))
                if not phone:
                    errors += 1
                    continue

                name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else None

                # Check duplicate
                existing = await repo.find_by_field("phone_number", phone, tenant_id)
                if existing:
                    duplicates += 1
                    continue

                contact_data = {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "phone_number": phone,
                    "name": name or "",
                    "source": f"excel:{file.filename}",
                    "category": category,
                    "tags": [category] if category else [],
                }
                await repo.create(contact_data)
                imported += 1

            except Exception as e:
                errors += 1
                if len(error_details) < 10:
                    error_details.append(f"Row {idx}: {str(e)[:80]}")

        await session.commit()

    return ImportResult(
        file_name=file.filename,
        category=category,
        total_records=len(df),
        imported=imported,
        duplicates=duplicates,
        errors=errors,
        error_details=error_details,
    )


# ============================================================================
# Call Log Import (CSV)
# ============================================================================

@router.post("/calls/upload", response_model=ImportResult)
async def import_call_logs_csv(
    file: UploadFile = File(...),
    salesperson: str = Query(None, description="Salesperson name (default: from filename)"),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Import call logs from CSV file.
    Expected columns: phone/number, duration, date/time, type, status.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files accepted")

    try:
        import pandas as pd
        content = await file.read()
        # Try multiple encodings
        for enc in ["utf-8", "utf-8-sig", "cp1256", "latin1"]:
            try:
                df = pd.read_csv(io.BytesIO(content), encoding=enc)
                break
            except Exception:
                continue
        else:
            raise HTTPException(400, "Cannot decode CSV file")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Cannot read CSV: {e}")

    if not salesperson:
        salesperson = _extract_salesperson(file.filename)

    phone_col = _find_phone_column(df)
    if not phone_col:
        raise HTTPException(400, f"No phone column found. Columns: {list(df.columns)}")

    duration_col = _find_column(df, ["duration", "مدت", "طول مکالمه", "Duration"])
    date_col = _find_column(df, ["date", "تاریخ", "Date", "DateTime", "Start"])

    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.repositories.communications import CallLogRepository

    session_factory = get_session_factory()
    imported = 0
    errors = 0
    error_details = []

    async with session_factory() as session:
        repo = CallLogRepository(session)

        for idx, row in df.iterrows():
            try:
                phone = _normalize_phone(str(row[phone_col]))
                if not phone:
                    errors += 1
                    continue

                duration = 0
                if duration_col and pd.notna(row.get(duration_col)):
                    try:
                        duration = int(float(str(row[duration_col]).replace(",", "")))
                    except ValueError:
                        pass

                call_data = {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "phone_number": phone,
                    "salesperson_name": salesperson or "unknown",
                    "duration_seconds": duration,
                    "direction": "outbound",
                    "answered": duration >= 90,  # 1.5 min = successful
                    "source": f"csv:{file.filename}",
                }
                await repo.create(call_data)
                imported += 1

            except Exception as e:
                errors += 1
                if len(error_details) < 10:
                    error_details.append(f"Row {idx}: {str(e)[:80]}")

        await session.commit()

    return ImportResult(
        file_name=file.filename,
        category=salesperson,
        total_records=len(df),
        imported=imported,
        errors=errors,
        error_details=error_details,
    )


# ============================================================================
# SMS Log Import (CSV from Kavenegar)
# ============================================================================

@router.post("/sms/upload", response_model=ImportResult)
async def import_sms_logs_csv(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import SMS delivery logs from CSV (Kavenegar format or generic)."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files accepted")

    try:
        import pandas as pd
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
    except Exception as e:
        raise HTTPException(400, f"Cannot read CSV: {e}")

    phone_col = _find_phone_column(df)
    if not phone_col:
        raise HTTPException(400, f"No phone column found. Columns: {list(df.columns)}")

    status_col = _find_column(df, ["status", "وضعیت", "StatusText", "delivery"])
    content_col = _find_column(df, ["message", "متن", "content", "body", "Message"])

    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.repositories.communications import SMSLogRepository

    session_factory = get_session_factory()
    imported = 0
    errors = 0

    async with session_factory() as session:
        repo = SMSLogRepository(session)
        for idx, row in df.iterrows():
            try:
                phone = _normalize_phone(str(row[phone_col]))
                if not phone:
                    errors += 1
                    continue

                status = "delivered"
                if status_col and pd.notna(row.get(status_col)):
                    raw_status = str(row[status_col]).lower()
                    if "deliver" in raw_status or "تحویل" in raw_status:
                        status = "delivered"
                    elif "fail" in raw_status or "خطا" in raw_status:
                        status = "failed"
                    else:
                        status = "sent"

                sms_data = {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "phone_number": phone,
                    "content": str(row.get(content_col, ""))[:500] if content_col else "",
                    "status": status,
                    "provider": "kavenegar",
                    "source": f"csv:{file.filename}",
                }
                await repo.create(sms_data)
                imported += 1

            except Exception as e:
                errors += 1

        await session.commit()

    return ImportResult(
        file_name=file.filename,
        total_records=len(df),
        imported=imported,
        errors=errors,
    )


# ============================================================================
# VoIP Call Log Import (JSON from Asterisk)
# ============================================================================

@router.post("/voip/upload", response_model=ImportResult)
async def import_voip_json(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import VoIP call logs from JSON (Asterisk CDR format)."""
    if not file.filename or not file.filename.endswith((".json", ".txt")):
        raise HTTPException(400, "Only .json/.txt files accepted")

    import json as json_mod
    try:
        content = await file.read()
        records = json_mod.loads(content)
        if isinstance(records, dict):
            records = records.get("records", records.get("calls", [records]))
        if not isinstance(records, list):
            records = [records]
    except Exception as e:
        raise HTTPException(400, f"Cannot parse JSON: {e}")

    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.repositories.communications import CallLogRepository

    session_factory = get_session_factory()
    imported = 0
    errors = 0

    async with session_factory() as session:
        repo = CallLogRepository(session)
        for rec in records:
            try:
                phone = _normalize_phone(
                    str(rec.get("dst", rec.get("destination", rec.get("phone", ""))))
                )
                if not phone:
                    errors += 1
                    continue

                duration = int(rec.get("billsec", rec.get("duration", 0)))
                call_data = {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "phone_number": phone,
                    "salesperson_name": str(rec.get("src", rec.get("caller", "voip"))),
                    "duration_seconds": duration,
                    "direction": rec.get("direction", "outbound"),
                    "answered": duration >= 90,
                    "source": f"voip:{file.filename}",
                }
                await repo.create(call_data)
                imported += 1
            except Exception as e:
                errors += 1

        await session.commit()

    return ImportResult(
        file_name=file.filename,
        total_records=len(records),
        imported=imported,
        errors=errors,
    )


# ============================================================================
# Scan existing leads-numbers folder
# ============================================================================

@router.get("/leads/scan")
async def scan_lead_files(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Scan the leads-numbers folder and return available files."""
    folder = Path(__file__).parent.parent.parent.parent.parent / "leads-numbers"
    if not folder.exists():
        return {"folder": str(folder), "files": [], "count": 0}

    files = []
    for f in sorted(folder.glob("*.xlsx")):
        files.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "category": _extract_category(f.name),
        })

    return {"folder": str(folder), "files": files, "count": len(files)}


@router.get("/calls/scan")
async def scan_call_log_files(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Scan the call logs folder and return available files."""
    folder = Path(__file__).parent.parent.parent.parent.parent / "call logs"
    if not folder.exists():
        return {"folder": str(folder), "files": [], "count": 0}

    files = []
    for f in sorted(folder.glob("*.csv")):
        files.append({
            "name": f.name,
            "size_kb": round(f.stat().st_size / 1024, 1),
            "salesperson": _extract_salesperson(f.name),
        })

    return {"folder": str(folder), "files": files, "count": len(files)}


# ============================================================================
# Async (Background) Import Endpoints — Celery-backed
# ============================================================================

@router.post("/leads/upload-async", response_model=AsyncTaskResponse)
async def import_leads_excel_async(
    file: UploadFile = File(...),
    category: str = Query(None, description="Override category (default: from filename)"),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """
    Import leads from Excel file asynchronously via background task.
    Returns a task_id that can be polled via GET /api/v1/tasks/{task_id}.
    """
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx/.xls files accepted")

    content = await file.read()
    content_b64 = base64.b64encode(content).decode()

    from src.infrastructure.messaging.tasks import import_leads_excel
    task = import_leads_excel.delay(
        content_b64, file.filename, str(tenant_id), category)

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Import of {file.filename} queued for background processing",
    )


@router.post("/calls/upload-async", response_model=AsyncTaskResponse)
async def import_call_logs_csv_async(
    file: UploadFile = File(...),
    salesperson: str = Query(None, description="Salesperson name"),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import call logs from CSV asynchronously via background task."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files accepted")

    content = await file.read()
    content_b64 = base64.b64encode(content).decode()

    from src.infrastructure.messaging.tasks import import_call_logs_csv
    task = import_call_logs_csv.delay(
        content_b64, file.filename, str(tenant_id), salesperson)

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Import of {file.filename} queued for background processing",
    )


@router.post("/sms/upload-async", response_model=AsyncTaskResponse)
async def import_sms_logs_csv_async(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import SMS logs from CSV asynchronously via background task."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only .csv files accepted")

    content = await file.read()
    content_b64 = base64.b64encode(content).decode()

    from src.infrastructure.messaging.tasks import import_sms_logs_csv
    task = import_sms_logs_csv.delay(
        content_b64, file.filename, str(tenant_id))

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Import of {file.filename} queued for background processing",
    )


@router.post("/voip/upload-async", response_model=AsyncTaskResponse)
async def import_voip_json_async(
    file: UploadFile = File(...),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import VoIP JSON logs asynchronously via background task."""
    if not file.filename or not file.filename.endswith((".json", ".txt")):
        raise HTTPException(400, "Only .json/.txt files accepted")

    content = await file.read()
    content_b64 = base64.b64encode(content).decode()

    from src.infrastructure.messaging.tasks import import_voip_json
    task = import_voip_json.delay(
        content_b64, file.filename, str(tenant_id))

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message=f"Import of {file.filename} queued for background processing",
    )


@router.post("/leads/batch-async", response_model=AsyncTaskResponse)
async def batch_import_leads_async(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Batch import all Excel files from leads-numbers folder asynchronously."""
    from src.infrastructure.messaging.tasks import import_leads_batch
    task = import_leads_batch.delay(str(tenant_id))

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message="Batch import of all lead files queued for background processing",
    )


# ============================================================================
# Analytics Trigger Endpoints
# ============================================================================

@router.post("/analytics/funnel-snapshot", response_model=AsyncTaskResponse)
async def trigger_funnel_snapshot(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Trigger an immediate funnel snapshot calculation."""
    from src.infrastructure.messaging.tasks import calculate_daily_funnel_snapshot
    task = calculate_daily_funnel_snapshot.delay(str(tenant_id))

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message="Funnel snapshot calculation queued",
    )


@router.post("/analytics/rfm-recalculate", response_model=AsyncTaskResponse)
async def trigger_rfm_recalculation(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Trigger an immediate RFM segment recalculation."""
    from src.infrastructure.messaging.tasks import calculate_rfm_segments
    task = calculate_rfm_segments.delay(str(tenant_id))

    return AsyncTaskResponse(
        task_id=task.id,
        status="queued",
        message="RFM recalculation queued",
    )


# ============================================================================
# Batch import from folder (synchronous — kept for backward compatibility)
# ============================================================================

@router.post("/leads/batch", response_model=ImportSummary)
async def batch_import_leads(
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    """Import all Excel files from leads-numbers folder."""
    import pandas as pd

    folder = Path(__file__).parent.parent.parent.parent.parent / "leads-numbers"
    if not folder.exists():
        raise HTTPException(404, f"Folder not found: {folder}")

    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.repositories.leads import ContactRepository

    session_factory = get_session_factory()
    results = []
    total_imported = 0
    total_dupes = 0
    total_errors = 0

    for xlsx in sorted(folder.glob("*.xlsx")):
        try:
            df = pd.read_excel(xlsx)
            phone_col = _find_phone_column(df)
            if not phone_col:
                results.append(ImportResult(
                    file_name=xlsx.name, errors=1,
                    error_details=[f"No phone column in {list(df.columns)}"],
                ))
                total_errors += 1
                continue

            category = _extract_category(xlsx.name)
            name_col = _find_name_column(df)
            imported = 0
            dupes = 0
            errs = 0

            async with session_factory() as session:
                repo = ContactRepository(session)
                for _, row in df.iterrows():
                    try:
                        phone = _normalize_phone(str(row[phone_col]))
                        if not phone:
                            errs += 1
                            continue
                        existing = await repo.find_by_field("phone_number", phone, tenant_id)
                        if existing:
                            dupes += 1
                            continue
                        name = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else ""
                        await repo.create({
                            "id": uuid4(), "tenant_id": tenant_id,
                            "phone_number": phone, "name": name,
                            "source": f"excel:{xlsx.name}", "category": category,
                            "tags": [category] if category else [],
                        })
                        imported += 1
                    except Exception:
                        errs += 1
                await session.commit()

            results.append(ImportResult(
                file_name=xlsx.name, category=category,
                total_records=len(df), imported=imported,
                duplicates=dupes, errors=errs,
            ))
            total_imported += imported
            total_dupes += dupes
            total_errors += errs

        except Exception as e:
            results.append(ImportResult(
                file_name=xlsx.name, errors=1,
                error_details=[str(e)[:200]],
            ))
            total_errors += 1

    return ImportSummary(
        files_processed=len(results),
        total_imported=total_imported,
        total_duplicates=total_dupes,
        total_errors=total_errors,
        results=results,
    )


# ============================================================================
# Helper functions
# ============================================================================

def _normalize_phone(raw: str) -> str | None:
    """Normalize Iranian phone number to 10-digit format (9XXXXXXXXX)."""
    if not raw:
        return None
    phone = "".join(c for c in raw if c.isdigit())
    if phone.startswith("98") and len(phone) == 12:
        phone = phone[2:]
    elif phone.startswith("0") and len(phone) == 11:
        phone = phone[1:]
    if len(phone) == 10 and phone.startswith("9"):
        return phone
    return None


def _find_phone_column(df) -> str | None:
    """Find the phone number column in a DataFrame."""
    candidates = [
        "phone", "phone_number", "mobile", "شماره", "شماره تلفن", "شماره موبایل",
        "تلفن", "موبایل", "Phone", "Mobile", "Number", "شماره تماس",
        "Destination", "dst", "number", "tel",
    ]
    for col in df.columns:
        col_lower = str(col).strip().lower()
        for c in candidates:
            if c.lower() in col_lower:
                return col
    # Heuristic: check each column for phone-like data
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


def _extract_category(filename: str) -> str:
    """Extract lead category from filename."""
    name = Path(filename).stem
    # Remove common prefixes/patterns
    for prefix in ["report_All_", "گزارش_"]:
        name = name.replace(prefix, "")
    return name.strip()


def _extract_salesperson(filename: str) -> str:
    """Extract salesperson name from call log filename."""
    name = Path(filename).stem
    # Pattern: "report_All_DATE - NAME"
    if " - " in name:
        return name.split(" - ")[-1].strip()
    return name.strip()

