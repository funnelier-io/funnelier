"""
Unit tests for Funnel Journey Orchestration (Phase 35)

Tests for:
- FunnelJourneyService (start_journey, correlate_event, get_journey_status,
  start_batch_journeys, _update_contact_stage)
- Funnel stage update worker (handle_update_funnel_stage)
- Journey API schemas
- FUNNEL_STAGES constant
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
    ProcessInstance,
)
from src.infrastructure.camunda.config import CamundaSettings
from src.modules.analytics.application.funnel_journey_service import (
    FUNNEL_STAGES,
    FunnelJourneyService,
)


# ─── Constants ────────────────────────────────────────────────────────────────


class TestFunnelStages:
    """Tests for the FUNNEL_STAGES constant."""

    def test_stages_are_ordered(self):
        assert FUNNEL_STAGES[0] == "lead_acquired"
        assert FUNNEL_STAGES[-1] == "payment_received"
        assert len(FUNNEL_STAGES) == 7

    def test_all_expected_stages(self):
        expected = [
            "lead_acquired",
            "sms_sent",
            "sms_delivered",
            "call_attempted",
            "call_answered",
            "invoice_issued",
            "payment_received",
        ]
        assert FUNNEL_STAGES == expected


# ─── FunnelJourneyService ─────────────────────────────────────────────────────


class TestFunnelJourneyServiceInit:
    """Tests for FunnelJourneyService construction."""

    def test_init_with_client(self):
        client = MagicMock(spec=CamundaClient)
        service = FunnelJourneyService(client)
        assert service._camunda is client


class TestStartJourney:
    """Tests for FunnelJourneyService.start_journey."""

    @pytest.mark.asyncio
    async def test_start_journey_disabled(self):
        """When Camunda is disabled, start_journey returns None."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = False
        service = FunnelJourneyService(client)

        result = await service.start_journey(
            contact_id=uuid4(),
            tenant_id=uuid4(),
            phone_number="09121234567",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_start_journey_success(self):
        """Start journey should return process instance ID."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True

        instance_data = {
            "id": "proc-journey-1",
            "definitionId": "funnel_journey:1:abc",
            "businessKey": "09121234567",
        }
        client.start_process = AsyncMock(return_value=ProcessInstance(instance_data))

        service = FunnelJourneyService(client)
        result = await service.start_journey(
            contact_id=uuid4(),
            tenant_id=uuid4(),
            phone_number="09121234567",
            contact_name="تست کاربر",
        )
        assert result == "proc-journey-1"

        # Verify the process was started with correct params
        client.start_process.assert_called_once()
        call_kwargs = client.start_process.call_args[1]
        assert call_kwargs["process_key"] == "funnel_journey"
        assert call_kwargs["business_key"] == "09121234567"
        assert "contact_id" in call_kwargs["variables"]
        assert "current_stage" in call_kwargs["variables"]
        assert call_kwargs["variables"]["current_stage"] == "lead_acquired"

    @pytest.mark.asyncio
    async def test_start_journey_connection_error(self):
        """Connection error should return None (graceful)."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.start_process = AsyncMock(
            side_effect=CamundaConnectionError("unreachable")
        )

        service = FunnelJourneyService(client)
        result = await service.start_journey(
            contact_id=uuid4(),
            tenant_id=uuid4(),
            phone_number="09121234567",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_start_journey_camunda_error(self):
        """Camunda error should return None (graceful)."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.start_process = AsyncMock(
            side_effect=CamundaError("Process not deployed")
        )

        service = FunnelJourneyService(client)
        result = await service.start_journey(
            contact_id=uuid4(),
            tenant_id=uuid4(),
            phone_number="09121234567",
        )
        assert result is None


class TestCorrelateEvent:
    """Tests for FunnelJourneyService.correlate_event."""

    @pytest.mark.asyncio
    async def test_unknown_event_returns_false(self):
        """Unknown event name should return False."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = True
        service = FunnelJourneyService(client)

        result = await service.correlate_event(
            event_name="unknown_event",
            phone_number="09121234567",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_lead_acquired_is_not_correlatable(self):
        """lead_acquired is a start event, not a message correlation."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = True
        service = FunnelJourneyService(client)

        result = await service.correlate_event(
            event_name="lead_acquired",
            phone_number="09121234567",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_correlate_disabled_without_session(self):
        """When disabled and no session, returns False."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = False
        service = FunnelJourneyService(client)

        result = await service.correlate_event(
            event_name="sms_sent",
            phone_number="09121234567",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_correlate_disabled_with_session_updates_db(self):
        """When disabled but session provided, falls back to DB update."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = False
        service = FunnelJourneyService(client)

        tenant_id = uuid4()
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service.correlate_event(
            event_name="sms_sent",
            phone_number="09121234567",
            tenant_id=tenant_id,
            session=mock_session,
        )
        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_correlate_success_with_camunda(self):
        """Successful correlation with Camunda enabled."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(return_value=None)

        service = FunnelJourneyService(client)
        tenant_id = uuid4()

        result = await service.correlate_event(
            event_name="call_answered",
            phone_number="09121234567",
            tenant_id=tenant_id,
        )
        assert result is True
        client.correlate_message.assert_called_once()

        # Verify message name and variables
        call_kwargs = client.correlate_message.call_args[1]
        assert call_kwargs["message_name"] == "call_answered"
        assert call_kwargs["business_key"] == "09121234567"
        assert "current_stage" in call_kwargs["variables"]
        assert call_kwargs["variables"]["current_stage"] == "call_answered"

    @pytest.mark.asyncio
    async def test_correlate_all_valid_events(self):
        """All events except lead_acquired should be correlatable."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(return_value=None)

        service = FunnelJourneyService(client)

        for event_name in FUNNEL_STAGES[1:]:
            result = await service.correlate_event(
                event_name=event_name,
                phone_number="09121234567",
            )
            assert result is True, f"Event {event_name} should correlate"

    @pytest.mark.asyncio
    async def test_correlate_connection_error_with_db_fallback(self):
        """Connection error returns True if DB was updated."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(
            side_effect=CamundaConnectionError("down")
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = FunnelJourneyService(client)
        result = await service.correlate_event(
            event_name="sms_delivered",
            phone_number="09121234567",
            tenant_id=uuid4(),
            session=mock_session,
        )
        # Should be True because DB was updated
        assert result is True

    @pytest.mark.asyncio
    async def test_correlate_connection_error_without_session(self):
        """Connection error without session returns False."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(
            side_effect=CamundaConnectionError("down")
        )

        service = FunnelJourneyService(client)
        result = await service.correlate_event(
            event_name="sms_sent",
            phone_number="09121234567",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_correlate_camunda_error_with_db_fallback(self):
        """Camunda error (e.g. no process) returns True if DB was updated."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(
            side_effect=CamundaError("no matching process instance")
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        service = FunnelJourneyService(client)
        result = await service.correlate_event(
            event_name="invoice_issued",
            phone_number="09121234567",
            tenant_id=uuid4(),
            session=mock_session,
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_correlate_with_extra_variables(self):
        """Extra variables should be passed to Camunda."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.correlate_message = AsyncMock(return_value=None)

        service = FunnelJourneyService(client)
        await service.correlate_event(
            event_name="payment_received",
            phone_number="09121234567",
            variables={"amount": 50000000, "invoice_id": "INV-001"},
        )

        call_kwargs = client.correlate_message.call_args[1]
        assert call_kwargs["variables"]["amount"] == 50000000
        assert call_kwargs["variables"]["invoice_id"] == "INV-001"


class TestUpdateContactStage:
    """Tests for FunnelJourneyService._update_contact_stage."""

    @pytest.mark.asyncio
    async def test_update_found(self):
        """Update should return True if contact was found."""
        client = MagicMock(spec=CamundaClient)
        service = FunnelJourneyService(client)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 1
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._update_contact_stage(
            session=mock_session,
            phone_number="09121234567",
            tenant_id=uuid4(),
            stage="call_answered",
        )
        assert result is True
        mock_session.execute.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_not_found(self):
        """Update should return False if contact was not found."""
        client = MagicMock(spec=CamundaClient)
        service = FunnelJourneyService(client)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await service._update_contact_stage(
            session=mock_session,
            phone_number="09999999999",
            tenant_id=uuid4(),
            stage="sms_sent",
        )
        assert result is False
        mock_session.flush.assert_not_called()


class TestGetJourneyStatus:
    """Tests for FunnelJourneyService.get_journey_status."""

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """When Camunda is disabled, returns None."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = False
        service = FunnelJourneyService(client)

        result = await service.get_journey_status("09121234567")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_active_instance(self):
        """When no active process instances, returns None."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.list_process_instances = AsyncMock(return_value=[])

        service = FunnelJourneyService(client)
        result = await service.get_journey_status("09121234567")
        assert result is None

    @pytest.mark.asyncio
    async def test_active_instance_found(self):
        """When process instance found, returns status dict."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True

        instance_data = {
            "id": "proc-1",
            "definitionId": "funnel_journey:1:abc",
            "businessKey": "09121234567",
        }
        client.list_process_instances = AsyncMock(
            return_value=[ProcessInstance(instance_data)]
        )
        client.get_process_variables = AsyncMock(
            return_value={
                "current_stage": "call_answered",
                "journey_started_at": "2026-04-10T10:00:00",
                "contact_id": "c-1",
                "sms_sent_at": "2026-04-10T10:05:00",
                "call_answered_at": "2026-04-10T11:00:00",
            }
        )

        service = FunnelJourneyService(client)
        result = await service.get_journey_status("09121234567")

        assert result is not None
        assert result["process_instance_id"] == "proc-1"
        assert result["current_stage"] == "call_answered"
        assert result["started_at"] == "2026-04-10T10:00:00"
        assert result["contact_id"] == "c-1"
        # Timestamp fields
        assert "sms_sent_at" in result
        assert "call_answered_at" in result

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self):
        """Connection error gracefully returns None."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.list_process_instances = AsyncMock(
            side_effect=CamundaConnectionError("unreachable")
        )

        service = FunnelJourneyService(client)
        result = await service.get_journey_status("09121234567")
        assert result is None

    @pytest.mark.asyncio
    async def test_camunda_error_returns_none(self):
        """Camunda API error gracefully returns None."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True
        client.list_process_instances = AsyncMock(
            side_effect=CamundaError("internal error")
        )

        service = FunnelJourneyService(client)
        result = await service.get_journey_status("09121234567")
        assert result is None


class TestStartBatchJourneys:
    """Tests for FunnelJourneyService.start_batch_journeys."""

    @pytest.mark.asyncio
    async def test_batch_disabled(self):
        """When disabled, returns 0."""
        client = MagicMock(spec=CamundaClient)
        client.enabled = False
        service = FunnelJourneyService(client)

        result = await service.start_batch_journeys(
            contacts=[
                {"id": uuid4(), "phone_number": "0912111", "name": "A"},
            ],
            tenant_id=uuid4(),
        )
        assert result == 0

    @pytest.mark.asyncio
    async def test_batch_success(self):
        """Batch start should return count of successful starts."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True

        instance_data = {"id": "proc-1", "definitionId": "def-1"}
        client.start_process = AsyncMock(return_value=ProcessInstance(instance_data))

        service = FunnelJourneyService(client)
        contacts = [
            {"id": uuid4(), "phone_number": "09121111111", "name": "Contact A"},
            {"id": uuid4(), "phone_number": "09122222222", "name": "Contact B"},
            {"id": uuid4(), "phone_number": "09123333333"},
        ]

        result = await service.start_batch_journeys(
            contacts=contacts, tenant_id=uuid4(),
        )
        assert result == 3
        assert client.start_process.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_partial_failure(self):
        """Some contacts fail → count reflects only successes."""
        client = AsyncMock(spec=CamundaClient)
        client.enabled = True

        call_count = 0

        async def mock_start(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise CamundaError("Process start failed")
            return ProcessInstance({"id": f"proc-{call_count}", "definitionId": "def"})

        client.start_process = mock_start

        service = FunnelJourneyService(client)
        contacts = [
            {"id": uuid4(), "phone_number": "09121111111"},
            {"id": uuid4(), "phone_number": "09122222222"},
            {"id": uuid4(), "phone_number": "09123333333"},
        ]

        result = await service.start_batch_journeys(
            contacts=contacts, tenant_id=uuid4(),
        )
        # Second one fails → 2 out of 3
        assert result == 2


# ─── Funnel Stage Update Worker ───────────────────────────────────────────────


class TestFunnelStageUpdateWorker:
    """Tests for the handle_update_funnel_stage external task worker."""

    def _make_task(self, variables: dict[str, Any]) -> ExternalTask:
        """Create an ExternalTask with process variables."""
        camunda_vars = {
            k: {"value": v, "type": "String"} for k, v in variables.items()
        }
        return ExternalTask({
            "id": "task-funnel-1",
            "topicName": "update-funnel-stage",
            "processInstanceId": "proc-1",
            "processDefinitionKey": "funnel_journey",
            "activityId": "update_stage",
            "variables": camunda_vars,
        })

    @pytest.mark.asyncio
    async def test_missing_variables(self):
        """Missing required variables should return stage_updated=False."""
        from src.infrastructure.camunda.workers.funnel_stage_update import (
            handle_update_funnel_stage,
        )

        task = self._make_task({"contact_id": str(uuid4())})  # Missing tenant_id, stage
        client = AsyncMock(spec=CamundaClient)

        result = await handle_update_funnel_stage(task, client)
        assert result["stage_updated"] is False

    @pytest.mark.asyncio
    async def test_successful_update(self):
        """Successful DB update returns stage_updated=True."""
        from src.infrastructure.camunda.workers.funnel_stage_update import (
            handle_update_funnel_stage,
        )

        contact_id = str(uuid4())
        tenant_id = str(uuid4())

        task = self._make_task({
            "contact_id": contact_id,
            "tenant_id": tenant_id,
            "current_stage": "call_answered",
            "phone_number": "09121234567",
        })
        client = AsyncMock(spec=CamundaClient)

        # Mock the DB session
        mock_result = MagicMock()
        mock_result.rowcount = 1

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.infrastructure.camunda.workers.funnel_stage_update.get_session_factory",
            return_value=mock_factory,
        ):
            result = await handle_update_funnel_stage(task, client)

        assert result["stage_updated"] is True
        assert "updated_at" in result

    @pytest.mark.asyncio
    async def test_contact_not_found(self):
        """Contact not found returns stage_updated=False."""
        from src.infrastructure.camunda.workers.funnel_stage_update import (
            handle_update_funnel_stage,
        )

        task = self._make_task({
            "contact_id": str(uuid4()),
            "tenant_id": str(uuid4()),
            "current_stage": "sms_sent",
            "phone_number": "09999999999",
        })
        client = AsyncMock(spec=CamundaClient)

        mock_result = MagicMock()
        mock_result.rowcount = 0

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "src.infrastructure.camunda.workers.funnel_stage_update.get_session_factory",
            return_value=mock_factory,
        ):
            result = await handle_update_funnel_stage(task, client)

        assert result["stage_updated"] is False


# ─── Journey API Schemas ──────────────────────────────────────────────────────


class TestJourneySchemas:
    """Tests for the journey API Pydantic schemas."""

    def test_start_journey_request(self):
        from src.modules.analytics.api.journey_routes import StartJourneyRequest

        req = StartJourneyRequest(
            contact_id=uuid4(),
            phone_number="09121234567",
            contact_name="تست",
        )
        assert req.phone_number == "09121234567"
        assert req.contact_name == "تست"

    def test_start_journey_request_no_name(self):
        from src.modules.analytics.api.journey_routes import StartJourneyRequest

        req = StartJourneyRequest(
            contact_id=uuid4(),
            phone_number="09121234567",
        )
        assert req.contact_name is None

    def test_start_journey_response(self):
        from src.modules.analytics.api.journey_routes import StartJourneyResponse

        resp = StartJourneyResponse(
            contact_id=uuid4(),
            phone_number="09121234567",
            process_instance_id="proc-1",
            camunda_enabled=True,
        )
        assert resp.current_stage == "lead_acquired"
        assert resp.camunda_enabled is True

    def test_correlate_event_request(self):
        from src.modules.analytics.api.journey_routes import CorrelateEventRequest

        req = CorrelateEventRequest(
            event_name="sms_sent",
            phone_number="09121234567",
        )
        assert req.variables == {}

    def test_correlate_event_request_with_variables(self):
        from src.modules.analytics.api.journey_routes import CorrelateEventRequest

        req = CorrelateEventRequest(
            event_name="payment_received",
            phone_number="09121234567",
            variables={"amount": 50000000},
        )
        assert req.variables["amount"] == 50000000

    def test_correlate_event_response(self):
        from src.modules.analytics.api.journey_routes import CorrelateEventResponse

        resp = CorrelateEventResponse(
            event_name="call_answered",
            phone_number="09121234567",
            correlated=True,
            new_stage="call_answered",
        )
        assert resp.correlated is True

    def test_journey_status_response(self):
        from src.modules.analytics.api.journey_routes import JourneyStatusResponse

        resp = JourneyStatusResponse(
            phone_number="09121234567",
            process_instance_id="proc-1",
            current_stage="sms_delivered",
            source="camunda",
        )
        assert resp.timestamps == {}
        assert resp.source == "camunda"

    def test_journey_status_response_db_source(self):
        from src.modules.analytics.api.journey_routes import JourneyStatusResponse

        resp = JourneyStatusResponse(
            phone_number="09121234567",
            current_stage="lead_acquired",
            source="database",
        )
        assert resp.process_instance_id is None
        assert resp.source == "database"

    def test_batch_start_request(self):
        from src.modules.analytics.api.journey_routes import BatchStartRequest

        req = BatchStartRequest(
            contacts=[
                {"id": str(uuid4()), "phone_number": "0912111", "name": "A"},
                {"id": str(uuid4()), "phone_number": "0912222"},
            ]
        )
        assert len(req.contacts) == 2

    def test_batch_start_response(self):
        from src.modules.analytics.api.journey_routes import BatchStartResponse

        resp = BatchStartResponse(total=5, started=3, camunda_enabled=True)
        assert resp.total == 5
        assert resp.started == 3

    def test_funnel_stages_response(self):
        from src.modules.analytics.api.journey_routes import FunnelStagesResponse

        resp = FunnelStagesResponse(stages=FUNNEL_STAGES, count=len(FUNNEL_STAGES))
        assert resp.count == 7
        assert resp.stages[0] == "lead_acquired"


# ─── Integration: Service + Worker Export ──────────────────────────────────────


class TestModuleExports:
    """Verify that the new components are properly exported."""

    def test_funnel_journey_service_importable(self):
        from src.modules.analytics.application import FunnelJourneyService
        assert FunnelJourneyService is not None

    def test_worker_importable(self):
        from src.infrastructure.camunda.workers import handle_update_funnel_stage
        assert handle_update_funnel_stage is not None
        assert callable(handle_update_funnel_stage)

    def test_journey_router_importable(self):
        from src.modules.analytics.api.journey_routes import router
        assert router is not None

    def test_funnel_stages_constant(self):
        from src.modules.analytics.application.funnel_journey_service import FUNNEL_STAGES
        assert isinstance(FUNNEL_STAGES, list)
        assert len(FUNNEL_STAGES) == 7

