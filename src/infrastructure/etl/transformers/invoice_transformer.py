"""
Invoice and Payment Transformers

Transforms invoice and payment data into standardized formats
for funnel analysis.
"""

from datetime import datetime
from typing import Any

from src.core.interfaces import DataRecord

from .base import BaseTransformer, TransformerRegistry
from .phone_normalizer import PhoneNormalizer


@TransformerRegistry.register("invoice")
class InvoiceTransformer(BaseTransformer):
    """
    Transformer for pre-invoice data.
    Normalizes invoice records for funnel stage tracking.
    """

    # Field mappings for common variations
    PHONE_FIELDS = ["phone", "customer_phone", "mobile", "شماره", "تلفن", "موبایل"]
    AMOUNT_FIELDS = ["total", "amount", "total_amount", "مبلغ", "جمع"]
    STATUS_FIELDS = ["status", "وضعیت", "invoice_status"]
    DATE_FIELDS = ["created_at", "createdAt", "date", "تاریخ", "invoice_date"]

    # Status normalization
    STATUS_MAPPING = {
        "draft": "draft",
        "pending": "pending",
        "sent": "sent",
        "paid": "paid",
        "partial": "partial",
        "overdue": "overdue",
        "cancelled": "cancelled",
        "پیش‌نویس": "draft",
        "در انتظار": "pending",
        "ارسال شده": "sent",
        "پرداخت شده": "paid",
        "پرداخت جزئی": "partial",
        "سررسید گذشته": "overdue",
        "لغو شده": "cancelled",
    }

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply invoice normalization."""
        result = []

        for record in records:
            data = record.data
            normalized = self._normalize_invoice(data)

            result.append(
                DataRecord(
                    data=normalized,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

    def _normalize_invoice(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a single invoice record."""
        # Find and normalize phone number
        phone = self._find_field(data, self.PHONE_FIELDS)
        phone_result = PhoneNormalizer.normalize(phone)

        # Find and parse amount
        amount_raw = self._find_field(data, self.AMOUNT_FIELDS)
        amount = self._parse_amount(amount_raw)

        # Find and normalize status
        status_raw = self._find_field(data, self.STATUS_FIELDS)
        status = self._normalize_status(status_raw)

        # Find and parse dates
        created_raw = self._find_field(data, self.DATE_FIELDS)
        created_at = self._parse_timestamp(created_raw)

        # Extract invoice items
        items = data.get("items", [])
        item_count = len(items) if isinstance(items, list) else 0
        product_categories = self._extract_categories(items)

        return {
            "invoice_id": str(data.get("_id") or data.get("invoice_id") or ""),
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "customer_name": data.get("customer_name") or data.get("name") or data.get("نام"),
            "total_amount": amount,
            "amount_formatted": self._format_amount(amount),
            "is_high_value": amount >= 1_000_000_000,  # 1B threshold
            "status": status,
            "item_count": item_count,
            "product_categories": product_categories,
            "salesperson": data.get("salesperson") or data.get("sales_rep") or data.get("فروشنده"),
            "created_at": created_at.isoformat() if created_at else None,
            "date": created_at.date().isoformat() if created_at else None,
            "updated_at": self._parse_timestamp(
                data.get("updated_at") or data.get("updatedAt")
            ),
            "raw_data": data,
        }

    def _find_field(self, data: dict[str, Any], field_names: list[str]) -> Any:
        """Find a field value from a list of possible field names."""
        for field in field_names:
            if field in data and data[field] is not None:
                return data[field]
            for key in data:
                if key.lower() == field.lower() and data[key] is not None:
                    return data[key]
        return None

    def _parse_amount(self, amount: Any) -> float:
        """Parse amount to float."""
        if amount is None:
            return 0.0

        if isinstance(amount, (int, float)):
            return float(amount)

        # Remove currency symbols, commas, and other characters
        amount_str = str(amount)
        cleaned = "".join(c for c in amount_str if c.isdigit() or c == ".")

        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def _format_amount(self, amount: float) -> str:
        """Format amount for display with thousand separators."""
        if amount >= 1_000_000_000:
            return f"{amount / 1_000_000_000:.1f}B"
        elif amount >= 1_000_000:
            return f"{amount / 1_000_000:.1f}M"
        else:
            return f"{amount:,.0f}"

    def _normalize_status(self, status: Any) -> str:
        """Normalize invoice status."""
        if status is None:
            return "unknown"

        status_str = str(status).lower().strip()

        if status_str in self.STATUS_MAPPING:
            return self.STATUS_MAPPING[status_str]

        # Try to match partial keywords
        if any(kw in status_str for kw in ["paid", "پرداخت"]):
            return "paid"
        if any(kw in status_str for kw in ["pending", "انتظار"]):
            return "pending"
        if any(kw in status_str for kw in ["cancel", "لغو"]):
            return "cancelled"

        return status_str

    def _parse_timestamp(self, timestamp: Any) -> datetime | None:
        """Parse timestamp to datetime."""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        timestamp_str = str(timestamp).strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _extract_categories(self, items: list[dict[str, Any]]) -> list[str]:
        """Extract product categories from invoice items."""
        if not isinstance(items, list):
            return []

        categories = set()
        for item in items:
            if isinstance(item, dict):
                cat = item.get("category") or item.get("product_category") or item.get("دسته‌بندی")
                if cat:
                    categories.add(str(cat))

        return list(categories)

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate an invoice record."""
        data = record.data

        if not data.get("invoice_id"):
            return False, "Missing invoice ID"

        if not data.get("phone_number"):
            return False, "Missing or invalid phone number"

        return True, None


@TransformerRegistry.register("payment")
class PaymentTransformer(BaseTransformer):
    """
    Transformer for payment data.
    Normalizes payment records for conversion tracking.
    """

    # Field mappings
    AMOUNT_FIELDS = ["amount", "مبلغ", "payment_amount", "paid_amount"]
    DATE_FIELDS = ["paid_at", "paidAt", "payment_date", "تاریخ پرداخت", "created_at"]
    METHOD_FIELDS = ["method", "payment_method", "روش پرداخت", "payment_type"]
    STATUS_FIELDS = ["status", "وضعیت", "payment_status"]

    # Payment method normalization
    METHOD_MAPPING = {
        "card": "card",
        "cash": "cash",
        "bank_transfer": "bank_transfer",
        "online": "online",
        "pos": "pos",
        "کارت": "card",
        "نقد": "cash",
        "انتقال": "bank_transfer",
        "آنلاین": "online",
    }

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply payment normalization."""
        result = []

        for record in records:
            data = record.data
            normalized = self._normalize_payment(data)

            result.append(
                DataRecord(
                    data=normalized,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

    def _normalize_payment(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a single payment record."""
        # Find and normalize phone number
        phone = data.get("phone") or data.get("customer_phone") or data.get("mobile")
        phone_result = PhoneNormalizer.normalize(phone)

        # Find and parse amount
        amount_raw = self._find_field(data, self.AMOUNT_FIELDS)
        amount = self._parse_amount(amount_raw)

        # Find and parse date
        paid_raw = self._find_field(data, self.DATE_FIELDS)
        paid_at = self._parse_timestamp(paid_raw)

        # Find and normalize payment method
        method_raw = self._find_field(data, self.METHOD_FIELDS)
        method = self._normalize_method(method_raw)

        # Find and normalize status
        status_raw = self._find_field(data, self.STATUS_FIELDS)
        status = self._normalize_status(status_raw)

        return {
            "payment_id": str(data.get("_id") or data.get("payment_id") or ""),
            "invoice_id": str(data.get("invoice_id") or data.get("invoiceId") or ""),
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "amount": amount,
            "amount_formatted": self._format_amount(amount),
            "is_high_value": amount >= 1_000_000_000,
            "payment_method": method,
            "status": status,
            "is_successful": status in ("completed", "success", "paid"),
            "paid_at": paid_at.isoformat() if paid_at else None,
            "date": paid_at.date().isoformat() if paid_at else None,
            "transaction_id": data.get("transaction_id") or data.get("ref") or data.get("reference"),
            "raw_data": data,
        }

    def _find_field(self, data: dict[str, Any], field_names: list[str]) -> Any:
        """Find a field value from a list of possible field names."""
        for field in field_names:
            if field in data and data[field] is not None:
                return data[field]
        return None

    def _parse_amount(self, amount: Any) -> float:
        """Parse amount to float."""
        if amount is None:
            return 0.0

        if isinstance(amount, (int, float)):
            return float(amount)

        cleaned = "".join(c for c in str(amount) if c.isdigit() or c == ".")

        try:
            return float(cleaned) if cleaned else 0.0
        except ValueError:
            return 0.0

    def _format_amount(self, amount: float) -> str:
        """Format amount for display."""
        if amount >= 1_000_000_000:
            return f"{amount / 1_000_000_000:.1f}B"
        elif amount >= 1_000_000:
            return f"{amount / 1_000_000:.1f}M"
        else:
            return f"{amount:,.0f}"

    def _normalize_method(self, method: Any) -> str:
        """Normalize payment method."""
        if method is None:
            return "unknown"

        method_str = str(method).lower().strip()

        if method_str in self.METHOD_MAPPING:
            return self.METHOD_MAPPING[method_str]

        return method_str

    def _normalize_status(self, status: Any) -> str:
        """Normalize payment status."""
        if status is None:
            return "unknown"

        status_str = str(status).lower().strip()

        if any(kw in status_str for kw in ["success", "complete", "paid", "موفق"]):
            return "completed"
        if any(kw in status_str for kw in ["fail", "error", "خطا"]):
            return "failed"
        if any(kw in status_str for kw in ["pending", "انتظار"]):
            return "pending"

        return status_str

    def _parse_timestamp(self, timestamp: Any) -> datetime | None:
        """Parse timestamp to datetime."""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        timestamp_str = str(timestamp).strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate a payment record."""
        data = record.data

        if not data.get("payment_id"):
            return False, "Missing payment ID"

        if not data.get("invoice_id"):
            return False, "Missing invoice ID"

        if data.get("amount", 0) <= 0:
            return False, "Invalid payment amount"

        return True, None

