"""
Odoo ERP Adapter — syncs invoices, payments, and customers via Odoo XML-RPC API.

Requires:
- ODOO_URL: e.g. "https://mycompany.odoo.com"
- ODOO_DB: database name
- ODOO_USERNAME: login email
- ODOO_PASSWORD: password or API key
"""

import logging
import xmlrpc.client
from datetime import datetime, timezone
from typing import Any

from src.core.interfaces.erp import (
    ConnectorInfo,
    ERPCustomer,
    ERPInvoice,
    ERPPayment,
    IERPConnector,
    SyncDirection,
)

logger = logging.getLogger(__name__)


class OdooERPAdapter(IERPConnector):
    """
    Odoo ERP adapter using XML-RPC (works with Odoo 14–17+).

    Connects to Odoo's external API to pull:
    - account.move (invoices/bills)
    - account.payment (payments)
    - res.partner (customers)
    """

    def __init__(
        self,
        url: str,
        db: str,
        username: str,
        password: str,
    ) -> None:
        self._url = url.rstrip("/")
        self._db = db
        self._username = username
        self._password = password
        self._uid: int | None = None
        self._models: xmlrpc.client.ServerProxy | None = None

    # ───────────── Connection ─────────────

    async def connect(self) -> bool:
        try:
            common = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")
            self._uid = common.authenticate(
                self._db, self._username, self._password, {},
            )
            if not self._uid:
                logger.error("Odoo authentication failed for %s", self._username)
                return False
            self._models = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/object")
            logger.info("Connected to Odoo at %s (uid=%d)", self._url, self._uid)
            return True
        except Exception as exc:
            logger.error("Odoo connection failed: %s", exc)
            return False

    async def disconnect(self) -> None:
        self._uid = None
        self._models = None

    async def test_connection(self) -> tuple[bool, str]:
        try:
            common = xmlrpc.client.ServerProxy(f"{self._url}/xmlrpc/2/common")
            uid = common.authenticate(
                self._db, self._username, self._password, {},
            )
            if uid:
                version = common.version()
                server_version = version.get("server_version", "unknown")
                return True, f"Connected to Odoo {server_version} (uid={uid})"
            return False, "Authentication failed"
        except Exception as exc:
            return False, f"Connection error: {exc}"

    # ───────────── Helpers ─────────────

    def _execute(
        self,
        model: str,
        method: str,
        domain: list | None = None,
        fields: list[str] | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Call Odoo execute_kw."""
        if not self._models or not self._uid:
            return []
        kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
        if fields:
            kwargs["fields"] = fields
        return self._models.execute_kw(
            self._db, self._uid, self._password,
            model, method,
            [domain or []],
            kwargs,
        )

    # ───────────── Invoices ─────────────

    async def sync_invoices(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPInvoice]:
        if not self._models:
            if not await self.connect():
                return []

        domain: list[Any] = [["move_type", "in", ["out_invoice", "out_refund"]]]
        if since:
            domain.append(["write_date", ">=", since.strftime("%Y-%m-%d %H:%M:%S")])

        fields = [
            "id", "name", "partner_id", "amount_total", "amount_residual",
            "state", "invoice_date", "invoice_date_due", "invoice_line_ids",
            "write_date",
        ]

        try:
            records = self._execute(
                "account.move", "search_read",
                domain=domain, fields=fields, limit=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch Odoo invoices: %s", exc)
            return []

        invoices: list[ERPInvoice] = []
        for rec in records:
            partner_name, partner_phone = self._resolve_partner(rec.get("partner_id"))
            line_items = self._fetch_invoice_lines(rec.get("invoice_line_ids", []))

            status_map = {
                "draft": "draft",
                "posted": "issued",
                "cancel": "cancelled",
            }

            invoices.append(ERPInvoice(
                external_id=str(rec["id"]),
                invoice_number=rec.get("name", ""),
                customer_name=partner_name,
                customer_phone=partner_phone,
                total_amount=float(rec.get("amount_total", 0)),
                amount_paid=float(rec.get("amount_total", 0)) - float(rec.get("amount_residual", 0)),
                status=status_map.get(rec.get("state", ""), "draft"),
                issued_at=self._parse_odoo_date(rec.get("invoice_date")),
                due_date=self._parse_odoo_date(rec.get("invoice_date_due")),
                line_items=line_items,
                raw_data=rec,
            ))

        logger.info("Fetched %d invoices from Odoo", len(invoices))
        return invoices

    def _fetch_invoice_lines(self, line_ids: list[int]) -> list[dict[str, Any]]:
        """Fetch invoice line items."""
        if not line_ids or not self._models:
            return []
        try:
            lines = self._execute(
                "account.move.line", "search_read",
                domain=[["id", "in", line_ids], ["display_type", "=", False]],
                fields=["product_id", "name", "quantity", "price_unit", "price_subtotal", "product_uom_id"],
                limit=100,
            )
            return [
                {
                    "product_name": ln.get("name", ""),
                    "product_code": str(ln["product_id"][0]) if ln.get("product_id") else None,
                    "quantity": ln.get("quantity", 1),
                    "unit_price": int(ln.get("price_unit", 0)),
                    "total": int(ln.get("price_subtotal", 0)),
                    "unit": ln["product_uom_id"][1] if ln.get("product_uom_id") else "unit",
                }
                for ln in lines
            ]
        except Exception as exc:
            logger.warning("Could not fetch invoice lines: %s", exc)
            return []

    # ───────────── Payments ─────────────

    async def sync_payments(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPPayment]:
        if not self._models:
            if not await self.connect():
                return []

        domain: list[Any] = [["payment_type", "=", "inbound"]]
        if since:
            domain.append(["write_date", ">=", since.strftime("%Y-%m-%d %H:%M:%S")])

        fields = [
            "id", "name", "amount", "payment_method_line_id",
            "date", "ref", "reconciled_invoice_ids", "partner_id",
        ]

        try:
            records = self._execute(
                "account.payment", "search_read",
                domain=domain, fields=fields, limit=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch Odoo payments: %s", exc)
            return []

        payments: list[ERPPayment] = []
        for rec in records:
            inv_ids = rec.get("reconciled_invoice_ids", [])
            invoice_ext_id = str(inv_ids[0]) if inv_ids else ""

            method = ""
            if rec.get("payment_method_line_id"):
                method = rec["payment_method_line_id"][1] if isinstance(rec["payment_method_line_id"], list) else str(rec["payment_method_line_id"])

            payments.append(ERPPayment(
                external_id=str(rec["id"]),
                invoice_external_id=invoice_ext_id,
                amount=float(rec.get("amount", 0)),
                payment_method=method or "bank_transfer",
                reference_number=rec.get("ref") or rec.get("name"),
                payment_date=self._parse_odoo_date(rec.get("date")),
                raw_data=rec,
            ))

        logger.info("Fetched %d payments from Odoo", len(payments))
        return payments

    # ───────────── Customers ─────────────

    async def sync_customers(
        self,
        since: datetime | None = None,
        batch_size: int = 500,
    ) -> list[ERPCustomer]:
        if not self._models:
            if not await self.connect():
                return []

        domain: list[Any] = [["customer_rank", ">", 0]]
        if since:
            domain.append(["write_date", ">=", since.strftime("%Y-%m-%d %H:%M:%S")])

        fields = [
            "id", "name", "phone", "mobile", "email",
            "company_name", "category_id", "is_company",
        ]

        try:
            records = self._execute(
                "res.partner", "search_read",
                domain=domain, fields=fields, limit=batch_size,
            )
        except Exception as exc:
            logger.error("Failed to fetch Odoo customers: %s", exc)
            return []

        customers: list[ERPCustomer] = []
        for rec in records:
            phone = rec.get("mobile") or rec.get("phone") or ""
            tags = []
            if rec.get("category_id"):
                tags = [str(t) for t in rec["category_id"]] if isinstance(rec["category_id"], list) else []

            customers.append(ERPCustomer(
                external_id=str(rec["id"]),
                name=rec.get("name", ""),
                phone=phone,
                email=rec.get("email"),
                company=rec.get("company_name"),
                tags=tags,
                raw_data=rec,
            ))

        logger.info("Fetched %d customers from Odoo", len(customers))
        return customers

    # ───────────── Info ─────────────

    def get_info(self) -> ConnectorInfo:
        return ConnectorInfo(
            name="odoo",
            display_name="Odoo ERP",
            supports_invoices=True,
            supports_payments=True,
            supports_customers=True,
            supports_products=False,
            sync_direction=SyncDirection.PULL,
            metadata={"url": self._url, "database": self._db},
        )

    # ───────────── Utilities ─────────────

    def _resolve_partner(self, partner_field: Any) -> tuple[str | None, str | None]:
        """Resolve partner name and phone from Odoo partner_id field."""
        if not partner_field or not self._models:
            return None, None
        partner_id = partner_field[0] if isinstance(partner_field, (list, tuple)) else partner_field
        try:
            partners = self._execute(
                "res.partner", "search_read",
                domain=[["id", "=", partner_id]],
                fields=["name", "phone", "mobile"],
                limit=1,
            )
            if partners:
                p = partners[0]
                return p.get("name"), p.get("mobile") or p.get("phone")
        except Exception:
            pass
        partner_name = partner_field[1] if isinstance(partner_field, (list, tuple)) else None
        return partner_name, None

    @staticmethod
    def _parse_odoo_date(val: Any) -> datetime | None:
        """Parse Odoo date string to datetime."""
        if not val or val is False:
            return None
        if isinstance(val, datetime):
            return val
        try:
            return datetime.strptime(str(val), "%Y-%m-%d")
        except ValueError:
            try:
                return datetime.strptime(str(val), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None

