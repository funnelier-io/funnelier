"""
Unit Tests — Named Segment Rules (Phase 38)

Covers:
- NamedSegmentRule domain entity (evaluate, defaults, validation)
- SegmentRulePreview / BulkAssignResult schemas
- SegmentRuleService (CRUD mocked via repository)
"""

import pytest
from datetime import datetime
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock, patch

from src.modules.segmentation.domain.segment_rules import (
    BulkAssignResult,
    NamedSegmentRule,
    SegmentRulePreview,
)


# ─── Domain Entity ───────────────────────────────────────────────────────────

class TestNamedSegmentRule:
    def _make_rule(self, **kwargs) -> NamedSegmentRule:
        defaults = dict(
            tenant_id=uuid4(),
            name="Champions Plus",
            r_min=4, r_max=5,
            f_min=4, f_max=5,
            m_min=4, m_max=5,
        )
        defaults.update(kwargs)
        return NamedSegmentRule(**defaults)

    def test_default_color(self):
        rule = self._make_rule()
        assert rule.color == "#6366f1"

    def test_default_priority_is_zero(self):
        rule = self._make_rule()
        assert rule.priority == 0

    def test_auto_id_generated(self):
        rule = self._make_rule()
        assert isinstance(rule.id, UUID)

    def test_evaluate_match(self):
        rule = self._make_rule(r_min=4, r_max=5, f_min=3, f_max=5, m_min=4, m_max=5)
        assert rule.evaluate(recency=5, frequency=4, monetary=4) is True

    def test_evaluate_no_match_recency(self):
        rule = self._make_rule(r_min=4, r_max=5)
        assert rule.evaluate(recency=3, frequency=4, monetary=4) is False

    def test_evaluate_no_match_frequency(self):
        rule = self._make_rule(f_min=3, f_max=5)
        assert rule.evaluate(recency=4, frequency=2, monetary=4) is False

    def test_evaluate_no_match_monetary(self):
        rule = self._make_rule(m_min=3, m_max=5)
        assert rule.evaluate(recency=4, frequency=3, monetary=2) is False

    def test_evaluate_edge_boundary_inclusive(self):
        rule = self._make_rule(r_min=3, r_max=3, f_min=3, f_max=3, m_min=3, m_max=3)
        assert rule.evaluate(3, 3, 3) is True
        assert rule.evaluate(2, 3, 3) is False
        assert rule.evaluate(4, 3, 3) is False

    def test_evaluate_full_range_always_true(self):
        rule = self._make_rule(r_min=1, r_max=5, f_min=1, f_max=5, m_min=1, m_max=5)
        for r in range(1, 6):
            for f in range(1, 6):
                assert rule.evaluate(r, f, 3) is True

    def test_custom_color(self):
        rule = self._make_rule(color="#ff0000")
        assert rule.color == "#ff0000"

    def test_optional_description(self):
        rule = self._make_rule(description="High-value customers")
        assert rule.description == "High-value customers"

    def test_description_defaults_to_none(self):
        rule = self._make_rule()
        assert rule.description is None

    def test_priority_ordering(self):
        r1 = self._make_rule(priority=1)
        r2 = self._make_rule(priority=10)
        assert r1.priority < r2.priority

    def test_timestamps_set_automatically(self):
        rule = self._make_rule()
        assert isinstance(rule.created_at, datetime)
        assert isinstance(rule.updated_at, datetime)

    def test_rfm_bounds_validation_min(self):
        with pytest.raises(Exception):
            self._make_rule(r_min=0)  # ge=1 constraint

    def test_rfm_bounds_validation_max(self):
        with pytest.raises(Exception):
            self._make_rule(r_max=6)  # le=5 constraint


# ─── Preview / BulkAssign schemas ────────────────────────────────────────────

class TestSegmentRulePreview:
    def test_default_empty_sample(self):
        preview = SegmentRulePreview(rule_id=uuid4(), matching_count=0)
        assert preview.sample_contact_ids == []

    def test_with_sample_ids(self):
        ids = [uuid4(), uuid4(), uuid4()]
        preview = SegmentRulePreview(rule_id=uuid4(), matching_count=3, sample_contact_ids=ids)
        assert len(preview.sample_contact_ids) == 3

    def test_matching_count_zero(self):
        preview = SegmentRulePreview(rule_id=uuid4(), matching_count=0)
        assert preview.matching_count == 0


class TestBulkAssignResult:
    def test_fields(self):
        rule_id = uuid4()
        result = BulkAssignResult(rule_id=rule_id, rule_name="VIP", assigned_count=42)
        assert result.rule_id == rule_id
        assert result.rule_name == "VIP"
        assert result.assigned_count == 42

    def test_zero_assigned(self):
        result = BulkAssignResult(rule_id=uuid4(), rule_name="", assigned_count=0)
        assert result.assigned_count == 0


# ─── SegmentRuleService (mocked) ─────────────────────────────────────────────

class TestSegmentRuleService:
    def _make_rule(self, tenant_id: UUID) -> NamedSegmentRule:
        return NamedSegmentRule(
            tenant_id=tenant_id,
            name="Test Rule",
            r_min=4, r_max=5,
            f_min=4, f_max=5,
            m_min=4, m_max=5,
        )

    @pytest.fixture
    def mock_session(self):
        return AsyncMock()

    @pytest.fixture
    def tenant_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_create_sets_tenant(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rule = self._make_rule(tenant_id)

        with patch.object(svc._repo, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = rule
            result = await svc.create(rule)
            assert result.tenant_id == tenant_id
            mock_create.assert_called_once_with(rule)

    @pytest.mark.asyncio
    async def test_get_delegates_to_repo(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rule_id = uuid4()
        rule = self._make_rule(tenant_id)

        with patch.object(svc._repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = rule
            result = await svc.get(rule_id)
            assert result == rule
            mock_get.assert_called_once_with(rule_id)

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)

        with patch.object(svc._repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await svc.get(uuid4())
            assert result is None

    @pytest.mark.asyncio
    async def test_list_rules_delegates_to_repo(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rules = [self._make_rule(tenant_id), self._make_rule(tenant_id)]

        with patch.object(svc._repo, "list_by_tenant", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = rules
            result = await svc.list_rules()
            assert result == rules

    @pytest.mark.asyncio
    async def test_delete_delegates_to_repo(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rule_id = uuid4()

        with patch.object(svc._repo, "delete", new_callable=AsyncMock) as mock_del:
            mock_del.return_value = True
            result = await svc.delete(rule_id)
            assert result is True
            mock_del.assert_called_once_with(rule_id)

    @pytest.mark.asyncio
    async def test_preview_returns_empty_when_rule_not_found(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rule_id = uuid4()

        with patch.object(svc._repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await svc.preview(rule_id)
            assert result.matching_count == 0
            assert result.sample_contact_ids == []

    @pytest.mark.asyncio
    async def test_bulk_assign_returns_empty_when_rule_not_found(self, mock_session, tenant_id):
        from src.modules.segmentation.application.segment_rule_service import SegmentRuleService
        svc = SegmentRuleService(mock_session, tenant_id)
        rule_id = uuid4()

        with patch.object(svc._repo, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            result = await svc.bulk_assign(rule_id)
            assert result.assigned_count == 0
            assert result.rule_name == ""

