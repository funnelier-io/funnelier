"""
SMS Log Transformer

Transforms SMS delivery data from various providers into a standardized format.
Supports Kavenegar and generic SMS provider formats.
"""

from datetime import datetime
from typing import Any

from src.core.interfaces import DataRecord

from .base import BaseTransformer, TransformerRegistry
from .phone_normalizer import PhoneNormalizer


@TransformerRegistry.register("sms_log")
class SMSLogTransformer(BaseTransformer):
    """
    Transformer for SMS delivery log data.
    Normalizes SMS records from various providers.
    """

    # Kavenegar status code mapping
    KAVENEGAR_STATUS = {
        1: ("queued", False),
        2: ("scheduled", False),
        4: ("sent_to_carrier", False),
        5: ("sent_to_carrier", False),
        6: ("failed", False),
        10: ("delivered", True),
        11: ("undelivered", False),
        13: ("canceled", False),
        14: ("blocked", False),
        100: ("unknown", False),
    }

    # Generic status normalization
    STATUS_MAPPING = {
        "delivered": ("delivered", True),
        "sent": ("sent", False),
        "pending": ("pending", False),
        "failed": ("failed", False),
        "rejected": ("rejected", False),
        "expired": ("expired", False),
        "undelivered": ("undelivered", False),
        "queued": ("queued", False),
    }

    # Field mappings for common variations
    PHONE_FIELDS = ["receptor", "phone", "mobile", "number", "شماره", "to", "destination"]
    MESSAGE_FIELDS = ["message", "text", "body", "content", "پیام", "متن"]
    STATUS_FIELDS = ["status", "delivery_status", "وضعیت", "status_code"]
    TIMESTAMP_FIELDS = ["date", "sent_at", "created_at", "timestamp", "تاریخ"]
    MESSAGE_ID_FIELDS = ["messageid", "message_id", "id", "sms_id"]

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply SMS log normalization."""
        provider = config.get("provider", "generic")
        result = []

        for record in records:
            data = record.data
            if provider == "kavenegar":
                normalized = self._normalize_kavenegar(data)
            else:
                normalized = self._normalize_generic(data)

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

    def _normalize_kavenegar(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize Kavenegar SMS record."""
        # Normalize phone number
        phone = data.get("receptor")
        phone_result = PhoneNormalizer.normalize(phone)

        # Parse status
        status_code = data.get("status")
        if isinstance(status_code, int) and status_code in self.KAVENEGAR_STATUS:
            status, is_delivered = self.KAVENEGAR_STATUS[status_code]
        else:
            status = "unknown"
            is_delivered = False

        # Parse timestamp (Kavenegar uses Unix timestamp)
        sent_date = data.get("date")
        if isinstance(sent_date, (int, float)):
            timestamp = datetime.fromtimestamp(sent_date)
        else:
            timestamp = self._parse_timestamp(sent_date)

        return {
            "message_id": str(data.get("messageid", "")),
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "phone_carrier": phone_result.carrier,
            "is_mobile": phone_result.is_mobile,
            "sender": data.get("sender"),
            "message": data.get("message"),
            "message_length": len(data.get("message", "")) if data.get("message") else 0,
            "status": status,
            "status_code": status_code,
            "delivered": is_delivered,
            "cost": data.get("cost"),
            "timestamp": timestamp.isoformat() if timestamp else None,
            "date": timestamp.date().isoformat() if timestamp else None,
            "provider": "kavenegar",
            "raw_data": data,
        }

    def _normalize_generic(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize generic SMS provider record."""
        # Find and normalize phone number
        phone = self._find_field(data, self.PHONE_FIELDS)
        phone_result = PhoneNormalizer.normalize(phone)

        # Find message
        message = self._find_field(data, self.MESSAGE_FIELDS)

        # Find and normalize status
        status_raw = self._find_field(data, self.STATUS_FIELDS)
        status, is_delivered = self._normalize_status(status_raw)

        # Find and parse timestamp
        timestamp_raw = self._find_field(data, self.TIMESTAMP_FIELDS)
        timestamp = self._parse_timestamp(timestamp_raw)

        # Find message ID
        message_id = self._find_field(data, self.MESSAGE_ID_FIELDS)

        return {
            "message_id": str(message_id) if message_id else None,
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "phone_carrier": phone_result.carrier,
            "is_mobile": phone_result.is_mobile,
            "sender": data.get("sender") or data.get("from"),
            "message": message,
            "message_length": len(message) if message else 0,
            "status": status,
            "delivered": is_delivered,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "date": timestamp.date().isoformat() if timestamp else None,
            "provider": "generic",
            "raw_data": data,
        }

    def _find_field(self, data: dict[str, Any], field_names: list[str]) -> Any:
        """Find a field value from a list of possible field names."""
        for field in field_names:
            if field in data and data[field] is not None:
                return data[field]
            # Check case-insensitive
            for key in data:
                if key.lower() == field.lower() and data[key] is not None:
                    return data[key]
        return None

    def _normalize_status(self, status: Any) -> tuple[str, bool]:
        """Normalize delivery status."""
        if status is None:
            return "unknown", False

        status_str = str(status).lower().strip()

        # Check direct mapping
        if status_str in self.STATUS_MAPPING:
            return self.STATUS_MAPPING[status_str]

        # Check for status keywords
        if any(kw in status_str for kw in ["deliver", "رسیده", "تحویل"]):
            return "delivered", True
        if any(kw in status_str for kw in ["fail", "error", "خطا"]):
            return "failed", False
        if any(kw in status_str for kw in ["sent", "ارسال"]):
            return "sent", False
        if any(kw in status_str for kw in ["pending", "queue", "در انتظار"]):
            return "pending", False

        return status_str, False

    def _parse_timestamp(self, timestamp: Any) -> datetime | None:
        """Parse timestamp to datetime."""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp)

        timestamp_str = str(timestamp).strip()

        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate an SMS log record."""
        data = record.data

        # Phone number is required
        if not data.get("phone_number"):
            return False, "Missing or invalid phone number"

        # Message ID is required for deduplication
        if not data.get("message_id"):
            return False, "Missing message ID"

        return True, None


@TransformerRegistry.register("sms_template")
class SMSTemplateTransformer(BaseTransformer):
    """
    Transformer for SMS templates.
    Identifies and categorizes SMS templates for analytics.
    """

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply SMS template normalization and classification."""
        templates = config.get("templates", {})
        result = []

        for record in records:
            data = dict(record.data)
            message = data.get("message", "")

            # Try to match template
            template_id, template_name = self._match_template(message, templates)

            data["template_id"] = template_id
            data["template_name"] = template_name

            result.append(
                DataRecord(
                    data=data,
                    source_name=record.source_name,
                    source_type=record.source_type,
                    extracted_at=record.extracted_at,
                    raw_data=record.raw_data,
                )
            )

        return result

    def _match_template(
        self,
        message: str,
        templates: dict[str, str],
    ) -> tuple[str | None, str | None]:
        """Match message to a template."""
        if not message:
            return None, None

        message_lower = message.lower()

        for template_id, pattern in templates.items():
            if pattern.lower() in message_lower:
                return template_id, pattern

        return None, None

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate an SMS template record."""
        return True, None

