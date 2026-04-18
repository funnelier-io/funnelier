"""
Tests for Communications Module — Sprint 2 P1 Gap Closure.

Covers:
- SMSTemplate entity (character count, SMS parts calculation)
- SMSLog entity (mark_sent, mark_delivered, mark_failed, factory)
- CallLog entity (evaluate_success, from_mobile_log, from_voip_log)
- Domain events emission
"""

import pytest
from datetime import datetime
from uuid import UUID, uuid4

from src.core.domain import (
    CallSource,
    CallType,
    SMSDirection,
    SMSStatus,
    SMSSentEvent,
    SMSDeliveredEvent,
    SMSFailedEvent,
    CallReceivedEvent,
    CallAnsweredEvent,
)
from src.modules.communications.domain.entities import (
    SMSTemplate,
    SMSLog,
    CallLog,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ═══════════════════════════════════════════════════════════════════
# SMSTemplate Entity
# ═══════════════════════════════════════════════════════════════════


class TestSMSTemplate:
    def test_basic_creation(self):
        t = SMSTemplate(
            tenant_id=TENANT_ID,
            name="welcome",
            content="سلام، به فانلیر خوش آمدید!",
        )
        assert t.name == "welcome"
        assert t.is_active is True
        assert t.times_used == 0

    def test_character_count(self):
        t = SMSTemplate(tenant_id=TENANT_ID, name="test", content="Hello World!")
        assert t.character_count == 12

    def test_sms_parts_single(self):
        """Short message (<=70 chars) should be 1 part."""
        t = SMSTemplate(tenant_id=TENANT_ID, name="short", content="a" * 70)
        assert t.sms_parts == 1

    def test_sms_parts_two(self):
        """71-134 chars should be 2 parts."""
        t = SMSTemplate(tenant_id=TENANT_ID, name="medium", content="a" * 71)
        assert t.sms_parts == 2

    def test_sms_parts_three(self):
        """135-201 chars should be 3 parts."""
        t = SMSTemplate(tenant_id=TENANT_ID, name="long", content="a" * 201)
        assert t.sms_parts == 3

    def test_persian_content_parts(self):
        # Each Persian character is 1 char
        content = "سلام" * 18  # 72 chars
        t = SMSTemplate(tenant_id=TENANT_ID, name="fa", content=content)
        assert t.sms_parts == 2

    def test_target_segments(self):
        t = SMSTemplate(
            tenant_id=TENANT_ID,
            name="promo",
            content="تخفیف ویژه",
            target_segments=["champions", "loyal"],
        )
        assert "champions" in t.target_segments

    def test_ab_variant(self):
        t = SMSTemplate(
            tenant_id=TENANT_ID,
            name="test_a",
            content="Version A",
            variant_group="promo_test",
            variant_name="A",
        )
        assert t.variant_group == "promo_test"


# ═══════════════════════════════════════════════════════════════════
# SMSLog Entity
# ═══════════════════════════════════════════════════════════════════


class TestSMSLog:
    def _make_sms_log(self, **kwargs) -> SMSLog:
        defaults = dict(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            direction=SMSDirection.OUTBOUND,
            content="تست پیامک",
        )
        defaults.update(kwargs)
        return SMSLog(**defaults)

    def test_default_status_is_pending(self):
        sms = self._make_sms_log()
        assert sms.status == SMSStatus.PENDING

    def test_mark_sent(self):
        sms = self._make_sms_log()
        sms.mark_sent(provider_message_id="kav-123")
        assert sms.status == SMSStatus.SENT
        assert sms.sent_at is not None
        assert sms.provider_message_id == "kav-123"
        events = [e for e in sms.domain_events if isinstance(e, SMSSentEvent)]
        assert len(events) == 1

    def test_mark_delivered(self):
        sms = self._make_sms_log()
        sms.mark_sent()
        sms.mark_delivered()
        assert sms.status == SMSStatus.DELIVERED
        assert sms.delivered_at is not None
        events = [e for e in sms.domain_events if isinstance(e, SMSDeliveredEvent)]
        assert len(events) == 1

    def test_mark_failed(self):
        sms = self._make_sms_log()
        sms.mark_failed("Invalid number")
        assert sms.status == SMSStatus.FAILED
        assert sms.failed_at is not None
        assert sms.failure_reason == "Invalid number"
        events = [e for e in sms.domain_events if isinstance(e, SMSFailedEvent)]
        assert len(events) == 1

    def test_create_outbound_factory(self):
        sms = SMSLog.create_outbound(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            content="سلام",
            provider_name="kavenegar",
        )
        assert sms.direction == SMSDirection.OUTBOUND
        assert sms.provider_name == "kavenegar"
        assert sms.status == SMSStatus.PENDING

    def test_create_outbound_with_campaign(self):
        campaign_id = uuid4()
        template_id = uuid4()
        sms = SMSLog.create_outbound(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            content="Campaign message",
            campaign_id=campaign_id,
            template_id=template_id,
        )
        assert sms.campaign_id == campaign_id
        assert sms.template_id == template_id

    def test_cost_default_zero(self):
        sms = self._make_sms_log()
        assert sms.cost == 0


# ═══════════════════════════════════════════════════════════════════
# CallLog Entity
# ═══════════════════════════════════════════════════════════════════


class TestCallLog:
    def _make_call_log(self, **kwargs) -> CallLog:
        defaults = dict(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type=CallType.OUTGOING,
            source=CallSource.MOBILE,
            duration_seconds=120,
            call_time=datetime.utcnow(),
        )
        defaults.update(kwargs)
        return CallLog(**defaults)

    def test_evaluate_success_above_threshold(self):
        call = self._make_call_log(duration_seconds=120)
        call.evaluate_success(min_duration_seconds=90)
        assert call.is_successful is True

    def test_evaluate_success_below_threshold(self):
        call = self._make_call_log(duration_seconds=60)
        call.evaluate_success(min_duration_seconds=90)
        assert call.is_successful is False

    def test_evaluate_success_missed_call(self):
        call = self._make_call_log(call_type=CallType.MISSED, duration_seconds=0)
        call.evaluate_success()
        assert call.is_successful is False

    def test_from_mobile_log_outgoing(self):
        call = CallLog.from_mobile_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="outgoing",
            duration_seconds=120,
            call_time=datetime.utcnow(),
        )
        assert call.call_type == CallType.OUTGOING
        assert call.source == CallSource.MOBILE
        assert call.is_successful is True
        # Should have CallReceivedEvent and CallAnsweredEvent
        event_types = [type(e) for e in call.domain_events]
        assert CallReceivedEvent in event_types
        assert CallAnsweredEvent in event_types

    def test_from_mobile_log_incoming_with_typo(self):
        """Handle 'incomming' typo in real data."""
        call = CallLog.from_mobile_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="incomming",
            duration_seconds=200,
            call_time=datetime.utcnow(),
        )
        assert call.call_type == CallType.INCOMING

    def test_from_mobile_log_missed(self):
        call = CallLog.from_mobile_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="missed",
            duration_seconds=0,
            call_time=datetime.utcnow(),
        )
        assert call.call_type == CallType.MISSED
        assert call.is_successful is False
        event_types = [type(e) for e in call.domain_events]
        assert CallAnsweredEvent not in event_types

    def test_from_mobile_log_short_call_not_successful(self):
        call = CallLog.from_mobile_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="outgoing",
            duration_seconds=30,
            call_time=datetime.utcnow(),
            min_duration_threshold=90,
        )
        assert call.is_successful is False

    def test_from_voip_log(self):
        call = CallLog.from_voip_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="inbound",
            duration_seconds=300,
            call_time=datetime.utcnow(),
            extension="201",
            voip_call_id="ast-12345",
        )
        assert call.call_type == CallType.INCOMING
        assert call.source == CallSource.VOIP
        assert call.voip_extension == "201"
        assert call.voip_call_id == "ast-12345"
        assert call.is_successful is True

    def test_from_voip_log_no_answer(self):
        call = CallLog.from_voip_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="no-answer",
            duration_seconds=0,
            call_time=datetime.utcnow(),
        )
        assert call.call_type == CallType.MISSED
        assert call.is_successful is False

    def test_from_voip_log_busy(self):
        call = CallLog.from_voip_log(
            tenant_id=TENANT_ID,
            phone_number="9121234567",
            call_type="busy",
            duration_seconds=0,
            call_time=datetime.utcnow(),
        )
        assert call.call_type == CallType.MISSED

    def test_default_is_successful_false(self):
        call = self._make_call_log()
        assert call.is_successful is False  # Must call evaluate_success

