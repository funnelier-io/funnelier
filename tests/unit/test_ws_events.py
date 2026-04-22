"""
Unit Tests — WebSocket Events & KPI Beat (Phase 40)

Covers:
- WSEventType enum values
- WSMessage serialization
- Factory helpers (make_kpi_snapshot, make_new_lead, etc.)
- push_kpi_snapshots task structure
- WS_KPI_CHANNEL_PREFIX constant
"""

import json
import pytest
from uuid import uuid4

from src.api.ws_events import (
    WSEventType,
    WSMessage,
    make_campaign_complete,
    make_kpi_snapshot,
    make_new_lead,
    make_sms_sent,
    make_stage_change,
)


# ─── WSEventType ─────────────────────────────────────────────────────────────

class TestWSEventType:
    def test_all_values_exist(self):
        assert WSEventType.KPI_SNAPSHOT == "kpi_snapshot"
        assert WSEventType.NEW_LEAD == "new_lead"
        assert WSEventType.STAGE_CHANGE == "stage_change"
        assert WSEventType.SMS_SENT == "sms_sent"
        assert WSEventType.CAMPAIGN_COMPLETE == "campaign_complete"

    def test_is_str_enum(self):
        assert isinstance(WSEventType.KPI_SNAPSHOT, str)

    def test_count_of_event_types(self):
        assert len(list(WSEventType)) == 5


# ─── WSMessage ────────────────────────────────────────────────────────────────

class TestWSMessage:
    def _make(self, event_type=WSEventType.KPI_SNAPSHOT, payload=None):
        return WSMessage(
            type=event_type,
            tenant_id=str(uuid4()),
            payload=payload or {},
        )

    def test_serialize_returns_json_string(self):
        msg = self._make()
        data = msg.serialize()
        assert isinstance(data, str)
        parsed = json.loads(data)
        assert "type" in parsed
        assert "tenant_id" in parsed
        assert "payload" in parsed
        assert "timestamp" in parsed

    def test_serialize_type_matches_event_type(self):
        msg = self._make(WSEventType.NEW_LEAD)
        parsed = json.loads(msg.serialize())
        assert parsed["type"] == "new_lead"

    def test_serialize_includes_payload(self):
        msg = self._make(payload={"total_contacts": 42})
        parsed = json.loads(msg.serialize())
        assert parsed["payload"]["total_contacts"] == 42

    def test_timestamp_auto_set(self):
        msg = self._make()
        assert msg.timestamp is not None
        assert "T" in msg.timestamp  # ISO format

    def test_empty_payload_default(self):
        msg = WSMessage(type=WSEventType.KPI_SNAPSHOT, tenant_id="tid")
        assert msg.payload == {}


# ─── Factory helpers ──────────────────────────────────────────────────────────

class TestWSFactoryHelpers:
    def test_make_kpi_snapshot(self):
        tid = uuid4()
        kpis = {"total_contacts": 100, "active_campaigns": 3}
        msg = make_kpi_snapshot(tid, kpis)
        assert msg.type == WSEventType.KPI_SNAPSHOT
        assert msg.tenant_id == str(tid)
        assert msg.payload["total_contacts"] == 100
        assert msg.payload["active_campaigns"] == 3

    def test_make_kpi_snapshot_with_string_tenant(self):
        msg = make_kpi_snapshot("tenant-123", {"sms_sent_today": 50})
        assert msg.tenant_id == "tenant-123"

    def test_make_new_lead(self):
        tid = uuid4()
        cid = str(uuid4())
        msg = make_new_lead(tid, cid, "Ahmad")
        assert msg.type == WSEventType.NEW_LEAD
        assert msg.payload["contact_id"] == cid
        assert msg.payload["name"] == "Ahmad"

    def test_make_stage_change(self):
        tid = uuid4()
        cid = str(uuid4())
        msg = make_stage_change(tid, cid, "converted")
        assert msg.type == WSEventType.STAGE_CHANGE
        assert msg.payload["stage"] == "converted"

    def test_make_sms_sent(self):
        tid = uuid4()
        cam_id = str(uuid4())
        msg = make_sms_sent(tid, cam_id, 250)
        assert msg.type == WSEventType.SMS_SENT
        assert msg.payload["count"] == 250

    def test_make_campaign_complete(self):
        tid = uuid4()
        cam_id = str(uuid4())
        msg = make_campaign_complete(tid, cam_id, "Spring Sale")
        assert msg.type == WSEventType.CAMPAIGN_COMPLETE
        assert msg.payload["name"] == "Spring Sale"

    def test_all_messages_serializable(self):
        tid = uuid4()
        cid = str(uuid4())
        messages = [
            make_kpi_snapshot(tid, {}),
            make_new_lead(tid, cid, "Test"),
            make_stage_change(tid, cid, "awareness"),
            make_sms_sent(tid, cid, 0),
            make_campaign_complete(tid, cid, "Campaign"),
        ]
        for msg in messages:
            serialized = msg.serialize()
            assert isinstance(serialized, str)
            parsed = json.loads(serialized)
            assert "type" in parsed

    def test_tenant_id_always_string(self):
        uuid_tenant = uuid4()
        msg = make_kpi_snapshot(uuid_tenant, {})
        assert isinstance(msg.tenant_id, str)


# ─── ws_kpi_beat module structure ─────────────────────────────────────────────

class TestWSKpiBeatModule:
    def test_module_importable(self):
        import src.tasks.ws_kpi_beat as beat
        assert hasattr(beat, "push_kpi_snapshots")
        assert hasattr(beat, "WS_KPI_CHANNEL_PREFIX")

    def test_channel_prefix(self):
        from src.tasks.ws_kpi_beat import WS_KPI_CHANNEL_PREFIX
        assert WS_KPI_CHANNEL_PREFIX == "ws:"

    def test_push_task_is_celery_task(self):
        from src.tasks.ws_kpi_beat import push_kpi_snapshots
        # Celery tasks have .name attribute
        assert hasattr(push_kpi_snapshots, "name")
        assert "push_kpi_snapshots" in push_kpi_snapshots.name


# ─── ConnectionManager ────────────────────────────────────────────────────────

class TestConnectionManager:
    def test_initial_connection_count_zero(self):
        from src.api.websocket import ConnectionManager
        mgr = ConnectionManager()
        assert mgr.connection_count == 0

    def test_disconnect_unknown_is_safe(self):
        from src.api.websocket import ConnectionManager
        from unittest.mock import MagicMock
        mgr = ConnectionManager()
        fake_ws = MagicMock()
        # Should not raise
        mgr.disconnect(fake_ws, "nonexistent-tenant")

    def test_manager_singleton_exported(self):
        from src.api.websocket import manager
        assert manager is not None

