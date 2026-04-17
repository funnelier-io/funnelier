"""
Unit tests for Camunda BPMS Infrastructure (Phase 32)

Tests for:
- CamundaSettings configuration
- CamundaClient REST API methods (mocked httpx)
- Data classes (ProcessInstance, ProcessDefinition, ExternalTask, HumanTask, Deployment)
- Variable conversion (_to_camunda_variable)
- BPMN deployment manager (deploy_all_bpmn, generate_funnel_bpmn)
- ExternalTaskWorkerRunner (register, poll, complete/fail)
- Singleton lifecycle (get_camunda_client, close_camunda_client)
- Process routes helper (_get_client when disabled)
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from src.infrastructure.camunda.config import CamundaSettings
from src.infrastructure.camunda.client import (
    CamundaClient,
    CamundaConnectionError,
    CamundaError,
    CamundaProcessNotFoundError,
    Deployment,
    ExternalTask,
    HumanTask,
    ProcessDefinition,
    ProcessInstance,
    _to_camunda_variable,
    get_camunda_client,
    close_camunda_client,
)
from src.infrastructure.camunda.deployment import deploy_all_bpmn, generate_funnel_bpmn, deploy_tenant_funnel
from src.infrastructure.camunda.workers.base import ExternalTaskWorkerRunner


# ─── CamundaSettings ─────────────────────────────────────────────────────────


class TestCamundaSettings:
    """Tests for CamundaSettings pydantic model."""

    def test_defaults(self):
        settings = CamundaSettings()
        assert settings.base_url == "http://localhost:8085/engine-rest"
        assert settings.engine_name == "default"
        assert settings.enabled is False
        assert settings.connect_timeout == 5.0
        assert settings.read_timeout == 30.0
        assert settings.worker_id == "funnelier-worker"
        assert settings.worker_max_tasks == 10
        assert settings.worker_lock_duration_ms == 30_000
        assert settings.task_max_retries == 3
        assert settings.auto_deploy is True

    def test_engine_url_property(self):
        settings = CamundaSettings(base_url="http://camunda:8080/engine-rest")
        assert settings.engine_url == "http://camunda:8080/engine-rest"

    def test_url_properties(self):
        settings = CamundaSettings()
        base = settings.engine_url
        assert settings.process_definition_url == f"{base}/process-definition"
        assert settings.process_instance_url == f"{base}/process-instance"
        assert settings.deployment_url == f"{base}/deployment"
        assert settings.external_task_url == f"{base}/external-task"
        assert settings.message_url == f"{base}/message"
        assert settings.task_url == f"{base}/task"


# ─── Data classes ─────────────────────────────────────────────────────────────


class TestDataClasses:
    """Tests for Camunda response data classes."""

    def test_process_instance(self):
        data = {
            "id": "proc-123",
            "definitionId": "def-456",
            "businessKey": "campaign-1",
            "tenantId": "t-1",
            "ended": False,
            "suspended": True,
        }
        pi = ProcessInstance(data)
        assert pi.id == "proc-123"
        assert pi.definition_id == "def-456"
        assert pi.business_key == "campaign-1"
        assert pi.tenant_id == "t-1"
        assert pi.ended is False
        assert pi.suspended is True
        assert "proc-123" in repr(pi)

    def test_process_instance_defaults(self):
        pi = ProcessInstance({})
        assert pi.id == ""
        assert pi.business_key is None
        assert pi.ended is False
        assert pi.suspended is False

    def test_process_definition(self):
        data = {
            "id": "campaign_lifecycle:1:abc",
            "key": "campaign_lifecycle",
            "name": "Campaign Lifecycle",
            "version": 3,
            "deploymentId": "dep-1",
            "suspended": False,
        }
        pd = ProcessDefinition(data)
        assert pd.key == "campaign_lifecycle"
        assert pd.version == 3
        assert pd.name == "Campaign Lifecycle"
        assert "campaign_lifecycle" in repr(pd)

    def test_deployment(self):
        data = {"id": "dep-1", "name": "funnelier", "deploymentTime": "2026-04-10T12:00:00Z"}
        d = Deployment(data)
        assert d.id == "dep-1"
        assert d.name == "funnelier"
        assert d.deployment_time == "2026-04-10T12:00:00Z"
        assert "dep-1" in repr(d)

    def test_external_task(self):
        data = {
            "id": "task-1",
            "workerId": "w-1",
            "topicName": "send-campaign-sms",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "campaign_lifecycle",
            "activityId": "send_sms_batch",
            "businessKey": "camp-123",
            "retries": 2,
            "priority": 5,
            "variables": {
                "campaign_id": {"value": "abc", "type": "String"},
                "recipient_count": {"value": 100, "type": "Long"},
            },
        }
        et = ExternalTask(data)
        assert et.id == "task-1"
        assert et.topic_name == "send-campaign-sms"
        assert et.get_variable("campaign_id") == "abc"
        assert et.get_variable("recipient_count") == 100
        assert et.get_variable("nonexistent") is None
        assert "send-campaign-sms" in repr(et)

    def test_human_task(self):
        data = {
            "id": "ht-1",
            "name": "Approve Campaign",
            "assignee": "admin",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "user_approval",
            "taskDefinitionKey": "admin_review",
            "created": "2026-04-10T12:00:00Z",
        }
        ht = HumanTask(data)
        assert ht.id == "ht-1"
        assert ht.name == "Approve Campaign"
        assert ht.assignee == "admin"
        assert ht.task_definition_key == "admin_review"
        assert "Approve Campaign" in repr(ht)


# ─── Variable Conversion ─────────────────────────────────────────────────────


class TestVariableConversion:
    """Tests for _to_camunda_variable helper."""

    def test_string(self):
        assert _to_camunda_variable("hello") == {"value": "hello", "type": "String"}

    def test_bool(self):
        assert _to_camunda_variable(True) == {"value": True, "type": "Boolean"}
        assert _to_camunda_variable(False) == {"value": False, "type": "Boolean"}

    def test_int(self):
        assert _to_camunda_variable(42) == {"value": 42, "type": "Long"}

    def test_float(self):
        assert _to_camunda_variable(3.14) == {"value": 3.14, "type": "Double"}

    def test_uuid(self):
        uid = UUID("12345678-1234-5678-1234-567812345678")
        result = _to_camunda_variable(uid)
        assert result == {"value": str(uid), "type": "String"}

    def test_list(self):
        result = _to_camunda_variable([1, 2, 3])
        assert result["type"] == "Json"
        assert json.loads(result["value"]) == [1, 2, 3]

    def test_dict(self):
        result = _to_camunda_variable({"key": "val"})
        assert result["type"] == "Json"
        assert json.loads(result["value"]) == {"key": "val"}

    def test_none(self):
        assert _to_camunda_variable(None) == {"value": None, "type": "Null"}

    def test_already_camunda_format(self):
        """Already-formatted variable should pass through."""
        var = {"value": "x", "type": "String"}
        assert _to_camunda_variable(var) == var

    def test_unknown_type_becomes_string(self):
        """Arbitrary objects become String via str()."""
        result = _to_camunda_variable(object)
        assert result["type"] == "String"


# ─── CamundaClient ───────────────────────────────────────────────────────────


class TestCamundaClient:
    """Tests for CamundaClient methods (httpx mocked)."""

    def _make_client(self, enabled: bool = True) -> CamundaClient:
        settings = CamundaSettings(enabled=enabled)
        return CamundaClient(settings)

    @pytest.mark.asyncio
    async def test_disabled_raises_on_request(self):
        """Disabled client raises CamundaError on _request() but check_health catches it."""
        client = self._make_client(enabled=False)
        assert client.enabled is False
        # check_health catches all exceptions and returns False
        result = await client.check_health()
        assert result is False
        # Direct API calls should raise
        with pytest.raises(CamundaError, match="disabled"):
            await client.get_engine_info()

    @pytest.mark.asyncio
    async def test_check_health_success(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = [{"name": "default"}]

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        result = await client.check_health()
        assert result is True

    @pytest.mark.asyncio
    async def test_check_health_failure(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = []

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        result = await client.check_health()
        assert result is False

    @pytest.mark.asyncio
    async def test_start_process(self):
        client = self._make_client()
        resp_data = {
            "id": "instance-1",
            "definitionId": "campaign_lifecycle:1:abc",
            "businessKey": "camp-1",
            "ended": False,
            "suspended": False,
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = resp_data

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        instance = await client.start_process(
            "campaign_lifecycle",
            business_key="camp-1",
            variables={"total_recipients": 100},
            tenant_id="tenant-1",
        )
        assert instance.id == "instance-1"
        assert instance.business_key == "camp-1"

        # Verify the request was made with correct payload
        call_args = mock_http.request.call_args
        assert call_args[0][0] == "POST"
        payload = call_args[1].get("json") or call_args[0][2] if len(call_args[0]) > 2 else call_args[1].get("json")
        assert payload["businessKey"] == "camp-1"
        assert "total_recipients" in payload["variables"]
        assert "tenant_id" in payload["variables"]

    @pytest.mark.asyncio
    async def test_404_raises_not_found(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"
        mock_response.headers = {"content-type": "text/plain"}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        with pytest.raises(CamundaProcessNotFoundError):
            await client.get_process_definition("nonexistent")

    @pytest.mark.asyncio
    async def test_500_raises_error(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_response.headers = {"content-type": "text/plain"}
        mock_response.json.side_effect = Exception("not json")

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        with pytest.raises(CamundaError, match="500"):
            await client.get_engine_info()

    @pytest.mark.asyncio
    async def test_connection_error(self):
        import httpx
        client = self._make_client()

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
        client._http = mock_http

        # check_health catches errors and returns False
        result = await client.check_health()
        assert result is False

        # Direct API calls should raise
        with pytest.raises(CamundaConnectionError, match="Cannot connect"):
            await client.get_engine_info()

    @pytest.mark.asyncio
    async def test_timeout_error(self):
        import httpx
        client = self._make_client()

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(side_effect=httpx.ReadTimeout("Timeout"))
        client._http = mock_http

        with pytest.raises(CamundaConnectionError, match="Timeout"):
            await client.get_engine_info()

    @pytest.mark.asyncio
    async def test_204_returns_none(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {"content-type": "text/plain"}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        result = await client.delete_process_instance("inst-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_correlate_message(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = [{"resultType": "ProcessDefinition"}]

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        result = await client.correlate_message(
            "sms_delivered",
            business_key="contact-phone",
            tenant_id="t-1",
            variables={"delivered_at": "2026-04-10"},
        )
        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_and_lock(self):
        client = self._make_client()
        resp_data = [
            {
                "id": "task-1",
                "topicName": "send-campaign-sms",
                "processInstanceId": "proc-1",
                "variables": {"campaign_id": {"value": "c-1", "type": "String"}},
            }
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = resp_data

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        tasks = await client.fetch_and_lock("send-campaign-sms")
        assert len(tasks) == 1
        assert tasks[0].topic_name == "send-campaign-sms"

    @pytest.mark.asyncio
    async def test_complete_external_task(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        await client.complete_external_task("task-1", variables={"sent_count": 100})

    @pytest.mark.asyncio
    async def test_fail_external_task(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        await client.fail_external_task("task-1", "SMS provider error", retries=2)

    @pytest.mark.asyncio
    async def test_bpmn_error_external_task(self):
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.headers = {}

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        await client.bpmn_error_external_task("task-1", "NO_RECIPIENTS", "Empty list")

    @pytest.mark.asyncio
    async def test_list_human_tasks(self):
        client = self._make_client()
        resp_data = [{"id": "ht-1", "name": "Approve", "assignee": "admin"}]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = resp_data

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        tasks = await client.list_tasks(assignee="admin")
        assert len(tasks) == 1
        assert tasks[0].name == "Approve"

    @pytest.mark.asyncio
    async def test_deploy_bpmn(self):
        client = self._make_client()
        resp_data = {"id": "dep-1", "name": "test", "deploymentTime": "2026-04-10"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = resp_data

        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.request = AsyncMock(return_value=mock_response)
        client._http = mock_http

        deployment = await client.deploy_bpmn("test", "<bpmn>...</bpmn>", "test.bpmn")
        assert deployment.id == "dep-1"
        assert deployment.name == "test"

    @pytest.mark.asyncio
    async def test_deploy_bpmn_file_not_found(self):
        client = self._make_client()
        with pytest.raises(CamundaError, match="not found"):
            await client.deploy_bpmn_file("/nonexistent/path.bpmn")

    @pytest.mark.asyncio
    async def test_close(self):
        client = self._make_client()
        mock_http = AsyncMock()
        mock_http.is_closed = False
        mock_http.aclose = AsyncMock()
        client._http = mock_http

        await client.close()
        mock_http.aclose.assert_called_once()
        assert client._http is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        client = self._make_client()
        await client.close()  # No error when no httpx client


# ─── Singleton ────────────────────────────────────────────────────────────────


class TestSingleton:
    """Tests for get_camunda_client / close_camunda_client."""

    @pytest.mark.asyncio
    async def test_get_and_close(self):
        import src.infrastructure.camunda.client as mod

        # Reset singleton
        mod._client = None

        client = get_camunda_client()
        assert client is not None
        assert isinstance(client, CamundaClient)

        # Same instance on second call
        client2 = get_camunda_client()
        assert client2 is client

        # Close resets
        await close_camunda_client()
        assert mod._client is None


# ─── BPMN Deployment ──────────────────────────────────────────────────────────


class TestBPMNDeployment:
    """Tests for deploy_all_bpmn and generate_funnel_bpmn."""

    @pytest.mark.asyncio
    async def test_deploy_disabled(self):
        client = CamundaClient(CamundaSettings(enabled=False))
        result = await deploy_all_bpmn(client)
        assert result == []

    def test_generate_funnel_bpmn_basic(self):
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
            {"name": "sms_delivered", "display_name": "SMS Delivered", "order": 2},
            {"name": "call_answered", "display_name": "Call Answered", "order": 3},
        ]
        xml = generate_funnel_bpmn(stages)
        assert '<?xml version="1.0"' in xml
        assert 'id="funnel_journey"' in xml
        assert "sms_sent" in xml
        assert "sms_delivered" in xml
        assert "call_answered" in xml
        assert 'isExecutable="true"' in xml
        assert "<bpmn:startEvent" in xml
        assert "<bpmn:endEvent" in xml
        # Each stage generates a message catch event + external task service task
        assert "<bpmn:intermediateCatchEvent" in xml
        assert '<camunda:topic="update-funnel-stage"' in xml or 'camunda:topic="update-funnel-stage"' in xml
        assert "<bpmn:serviceTask" in xml

    def test_generate_funnel_bpmn_custom_key(self):
        stages = [{"name": "step_a", "display_name": "Step A", "order": 1}]
        xml = generate_funnel_bpmn(stages, process_key="custom_funnel", process_name="Custom Flow")
        assert 'id="custom_funnel"' in xml
        assert 'name="Custom Flow"' in xml

    def test_generate_funnel_bpmn_sorts_by_order(self):
        stages = [
            {"name": "third", "display_name": "Third", "order": 3},
            {"name": "first", "display_name": "First", "order": 1},
            {"name": "second", "display_name": "Second", "order": 2},
        ]
        xml = generate_funnel_bpmn(stages)
        first_pos = xml.index("first")
        second_pos = xml.index("second")
        third_pos = xml.index("third")
        assert first_pos < second_pos < third_pos

    def test_bpmn_files_exist(self):
        """Verify all expected BPMN files are in the bpmn/ directory."""
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        assert bpmn_dir.exists(), f"BPMN directory not found: {bpmn_dir}"
        bpmn_files = [f.name for f in bpmn_dir.glob("*.bpmn")]
        assert "campaign_lifecycle.bpmn" in bpmn_files
        assert "user_approval.bpmn" in bpmn_files
        assert "funnel_journey.bpmn" in bpmn_files

    def test_campaign_lifecycle_bpmn_valid(self):
        """Verify campaign_lifecycle.bpmn has required elements."""
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        content = (bpmn_dir / "campaign_lifecycle.bpmn").read_text()
        assert 'id="campaign_lifecycle"' in content
        assert 'camunda:topic="prepare-campaign-recipients"' in content
        assert 'camunda:topic="send-campaign-sms"' in content
        assert 'camunda:topic="track-sms-delivery"' in content
        assert 'camunda:topic="measure-campaign-results"' in content


# ─── ExternalTaskWorkerRunner ─────────────────────────────────────────────────


class TestExternalTaskWorkerRunner:
    """Tests for the external task worker runner."""

    def test_register(self):
        runner = ExternalTaskWorkerRunner(
            settings=CamundaSettings(enabled=True),
        )
        handler = AsyncMock()
        runner.register("test-topic", handler)
        assert "test-topic" in runner._handlers

    @pytest.mark.asyncio
    async def test_run_when_disabled(self):
        runner = ExternalTaskWorkerRunner(
            settings=CamundaSettings(enabled=False),
        )
        runner.register("topic", AsyncMock())
        await runner.run()  # Should return immediately

    @pytest.mark.asyncio
    async def test_run_no_handlers(self):
        runner = ExternalTaskWorkerRunner(
            settings=CamundaSettings(enabled=True),
        )
        await runner.run()  # Should return with warning

    @pytest.mark.asyncio
    async def test_stop(self):
        runner = ExternalTaskWorkerRunner(
            settings=CamundaSettings(enabled=True),
        )
        runner._running = True
        runner.stop()
        assert runner._running is False

    @pytest.mark.asyncio
    async def test_poll_and_complete(self):
        """Test that worker fetches task, calls handler, and completes."""
        settings = CamundaSettings(enabled=True)
        mock_client = AsyncMock(spec=CamundaClient)
        mock_client.enabled = True
        mock_client.settings = settings

        task_data = {
            "id": "task-1",
            "topicName": "test-topic",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "test",
            "activityId": "act-1",
            "variables": {},
        }
        mock_task = ExternalTask(task_data)
        mock_client.fetch_and_lock = AsyncMock(return_value=[mock_task])
        mock_client.complete_external_task = AsyncMock()

        handler = AsyncMock(return_value={"result": "ok"})

        runner = ExternalTaskWorkerRunner(client=mock_client, settings=settings)
        runner.register("test-topic", handler)

        # Run one poll cycle
        await runner._poll_topic("test-topic", handler)

        handler.assert_called_once_with(mock_task, mock_client)
        mock_client.complete_external_task.assert_called_once_with(
            task_id="task-1", variables={"result": "ok"}
        )

    @pytest.mark.asyncio
    async def test_poll_handler_failure_reports_to_camunda(self):
        """Test that handler failure is reported back to Camunda."""
        settings = CamundaSettings(enabled=True)
        mock_client = AsyncMock(spec=CamundaClient)
        mock_client.enabled = True
        mock_client.settings = settings

        task_data = {
            "id": "task-2",
            "topicName": "test-topic",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "test",
            "activityId": "act-1",
            "retries": 3,
            "variables": {},
        }
        mock_task = ExternalTask(task_data)
        mock_client.fetch_and_lock = AsyncMock(return_value=[mock_task])
        mock_client.fail_external_task = AsyncMock()

        handler = AsyncMock(side_effect=RuntimeError("SMS provider down"))

        runner = ExternalTaskWorkerRunner(client=mock_client, settings=settings)
        runner.register("test-topic", handler)

        await runner._poll_topic("test-topic", handler)

        mock_client.fail_external_task.assert_called_once()
        call_kwargs = mock_client.fail_external_task.call_args[1]
        assert call_kwargs["task_id"] == "task-2"
        assert "SMS provider down" in call_kwargs["error_message"]
        assert call_kwargs["retries"] == 2  # 3 - 1


# ─── Exception Classes ────────────────────────────────────────────────────────


class TestExceptions:
    """Tests for Camunda exception hierarchy."""

    def test_camunda_error(self):
        e = CamundaError("test error", status_code=400, detail={"type": "bad"})
        assert str(e) == "test error"
        assert e.status_code == 400
        assert e.detail == {"type": "bad"}

    def test_connection_error_is_camunda_error(self):
        e = CamundaConnectionError("cannot connect")
        assert isinstance(e, CamundaError)

    def test_not_found_error_is_camunda_error(self):
        e = CamundaProcessNotFoundError("not found", status_code=404)
        assert isinstance(e, CamundaError)
        assert e.status_code == 404


# ─── Phase 35: Enhanced BPMN Generation & Deployment ──────────────────────────


class TestEnhancedBPMNGeneration:
    """Tests for enhanced generate_funnel_bpmn with stale timeouts."""

    def test_bpmn_with_stale_timeouts(self):
        """Stale timeouts should add boundary timer events."""
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
            {"name": "call_answered", "display_name": "Call Answered", "order": 2},
        ]
        xml = generate_funnel_bpmn(
            stages,
            stale_timeouts={"sms_sent": "P14D", "call_answered": "P7D"},
        )
        assert "<bpmn:boundaryEvent" in xml
        assert "<bpmn:timeDuration>P14D</bpmn:timeDuration>" in xml
        assert "<bpmn:timeDuration>P7D</bpmn:timeDuration>" in xml
        assert 'camunda:topic="notify-stale-stage"' in xml
        assert 'cancelActivity="false"' in xml

    def test_bpmn_without_stale_timeouts(self):
        """No stale timeouts should not add boundary timer events."""
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
        ]
        xml = generate_funnel_bpmn(stages)
        assert "<bpmn:boundaryEvent" not in xml
        assert "notify-stale-stage" not in xml

    def test_bpmn_partial_stale_timeouts(self):
        """Only specified stages get boundary timers."""
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
            {"name": "call_answered", "display_name": "Call Answered", "order": 2},
            {"name": "invoice_issued", "display_name": "Invoice Issued", "order": 3},
        ]
        xml = generate_funnel_bpmn(
            stages,
            stale_timeouts={"call_answered": "P7D"},
        )
        assert "<bpmn:timeDuration>P7D</bpmn:timeDuration>" in xml
        # Only one timer, not three
        assert xml.count("<bpmn:boundaryEvent") == 1

    def test_bpmn_has_camunda_namespace(self):
        """Generated BPMN should include camunda namespace for external tasks."""
        stages = [{"name": "sms_sent", "display_name": "SMS Sent", "order": 1}]
        xml = generate_funnel_bpmn(stages)
        assert 'xmlns:camunda="http://camunda.org/schema/1.0/bpmn"' in xml

    def test_bpmn_has_external_task_service_tasks(self):
        """Each stage should have both a message catch and a service task."""
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
            {"name": "call_answered", "display_name": "Call Answered", "order": 2},
        ]
        xml = generate_funnel_bpmn(stages)
        # 2 stage service tasks + 1 lead_acquired service task = at least 3
        assert xml.count("update-funnel-stage") >= 3
        # 2 message catch events
        assert xml.count("<bpmn:intermediateCatchEvent") == 2
        assert xml.count("<bpmn:messageEventDefinition") == 2

    def test_bpmn_message_definitions(self):
        """Message definitions should be generated for each stage."""
        stages = [
            {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
            {"name": "sms_delivered", "display_name": "SMS Delivered", "order": 2},
        ]
        xml = generate_funnel_bpmn(stages)
        assert 'id="msg_sms_sent" name="sms_sent"' in xml
        assert 'id="msg_sms_delivered" name="sms_delivered"' in xml

    def test_bpmn_single_stage(self):
        """Single stage should still produce valid BPMN."""
        stages = [{"name": "payment", "display_name": "Payment", "order": 1}]
        xml = generate_funnel_bpmn(stages)
        assert "<bpmn:startEvent" in xml
        assert "<bpmn:endEvent" in xml
        assert 'id="msg_payment"' in xml


class TestDeployTenantFunnel:
    """Tests for deploy_tenant_funnel function."""

    @pytest.mark.asyncio
    async def test_deploy_disabled(self):
        """When Camunda is disabled, returns None."""
        from src.infrastructure.camunda.deployment import deploy_tenant_funnel as _deploy

        client = CamundaClient(CamundaSettings(enabled=False))
        result = await _deploy(
            client=client,
            tenant_id="00000000-0000-0000-0000-000000000001",
            stages=[{"name": "sms_sent", "display_name": "SMS Sent", "order": 1}],
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_deploy_success(self):
        """Successful deployment returns Deployment object."""
        from src.infrastructure.camunda.deployment import deploy_tenant_funnel as _deploy

        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        mock_deployment = Deployment({"id": "deploy-1", "name": "test"})
        client.deploy_bpmn = AsyncMock(return_value=mock_deployment)

        result = await _deploy(
            client=client,
            tenant_id="00000000-0000-0000-0000-000000000001",
            stages=[
                {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
                {"name": "call_answered", "display_name": "Call Answered", "order": 2},
            ],
            stale_timeouts={"sms_sent": "P14D"},
        )
        assert result is not None
        assert result.id == "deploy-1"
        client.deploy_bpmn.assert_called_once()

        # Check that the generated BPMN includes tenant-specific process key
        call_kwargs = client.deploy_bpmn.call_args[1]
        assert "00000000" in call_kwargs["name"]

    @pytest.mark.asyncio
    async def test_deploy_connection_error(self):
        """Connection error returns None gracefully."""
        from src.infrastructure.camunda.deployment import deploy_tenant_funnel as _deploy

        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.deploy_bpmn = AsyncMock(
            side_effect=CamundaConnectionError("unreachable")
        )

        result = await _deploy(
            client=client,
            tenant_id="00000000-0000-0000-0000-000000000001",
            stages=[{"name": "sms_sent", "display_name": "SMS Sent", "order": 1}],
        )
        assert result is None


class TestStaleStageWorker:
    """Tests for handle_notify_stale_stage external task worker."""

    def _make_task(self, variables: dict[str, Any]) -> ExternalTask:
        camunda_vars = {
            k: {"value": v, "type": "String"} for k, v in variables.items()
        }
        return ExternalTask({
            "id": "task-stale-1",
            "topicName": "notify-stale-stage",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "funnel_journey",
            "activityId": "notify_stale",
            "variables": camunda_vars,
        })

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        """Missing contact_id/tenant_id returns notification_sent=False."""
        from src.infrastructure.camunda.workers.stale_stage_notify import (
            handle_notify_stale_stage,
        )

        task = self._make_task({"phone_number": "09121234567"})
        client = AsyncMock(spec=CamundaClient)

        result = await handle_notify_stale_stage(task, client)
        assert result["notification_sent"] is False

    @pytest.mark.asyncio
    async def test_successful_notification(self):
        """Successful DB insert returns notification_sent=True."""
        from src.infrastructure.camunda.workers.stale_stage_notify import (
            handle_notify_stale_stage,
        )

        contact_id = str(uuid4())
        tenant_id = str(uuid4())

        task = self._make_task({
            "contact_id": contact_id,
            "tenant_id": tenant_id,
            "phone_number": "09121234567",
            "current_stage": "sms_sent",
            "contact_name": "تست",
        })
        client = AsyncMock(spec=CamundaClient)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.infrastructure.camunda.workers.stale_stage_notify.get_session_factory",
            return_value=mock_factory,
        ):
            result = await handle_notify_stale_stage(task, client)

        assert result["notification_sent"] is True
        assert "notified_at" in result
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_worker_importable(self):
        """Verify the stale stage worker is properly exported."""
        from src.infrastructure.camunda.workers import handle_notify_stale_stage
        assert handle_notify_stale_stage is not None
        assert callable(handle_notify_stale_stage)


class TestNewJourneySchemas:
    """Tests for the new journey API schemas added in Phase 35."""

    def test_deploy_tenant_funnel_request(self):
        from src.modules.analytics.api.journey_routes import DeployTenantFunnelRequest

        req = DeployTenantFunnelRequest(
            stages=[
                {"name": "sms_sent", "display_name": "SMS Sent", "order": 1},
                {"name": "call_answered", "display_name": "Call Answered", "order": 2},
            ],
            stale_timeouts={"sms_sent": "P14D"},
        )
        assert len(req.stages) == 2
        assert req.stale_timeouts["sms_sent"] == "P14D"

    def test_deploy_tenant_funnel_request_no_timeouts(self):
        from src.modules.analytics.api.journey_routes import DeployTenantFunnelRequest

        req = DeployTenantFunnelRequest(
            stages=[{"name": "step", "display_name": "Step", "order": 1}],
        )
        assert req.stale_timeouts == {}

    def test_deploy_tenant_funnel_response(self):
        from src.modules.analytics.api.journey_routes import DeployTenantFunnelResponse

        resp = DeployTenantFunnelResponse(
            deployment_id="deploy-1",
            process_key="funnel_journey_tenant_abc",
            stages_count=3,
            camunda_enabled=True,
        )
        assert resp.deployment_id == "deploy-1"
        assert resp.stages_count == 3

    def test_deploy_tenant_funnel_response_disabled(self):
        from src.modules.analytics.api.journey_routes import DeployTenantFunnelResponse

        resp = DeployTenantFunnelResponse(
            process_key="funnel_journey_tenant_abc",
            stages_count=2,
        )
        assert resp.deployment_id is None
        assert resp.camunda_enabled is False

    def test_journey_analytics_response(self):
        from src.modules.analytics.api.journey_routes import JourneyAnalyticsResponse

        resp = JourneyAnalyticsResponse(
            total_active=100,
            by_stage={"lead_acquired": 80, "sms_sent": 15, "payment_received": 5},
            stale_count=10,
            conversion_rate=5.0,
            camunda_enabled=False,
            source="database",
        )
        assert resp.total_active == 100
        assert resp.conversion_rate == 5.0
        assert resp.by_stage["lead_acquired"] == 80

    def test_journey_analytics_response_defaults(self):
        from src.modules.analytics.api.journey_routes import JourneyAnalyticsResponse

        resp = JourneyAnalyticsResponse()
        assert resp.total_active == 0
        assert resp.by_stage == {}
        assert resp.stale_count == 0
        assert resp.conversion_rate == 0.0
        assert resp.source == "database"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 36 tests: Advanced Process Features
# ═══════════════════════════════════════════════════════════════════════════


class TestERPSyncEscalationBPMN:
    """Tests for erp_sync_escalation.bpmn structure."""

    def test_bpmn_file_exists(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "erp_sync_escalation.bpmn"
        assert bpmn_path.exists(), f"Missing BPMN: {bpmn_path}"

    def test_bpmn_has_required_elements(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "erp_sync_escalation.bpmn"
        content = bpmn_path.read_text()
        assert 'id="erp_sync_escalation"' in content
        assert 'topic="erp-log-sync-failure"' in content
        assert 'topic="erp-retry-sync"' in content
        assert 'topic="erp-mark-resolved"' in content
        assert 'topic="erp-escalate-failure"' in content
        assert 'topic="erp-send-reminder"' in content

    def test_bpmn_has_retry_gateway(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "erp_sync_escalation.bpmn"
        content = bpmn_path.read_text()
        assert 'id="gw_retry"' in content
        assert "retry_count" in content
        assert "max_retries" in content

    def test_bpmn_has_timer_events(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "erp_sync_escalation.bpmn"
        content = bpmn_path.read_text()
        # 5 minute retry wait
        assert "PT5M" in content
        # 24h reminder cycle
        assert "PT24H" in content

    def test_bpmn_has_message_for_resolution(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "erp_sync_escalation.bpmn"
        content = bpmn_path.read_text()
        assert 'name="erp_sync_resolved"' in content


class TestCampaignCompensationBPMN:
    """Tests for enhanced campaign_lifecycle.bpmn with error boundary."""

    def test_bpmn_has_error_definition(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "campaign_lifecycle.bpmn"
        content = bpmn_path.read_text()
        assert 'errorCode="SMS_SEND_FAILED"' in content

    def test_bpmn_has_boundary_error_event(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "campaign_lifecycle.bpmn"
        content = bpmn_path.read_text()
        assert 'id="boundary_sms_error"' in content
        assert 'attachedToRef="send_sms_batch"' in content

    def test_bpmn_has_compensation_task(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "campaign_lifecycle.bpmn"
        content = bpmn_path.read_text()
        assert 'topic="compensate-sms-failure"' in content
        assert 'id="compensate_sms"' in content

    def test_bpmn_has_stale_delivery_timer(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "campaign_lifecycle.bpmn"
        content = bpmn_path.read_text()
        assert 'id="timer_stale_delivery"' in content
        assert "PT24H" in content

    def test_bpmn_has_compensated_end_event(self):
        bpmn_path = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn" / "campaign_lifecycle.bpmn"
        content = bpmn_path.read_text()
        assert 'id="end_compensated"' in content


class TestSMSCompensationWorker:
    """Tests for the SMS compensation external task worker."""

    def test_worker_importable(self):
        from src.infrastructure.camunda.workers.sms_compensation import handle_compensate_sms_failure
        assert callable(handle_compensate_sms_failure)

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        from src.infrastructure.camunda.workers.sms_compensation import handle_compensate_sms_failure

        task = MagicMock()
        task.id = "task-1"
        task.get_variable = MagicMock(return_value=None)

        client = MagicMock()
        result = await handle_compensate_sms_failure(task, client)
        assert result["compensated"] is False

    def test_worker_exported_in_init(self):
        from src.infrastructure.camunda.workers import handle_compensate_sms_failure
        assert callable(handle_compensate_sms_failure)


class TestERPEscalationWorkers:
    """Tests for ERP sync escalation external task workers."""

    def test_all_workers_importable(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import (
            handle_log_sync_failure,
            handle_retry_sync,
            handle_mark_resolved,
            handle_escalate_failure,
            handle_send_escalation_reminder,
        )
        assert callable(handle_log_sync_failure)
        assert callable(handle_retry_sync)
        assert callable(handle_mark_resolved)
        assert callable(handle_escalate_failure)
        assert callable(handle_send_escalation_reminder)

    @pytest.mark.asyncio
    async def test_log_failure_missing_tenant(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import handle_log_sync_failure

        task = MagicMock()
        task.id = "task-1"
        task.get_variable = MagicMock(return_value=None)

        client = MagicMock()
        result = await handle_log_sync_failure(task, client)
        assert result["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_retry_sync_missing_tenant(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import handle_retry_sync

        task = MagicMock()
        task.id = "task-2"
        task.get_variable = MagicMock(return_value=None)

        client = MagicMock()
        result = await handle_retry_sync(task, client)
        assert result["retry_success"] is False
        assert result["retry_count"] == 1

    @pytest.mark.asyncio
    async def test_mark_resolved(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import handle_mark_resolved

        task = MagicMock()
        task.id = "task-3"
        task.get_variable = MagicMock(side_effect=lambda k: {
            "tenant_id": str(uuid4()),
            "source_name": "mongodb_invoices",
        }.get(k))

        client = MagicMock()
        result = await handle_mark_resolved(task, client)
        assert result["resolution"] == "auto_retry"
        assert "resolved_at" in result

    @pytest.mark.asyncio
    async def test_escalate_failure_missing_tenant(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import handle_escalate_failure

        task = MagicMock()
        task.id = "task-4"
        task.get_variable = MagicMock(return_value=None)

        client = MagicMock()
        result = await handle_escalate_failure(task, client)
        assert result["escalated"] is False

    @pytest.mark.asyncio
    async def test_send_reminder_missing_tenant(self):
        from src.infrastructure.camunda.workers.erp_sync_escalation import handle_send_escalation_reminder

        task = MagicMock()
        task.id = "task-5"
        task.get_variable = MagicMock(return_value=None)

        client = MagicMock()
        result = await handle_send_escalation_reminder(task, client)
        assert result["reminder_sent"] is False

    def test_all_workers_exported_in_init(self):
        from src.infrastructure.camunda.workers import (
            handle_log_sync_failure,
            handle_retry_sync,
            handle_mark_resolved,
            handle_escalate_failure,
            handle_send_escalation_reminder,
        )
        assert callable(handle_log_sync_failure)
        assert callable(handle_send_escalation_reminder)


class TestProcessOverviewSchemas:
    """Tests for the process overview dashboard widget schemas."""

    def test_process_overview_response_defaults(self):
        from src.api.routes.processes import ProcessOverviewResponse

        resp = ProcessOverviewResponse()
        assert resp.camunda_enabled is False
        assert resp.healthy is False
        assert resp.process_types == []
        assert resp.total_active == 0
        assert resp.total_completed == 0
        assert resp.total_failed == 0
        assert resp.escalations_pending == 0
        assert resp.source == "database"

    def test_process_overview_response_with_data(self):
        from src.api.routes.processes import ProcessOverviewResponse

        resp = ProcessOverviewResponse(
            camunda_enabled=True,
            healthy=True,
            process_types=[
                {"type": "campaign_lifecycle", "display_name": "کمپین", "active": 3, "completed": 10, "failed": 1},
                {"type": "funnel_journey", "display_name": "قیف", "active": 100, "completed": 5, "failed": 0},
            ],
            total_active=103,
            total_completed=15,
            total_failed=1,
            escalations_pending=2,
            source="camunda+database",
        )
        assert resp.total_active == 103
        assert resp.escalations_pending == 2
        assert len(resp.process_types) == 2

    def test_start_escalation_request(self):
        from src.api.routes.processes import StartEscalationRequest

        req = StartEscalationRequest(
            source_name="mongodb_invoices",
            error_message="Connection refused",
            max_retries=5,
        )
        assert req.source_name == "mongodb_invoices"
        assert req.max_retries == 5

    def test_start_escalation_request_defaults(self):
        from src.api.routes.processes import StartEscalationRequest

        req = StartEscalationRequest(
            source_name="test",
            error_message="error",
        )
        assert req.max_retries == 3

    def test_start_escalation_response(self):
        from src.api.routes.processes import StartEscalationResponse

        resp = StartEscalationResponse(
            process_instance_id="inst-1",
            source_name="mongodb",
            camunda_enabled=True,
        )
        assert resp.process_instance_id == "inst-1"
        assert resp.fallback_used is False

    def test_start_escalation_response_fallback(self):
        from src.api.routes.processes import StartEscalationResponse

        resp = StartEscalationResponse(
            source_name="mongodb",
            camunda_enabled=False,
            fallback_used=True,
        )
        assert resp.process_instance_id is None
        assert resp.fallback_used is True


class TestPhase36WorkerRegistration:
    """Tests that all Phase 36 workers are properly registered."""

    def test_total_worker_count_in_init(self):
        from src.infrastructure.camunda import workers
        all_exported = workers.__all__
        # Should have: 1 runner + 4 campaign + 5 user approval + 2 funnel + 5 ERP + 1 SMS comp = 18
        assert len(all_exported) == 18

    def test_erp_workers_in_all(self):
        from src.infrastructure.camunda import workers
        assert "handle_log_sync_failure" in workers.__all__
        assert "handle_retry_sync" in workers.__all__
        assert "handle_mark_resolved" in workers.__all__
        assert "handle_escalate_failure" in workers.__all__
        assert "handle_send_escalation_reminder" in workers.__all__

    def test_sms_compensation_in_all(self):
        from src.infrastructure.camunda import workers
        assert "handle_compensate_sms_failure" in workers.__all__

    def test_bpmn_directory_has_4_files(self):
        bpmn_dir = Path(__file__).parent.parent.parent / "src" / "infrastructure" / "camunda" / "bpmn"
        bpmn_files = sorted(bpmn_dir.glob("*.bpmn"))
        assert len(bpmn_files) == 4
        names = [f.name for f in bpmn_files]
        assert "campaign_lifecycle.bpmn" in names
        assert "erp_sync_escalation.bpmn" in names
        assert "funnel_journey.bpmn" in names
        assert "user_approval.bpmn" in names

