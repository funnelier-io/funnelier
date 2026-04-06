"""
Unit tests for Notification module — domain entities and schemas.
"""

import pytest
from uuid import uuid4
from datetime import datetime, time

from src.modules.notifications.domain.entities import (
    Notification,
    NotificationPreference,
    NOTIFICATION_TYPES,
    SEVERITY_LEVELS,
    NOTIFICATION_ROUTING,
)
from src.modules.notifications.api.schemas import (
    NotificationResponse,
    NotificationListResponse,
    UnreadCountResponse,
    MarkReadResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdateRequest,
    CreateNotificationRequest,
    PushSubscriptionRequest,
)


class TestNotificationEntity:
    def test_create_notification_defaults(self):
        n = Notification(
            tenant_id=uuid4(),
            user_id=uuid4(),
            title="Test notification",
        )
        assert n.type == "system"
        assert n.severity == "info"
        assert n.is_read is False
        assert n.read_at is None
        assert n.body is None
        assert n.source_type is None

    def test_create_notification_full(self):
        tid = uuid4()
        uid = uuid4()
        sid = uuid4()
        n = Notification(
            tenant_id=tid,
            user_id=uid,
            type="alert",
            severity="critical",
            title="High drop-off rate",
            body="Funnel conversion dropped below 1%",
            source_type="alert_instances",
            source_id=sid,
            metadata={"threshold": 1.0, "actual": 0.3},
        )
        assert n.tenant_id == tid
        assert n.user_id == uid
        assert n.type == "alert"
        assert n.severity == "critical"
        assert n.source_id == sid
        assert n.metadata["threshold"] == 1.0

    def test_notification_types_defined(self):
        assert "alert" in NOTIFICATION_TYPES
        assert "import" in NOTIFICATION_TYPES
        assert "campaign" in NOTIFICATION_TYPES
        assert "system" in NOTIFICATION_TYPES
        assert "sync" in NOTIFICATION_TYPES
        assert "report" in NOTIFICATION_TYPES
        assert "sms" in NOTIFICATION_TYPES

    def test_severity_levels_defined(self):
        assert "info" in SEVERITY_LEVELS
        assert "success" in SEVERITY_LEVELS
        assert "warning" in SEVERITY_LEVELS
        assert "error" in SEVERITY_LEVELS
        assert "critical" in SEVERITY_LEVELS

    def test_routing_map(self):
        assert "super_admin" in NOTIFICATION_ROUTING["alert"]
        assert "viewer" not in NOTIFICATION_ROUTING["alert"]
        assert "salesperson" in NOTIFICATION_ROUTING["campaign"]


class TestNotificationPreferenceEntity:
    def test_defaults(self):
        p = NotificationPreference(
            tenant_id=uuid4(),
            user_id=uuid4(),
        )
        assert p.in_app_enabled is True
        assert p.email_enabled is False
        assert p.sms_enabled is False
        assert p.push_enabled is False
        assert p.disabled_types == []
        assert p.quiet_hours_start is None

    def test_with_quiet_hours(self):
        p = NotificationPreference(
            tenant_id=uuid4(),
            user_id=uuid4(),
            quiet_hours_start=time(22, 0),
            quiet_hours_end=time(7, 0),
            disabled_types=["import", "sync"],
        )
        assert p.quiet_hours_start == time(22, 0)
        assert p.quiet_hours_end == time(7, 0)
        assert "import" in p.disabled_types


class TestNotificationSchemas:
    def test_notification_response(self):
        r = NotificationResponse(
            id=uuid4(),
            tenant_id=uuid4(),
            user_id=uuid4(),
            type="alert",
            severity="warning",
            title="Test",
            is_read=False,
            created_at=datetime.utcnow(),
        )
        assert r.type == "alert"
        assert r.is_read is False

    def test_notification_list_response(self):
        r = NotificationListResponse(items=[], total=0, unread_count=5)
        assert r.unread_count == 5
        assert r.total == 0

    def test_unread_count_response(self):
        r = UnreadCountResponse(unread_count=42)
        assert r.unread_count == 42

    def test_mark_read_response(self):
        r = MarkReadResponse(success=True, marked_count=3)
        assert r.success is True
        assert r.marked_count == 3

    def test_preference_response(self):
        r = NotificationPreferenceResponse(
            user_id=uuid4(),
            in_app_enabled=True,
            email_enabled=False,
            sms_enabled=False,
            push_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            disabled_types=["sync"],
        )
        assert r.push_enabled is True
        assert r.quiet_hours_start == "22:00"
        assert "sync" in r.disabled_types

    def test_preference_update_request(self):
        r = NotificationPreferenceUpdateRequest(
            email_enabled=True,
            disabled_types=["import"],
        )
        assert r.email_enabled is True
        assert r.in_app_enabled is None  # Not set

    def test_create_notification_request(self):
        r = CreateNotificationRequest(
            title="New import completed",
            type="import",
            severity="success",
            body="13,000 leads imported",
        )
        assert r.title == "New import completed"
        assert r.user_id is None  # broadcast mode

    def test_push_subscription_request(self):
        r = PushSubscriptionRequest(
            endpoint="https://fcm.googleapis.com/fcm/send/abc123",
            keys={"p256dh": "key1", "auth": "key2"},
        )
        assert "p256dh" in r.keys

