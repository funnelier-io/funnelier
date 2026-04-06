"""
Kavenegar SMS Provider — wraps the existing KavenegarConnector.

Supports single and bulk SMS sending, delivery status tracking,
webhook-based delivery updates, and credit/balance querying.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.core.interfaces.messaging import (
    IMessagingProvider,
    MessageStatus,
    ProviderInfo,
    SendResult,
    StatusResult,
)

logger = logging.getLogger(__name__)

# Comprehensive Kavenegar status code → MessageStatus mapping
# See https://kavenegar.com/rest.html#status-table
KAVENEGAR_STATUS_MAP: dict[int, MessageStatus] = {
    1: MessageStatus.QUEUED,       # در صف ارسال
    2: MessageStatus.SENT,         # زمان‌بندی شده
    4: MessageStatus.SENT,         # ارسال به مخابرات
    5: MessageStatus.SENT,         # ارسال به مخابرات
    6: MessageStatus.FAILED,       # خطای مخابرات
    10: MessageStatus.DELIVERED,   # رسیده به گیرنده
    11: MessageStatus.DELIVERED,   # نرسیده به گیرنده (operator says delivered)
    13: MessageStatus.FAILED,      # ارسال نشده
    14: MessageStatus.FAILED,      # بلاک شده
    100: MessageStatus.FAILED,     # شناسه نامعتبر
}

# Cost per SMS part in Rial (approximate, varies by line type)
DEFAULT_COST_PER_PART_RIAL = 680


class KavenegarProvider(IMessagingProvider):
    """
    Kavenegar SMS gateway adapter.

    Requires KAVENEGAR_API_KEY and KAVENEGAR_SENDER env vars.
    Wraps the Kavenegar REST API for sending SMS in Iran.
    """

    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender
        self._base_url = "https://api.kavenegar.com/v1"

    # ── Send single SMS ──────────────────────────────────────────────────

    async def send(self, phone_number: str, content: str, **kwargs: Any) -> SendResult:
        try:
            import httpx
        except ImportError:
            return SendResult(
                message_id=f"err-{uuid.uuid4().hex[:8]}",
                phone_number=phone_number,
                status=MessageStatus.FAILED,
                error_message="httpx not installed — run: pip install httpx",
            )

        url = f"{self._base_url}/{self._api_key}/sms/send.json"
        params = {
            "receptor": phone_number,
            "sender": kwargs.get("sender", self._sender),
            "message": content,
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params)
                data = resp.json()

            if resp.status_code == 200 and data.get("return", {}).get("status") == 200:
                entry = data["entries"][0] if data.get("entries") else {}
                cost_raw = entry.get("cost", 0)
                # Kavenegar returns cost in Toman; store in Rial (* 10)
                cost_rial = int(float(cost_raw or 0) * 10)
                return SendResult(
                    message_id=str(entry.get("messageid", uuid.uuid4().hex[:12])),
                    phone_number=phone_number,
                    status=MessageStatus.SENT,
                    provider_ref=str(entry.get("messageid", "")),
                    sent_at=datetime.now(timezone.utc),
                    cost=cost_rial,
                )
            else:
                return SendResult(
                    message_id=f"err-{uuid.uuid4().hex[:8]}",
                    phone_number=phone_number,
                    status=MessageStatus.FAILED,
                    error_message=data.get("return", {}).get("message", str(data)),
                )
        except Exception as exc:
            logger.exception("Kavenegar send failed: %s", exc)
            return SendResult(
                message_id=f"err-{uuid.uuid4().hex[:8]}",
                phone_number=phone_number,
                status=MessageStatus.FAILED,
                error_message=str(exc),
            )

    # ── Send bulk SMS (batch up to 200 per Kavenegar API) ────────────────

    async def send_bulk(
        self,
        phone_numbers: list[str],
        content: str,
        **kwargs: Any,
    ) -> list[SendResult]:
        try:
            import httpx
        except ImportError:
            return [
                SendResult(
                    message_id=f"err-{uuid.uuid4().hex[:8]}",
                    phone_number=p,
                    status=MessageStatus.FAILED,
                    error_message="httpx not installed",
                )
                for p in phone_numbers
            ]

        results: list[SendResult] = []
        batch_size = 200  # Kavenegar limit per request

        for i in range(0, len(phone_numbers), batch_size):
            batch = phone_numbers[i : i + batch_size]
            url = f"{self._base_url}/{self._api_key}/sms/send.json"
            params = {
                "receptor": ",".join(batch),
                "sender": kwargs.get("sender", self._sender),
                "message": content,
            }

            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(url, params=params)
                    data = resp.json()

                if resp.status_code == 200 and data.get("return", {}).get("status") == 200:
                    for entry in data.get("entries", []):
                        cost_rial = int(float(entry.get("cost", 0)) * 10)
                        results.append(SendResult(
                            message_id=str(entry.get("messageid", uuid.uuid4().hex[:12])),
                            phone_number=str(entry.get("receptor", "")),
                            status=MessageStatus.SENT,
                            provider_ref=str(entry.get("messageid", "")),
                            sent_at=datetime.now(timezone.utc),
                            cost=cost_rial,
                        ))
                else:
                    error_msg = data.get("return", {}).get("message", str(data))
                    for phone in batch:
                        results.append(SendResult(
                            message_id=f"err-{uuid.uuid4().hex[:8]}",
                            phone_number=phone,
                            status=MessageStatus.FAILED,
                            error_message=error_msg,
                        ))
            except Exception as exc:
                logger.exception("Kavenegar bulk send failed for batch %d: %s", i, exc)
                for phone in batch:
                    results.append(SendResult(
                        message_id=f"err-{uuid.uuid4().hex[:8]}",
                        phone_number=phone,
                        status=MessageStatus.FAILED,
                        error_message=str(exc),
                    ))

        return results

    # ── Check delivery status ────────────────────────────────────────────

    async def check_status(self, message_ids: list[str]) -> list[StatusResult]:
        try:
            import httpx
        except ImportError:
            return [
                StatusResult(message_id=mid, status=MessageStatus.UNKNOWN, error_message="httpx not installed")
                for mid in message_ids
            ]

        results: list[StatusResult] = []
        url = f"{self._base_url}/{self._api_key}/sms/status.json"

        # Kavenegar supports up to 500 message IDs per status check
        batch_size = 500
        for i in range(0, len(message_ids), batch_size):
            batch = message_ids[i : i + batch_size]
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(url, params={"messageid": ",".join(batch)})
                    data = resp.json()

                for entry in data.get("entries", []):
                    raw_status = entry.get("status", 0)
                    results.append(StatusResult(
                        message_id=str(entry.get("messageid", "")),
                        status=KAVENEGAR_STATUS_MAP.get(raw_status, MessageStatus.UNKNOWN),
                    ))
            except Exception as exc:
                logger.exception("Kavenegar status check failed: %s", exc)
                for mid in batch:
                    results.append(
                        StatusResult(message_id=mid, status=MessageStatus.UNKNOWN, error_message=str(exc))
                    )

        return results

    # ── Webhook payload parsing ──────────────────────────────────────────

    def parse_webhook_payload(self, data: dict[str, Any]) -> StatusResult:
        """
        Parse a Kavenegar delivery webhook POST payload into a StatusResult.

        Kavenegar webhook body fields:
            messageid, status, statustext, receptor, sender, message, date
        """
        raw_status = int(data.get("status", 0))
        message_id = str(data.get("messageid", ""))
        delivered_at = None
        if raw_status == 10:
            ts = data.get("date")
            delivered_at = (
                datetime.fromtimestamp(int(ts), tz=timezone.utc)
                if ts else datetime.now(timezone.utc)
            )

        return StatusResult(
            message_id=message_id,
            status=KAVENEGAR_STATUS_MAP.get(raw_status, MessageStatus.UNKNOWN),
            delivered_at=delivered_at,
            error_message=data.get("statustext") if raw_status not in (10, 11) else None,
        )

    # ── Account credit / balance ─────────────────────────────────────────

    async def get_credit(self) -> float | None:
        """Get remaining credit in Toman."""
        try:
            import httpx
            url = f"{self._base_url}/{self._api_key}/account/info.json"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                data = resp.json()
            return data.get("entries", {}).get("remaincredit")
        except Exception:
            return None

    # ── Cost estimation ──────────────────────────────────────────────────

    @staticmethod
    def estimate_cost(content: str, recipient_count: int = 1) -> int:
        """
        Estimate SMS cost in Rial.

        Persian SMS: 70 chars for 1 part, 67 chars per part for multi-part.
        """
        length = len(content)
        parts = 1 if length <= 70 else (length + 66) // 67
        return parts * DEFAULT_COST_PER_PART_RIAL * recipient_count

    # ── Provider info ────────────────────────────────────────────────────

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="kavenegar",
            display_name="Kavenegar SMS",
            supports_bulk=True,
            supports_status_check=True,
            supports_templates=True,
            max_batch_size=200,
            metadata={"region": "IR"},
        )

    async def test_connection(self) -> tuple[bool, str]:
        credit = await self.get_credit()
        if credit is not None:
            return True, f"Connected. Credit: {credit:,.0f} Toman"
        return False, "Could not reach Kavenegar API"

