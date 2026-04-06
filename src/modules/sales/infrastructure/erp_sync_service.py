"""
ERP Sync Service — orchestrates data sync from ERP/CRM connectors into PostgreSQL.

Uses the IERPConnector abstraction to pull invoices, payments, and customers
from any configured ERP and upserts them into the Funnelier database.
"""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.interfaces.erp import (
    ERPCustomer,
    ERPInvoice,
    ERPPayment,
    IERPConnector,
    SyncResult,
)
from src.infrastructure.database.models.leads import ContactModel
from src.infrastructure.database.models.sales import (
    InvoiceModel,
    InvoiceLineItemModel,
    PaymentModel,
)
from src.infrastructure.database.models.sync import SyncLogModel

logger = logging.getLogger(__name__)


class ERPSyncService:
    """
    Pulls data from an ERP connector and upserts into PostgreSQL.

    Supports:
    - Invoice sync (create/update by external_id)
    - Payment sync (create/update by external_id)
    - Customer sync (create/update by phone number)
    - Full sync (all entities)

    Each operation is logged in the sync_logs table.
    """

    def __init__(
        self,
        connector: IERPConnector,
        session: AsyncSession,
        tenant_id: UUID,
        source_system: str = "erp",
        data_source_id: UUID | None = None,
    ):
        self._connector = connector
        self._session = session
        self._tenant_id = tenant_id
        self._source_system = source_system
        self._data_source_id = data_source_id

    # ─────────────────────── Invoice Sync ───────────────────────

    async def sync_invoices(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> dict[str, int]:
        """
        Pull invoices from ERP and upsert into the invoices table.
        Returns {"created": N, "updated": N, "skipped": N, "failed": N}.
        """
        stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

        try:
            erp_invoices = await self._connector.sync_invoices(
                since=since, batch_size=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch invoices from ERP: %s", exc)
            stats["failed"] = -1
            return stats

        for erp_inv in erp_invoices:
            try:
                await self._upsert_invoice(erp_inv, stats)
            except Exception as exc:
                logger.error(
                    "Error syncing invoice %s: %s", erp_inv.external_id, exc,
                )
                stats["failed"] += 1

        await self._session.flush()
        logger.info("Invoice sync complete: %s", stats)
        return stats

    async def _upsert_invoice(
        self, erp_inv: ERPInvoice, stats: dict[str, int],
    ) -> None:
        """Create or update a single invoice from ERP data."""
        # Find by external_id + tenant
        existing_q = await self._session.execute(
            select(InvoiceModel).where(
                InvoiceModel.tenant_id == self._tenant_id,
                InvoiceModel.external_id == erp_inv.external_id,
            )
        )
        existing = existing_q.scalar_one_or_none()

        phone = self._normalize_phone(erp_inv.customer_phone or "")
        if not phone:
            stats["skipped"] += 1
            return

        # Resolve contact
        contact_id = await self._resolve_contact_id(
            phone, erp_inv.customer_name,
        )

        if existing:
            # Update
            existing.invoice_number = erp_inv.invoice_number or existing.invoice_number
            existing.phone_number = phone
            existing.contact_id = contact_id or existing.contact_id
            existing.total_amount = int(erp_inv.total_amount)
            existing.status = self._map_invoice_status(erp_inv.status)
            existing.issued_at = erp_inv.issued_at or existing.issued_at
            existing.due_date = erp_inv.due_date or existing.due_date
            existing.source_system = self._source_system
            existing.metadata_ = {
                **(existing.metadata_ or {}),
                "erp_raw": {
                    k: str(v) for k, v in erp_inv.raw_data.items()
                } if erp_inv.raw_data else {},
                "last_synced": datetime.now(timezone.utc).isoformat(),
            }
            stats["updated"] += 1
        else:
            # Create
            inv_model = InvoiceModel(
                id=uuid4(),
                tenant_id=self._tenant_id,
                contact_id=contact_id,
                phone_number=phone,
                invoice_number=erp_inv.invoice_number or f"ERP-{erp_inv.external_id[:12]}",
                invoice_type="invoice",
                external_id=erp_inv.external_id,
                source_system=self._source_system,
                subtotal=int(erp_inv.total_amount),
                total_amount=int(erp_inv.total_amount),
                status=self._map_invoice_status(erp_inv.status),
                issued_at=erp_inv.issued_at,
                due_date=erp_inv.due_date,
                metadata_={
                    "erp_raw": {
                        k: str(v) for k, v in erp_inv.raw_data.items()
                    } if erp_inv.raw_data else {},
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self._session.add(inv_model)

            # Create line items
            for idx, li_data in enumerate(erp_inv.line_items):
                li_model = InvoiceLineItemModel(
                    id=uuid4(),
                    invoice_id=inv_model.id,
                    product_name=li_data.get("product_name", li_data.get("name", f"Item {idx+1}")),
                    product_code=li_data.get("product_code", li_data.get("code")),
                    product_category=li_data.get("category"),
                    quantity=float(li_data.get("quantity", 1)),
                    unit=li_data.get("unit", "unit"),
                    unit_price=int(li_data.get("unit_price", 0)),
                    total=int(li_data.get("total", li_data.get("unit_price", 0))),
                    metadata_=li_data,
                )
                self._session.add(li_model)

            stats["created"] += 1

    # ─────────────────────── Payment Sync ───────────────────────

    async def sync_payments(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> dict[str, int]:
        """Pull payments from ERP and upsert into payments table."""
        stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

        try:
            erp_payments = await self._connector.sync_payments(
                since=since, batch_size=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch payments from ERP: %s", exc)
            stats["failed"] = -1
            return stats

        for erp_pay in erp_payments:
            try:
                await self._upsert_payment(erp_pay, stats)
            except Exception as exc:
                logger.error(
                    "Error syncing payment %s: %s", erp_pay.external_id, exc,
                )
                stats["failed"] += 1

        await self._session.flush()
        logger.info("Payment sync complete: %s", stats)
        return stats

    async def _upsert_payment(
        self, erp_pay: ERPPayment, stats: dict[str, int],
    ) -> None:
        """Create or update a single payment from ERP data."""
        existing_q = await self._session.execute(
            select(PaymentModel).where(
                PaymentModel.tenant_id == self._tenant_id,
                PaymentModel.external_id == erp_pay.external_id,
            )
        )
        existing = existing_q.scalar_one_or_none()

        # Resolve invoice by external_id
        invoice_id = None
        phone_number = ""
        if erp_pay.invoice_external_id:
            inv_q = await self._session.execute(
                select(InvoiceModel).where(
                    InvoiceModel.tenant_id == self._tenant_id,
                    InvoiceModel.external_id == erp_pay.invoice_external_id,
                )
            )
            inv = inv_q.scalar_one_or_none()
            if inv:
                invoice_id = inv.id
                phone_number = inv.phone_number

        if not phone_number:
            stats["skipped"] += 1
            return

        if existing:
            existing.amount = int(erp_pay.amount)
            existing.payment_method = erp_pay.payment_method or existing.payment_method
            existing.reference_number = erp_pay.reference_number or existing.reference_number
            existing.paid_at = erp_pay.payment_date or existing.paid_at
            existing.notes = erp_pay.notes or existing.notes
            existing.source_system = self._source_system
            existing.metadata_ = {
                **(existing.metadata_ or {}),
                "last_synced": datetime.now(timezone.utc).isoformat(),
            }
            stats["updated"] += 1
        else:
            pay_model = PaymentModel(
                id=uuid4(),
                tenant_id=self._tenant_id,
                invoice_id=invoice_id,
                phone_number=phone_number,
                amount=int(erp_pay.amount),
                payment_method=erp_pay.payment_method or "bank_transfer",
                external_id=erp_pay.external_id,
                source_system=self._source_system,
                reference_number=erp_pay.reference_number,
                status="confirmed",
                paid_at=erp_pay.payment_date or datetime.now(timezone.utc),
                notes=erp_pay.notes,
                metadata_={
                    "synced_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self._session.add(pay_model)
            stats["created"] += 1

    # ─────────────────────── Customer Sync ───────────────────────

    async def sync_customers(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> dict[str, int]:
        """Pull customers from ERP and upsert into contacts table."""
        stats = {"created": 0, "updated": 0, "skipped": 0, "failed": 0}

        try:
            erp_customers = await self._connector.sync_customers(
                since=since, batch_size=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch customers from ERP: %s", exc)
            stats["failed"] = -1
            return stats

        for erp_cust in erp_customers:
            try:
                await self._upsert_customer(erp_cust, stats)
            except Exception as exc:
                logger.error(
                    "Error syncing customer %s: %s", erp_cust.external_id, exc,
                )
                stats["failed"] += 1

        await self._session.flush()
        logger.info("Customer sync complete: %s", stats)
        return stats

    async def _upsert_customer(
        self, erp_cust: ERPCustomer, stats: dict[str, int],
    ) -> None:
        """Create or update a contact from ERP customer data."""
        phone = self._normalize_phone(erp_cust.phone or "")
        if not phone:
            stats["skipped"] += 1
            return

        existing_q = await self._session.execute(
            select(ContactModel).where(
                ContactModel.tenant_id == self._tenant_id,
                ContactModel.phone_number == phone,
            )
        )
        existing = existing_q.scalar_one_or_none()

        if existing:
            if erp_cust.name and not existing.name:
                existing.name = erp_cust.name
            if erp_cust.email and not existing.email:
                existing.email = erp_cust.email
            existing.custom_fields = {
                **(existing.custom_fields or {}),
                "erp_id": erp_cust.external_id,
                "erp_source": self._source_system,
                "erp_company": erp_cust.company,
                "erp_tags": erp_cust.tags,
                "last_erp_sync": datetime.now(timezone.utc).isoformat(),
            }
            stats["updated"] += 1
        else:
            new_contact = ContactModel(
                id=uuid4(),
                tenant_id=self._tenant_id,
                phone_number=phone,
                name=erp_cust.name or None,
                email=erp_cust.email,
                source_name="erp_sync",
                current_stage="lead_acquired",
                is_active=True,
                total_calls=0,
                total_answered_calls=0,
                total_call_duration=0,
                total_sms_sent=0,
                total_sms_delivered=0,
                total_invoices=0,
                total_paid_invoices=0,
                total_revenue=0,
                tags=erp_cust.tags or [],
                custom_fields={
                    "erp_id": erp_cust.external_id,
                    "erp_source": self._source_system,
                    "erp_company": erp_cust.company,
                },
            )
            self._session.add(new_contact)
            stats["created"] += 1

    # ─────────────────────── Full Sync ───────────────────────

    async def full_sync(
        self,
        since: datetime | None = None,
        triggered_by: str = "manual",
        triggered_by_user_id: UUID | None = None,
    ) -> SyncResult:
        """
        Run a full sync of invoices, payments, and customers.
        Creates a SyncLog entry to track the operation.
        """
        started = datetime.now(timezone.utc)

        # Create sync log entry
        log = SyncLogModel(
            id=uuid4(),
            tenant_id=self._tenant_id,
            data_source_id=self._data_source_id,
            sync_type="full" if since is None else "incremental",
            direction="pull",
            status="running",
            started_at=started,
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
        )
        self._session.add(log)
        await self._session.flush()

        all_errors: list[str] = []
        details: dict[str, Any] = {}

        try:
            # Connect
            connected = await self._connector.connect()
            if not connected:
                raise ConnectionError("Could not connect to ERP")

            # Sync each entity type
            info = self._connector.get_info()

            if info.supports_invoices:
                inv_stats = await self.sync_invoices(since=since)
                details["invoices"] = inv_stats
                if inv_stats.get("failed", 0) < 0:
                    all_errors.append("Invoice fetch failed")

            if info.supports_payments:
                pay_stats = await self.sync_payments(since=since)
                details["payments"] = pay_stats
                if pay_stats.get("failed", 0) < 0:
                    all_errors.append("Payment fetch failed")

            if info.supports_customers:
                cust_stats = await self.sync_customers(since=since)
                details["customers"] = cust_stats
                if cust_stats.get("failed", 0) < 0:
                    all_errors.append("Customer fetch failed")

            # Aggregate totals
            total_created = sum(d.get("created", 0) for d in details.values())
            total_updated = sum(d.get("updated", 0) for d in details.values())
            total_skipped = sum(d.get("skipped", 0) for d in details.values())
            total_failed = sum(max(d.get("failed", 0), 0) for d in details.values())
            total_fetched = total_created + total_updated + total_skipped

            completed = datetime.now(timezone.utc)
            duration = (completed - started).total_seconds()

            # Update sync log
            log.status = "success" if not all_errors else "partial"
            log.records_fetched = total_fetched
            log.records_created = total_created
            log.records_updated = total_updated
            log.records_skipped = total_skipped
            log.records_failed = total_failed
            log.completed_at = completed
            log.duration_seconds = duration
            log.errors = all_errors
            log.details = details

            result = SyncResult(
                success=True,
                records_synced=total_created + total_updated,
                records_created=total_created,
                records_updated=total_updated,
                records_failed=total_failed,
                errors=all_errors,
                started_at=started,
                completed_at=completed,
                metadata=details,
            )

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            error_msg = str(exc)
            logger.exception("Full ERP sync failed: %s", error_msg)

            log.status = "failed"
            log.completed_at = completed
            log.duration_seconds = (completed - started).total_seconds()
            log.error_message = error_msg
            log.errors = [error_msg]
            log.details = details

            result = SyncResult(
                success=False,
                errors=[error_msg],
                started_at=started,
                completed_at=completed,
                metadata=details,
            )

        finally:
            try:
                await self._connector.disconnect()
            except Exception:
                pass

        await self._session.flush()
        return result

    # ─────────────────────── Helpers ───────────────────────

    async def _resolve_contact_id(
        self, phone: str, name: str | None = None,
    ) -> UUID | None:
        """Find or create a contact by phone number, return its ID."""
        result = await self._session.execute(
            select(ContactModel.id).where(
                ContactModel.tenant_id == self._tenant_id,
                ContactModel.phone_number == phone,
            )
        )
        row = result.scalar_one_or_none()
        if row:
            return row

        # Auto-create contact
        contact = ContactModel(
            id=uuid4(),
            tenant_id=self._tenant_id,
            phone_number=phone,
            name=name,
            source_name="erp_sync",
            current_stage="lead_acquired",
            is_active=True,
            total_calls=0,
            total_answered_calls=0,
            total_call_duration=0,
            total_sms_sent=0,
            total_sms_delivered=0,
            total_invoices=0,
            total_paid_invoices=0,
            total_revenue=0,
            tags=[],
            custom_fields={"auto_created_by": "erp_sync"},
        )
        self._session.add(contact)
        await self._session.flush()
        return contact.id

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        """Normalize an Iranian phone number to 10-digit format."""
        phone = raw.replace("+", "").replace(" ", "").replace("-", "")
        if phone.startswith("0") and len(phone) == 11:
            phone = phone[1:]
        elif phone.startswith("98") and len(phone) == 12:
            phone = phone[2:]
        if len(phone) == 10 and phone.startswith("9"):
            return phone
        # Return as-is if non-Iranian or already good
        return phone if phone else ""

    @staticmethod
    def _map_invoice_status(erp_status: str) -> str:
        """Map ERP status strings to Funnelier invoice statuses."""
        mapping = {
            "draft": "draft",
            "pending": "issued",
            "issued": "issued",
            "sent": "issued",
            "open": "issued",
            "partial": "partially_paid",
            "partially_paid": "partially_paid",
            "paid": "paid",
            "completed": "paid",
            "cancelled": "cancelled",
            "canceled": "cancelled",
            "voided": "cancelled",
            "overdue": "issued",
        }
        return mapping.get(erp_status.lower(), "draft")

