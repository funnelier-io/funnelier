"""
Tests for Leads Module — Sprint 1 P0 Gap Closure.

Covers:
- Contact entity (create, assign, stage transitions, record metrics, block/unblock)
- LeadCategory & LeadSourceConfig entities
- ContactService (with mocked repositories)
- CategoryService
- API schemas validation
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from src.core.domain import (
    InvoiceStatus,
    LeadSource,
    PhoneNumber,
    LeadCreatedEvent,
    LeadCategorizedEvent,
    LeadAssignedEvent,
)
from src.modules.leads.domain.entities import Contact, LeadCategory, LeadSourceConfig
from src.modules.leads.application.services import (
    ContactService,
    CategoryService,
    LeadSourceService,
)
from src.modules.leads.api.schemas import (
    ContactBase,
    CreateContactRequest,
    UpdateContactRequest,
    ContactResponse,
    ContactListResponse,
    LeadStatsResponse,
    BulkImportRequest,
    BulkImportResponse,
    CreateCategoryRequest,
    CategoryResponse,
    ContactSearchRequest,
    BulkAssignRequest,
    AutoAssignRequest,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ═══════════════════════════════════════════════════════════════════
# Contact Entity
# ═══════════════════════════════════════════════════════════════════


class TestContactEntity:
    """Tests for Contact aggregate root."""

    def _make_contact(self, **kwargs) -> Contact:
        defaults = dict(
            tenant_id=TENANT_ID,
            phone_number=PhoneNumber.from_string("9121234567"),
            name="علی رضایی",
            source_name="excel:test.xlsx",
            category_name="سازندگان",
        )
        defaults.update(kwargs)
        return Contact(**defaults)

    def test_create_factory(self):
        contact = Contact.create(
            tenant_id=TENANT_ID,
            phone="09121234567",
            source_name="manual",
            name="Test User",
            category_name="تست",
        )
        assert contact.tenant_id == TENANT_ID
        assert contact.phone_number.normalized == "9121234567"
        assert contact.name == "Test User"
        assert contact.current_stage == "lead_acquired"
        # Should emit a LeadCreatedEvent
        assert len(contact.domain_events) == 1
        assert isinstance(contact.domain_events[0], LeadCreatedEvent)

    def test_default_stage_is_lead_acquired(self):
        c = self._make_contact()
        assert c.current_stage == "lead_acquired"

    def test_assign_category_emits_event(self):
        c = self._make_contact()
        cat_id = uuid4()
        c.assign_category(cat_id, "خریداران سیمان")

        assert c.category_id == cat_id
        assert c.category_name == "خریداران سیمان"
        events = [e for e in c.domain_events if isinstance(e, LeadCategorizedEvent)]
        assert len(events) == 1
        assert events[0].new_category == "خریداران سیمان"

    def test_assign_to_salesperson(self):
        c = self._make_contact()
        sp_id = uuid4()
        c.assign_to_salesperson(sp_id, "بردبار")

        assert c.assigned_to == sp_id
        assert c.assigned_at is not None
        events = [e for e in c.domain_events if isinstance(e, LeadAssignedEvent)]
        assert len(events) == 1

    def test_update_stage(self):
        c = self._make_contact()
        c.update_stage("sms_sent")
        assert c.current_stage == "sms_sent"

    def test_update_stage_noop_when_same(self):
        c = self._make_contact()
        original_time = c.stage_entered_at
        c.update_stage("lead_acquired")
        assert c.stage_entered_at == original_time

    def test_record_sms_sent_updates_counters(self):
        c = self._make_contact()
        c.record_sms_sent(delivered=False)
        assert c.total_sms_sent == 1
        assert c.total_sms_delivered == 0
        assert c.current_stage == "sms_sent"

    def test_record_sms_delivered(self):
        c = self._make_contact()
        c.record_sms_sent(delivered=True)
        assert c.total_sms_sent == 1
        assert c.total_sms_delivered == 1

    def test_record_call_answered_updates_stage(self):
        c = self._make_contact()
        c.record_call(duration_seconds=120, is_answered=True)
        assert c.total_calls == 1
        assert c.total_answered_calls == 1
        assert c.total_call_duration == 120
        assert c.current_stage == "call_answered"

    def test_record_call_short_duration_not_answered(self):
        """Calls shorter than threshold (90s) are not counted as answered."""
        c = self._make_contact()
        c.record_call(duration_seconds=60, is_answered=True, min_duration_threshold=90)
        assert c.total_answered_calls == 0
        assert c.current_stage == "call_attempted"

    def test_record_call_missed(self):
        c = self._make_contact()
        c.record_call(duration_seconds=0, is_answered=False)
        assert c.total_calls == 1
        assert c.current_stage == "call_attempted"

    def test_record_invoice_unpaid(self):
        c = self._make_contact()
        c.record_invoice(amount=5_000_000, is_paid=False)
        assert c.total_invoices == 1
        assert c.total_paid_invoices == 0
        assert c.current_stage == "invoice_issued"

    def test_record_invoice_paid(self):
        c = self._make_contact()
        c.record_invoice(amount=10_000_000, is_paid=True)
        assert c.total_invoices == 1
        assert c.total_paid_invoices == 1
        assert c.total_revenue == 10_000_000
        assert c.last_purchase_at is not None
        assert c.first_purchase_at is not None
        assert c.current_stage == "payment_received"

    def test_record_multiple_paid_invoices(self):
        c = self._make_contact()
        c.record_invoice(amount=5_000_000, is_paid=True)
        c.record_invoice(amount=3_000_000, is_paid=True)
        assert c.total_revenue == 8_000_000
        assert c.total_paid_invoices == 2

    def test_block_and_unblock(self):
        c = self._make_contact()
        c.block(reason="درخواست مشتری")
        assert c.is_blocked is True
        assert c.blocked_reason == "درخواست مشتری"

        c.unblock()
        assert c.is_blocked is False
        assert c.blocked_reason is None

    def test_default_values(self):
        c = self._make_contact()
        assert c.is_active is True
        assert c.is_blocked is False
        assert c.tags == []
        assert c.custom_fields == {}
        assert c.total_sms_sent == 0
        assert c.total_calls == 0
        assert c.total_revenue == 0


# ═══════════════════════════════════════════════════════════════════
# LeadCategory Entity
# ═══════════════════════════════════════════════════════════════════


class TestLeadCategory:
    def test_basic_creation(self):
        cat = LeadCategory(
            tenant_id=TENANT_ID,
            name="سازندگان",
            description="سازندگان مسکونی",
            color="#3B82F6",
        )
        assert cat.name == "سازندگان"
        assert cat.is_active is True
        assert cat.parent_id is None

    def test_hierarchical_category(self):
        parent = LeadCategory(tenant_id=TENANT_ID, name="ساختمان")
        child = LeadCategory(
            tenant_id=TENANT_ID,
            name="سیمان",
            parent_id=parent.id,
        )
        assert child.parent_id == parent.id

    def test_metadata_defaults_to_empty(self):
        cat = LeadCategory(tenant_id=TENANT_ID, name="تست")
        assert cat.metadata == {}


# ═══════════════════════════════════════════════════════════════════
# LeadSourceConfig Entity
# ═══════════════════════════════════════════════════════════════════


class TestLeadSourceConfig:
    def test_creation(self):
        src = LeadSourceConfig(
            tenant_id=TENANT_ID,
            name="تهران بردبار",
            source_type=LeadSource.FILE_IMPORT,
            file_path="/data/tehran.xlsx",
        )
        assert src.name == "تهران بردبار"
        assert src.source_type == LeadSource.FILE_IMPORT
        assert src.is_active is True
        assert src.total_leads == 0


# ═══════════════════════════════════════════════════════════════════
# ContactService (Application Layer)
# ═══════════════════════════════════════════════════════════════════


class TestContactService:
    """Tests for ContactService with mocked repositories."""

    def _make_service(self):
        contact_repo = AsyncMock()
        category_repo = AsyncMock()
        source_repo = AsyncMock()
        svc = ContactService(contact_repo, category_repo, source_repo)
        return svc, contact_repo, category_repo, source_repo

    @pytest.mark.asyncio
    async def test_create_contact_success(self):
        svc, contact_repo, _, _ = self._make_service()
        contact_repo.get_by_phone.return_value = None

        contact = await svc.create_contact(
            tenant_id=TENANT_ID,
            phone_number="09121234567",
            name="Test",
        )
        assert contact.name == "Test"
        contact_repo.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_contact_duplicate_raises(self):
        svc, contact_repo, _, _ = self._make_service()
        contact_repo.get_by_phone.return_value = MagicMock()

        with pytest.raises(ValueError, match="already exists"):
            await svc.create_contact(
                tenant_id=TENANT_ID,
                phone_number="09121234567",
            )

    @pytest.mark.asyncio
    async def test_assign_contact_to_salesperson(self):
        svc, contact_repo, _, _ = self._make_service()
        existing = Contact(
            tenant_id=TENANT_ID,
            phone_number=PhoneNumber.from_string("9121234567"),
        )
        contact_repo.get.return_value = existing
        sp_id = uuid4()

        result = await svc.assign_contact_to_salesperson(
            existing.id, sp_id, "بردبار"
        )
        assert result.assigned_to == sp_id
        contact_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_assign_nonexistent_contact_raises(self):
        svc, contact_repo, _, _ = self._make_service()
        contact_repo.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await svc.assign_contact_to_salesperson(uuid4(), uuid4(), "test")

    @pytest.mark.asyncio
    async def test_update_contact_stage(self):
        svc, contact_repo, _, _ = self._make_service()
        existing = Contact(
            tenant_id=TENANT_ID,
            phone_number=PhoneNumber.from_string("9121234567"),
        )
        contact_repo.get.return_value = existing

        result = await svc.update_contact_stage(existing.id, "sms_sent")
        assert result.current_stage == "sms_sent"

    @pytest.mark.asyncio
    async def test_block_contact(self):
        svc, contact_repo, _, _ = self._make_service()
        existing = Contact(
            tenant_id=TENANT_ID,
            phone_number=PhoneNumber.from_string("9121234567"),
        )
        contact_repo.get.return_value = existing

        result = await svc.block_contact(existing.id, "spam")
        assert result.is_blocked is True

    @pytest.mark.asyncio
    async def test_unblock_contact(self):
        svc, contact_repo, _, _ = self._make_service()
        existing = Contact(
            tenant_id=TENANT_ID,
            phone_number=PhoneNumber.from_string("9121234567"),
            is_blocked=True,
        )
        contact_repo.get.return_value = existing

        result = await svc.unblock_contact(existing.id)
        assert result.is_blocked is False

    @pytest.mark.asyncio
    async def test_bulk_import_contacts(self):
        svc, contact_repo, category_repo, _ = self._make_service()
        contact_repo.get_by_phone.return_value = None
        contact_repo.bulk_create.return_value = (3, 0, [])

        success, errors, dupes, error_list = await svc.bulk_import_contacts(
            tenant_id=TENANT_ID,
            contacts_data=[
                {"phone_number": "09121234567", "name": "A"},
                {"phone_number": "09131234567", "name": "B"},
                {"phone_number": "09351234567", "name": "C"},
            ],
        )
        assert success == 3
        assert dupes == 0

    @pytest.mark.asyncio
    async def test_bulk_import_skips_duplicates(self):
        svc, contact_repo, _, _ = self._make_service()
        contact_repo.get_by_phone.return_value = MagicMock()  # All are duplicates
        contact_repo.bulk_create.return_value = (0, 0, [])

        success, errors, dupes, _ = await svc.bulk_import_contacts(
            tenant_id=TENANT_ID,
            contacts_data=[{"phone_number": "09121234567"}],
            skip_duplicates=True,
        )
        assert dupes == 1
        assert success == 0

    @pytest.mark.asyncio
    async def test_bulk_import_empty_phone_counted_as_error(self):
        svc, contact_repo, _, _ = self._make_service()
        contact_repo.bulk_create.return_value = (0, 0, [])

        success, errors, dupes, error_list = await svc.bulk_import_contacts(
            tenant_id=TENANT_ID,
            contacts_data=[{"phone_number": ""}],
        )
        assert errors == 1
        assert "Missing phone" in error_list[0]


# ═══════════════════════════════════════════════════════════════════
# CategoryService
# ═══════════════════════════════════════════════════════════════════


class TestCategoryService:
    @pytest.mark.asyncio
    async def test_create_category_success(self):
        repo = AsyncMock()
        repo.get_by_name.return_value = None
        svc = CategoryService(repo)

        cat = await svc.create_category(
            tenant_id=TENANT_ID,
            name="سازندگان",
            description="سازندگان مسکونی",
            color="#3B82F6",
        )
        assert cat.name == "سازندگان"
        repo.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_category_duplicate_raises(self):
        repo = AsyncMock()
        repo.get_by_name.return_value = MagicMock()
        svc = CategoryService(repo)

        with pytest.raises(ValueError, match="already exists"):
            await svc.create_category(tenant_id=TENANT_ID, name="سازندگان")

    @pytest.mark.asyncio
    async def test_get_category_tree_empty(self):
        repo = AsyncMock()
        repo.get_root_categories.return_value = []
        svc = CategoryService(repo)

        tree = await svc.get_category_tree()
        assert tree == []


# ═══════════════════════════════════════════════════════════════════
# LeadSourceService
# ═══════════════════════════════════════════════════════════════════


class TestLeadSourceService:
    @pytest.mark.asyncio
    async def test_create_source_success(self):
        repo = AsyncMock()
        repo.get_by_name.return_value = None
        svc = LeadSourceService(repo)

        src = await svc.create_source(
            tenant_id=TENANT_ID,
            name="تهران بردبار",
            source_type=LeadSource.FILE_IMPORT,
            file_path="/data/test.xlsx",
        )
        assert src.name == "تهران بردبار"
        repo.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_source_duplicate_raises(self):
        repo = AsyncMock()
        repo.get_by_name.return_value = MagicMock()
        svc = LeadSourceService(repo)

        with pytest.raises(ValueError, match="already exists"):
            await svc.create_source(
                tenant_id=TENANT_ID,
                name="existing",
                source_type=LeadSource.MANUAL,
            )


# ═══════════════════════════════════════════════════════════════════
# API Schemas
# ═══════════════════════════════════════════════════════════════════


class TestLeadSchemas:
    def test_create_contact_request(self):
        req = CreateContactRequest(phone_number="09121234567", name="Ali")
        assert req.phone_number == "09121234567"
        assert req.tags == []

    def test_update_contact_request_all_optional(self):
        req = UpdateContactRequest()
        assert req.name is None
        assert req.tags is None

    def test_contact_list_response(self):
        resp = ContactListResponse(
            contacts=[],
            total_count=0,
            page=1,
            page_size=20,
            has_next=False,
            has_prev=False,
        )
        assert resp.total_count == 0

    def test_lead_stats_response(self):
        stats = LeadStatsResponse(
            total_contacts=100,
            active_contacts=90,
            blocked_contacts=10,
            by_stage={"lead_acquired": 50, "sms_sent": 30},
            by_category={"سازندگان": 60},
        )
        assert stats.total_contacts == 100
        assert stats.by_stage["lead_acquired"] == 50

    def test_bulk_import_request(self):
        req = BulkImportRequest(
            contacts=[
                CreateContactRequest(phone_number="09121234567"),
                CreateContactRequest(phone_number="09131234567"),
            ],
        )
        assert len(req.contacts) == 2
        assert req.skip_duplicates is True

    def test_contact_search_request(self):
        req = ContactSearchRequest(
            query="علی",
            stage="lead_acquired",
            is_active=True,
        )
        assert req.query == "علی"

    def test_bulk_assign_request(self):
        sp_id = uuid4()
        req = BulkAssignRequest(
            contact_ids=[uuid4(), uuid4()],
            salesperson_id=sp_id,
        )
        assert len(req.contact_ids) == 2

    def test_auto_assign_defaults(self):
        req = AutoAssignRequest()
        assert req.assignment_strategy == "round_robin"

