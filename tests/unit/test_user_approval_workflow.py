"""
Unit tests for Phase 34: User Approval Workflow (Camunda BPMS)

Tests for:
- UserApprovalWorkflowService (register/approve/reject with Camunda & fallback)
- External task workers (notify, activate, reject, remind)
- TenantUserModel approval_process_id column
- Migration file and revision chain
- Worker registration for 9 topics
"""

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
    ExternalTask,
    HumanTask,
    ProcessInstance,
)
from src.infrastructure.camunda.config import CamundaSettings


# ─── UserApprovalWorkflowService ─────────────────────────────────────────────


class TestUserApprovalOnRegistered:
    """Tests for on_user_registered."""

    def _make_service(self, enabled: bool = True):
        from src.modules.auth.application.user_approval_service import (
            UserApprovalWorkflowService,
        )
        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        return UserApprovalWorkflowService(camunda_client=client), client

    @pytest.mark.asyncio
    async def test_starts_process_when_enabled(self):
        svc, client = self._make_service(enabled=True)
        instance = ProcessInstance({"id": "proc-abc", "businessKey": "user-1"})
        client.start_process.return_value = instance

        uid = uuid4()
        tid = uuid4()
        result = await svc.on_user_registered(uid, tid, "testuser", "test@test.com")

        assert result == "proc-abc"
        client.start_process.assert_called_once()
        call_kwargs = client.start_process.call_args[1]
        assert call_kwargs["process_key"] == "user_approval"
        assert call_kwargs["business_key"] == str(uid)
        assert "username" in call_kwargs["variables"]

    @pytest.mark.asyncio
    async def test_returns_none_when_disabled(self):
        svc, client = self._make_service(enabled=False)

        result = await svc.on_user_registered(uuid4(), uuid4(), "user", "e@e.com")

        assert result is None
        client.start_process.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_on_connection_error(self):
        svc, client = self._make_service(enabled=True)
        client.start_process.side_effect = CamundaConnectionError("Refused")

        result = await svc.on_user_registered(uuid4(), uuid4(), "user", "e@e.com")

        assert result is None


class TestUserApprovalOnApproved:
    """Tests for on_user_approved."""

    def _make_service(self, enabled: bool = True):
        from src.modules.auth.application.user_approval_service import (
            UserApprovalWorkflowService,
        )
        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        return UserApprovalWorkflowService(camunda_client=client), client

    @pytest.mark.asyncio
    async def test_completes_camunda_task(self):
        svc, client = self._make_service(enabled=True)
        task = HumanTask({
            "id": "ht-1",
            "name": "Review",
            "taskDefinitionKey": "admin_review",
        })
        client.list_tasks.return_value = [task]

        result = await svc.on_user_approved(uuid4(), uuid4(), "proc-abc")

        assert result is True
        client.complete_task.assert_called_once()
        call_kwargs = client.complete_task.call_args[1]
        assert call_kwargs["variables"]["approved"] is True

    @pytest.mark.asyncio
    async def test_returns_false_without_process_id(self):
        svc, client = self._make_service(enabled=True)

        result = await svc.on_user_approved(uuid4(), uuid4(), None)

        assert result is False
        client.list_tasks.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_when_disabled(self):
        svc, client = self._make_service(enabled=False)

        result = await svc.on_user_approved(uuid4(), uuid4(), "proc-abc")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_no_task_found(self):
        svc, client = self._make_service(enabled=True)
        client.list_tasks.return_value = []

        result = await svc.on_user_approved(uuid4(), uuid4(), "proc-abc")

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_camunda_error(self):
        svc, client = self._make_service(enabled=True)
        client.list_tasks.side_effect = CamundaError("Error")

        result = await svc.on_user_approved(uuid4(), uuid4(), "proc-abc")

        assert result is False


class TestUserApprovalOnRejected:
    """Tests for on_user_rejected."""

    def _make_service(self, enabled: bool = True):
        from src.modules.auth.application.user_approval_service import (
            UserApprovalWorkflowService,
        )
        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        return UserApprovalWorkflowService(camunda_client=client), client

    @pytest.mark.asyncio
    async def test_completes_rejection_task(self):
        svc, client = self._make_service(enabled=True)
        task = HumanTask({
            "id": "ht-2",
            "name": "Review",
            "taskDefinitionKey": "admin_review",
        })
        client.list_tasks.return_value = [task]

        result = await svc.on_user_rejected(uuid4(), uuid4(), "proc-abc", "No valid ID")

        assert result is True
        call_kwargs = client.complete_task.call_args[1]
        assert call_kwargs["variables"]["approved"] is False
        assert call_kwargs["variables"]["rejection_reason"] == "No valid ID"

    @pytest.mark.asyncio
    async def test_returns_false_without_process_id(self):
        svc, client = self._make_service(enabled=True)

        result = await svc.on_user_rejected(uuid4(), uuid4(), None)

        assert result is False


# ─── External Task Workers ───────────────────────────────────────────────────


class TestNotifyPendingUserWorker:
    """Tests for handle_notify_pending_user worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.user_approval import (
            handle_notify_pending_user,
        )
        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_notify_pending_user(task, AsyncMock())
        assert result == {"notification_sent": False}


class TestActivateApprovedUserWorker:
    """Tests for handle_activate_approved_user worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.user_approval import (
            handle_activate_approved_user,
        )
        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_activate_approved_user(task, AsyncMock())
        assert result == {"activated": False}


class TestNotifyUserApprovedWorker:
    """Tests for handle_notify_user_approved worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.user_approval import (
            handle_notify_user_approved,
        )
        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_notify_user_approved(task, AsyncMock())
        assert result == {"notified": False}


class TestNotifyUserRejectedWorker:
    """Tests for handle_notify_user_rejected worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.user_approval import (
            handle_notify_user_rejected,
        )
        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_notify_user_rejected(task, AsyncMock())
        assert result == {"notified": False}


class TestSendApprovalReminderWorker:
    """Tests for handle_send_approval_reminder worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.user_approval import (
            handle_send_approval_reminder,
        )
        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_send_approval_reminder(task, AsyncMock())
        assert result == {"reminder_sent": False}


# ─── TenantUserModel ─────────────────────────────────────────────────────────


class TestTenantUserModelApprovalField:
    """Tests for approval_process_id column on TenantUserModel."""

    def test_model_has_approval_process_id_column(self):
        from src.infrastructure.database.models.tenants import TenantUserModel
        columns = {c.name for c in TenantUserModel.__table__.columns}
        assert "approval_process_id" in columns

    def test_column_is_nullable(self):
        from src.infrastructure.database.models.tenants import TenantUserModel
        col = TenantUserModel.__table__.c.approval_process_id
        assert col.nullable is True


# ─── Worker Registration (all 9 topics) ──────────────────────────────────────


class TestAllWorkerTopics:
    """Verify all 9 worker handlers can be registered."""

    def test_register_all_9_topics(self):
        from src.infrastructure.camunda.workers import (
            ExternalTaskWorkerRunner,
            handle_prepare_recipients,
            handle_send_campaign_sms,
            handle_track_delivery,
            handle_measure_results,
            handle_notify_pending_user,
            handle_activate_approved_user,
            handle_notify_user_approved,
            handle_notify_user_rejected,
            handle_send_approval_reminder,
        )

        runner = ExternalTaskWorkerRunner(settings=CamundaSettings(enabled=True))
        # Campaign
        runner.register("prepare-campaign-recipients", handle_prepare_recipients)
        runner.register("send-campaign-sms", handle_send_campaign_sms)
        runner.register("track-sms-delivery", handle_track_delivery)
        runner.register("measure-campaign-results", handle_measure_results)
        # User approval
        runner.register("notify-pending-user", handle_notify_pending_user)
        runner.register("activate-approved-user", handle_activate_approved_user)
        runner.register("notify-user-approved", handle_notify_user_approved)
        runner.register("notify-user-rejected", handle_notify_user_rejected)
        runner.register("send-approval-reminder", handle_send_approval_reminder)

        assert len(runner._handlers) == 9


# ─── BPMN Validation ─────────────────────────────────────────────────────────


class TestUserApprovalBPMN:
    """Validate user_approval.bpmn content."""

    def test_bpmn_has_required_topics(self):
        from pathlib import Path
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        content = (bpmn_dir / "user_approval.bpmn").read_text()
        assert 'id="user_approval"' in content
        assert 'camunda:topic="notify-pending-user"' in content
        assert 'camunda:topic="activate-approved-user"' in content
        assert 'camunda:topic="notify-user-approved"' in content
        assert 'camunda:topic="notify-user-rejected"' in content
        assert 'camunda:topic="send-approval-reminder"' in content

    def test_bpmn_has_human_task(self):
        from pathlib import Path
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        content = (bpmn_dir / "user_approval.bpmn").read_text()
        assert 'id="admin_review"' in content
        assert "userTask" in content
        assert "candidateGroups" in content

    def test_bpmn_has_timer(self):
        from pathlib import Path
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        content = (bpmn_dir / "user_approval.bpmn").read_text()
        assert "PT48H" in content
        assert "boundaryEvent" in content


# ─── Migration ────────────────────────────────────────────────────────────────


class TestPhase34Migration:
    """Tests for Phase 34 migration."""

    def test_migration_file_exists(self):
        from pathlib import Path
        path = (
            Path(__file__).parent.parent.parent
            / "alembic" / "versions"
            / "c2d3e4f5a6b7_phase_34_user_approval_process_id.py"
        )
        assert path.exists()

    def test_migration_revision_chain(self):
        import importlib.util
        from pathlib import Path
        path = (
            Path(__file__).parent.parent.parent
            / "alembic" / "versions"
            / "c2d3e4f5a6b7_phase_34_user_approval_process_id.py"
        )
        spec = importlib.util.spec_from_file_location("migration", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.revision == "c2d3e4f5a6b7"
        assert mod.down_revision == "b1c2d3e4f5a6"

