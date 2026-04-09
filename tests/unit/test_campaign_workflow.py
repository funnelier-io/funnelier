"""
Unit tests for Phase 33: Campaign Workflow Migration to Camunda

Tests for:
- CampaignWorkflowService (start/pause/resume/cancel with Camunda & fallback)
- CamundaClient suspend/activate methods
- External task worker handlers (prepare, send, track, measure)
- CampaignResponse schema (process_instance_id field)
- CampaignModel (process_instance_id column)
"""

import json
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
    ProcessInstance,
)
from src.infrastructure.camunda.config import CamundaSettings


# ─── CampaignWorkflowService ─────────────────────────────────────────────────


class TestCampaignWorkflowServiceStart:
    """Tests for CampaignWorkflowService.start_campaign."""

    def _make_service(self, enabled: bool = True):
        from src.modules.campaigns.application.campaign_workflow_service import (
            CampaignWorkflowService,
        )

        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        repo = AsyncMock()
        return CampaignWorkflowService(camunda_client=client, repo=repo), client, repo

    def _make_campaign_model(self, **overrides):
        defaults = {
            "id": uuid4(),
            "tenant_id": uuid4(),
            "name": "Test Campaign",
            "campaign_type": "sms",
            "status": "draft",
            "process_instance_id": None,
        }
        defaults.update(overrides)
        model = MagicMock()
        for k, v in defaults.items():
            setattr(model, k, v)
        return model

    @pytest.mark.asyncio
    async def test_start_with_camunda_enabled(self):
        """When Camunda is enabled, start_process is called and process_instance_id saved."""
        svc, client, repo = self._make_service(enabled=True)
        model = self._make_campaign_model()
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        instance = ProcessInstance({"id": "proc-123", "businessKey": str(model.id)})
        client.start_process.return_value = instance

        result = await svc.start_campaign(model.id, model.tenant_id)

        client.start_process.assert_called_once()
        call_kwargs = client.start_process.call_args[1]
        assert call_kwargs["process_key"] == "campaign_lifecycle"
        assert call_kwargs["business_key"] == str(model.id)

        # Verify update_status was called with process_instance_id
        repo.update_status.assert_called_once()
        status_args = repo.update_status.call_args
        assert status_args[0][1] == "running"
        assert status_args[1]["process_instance_id"] == "proc-123"

    @pytest.mark.asyncio
    async def test_start_with_camunda_disabled(self):
        """When Camunda is disabled, falls back to direct status update."""
        svc, client, repo = self._make_service(enabled=False)
        model = self._make_campaign_model()
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        result = await svc.start_campaign(model.id, model.tenant_id)

        client.start_process.assert_not_called()
        repo.update_status.assert_called_once()
        status_args = repo.update_status.call_args
        assert status_args[0][1] == "running"
        # No process_instance_id in kwargs
        assert "process_instance_id" not in status_args[1]

    @pytest.mark.asyncio
    async def test_start_camunda_connection_error_fallback(self):
        """When Camunda raises CamundaConnectionError, falls back gracefully."""
        svc, client, repo = self._make_service(enabled=True)
        model = self._make_campaign_model()
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        client.start_process.side_effect = CamundaConnectionError("Connection refused")

        result = await svc.start_campaign(model.id, model.tenant_id)

        repo.update_status.assert_called_once()
        # Falls back: no process_instance_id
        assert "process_instance_id" not in repo.update_status.call_args[1]

    @pytest.mark.asyncio
    async def test_start_campaign_not_found(self):
        """Returns None when campaign doesn't exist."""
        svc, client, repo = self._make_service()
        repo.get_model.return_value = None

        result = await svc.start_campaign(uuid4(), uuid4())
        assert result is None


class TestCampaignWorkflowServicePause:
    """Tests for CampaignWorkflowService.pause_campaign."""

    def _make_service(self, enabled: bool = True):
        from src.modules.campaigns.application.campaign_workflow_service import (
            CampaignWorkflowService,
        )

        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        repo = AsyncMock()
        return CampaignWorkflowService(camunda_client=client, repo=repo), client, repo

    @pytest.mark.asyncio
    async def test_pause_with_camunda(self):
        """Suspend process instance when Camunda enabled and process_instance_id exists."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        await svc.pause_campaign(uuid4())

        client.suspend_process_instance.assert_called_once_with("proc-123")
        repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_without_process_instance(self):
        """No Camunda call when process_instance_id is None."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = None
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        await svc.pause_campaign(uuid4())

        client.suspend_process_instance.assert_not_called()
        repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_pause_camunda_error_fallback(self):
        """Falls back to DB update when Camunda suspend fails."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        client.suspend_process_instance.side_effect = CamundaError("Error")

        await svc.pause_campaign(uuid4())

        repo.update_status.assert_called_once()


class TestCampaignWorkflowServiceResume:
    """Tests for CampaignWorkflowService.resume_campaign."""

    def _make_service(self, enabled: bool = True):
        from src.modules.campaigns.application.campaign_workflow_service import (
            CampaignWorkflowService,
        )

        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        repo = AsyncMock()
        return CampaignWorkflowService(camunda_client=client, repo=repo), client, repo

    @pytest.mark.asyncio
    async def test_resume_with_camunda(self):
        """Activate process instance when Camunda enabled."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        await svc.resume_campaign(uuid4())

        client.activate_process_instance.assert_called_once_with("proc-123")
        repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_resume_disabled_fallback(self):
        """Direct status update when Camunda disabled."""
        svc, client, repo = self._make_service(enabled=False)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        await svc.resume_campaign(uuid4())

        client.activate_process_instance.assert_not_called()
        repo.update_status.assert_called_once()


class TestCampaignWorkflowServiceCancel:
    """Tests for CampaignWorkflowService.cancel_campaign."""

    def _make_service(self, enabled: bool = True):
        from src.modules.campaigns.application.campaign_workflow_service import (
            CampaignWorkflowService,
        )

        client = AsyncMock(spec=CamundaClient)
        client.enabled = enabled
        repo = AsyncMock()
        return CampaignWorkflowService(camunda_client=client, repo=repo), client, repo

    @pytest.mark.asyncio
    async def test_cancel_with_camunda(self):
        """Delete process instance when cancelling via Camunda."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        campaign_id = uuid4()
        await svc.cancel_campaign(campaign_id)

        client.delete_process_instance.assert_called_once()
        repo.update_status.assert_called_once()
        assert repo.update_status.call_args[0][1] == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_connection_error_fallback(self):
        """Falls back to DB update when delete fails."""
        svc, client, repo = self._make_service(enabled=True)
        model = MagicMock()
        model.process_instance_id = "proc-123"
        repo.get_model.return_value = model
        repo.update_status.return_value = model

        client.delete_process_instance.side_effect = CamundaConnectionError("Unreachable")

        await svc.cancel_campaign(uuid4())

        repo.update_status.assert_called_once()
        assert repo.update_status.call_args[0][1] == "cancelled"


# ─── CamundaClient suspend/activate ──────────────────────────────────────────


class TestCamundaClientSuspendActivate:
    """Tests for suspend_process_instance and activate_process_instance."""

    def _make_client(self) -> CamundaClient:
        settings = CamundaSettings(enabled=True)
        return CamundaClient(settings)

    @pytest.mark.asyncio
    async def test_suspend_process_instance(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        await client.suspend_process_instance("inst-1")

        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"
        assert "/process-instance/inst-1/suspended" in call_args[0][1]
        payload = call_args[1].get("json")
        assert payload == {"suspended": True}

    @pytest.mark.asyncio
    async def test_activate_process_instance(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        await client.activate_process_instance("inst-1")

        call_args = mock_http.request.call_args
        assert call_args[0][0] == "PUT"
        assert "/process-instance/inst-1/suspended" in call_args[0][1]
        payload = call_args[1].get("json")
        assert payload == {"suspended": False}


# ─── External Task Workers ───────────────────────────────────────────────────


class TestHandlePrepareRecipients:
    """Tests for handle_prepare_recipients worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.campaign_prepare import (
            handle_prepare_recipients,
        )

        task = ExternalTask({"id": "t-1", "variables": {}})
        client = AsyncMock()
        result = await handle_prepare_recipients(task, client)
        assert result == {"recipient_count": 0}

    @pytest.mark.asyncio
    async def test_campaign_not_found(self):
        from src.infrastructure.camunda.workers.campaign_prepare import (
            handle_prepare_recipients,
        )

        campaign_id = str(uuid4())
        tenant_id = str(uuid4())
        task = ExternalTask({
            "id": "t-1",
            "variables": {
                "campaign_id": {"value": campaign_id, "type": "String"},
                "tenant_id": {"value": tenant_id, "type": "String"},
            },
        })

        # Mock DB session with no campaign found
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "src.infrastructure.camunda.workers.campaign_prepare.get_session_factory",
            return_value=mock_factory,
        ):
            result = await handle_prepare_recipients(task, AsyncMock())

        assert result == {"recipient_count": 0}


class TestHandleSendCampaignSms:
    """Tests for handle_send_campaign_sms worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.campaign_send import (
            handle_send_campaign_sms,
        )

        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_send_campaign_sms(task, AsyncMock())
        assert result == {"sent_count": 0, "failed_count": 0}

    @pytest.mark.asyncio
    async def test_campaign_not_found(self):
        from src.infrastructure.camunda.workers.campaign_send import (
            handle_send_campaign_sms,
        )

        task = ExternalTask({
            "id": "t-1",
            "variables": {
                "campaign_id": {"value": str(uuid4()), "type": "String"},
                "tenant_id": {"value": str(uuid4()), "type": "String"},
            },
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch(
            "src.infrastructure.camunda.workers.campaign_send.get_session_factory",
            return_value=mock_factory,
        ):
            result = await handle_send_campaign_sms(task, AsyncMock())

        assert result == {"sent_count": 0, "failed_count": 0}


class TestHandleTrackDelivery:
    """Tests for handle_track_delivery worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.campaign_track import (
            handle_track_delivery,
        )

        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_track_delivery(task, AsyncMock())
        assert result == {
            "delivered_count": 0,
            "delivery_failed_count": 0,
            "delivery_rate": 0.0,
        }


class TestHandleMeasureResults:
    """Tests for handle_measure_results worker."""

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.campaign_measure import (
            handle_measure_results,
        )

        task = ExternalTask({"id": "t-1", "variables": {}})
        result = await handle_measure_results(task, AsyncMock())
        assert result == {"campaign_status": "error"}


# ─── Schema / Model ──────────────────────────────────────────────────────────


class TestCampaignResponseSchema:
    """Tests for CampaignResponse schema with process_instance_id."""

    def test_schema_includes_process_instance_id(self):
        from src.modules.campaigns.api.schemas import CampaignResponse

        fields = CampaignResponse.model_fields
        assert "process_instance_id" in fields

    def test_schema_process_instance_id_optional(self):
        from src.modules.campaigns.api.schemas import CampaignResponse

        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "name": "Test",
            "campaign_type": "sms",
            "status": "draft",
            "created_at": datetime.utcnow().isoformat(),
        }
        resp = CampaignResponse(**data)
        assert resp.process_instance_id is None

    def test_schema_process_instance_id_set(self):
        from src.modules.campaigns.api.schemas import CampaignResponse

        data = {
            "id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "name": "Test",
            "campaign_type": "sms",
            "status": "running",
            "process_instance_id": "proc-abc",
            "created_at": datetime.utcnow().isoformat(),
        }
        resp = CampaignResponse(**data)
        assert resp.process_instance_id == "proc-abc"


class TestCampaignModel:
    """Tests for CampaignModel process_instance_id column."""

    def test_model_has_process_instance_id_column(self):
        from src.infrastructure.database.models.campaigns import CampaignModel

        columns = {c.name for c in CampaignModel.__table__.columns}
        assert "process_instance_id" in columns

    def test_model_process_instance_id_nullable(self):
        from src.infrastructure.database.models.campaigns import CampaignModel

        col = CampaignModel.__table__.c.process_instance_id
        assert col.nullable is True

    def test_model_has_tenant_process_instance_index(self):
        from src.infrastructure.database.models.campaigns import CampaignModel

        index_names = {idx.name for idx in CampaignModel.__table__.indexes}
        assert "ix_campaigns_tenant_process_instance" in index_names


class TestModelToResponse:
    """Tests for _model_to_response helper including process_instance_id."""

    def test_response_includes_process_instance_id(self):
        from src.modules.campaigns.api.routes import _model_to_response

        model = MagicMock()
        model.id = uuid4()
        model.tenant_id = uuid4()
        model.name = "Test"
        model.description = None
        model.campaign_type = "sms"
        model.template_id = None
        model.message_content = "Hello"
        model.targeting = {}
        model.schedule = None
        model.status = "running"
        model.process_instance_id = "proc-xyz"
        model.is_active = True
        model.total_recipients = 100
        model.total_sent = 50
        model.total_delivered = 45
        model.total_failed = 5
        model.total_calls_received = 10
        model.total_conversions = 3
        model.started_at = datetime.utcnow()
        model.completed_at = None
        model.created_at = datetime.utcnow()
        model.updated_at = None
        model.metadata_ = {}

        resp = _model_to_response(model)
        assert resp.process_instance_id == "proc-xyz"

    def test_response_none_when_no_process_instance(self):
        from src.modules.campaigns.api.routes import _model_to_response

        model = MagicMock()
        model.id = uuid4()
        model.tenant_id = uuid4()
        model.name = "Test"
        model.description = None
        model.campaign_type = "sms"
        model.template_id = None
        model.message_content = "Hello"
        model.targeting = {}
        model.schedule = None
        model.status = "draft"
        model.process_instance_id = None
        model.is_active = True
        model.total_recipients = 0
        model.total_sent = 0
        model.total_delivered = 0
        model.total_failed = 0
        model.total_calls_received = 0
        model.total_conversions = 0
        model.started_at = None
        model.completed_at = None
        model.created_at = datetime.utcnow()
        model.updated_at = None
        model.metadata_ = {}

        resp = _model_to_response(model)
        assert resp.process_instance_id is None


# ─── Worker Registration ─────────────────────────────────────────────────────


class TestWorkerRegistration:
    """Tests for worker __init__ exports."""

    def test_all_handlers_exported(self):
        from src.infrastructure.camunda import workers

        assert hasattr(workers, "handle_prepare_recipients")
        assert hasattr(workers, "handle_send_campaign_sms")
        assert hasattr(workers, "handle_track_delivery")
        assert hasattr(workers, "handle_measure_results")
        assert hasattr(workers, "ExternalTaskWorkerRunner")

    def test_register_campaign_topics(self):
        from src.infrastructure.camunda.workers import (
            ExternalTaskWorkerRunner,
            handle_prepare_recipients,
            handle_send_campaign_sms,
            handle_track_delivery,
            handle_measure_results,
        )

        runner = ExternalTaskWorkerRunner(settings=CamundaSettings(enabled=True))
        runner.register("prepare-campaign-recipients", handle_prepare_recipients)
        runner.register("send-campaign-sms", handle_send_campaign_sms)
        runner.register("track-sms-delivery", handle_track_delivery)
        runner.register("measure-campaign-results", handle_measure_results)

        assert len(runner._handlers) == 4
        assert "prepare-campaign-recipients" in runner._handlers
        assert "send-campaign-sms" in runner._handlers
        assert "track-sms-delivery" in runner._handlers
        assert "measure-campaign-results" in runner._handlers


# ─── Migration ────────────────────────────────────────────────────────────────


class TestMigration:
    """Tests that the migration file exists and has correct metadata."""

    def test_migration_file_exists(self):
        from pathlib import Path

        migration_path = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "b1c2d3e4f5a6_phase_33_campaign_process_instance_id.py"
        )
        assert migration_path.exists(), f"Migration file not found: {migration_path}"

    def test_migration_revision_chain(self):
        import importlib.util
        from pathlib import Path

        migration_path = (
            Path(__file__).parent.parent.parent
            / "alembic"
            / "versions"
            / "b1c2d3e4f5a6_phase_33_campaign_process_instance_id.py"
        )
        spec = importlib.util.spec_from_file_location("migration", migration_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.revision == "b1c2d3e4f5a6"
        assert mod.down_revision == "a30b1c2d3e4f"

