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
from uuid import UUID

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
from src.infrastructure.camunda.deployment import deploy_all_bpmn, generate_funnel_bpmn
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
        assert "<bpmn:receiveTask" in xml

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



