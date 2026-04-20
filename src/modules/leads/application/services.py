"""
Leads Application Services

Business logic and use cases for lead management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from src.core.domain import LeadSource, PhoneNumber
from src.modules.leads.domain.entities import Contact, LeadCategory, LeadSourceConfig
from src.modules.leads.domain.repositories import (
    IContactRepository,
    ILeadCategoryRepository,
    ILeadSourceRepository,
)


class ContactService:
    """Service for managing contacts."""

    def __init__(
        self,
        contact_repo: IContactRepository,
        category_repo: ILeadCategoryRepository,
        source_repo: ILeadSourceRepository,
    ):
        self._contact_repo = contact_repo
        self._category_repo = category_repo
        self._source_repo = source_repo

    async def create_contact(
        self,
        tenant_id: UUID,
        phone_number: str,
        name: str | None = None,
        email: str | None = None,
        source_id: UUID | None = None,
        source_name: str | None = None,
        category_id: UUID | None = None,
        category_name: str | None = None,
        assigned_to: UUID | None = None,
        tags: list[str] | None = None,
        custom_fields: dict[str, Any] | None = None,
        notes: str | None = None,
    ) -> Contact:
        """Create a new contact."""
        # Normalize phone number
        normalized_phone = PhoneNumber.from_string(phone_number)

        # Check for existing contact
        existing = await self._contact_repo.get_by_phone(normalized_phone.normalized)
        if existing:
            raise ValueError(f"Contact with phone {phone_number} already exists")

        # Create contact
        contact = Contact(
            tenant_id=tenant_id,
            phone_number=normalized_phone,
            name=name,
            email=email,
            source_id=source_id,
            source_name=source_name,
            category_id=category_id,
            category_name=category_name,
            assigned_to=assigned_to,
            assigned_at=datetime.utcnow() if assigned_to else None,
            tags=tags or [],
            custom_fields=custom_fields or {},
            notes=notes,
        )

        await self._contact_repo.add(contact)
        return contact

    async def bulk_import_contacts(
        self,
        tenant_id: UUID,
        contacts_data: list[dict[str, Any]],
        source_id: UUID | None = None,
        category_id: UUID | None = None,
        skip_duplicates: bool = True,
    ) -> tuple[int, int, int, list[str]]:
        """
        Bulk import contacts.
        Returns (success_count, error_count, duplicate_count, errors).
        """
        success_count = 0
        error_count = 0
        duplicate_count = 0
        errors: list[str] = []

        # Get category name if category_id provided
        category_name = None
        if category_id:
            category = await self._category_repo.get(category_id)
            if category:
                category_name = category.name

        contacts_to_create: list[Contact] = []

        for idx, data in enumerate(contacts_data):
            try:
                phone_number = data.get("phone_number", "").strip()
                if not phone_number:
                    errors.append(f"Row {idx + 1}: Missing phone number")
                    error_count += 1
                    continue

                # Normalize phone
                normalized_phone = PhoneNumber.from_string(phone_number)

                # Check for duplicate
                existing = await self._contact_repo.get_by_phone(normalized_phone.normalized)
                if existing:
                    if skip_duplicates:
                        duplicate_count += 1
                        continue
                    else:
                        errors.append(f"Row {idx + 1}: Duplicate phone {phone_number}")
                        error_count += 1
                        continue

                contact = Contact(
                    tenant_id=tenant_id,
                    phone_number=normalized_phone,
                    name=data.get("name"),
                    email=data.get("email"),
                    source_id=source_id,
                    source_name=data.get("source_name"),
                    category_id=category_id,
                    category_name=category_name,
                    tags=data.get("tags", []),
                    custom_fields=data.get("custom_fields", {}),
                    notes=data.get("notes"),
                )
                contacts_to_create.append(contact)

            except Exception as e:
                errors.append(f"Row {idx + 1}: {str(e)}")
                error_count += 1

        # Bulk create
        if contacts_to_create:
            created, failed, create_errors = await self._contact_repo.bulk_create(contacts_to_create)
            success_count = created
            error_count += failed
            errors.extend(create_errors)

        return success_count, error_count, duplicate_count, errors

    async def assign_contact_to_salesperson(
        self,
        contact_id: UUID,
        salesperson_id: UUID,
        salesperson_name: str,
    ) -> Contact:
        """Assign a contact to a salesperson."""
        contact = await self._contact_repo.get(contact_id)
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")

        contact.assign_to_salesperson(salesperson_id, salesperson_name)
        await self._contact_repo.update(contact)
        return contact

    async def bulk_assign_contacts(
        self,
        contact_ids: list[UUID],
        salesperson_id: UUID,
    ) -> int:
        """Bulk assign contacts to a salesperson."""
        return await self._contact_repo.bulk_assign(contact_ids, salesperson_id)

    async def update_contact_stage(
        self,
        contact_id: UUID,
        new_stage: str,
    ) -> Contact:
        """Update contact's funnel stage."""
        contact = await self._contact_repo.get(contact_id)
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")

        contact.update_stage(new_stage)
        await self._contact_repo.update(contact)
        return contact

    async def block_contact(
        self,
        contact_id: UUID,
        reason: str | None = None,
    ) -> Contact:
        """Block a contact."""
        contact = await self._contact_repo.get(contact_id)
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")

        contact.block(reason)
        await self._contact_repo.update(contact)
        return contact

    async def unblock_contact(
        self,
        contact_id: UUID,
    ) -> Contact:
        """Unblock a contact."""
        contact = await self._contact_repo.get(contact_id)
        if not contact:
            raise ValueError(f"Contact {contact_id} not found")

        contact.unblock()
        await self._contact_repo.update(contact)
        return contact


class CategoryService:
    """Service for managing lead categories."""

    def __init__(self, category_repo: ILeadCategoryRepository):
        self._category_repo = category_repo

    async def create_category(
        self,
        tenant_id: UUID,
        name: str,
        description: str | None = None,
        parent_id: UUID | None = None,
        color: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LeadCategory:
        """Create a new category."""
        # Check for existing category with same name
        existing = await self._category_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Category '{name}' already exists")

        category = LeadCategory(
            tenant_id=tenant_id,
            name=name,
            description=description,
            parent_id=parent_id,
            color=color,
            metadata=metadata or {},
        )

        await self._category_repo.add(category)
        return category

    async def get_category_tree(self) -> list[dict[str, Any]]:
        """Get categories in hierarchical tree structure."""
        root_categories = await self._category_repo.get_root_categories()
        tree = []

        for root in root_categories:
            node = await self._build_category_node(root)
            tree.append(node)

        return tree

    async def _build_category_node(self, category: LeadCategory) -> dict[str, Any]:
        """Recursively build category tree node."""
        children = await self._category_repo.get_children(category.id)
        child_nodes = []

        for child in children:
            child_node = await self._build_category_node(child)
            child_nodes.append(child_node)

        return {
            "id": str(category.id),
            "name": category.name,
            "description": category.description,
            "color": category.color,
            "children": child_nodes,
        }


class LeadSourceService:
    """Service for managing lead sources."""

    def __init__(self, source_repo: ILeadSourceRepository):
        self._source_repo = source_repo

    async def create_source(
        self,
        tenant_id: UUID,
        name: str,
        source_type: LeadSource,
        file_path: str | None = None,
        category_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> LeadSourceConfig:
        """Create a new lead source."""
        # Check for existing source with same name
        existing = await self._source_repo.get_by_name(name)
        if existing:
            raise ValueError(f"Source '{name}' already exists")

        source = LeadSourceConfig(
            tenant_id=tenant_id,
            name=name,
            source_type=source_type,
            file_path=file_path,
            category_id=category_id,
            metadata=metadata or {},
        )

        await self._source_repo.add(source)
        return source

    async def update_import_stats(
        self,
        source_id: UUID,
        total_leads: int,
    ) -> None:
        """Update import statistics for a source."""
        await self._source_repo.update_import_stats(source_id, total_leads)

