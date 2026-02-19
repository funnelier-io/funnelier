"""
Leads Module - Domain Repository Interfaces
"""

from abc import abstractmethod
from typing import Any
from uuid import UUID

from src.core.interfaces import IAggregateRepository, ITenantRepository

from .entities import Contact, LeadCategory, LeadSourceConfig


class IContactRepository(IAggregateRepository[Contact, UUID]):
    """Repository interface for Contact aggregate."""

    @abstractmethod
    async def get_by_phone(self, phone_number: str) -> Contact | None:
        """Get contact by normalized phone number."""
        pass

    @abstractmethod
    async def get_by_category(
        self,
        category_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts by category."""
        pass

    @abstractmethod
    async def get_by_source(
        self,
        source_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts by source."""
        pass

    @abstractmethod
    async def get_by_segment(
        self,
        segment: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts by RFM segment."""
        pass

    @abstractmethod
    async def get_by_stage(
        self,
        stage: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts by funnel stage."""
        pass

    @abstractmethod
    async def get_by_salesperson(
        self,
        salesperson_id: UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts assigned to a salesperson."""
        pass

    @abstractmethod
    async def get_unassigned(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Get contacts not assigned to any salesperson."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Contact]:
        """Search contacts by phone or name."""
        pass

    @abstractmethod
    async def bulk_create(
        self,
        contacts: list[Contact],
    ) -> tuple[int, int, list[str]]:
        """
        Bulk create contacts.
        Returns (success_count, error_count, errors).
        """
        pass

    @abstractmethod
    async def bulk_update_category(
        self,
        contact_ids: list[UUID],
        category_id: UUID,
        category_name: str,
    ) -> int:
        """Bulk update category for contacts."""
        pass

    @abstractmethod
    async def bulk_assign(
        self,
        contact_ids: list[UUID],
        salesperson_id: UUID,
    ) -> int:
        """Bulk assign contacts to salesperson."""
        pass


class ILeadCategoryRepository(ITenantRepository[LeadCategory, UUID]):
    """Repository interface for LeadCategory."""

    @abstractmethod
    async def get_by_name(self, name: str) -> LeadCategory | None:
        """Get category by name."""
        pass

    @abstractmethod
    async def get_children(self, parent_id: UUID) -> list[LeadCategory]:
        """Get child categories."""
        pass

    @abstractmethod
    async def get_root_categories(self) -> list[LeadCategory]:
        """Get top-level categories."""
        pass

    @abstractmethod
    async def get_with_contact_count(self) -> list[tuple[LeadCategory, int]]:
        """Get all categories with their contact counts."""
        pass


class ILeadSourceRepository(ITenantRepository[LeadSourceConfig, UUID]):
    """Repository interface for LeadSourceConfig."""

    @abstractmethod
    async def get_by_name(self, name: str) -> LeadSourceConfig | None:
        """Get source by name."""
        pass

    @abstractmethod
    async def get_active_sources(self) -> list[LeadSourceConfig]:
        """Get all active sources."""
        pass

    @abstractmethod
    async def update_import_stats(
        self,
        source_id: UUID,
        total_leads: int,
    ) -> None:
        """Update import statistics for a source."""
        pass

