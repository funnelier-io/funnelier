"""
Unit Tests for Phase 23: Audit Trail & Activity Log

Tests for audit domain entities, schemas, and constants.
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID

from src.modules.audit.domain.entities import (
    AuditLogEntry,
    ACTION_TYPES,
    RESOURCE_TYPES,
)
from src.modules.audit.api.schemas import (
    AuditLogResponse,
    AuditLogListResponse,
    AuditStatsResponse,
    UserActivitySummary,
    ActionBreakdown,
)


# ============================================================================
# Domain Entity Tests
# ============================================================================

class TestAuditLogEntry:
    """Tests for AuditLogEntry domain entity."""

    def test_create_entry(self):
        entry = AuditLogEntry(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="Admin User",
            user_role="tenant_admin",
            action="create",
            resource_type="user",
            description="Created user john.doe",
        )
        assert entry.action == "create"
        assert entry.resource_type == "user"
        assert entry.id is not None
        assert entry.changes is None
        assert entry.ip_address is None

    def test_entry_with_changes(self):
        entry = AuditLogEntry(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="Admin",
            user_role="tenant_admin",
            action="update",
            resource_type="contact",
            resource_id=str(uuid4()),
            description="Updated contact name",
            changes={"name": {"old": "Ali", "new": "Ali Rezaei"}},
        )
        assert entry.changes is not None
        assert "name" in entry.changes
        assert entry.changes["name"]["old"] == "Ali"

    def test_entry_with_ip_and_agent(self):
        entry = AuditLogEntry(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="User",
            user_role="viewer",
            action="login",
            resource_type="user",
            description="User logged in",
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "Mozilla/5.0"

    def test_entry_defaults(self):
        entry = AuditLogEntry(
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="Test",
            user_role="viewer",
            action="login",
            resource_type="user",
            description="Login",
        )
        assert entry.resource_id is None
        assert entry.changes is None
        assert entry.ip_address is None
        assert entry.user_agent is None
        assert isinstance(entry.created_at, datetime)


# ============================================================================
# Constants Tests
# ============================================================================

class TestAuditConstants:
    """Tests for audit action/resource type constants."""

    def test_action_types_defined(self):
        assert len(ACTION_TYPES) >= 15
        assert "create" in ACTION_TYPES
        assert "login" in ACTION_TYPES
        assert "delete" in ACTION_TYPES
        assert "approve" in ACTION_TYPES
        assert "sync" in ACTION_TYPES

    def test_resource_types_defined(self):
        assert len(RESOURCE_TYPES) >= 10
        assert "user" in RESOURCE_TYPES
        assert "contact" in RESOURCE_TYPES
        assert "campaign" in RESOURCE_TYPES
        assert "invoice" in RESOURCE_TYPES
        assert "sms_log" in RESOURCE_TYPES


# ============================================================================
# Schema Tests
# ============================================================================

class TestAuditLogResponse:
    """Tests for AuditLogResponse schema."""

    def test_full_response(self):
        resp = AuditLogResponse(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="Admin",
            user_role="tenant_admin",
            action="create",
            resource_type="user",
            resource_id=str(uuid4()),
            description="Created user",
            changes={"role": {"old": None, "new": "viewer"}},
            ip_address="10.0.0.1",
            created_at=datetime.utcnow(),
        )
        assert resp.action == "create"
        assert resp.changes is not None

    def test_response_optional_fields(self):
        resp = AuditLogResponse(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="User",
            user_role="viewer",
            action="login",
            resource_type="user",
            description="Login",
            created_at=datetime.utcnow(),
        )
        assert resp.resource_id is None
        assert resp.changes is None
        assert resp.ip_address is None


class TestAuditLogListResponse:
    """Tests for AuditLogListResponse schema."""

    def test_list_response(self):
        resp = AuditLogListResponse(
            items=[],
            total=0,
            offset=0,
            limit=50,
        )
        assert resp.total == 0
        assert len(resp.items) == 0

    def test_list_with_items(self):
        item = AuditLogResponse(
            id=uuid4(),
            tenant_id=UUID("00000000-0000-0000-0000-000000000001"),
            user_id=uuid4(),
            user_name="Test",
            user_role="manager",
            action="update",
            resource_type="contact",
            description="Updated",
            created_at=datetime.utcnow(),
        )
        resp = AuditLogListResponse(
            items=[item],
            total=1,
            offset=0,
            limit=50,
        )
        assert resp.total == 1
        assert len(resp.items) == 1


class TestAuditStatsResponse:
    """Tests for AuditStatsResponse schema."""

    def test_stats_response(self):
        resp = AuditStatsResponse(
            total_entries=100,
            user_activity=[
                UserActivitySummary(
                    user_id=str(uuid4()),
                    user_name="Admin",
                    action_count=50,
                    last_action="2026-04-06T12:00:00",
                )
            ],
            action_breakdown=[
                ActionBreakdown(action="login", count=30),
                ActionBreakdown(action="create", count=20),
            ],
        )
        assert resp.total_entries == 100
        assert len(resp.user_activity) == 1
        assert len(resp.action_breakdown) == 2
        assert resp.action_breakdown[0].action == "login"

    def test_empty_stats(self):
        resp = AuditStatsResponse(
            total_entries=0,
            user_activity=[],
            action_breakdown=[],
        )
        assert resp.total_entries == 0


class TestUserActivitySummary:
    """Tests for UserActivitySummary schema."""

    def test_summary(self):
        s = UserActivitySummary(
            user_id=str(uuid4()),
            user_name="Test User",
            action_count=25,
        )
        assert s.action_count == 25
        assert s.last_action is None

    def test_summary_with_last_action(self):
        s = UserActivitySummary(
            user_id=str(uuid4()),
            user_name="Admin",
            action_count=10,
            last_action="2026-04-06T10:30:00",
        )
        assert s.last_action is not None


class TestActionBreakdown:
    """Tests for ActionBreakdown schema."""

    def test_breakdown(self):
        b = ActionBreakdown(action="login", count=42)
        assert b.action == "login"
        assert b.count == 42

