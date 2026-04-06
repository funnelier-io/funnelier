"""
Abstract Messaging Provider Interface

Pluggable adapter pattern for SMS/messaging services.
Implement this interface to add support for any SMS or messaging provider
(Kavenegar, Twilio, Ghasedak, AWS SNS, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageStatus(str, Enum):
    """Delivery status for a message."""
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass
class SendResult:
    """Result of sending a single message."""
    message_id: str
    phone_number: str
    status: MessageStatus
    provider_ref: str | None = None   # Provider-specific reference
    error_message: str | None = None
    sent_at: datetime | None = None
    cost: float | None = None         # Cost in provider's currency unit


@dataclass
class StatusResult:
    """Result of checking message delivery status."""
    message_id: str
    status: MessageStatus
    delivered_at: datetime | None = None
    error_message: str | None = None


@dataclass
class ProviderInfo:
    """Metadata about a messaging provider."""
    name: str
    display_name: str
    supports_bulk: bool = True
    supports_status_check: bool = True
    supports_templates: bool = False
    max_batch_size: int = 500
    metadata: dict[str, Any] = field(default_factory=dict)


class IMessagingProvider(ABC):
    """
    Abstract interface for messaging/SMS providers.

    Implementations:
    - KavenegarProvider: Iran-based SMS via Kavenegar API
    - MockProvider: Development/test provider that logs messages
    - (Future) TwilioProvider, GhasedakProvider, etc.

    Usage:
        provider = MessagingProviderRegistry.get()
        result = await provider.send("09123456789", "Hello!")
    """

    @abstractmethod
    async def send(self, phone_number: str, content: str, **kwargs: Any) -> SendResult:
        """
        Send a single message.

        Args:
            phone_number: Recipient phone number (E.164 or local format)
            content: Message text content
            **kwargs: Provider-specific options (template_id, sender, etc.)

        Returns:
            SendResult with status and message_id
        """
        ...

    @abstractmethod
    async def send_bulk(
        self,
        phone_numbers: list[str],
        content: str,
        **kwargs: Any,
    ) -> list[SendResult]:
        """
        Send the same message to multiple recipients.

        Args:
            phone_numbers: List of recipient phone numbers
            content: Message text
            **kwargs: Provider-specific options

        Returns:
            List of SendResult, one per recipient
        """
        ...

    @abstractmethod
    async def check_status(self, message_ids: list[str]) -> list[StatusResult]:
        """
        Check delivery status for previously sent messages.

        Args:
            message_ids: List of message IDs returned from send()

        Returns:
            List of StatusResult with current delivery status
        """
        ...

    @abstractmethod
    async def get_credit(self) -> float | None:
        """
        Get remaining credit/balance for this provider.

        Returns:
            Remaining credit in provider's currency, or None if not supported
        """
        ...

    @abstractmethod
    def get_info(self) -> ProviderInfo:
        """Get metadata about this provider."""
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """
        Test connectivity to the provider.

        Returns:
            (success, message) tuple
        """
        ...

