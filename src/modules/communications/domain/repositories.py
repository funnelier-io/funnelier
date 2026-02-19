"""
Communications Module - Domain Repository Interfaces
"""

from abc import abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from src.core.interfaces import IAggregateRepository, ITenantRepository

from .entities import CallLog, SMSLog, SMSTemplate


class ISMSLogRepository(IAggregateRepository[SMSLog, UUID]):
    """Repository interface for SMS logs."""

    @abstractmethod
    async def get_by_phone(
        self,
        phone_number: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SMSLog]:
        """Get SMS logs by phone number."""
        pass

    @abstractmethod
    async def get_by_campaign(
        self,
        campaign_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SMSLog]:
        """Get SMS logs by campaign."""
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SMSLog]:
        """Get SMS logs by status."""
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SMSLog]:
        """Get SMS logs within date range."""
        pass

    @abstractmethod
    async def get_delivery_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, int]:
        """Get delivery statistics."""
        pass

    @abstractmethod
    async def bulk_create(
        self,
        logs: list[SMSLog],
    ) -> tuple[int, int, list[str]]:
        """Bulk create SMS logs."""
        pass


class ICallLogRepository(IAggregateRepository[CallLog, UUID]):
    """Repository interface for call logs."""

    @abstractmethod
    async def get_by_phone(
        self,
        phone_number: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CallLog]:
        """Get call logs by phone number."""
        pass

    @abstractmethod
    async def get_by_salesperson(
        self,
        salesperson_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CallLog]:
        """Get call logs by salesperson."""
        pass

    @abstractmethod
    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CallLog]:
        """Get call logs within date range."""
        pass

    @abstractmethod
    async def get_by_source(
        self,
        source: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CallLog]:
        """Get call logs by source (mobile/voip)."""
        pass

    @abstractmethod
    async def get_successful_calls(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CallLog]:
        """Get successful calls (duration >= threshold)."""
        pass

    @abstractmethod
    async def get_call_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        group_by: str | None = None,  # salesperson, source, type
    ) -> dict[str, Any]:
        """Get call statistics."""
        pass

    @abstractmethod
    async def bulk_create(
        self,
        logs: list[CallLog],
    ) -> tuple[int, int, list[str]]:
        """Bulk create call logs."""
        pass


class ISMSTemplateRepository(ITenantRepository[SMSTemplate, UUID]):
    """Repository interface for SMS templates."""

    @abstractmethod
    async def get_by_name(self, name: str) -> SMSTemplate | None:
        """Get template by name."""
        pass

    @abstractmethod
    async def get_by_category(
        self,
        category: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[SMSTemplate]:
        """Get templates by category."""
        pass

    @abstractmethod
    async def get_for_segment(
        self,
        segment: str,
    ) -> list[SMSTemplate]:
        """Get templates recommended for an RFM segment."""
        pass

    @abstractmethod
    async def get_active_templates(self) -> list[SMSTemplate]:
        """Get all active templates."""
        pass

    @abstractmethod
    async def increment_usage(self, template_id: UUID) -> None:
        """Increment template usage counter."""
        pass

