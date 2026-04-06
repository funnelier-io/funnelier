"""
Mock Messaging Provider — logs messages without sending.
Used for development and testing.
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


class MockMessagingProvider(IMessagingProvider):
    """Development/test messaging provider that logs messages instead of sending."""

    def __init__(self) -> None:
        self._sent: dict[str, SendResult] = {}

    async def send(self, phone_number: str, content: str, **kwargs: Any) -> SendResult:
        msg_id = f"mock-{uuid.uuid4().hex[:12]}"
        result = SendResult(
            message_id=msg_id,
            phone_number=phone_number,
            status=MessageStatus.DELIVERED,
            provider_ref=msg_id,
            sent_at=datetime.now(timezone.utc),
            cost=0.0,
        )
        self._sent[msg_id] = result
        logger.info(
            "[MockSMS] → %s | %s",
            phone_number,
            content[:80],
        )
        return result

    async def send_bulk(
        self,
        phone_numbers: list[str],
        content: str,
        **kwargs: Any,
    ) -> list[SendResult]:
        results = []
        for phone in phone_numbers:
            results.append(await self.send(phone, content, **kwargs))
        return results

    async def check_status(self, message_ids: list[str]) -> list[StatusResult]:
        out: list[StatusResult] = []
        for mid in message_ids:
            if mid in self._sent:
                out.append(StatusResult(
                    message_id=mid,
                    status=MessageStatus.DELIVERED,
                    delivered_at=self._sent[mid].sent_at,
                ))
            else:
                out.append(StatusResult(
                    message_id=mid,
                    status=MessageStatus.UNKNOWN,
                    error_message="Not found in mock store",
                ))
        return out

    async def get_credit(self) -> float | None:
        return 999_999.0  # unlimited in dev

    def get_info(self) -> ProviderInfo:
        return ProviderInfo(
            name="mock",
            display_name="Mock Provider (Dev)",
            supports_bulk=True,
            supports_status_check=True,
            supports_templates=False,
        )

    async def test_connection(self) -> tuple[bool, str]:
        return True, "Mock provider always connected"

