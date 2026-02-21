"""
Call Log Transformer

Transforms call log data from various sources into a standardized format.
Handles both CSV call logs and VoIP logs.
"""

from datetime import datetime
from typing import Any

from src.core.interfaces import DataRecord

from .base import BaseTransformer, TransformerRegistry
from .phone_normalizer import PhoneNormalizer


@TransformerRegistry.register("call_log")
class CallLogTransformer(BaseTransformer):
    """
    Transformer for call log data.
    Normalizes call records from CSV and VoIP sources.
    """

    # Minimum call duration in seconds for "successful" call (1.5 minutes)
    SUCCESSFUL_CALL_THRESHOLD = 90

    # Field mappings for common variations
    PHONE_FIELDS = ["phone", "number", "mobile", "شماره", "تلفن", "موبایل", "receptor", "dst", "src"]
    DURATION_FIELDS = ["duration", "مدت", "duration_seconds", "billsec", "طول تماس"]
    TIMESTAMP_FIELDS = ["date", "time", "timestamp", "datetime", "تاریخ", "start", "created_at"]
    TYPE_FIELDS = ["type", "call_type", "direction", "نوع", "نوع تماس"]

    async def _apply_normalize(
        self,
        records: list[DataRecord],
        config: dict[str, Any],
    ) -> list[DataRecord]:
        """Apply call log normalization."""
        result = []

        for record in records:
            data = record.data
            normalized = self._normalize_call_log(data)

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

    def _normalize_call_log(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize a single call log record."""
        # Find and normalize phone number
        phone = self._find_field(data, self.PHONE_FIELDS)
        phone_result = PhoneNormalizer.normalize(phone)

        # Find and parse duration
        duration_raw = self._find_field(data, self.DURATION_FIELDS)
        duration = self._parse_duration(duration_raw)

        # Find and parse timestamp
        timestamp_raw = self._find_field(data, self.TIMESTAMP_FIELDS)
        timestamp = self._parse_timestamp(timestamp_raw)

        # Find call type/direction
        call_type = self._find_field(data, self.TYPE_FIELDS)
        direction = self._normalize_direction(call_type)

        # Determine if call was answered and successful
        answered = self._determine_answered(data, duration)
        successful = answered and duration >= self.SUCCESSFUL_CALL_THRESHOLD

        # Extract salesperson from metadata
        salesperson = data.get("salesperson") or data.get("فروشنده") or data.get("account_code")

        return {
            "phone_number": phone_result.normalized,
            "phone_valid": phone_result.is_valid,
            "phone_carrier": phone_result.carrier,
            "is_mobile": phone_result.is_mobile,
            "duration_seconds": duration,
            "duration_display": self._format_duration(duration),
            "timestamp": timestamp.isoformat() if timestamp else None,
            "date": timestamp.date().isoformat() if timestamp else None,
            "time": timestamp.time().isoformat() if timestamp else None,
            "direction": direction,
            "answered": answered,
            "successful": successful,
            "salesperson": salesperson,
            "call_id": data.get("call_id") or data.get("uniqueid"),
            "disposition": data.get("disposition"),
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

    def _parse_duration(self, duration: Any) -> int:
        """Parse duration to seconds."""
        if duration is None:
            return 0

        if isinstance(duration, (int, float)):
            return int(duration)

        duration_str = str(duration).strip()

        # Handle HH:MM:SS format
        if ":" in duration_str:
            parts = duration_str.split(":")
            try:
                if len(parts) == 3:
                    h, m, s = map(int, parts)
                    return h * 3600 + m * 60 + s
                elif len(parts) == 2:
                    m, s = map(int, parts)
                    return m * 60 + s
            except ValueError:
                pass

        # Try direct conversion
        try:
            return int(float(duration_str))
        except ValueError:
            return 0

    def _parse_timestamp(self, timestamp: Any) -> datetime | None:
        """Parse timestamp to datetime."""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        timestamp_str = str(timestamp).strip()

        # Try various formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _normalize_direction(self, call_type: Any) -> str:
        """Normalize call direction."""
        if call_type is None:
            return "unknown"

        type_str = str(call_type).lower().strip()

        outbound_keywords = ["outbound", "outgoing", "out", "خروجی", "صادره"]
        inbound_keywords = ["inbound", "incoming", "in", "ورودی", "وارده"]
        missed_keywords = ["missed", "missed_call", "بی‌پاسخ", "از دست رفته"]

        for keyword in outbound_keywords:
            if keyword in type_str:
                return "outbound"

        for keyword in inbound_keywords:
            if keyword in type_str:
                return "inbound"

        for keyword in missed_keywords:
            if keyword in type_str:
                return "missed"

        return type_str

    def _determine_answered(self, data: dict[str, Any], duration: int) -> bool:
        """Determine if call was answered."""
        # Check explicit disposition
        disposition = data.get("disposition", "").upper()
        if disposition == "ANSWERED":
            return True
        if disposition in ("NO ANSWER", "BUSY", "FAILED", "CONGESTION"):
            return False

        # Check explicit answered field
        answered = data.get("answered")
        if answered is not None:
            return bool(answered)

        # Infer from duration
        return duration > 0

    def _format_duration(self, seconds: int) -> str:
        """Format duration as HH:MM:SS."""
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _validate_record(self, record: DataRecord) -> tuple[bool, str | None]:
        """Validate a call log record."""
        data = record.data

        # Phone number is required
        if not data.get("phone_number"):
            return False, "Missing or invalid phone number"

        # Timestamp is recommended
        if not data.get("timestamp"):
            # Allow records without timestamp but log warning
            pass

        return True, None


@TransformerRegistry.register("voip_call_log")
class VoIPCallLogTransformer(CallLogTransformer):
    """
    Specialized transformer for VoIP call logs from Asterisk.
    """

    # Internal extension length threshold
    INTERNAL_EXTENSION_MAX_LENGTH = 4

    def _normalize_call_log(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize VoIP call log with Asterisk-specific logic."""
        # Get source and destination
        src = data.get("src", "")
        dst = data.get("dst", "")

        # Determine direction based on internal/external numbers
        is_src_internal = self._is_internal(src)
        is_dst_internal = self._is_internal(dst)

        if is_src_internal and not is_dst_internal:
            direction = "outbound"
            external_number = dst
            extension = src
        elif not is_src_internal and is_dst_internal:
            direction = "inbound"
            external_number = src
            extension = dst
        else:
            direction = "internal"
            external_number = None
            extension = src or dst

        # Normalize phone number
        phone_result = PhoneNormalizer.normalize(external_number) if external_number else None

        # Parse timestamps
        start_time = self._parse_timestamp(data.get("start"))
        answer_time = self._parse_timestamp(data.get("answer"))
        end_time = self._parse_timestamp(data.get("end"))

        # Get duration
        duration = self._parse_duration(data.get("billsec") or data.get("duration"))

        # Determine call status
        disposition = data.get("disposition", "").upper()
        answered = disposition == "ANSWERED" or (answer_time is not None)
        successful = answered and duration >= self.SUCCESSFUL_CALL_THRESHOLD

        return {
            "call_id": data.get("uniqueid"),
            "phone_number": phone_result.normalized if phone_result else None,
            "phone_valid": phone_result.is_valid if phone_result else False,
            "phone_carrier": phone_result.carrier if phone_result else None,
            "is_mobile": phone_result.is_mobile if phone_result else False,
            "extension": extension,
            "direction": direction,
            "duration_seconds": duration,
            "duration_display": self._format_duration(duration),
            "start_time": start_time.isoformat() if start_time else None,
            "answer_time": answer_time.isoformat() if answer_time else None,
            "end_time": end_time.isoformat() if end_time else None,
            "timestamp": start_time.isoformat() if start_time else None,
            "date": start_time.date().isoformat() if start_time else None,
            "disposition": disposition,
            "answered": answered,
            "successful": successful,
            "channel": data.get("channel"),
            "context": data.get("dcontext"),
            "account_code": data.get("accountcode"),
            "salesperson": data.get("accountcode"),  # Map account code to salesperson
            "raw_data": data,
        }

    def _is_internal(self, number: str | None) -> bool:
        """Check if number is an internal extension."""
        if not number:
            return False
        digits = "".join(c for c in number if c.isdigit())
        return len(digits) <= self.INTERNAL_EXTENSION_MAX_LENGTH

