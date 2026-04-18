"""
Tests for Infrastructure Connectors — Sprint 2 P1 Gap Closure.

Covers:
- KavenegarStatus enum
- KavenegarConfig, SMSMessage, SMSDeliveryReport dataclasses
- KavenegarCSVParser (parse_csv, _parse_status, _parse_date, transform_to_sms_logs)
- KavenegarConnector (parse_webhook, connect, import_csv)
- KavenegarClient URL building
"""

import pytest
from datetime import datetime
from uuid import UUID, uuid4

from src.infrastructure.connectors.kavenegar_connector import (
    KavenegarStatus,
    KavenegarConfig,
    SMSMessage,
    SMSDeliveryReport,
    KavenegarClient,
    KavenegarCSVParser,
    KavenegarConnector,
)

TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


# ═══════════════════════════════════════════════════════════════════
# KavenegarStatus Enum
# ═══════════════════════════════════════════════════════════════════


class TestKavenegarStatus:
    def test_delivered_value(self):
        assert KavenegarStatus.DELIVERED.value == 10

    def test_queued_value(self):
        assert KavenegarStatus.QUEUED.value == 1

    def test_blocked_value(self):
        assert KavenegarStatus.BLOCKED.value == 14

    def test_from_value(self):
        assert KavenegarStatus(10) == KavenegarStatus.DELIVERED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            KavenegarStatus(999)


# ═══════════════════════════════════════════════════════════════════
# Config & Dataclasses
# ═══════════════════════════════════════════════════════════════════


class TestKavenegarConfig:
    def test_basic_config(self):
        config = KavenegarConfig(api_key="test-key-123")
        assert config.api_key == "test-key-123"
        assert config.base_url == "https://api.kavenegar.com/v1"
        assert config.sender is None

    def test_custom_sender(self):
        config = KavenegarConfig(api_key="key", sender="10004346")
        assert config.sender == "10004346"


class TestSMSMessage:
    def test_basic_message(self):
        msg = SMSMessage(receptor="989121234567", message="سلام")
        assert msg.type == 1  # simple SMS
        assert msg.sender is None
        assert msg.date is None

    def test_scheduled_message(self):
        dt = datetime(2026, 5, 1, 10, 0)
        msg = SMSMessage(receptor="989121234567", message="test", date=dt)
        assert msg.date == dt


class TestSMSDeliveryReport:
    def test_creation(self):
        report = SMSDeliveryReport(
            message_id="123",
            status=KavenegarStatus.DELIVERED,
            status_text="Delivered",
            receptor="989121234567",
            sender="10004346",
            message="test",
            cost=250,
            date=datetime.utcnow(),
            sent_date=datetime.utcnow(),
            delivery_date=datetime.utcnow(),
        )
        assert report.status == KavenegarStatus.DELIVERED
        assert report.cost == 250


# ═══════════════════════════════════════════════════════════════════
# KavenegarClient
# ═══════════════════════════════════════════════════════════════════


class TestKavenegarClient:
    def test_url_building(self):
        config = KavenegarConfig(api_key="test-key-123")
        client = KavenegarClient(config)
        url = client._get_url("sms/send")
        assert url == "https://api.kavenegar.com/v1/test-key-123/sms/send.json"

    def test_url_building_status(self):
        config = KavenegarConfig(api_key="abc")
        client = KavenegarClient(config)
        url = client._get_url("sms/status")
        assert "abc/sms/status.json" in url


# ═══════════════════════════════════════════════════════════════════
# KavenegarCSVParser
# ═══════════════════════════════════════════════════════════════════


class TestKavenegarCSVParser:
    def test_parse_status_delivered_persian(self):
        assert KavenegarCSVParser._parse_status("تحویل شده") == "delivered"

    def test_parse_status_delivered_english(self):
        assert KavenegarCSVParser._parse_status("Delivered") == "delivered"

    def test_parse_status_sent_persian(self):
        assert KavenegarCSVParser._parse_status("ارسال شده") == "sent"

    def test_parse_status_failed(self):
        assert KavenegarCSVParser._parse_status("Failed") == "failed"

    def test_parse_status_persian_failed(self):
        assert KavenegarCSVParser._parse_status("تحویل نشده") == "failed"

    def test_parse_status_queued(self):
        assert KavenegarCSVParser._parse_status("queued") == "pending"

    def test_parse_status_unknown(self):
        assert KavenegarCSVParser._parse_status("something_else") == "unknown"

    def test_parse_date_iso_format(self):
        dt = KavenegarCSVParser._parse_date("2026-04-18 14:30:00")
        assert dt == datetime(2026, 4, 18, 14, 30, 0)

    def test_parse_date_slash_format(self):
        dt = KavenegarCSVParser._parse_date("2026/04/18 14:30:00")
        assert dt is not None

    def test_parse_date_date_only(self):
        dt = KavenegarCSVParser._parse_date("2026-04-18")
        assert dt == datetime(2026, 4, 18)

    def test_parse_date_empty_returns_none(self):
        assert KavenegarCSVParser._parse_date("") is None

    def test_parse_date_invalid_returns_none(self):
        assert KavenegarCSVParser._parse_date("not-a-date") is None

    def test_parse_csv_basic(self):
        csv_content = (
            "شماره پیام,فرستنده,گیرنده,متن پیام,وضعیت,تاریخ ارسال,هزینه\n"
            "123,10004346,989121234567,سلام,تحویل شده,2026-04-18 10:00:00,250\n"
            "124,10004346,989131234567,تست,ارسال شده,2026-04-18 10:01:00,250\n"
        )
        records = KavenegarCSVParser.parse_csv(csv_content)
        assert len(records) == 2
        assert records[0]["receptor"] == "989121234567"
        assert records[0]["status"] == "delivered"
        assert records[1]["status"] == "sent"

    def test_parse_csv_with_bom(self):
        csv_content = (
            "\ufeffشماره پیام,فرستنده,گیرنده,متن پیام,وضعیت\n"
            "123,sender,989121234567,hello,Delivered\n"
        )
        records = KavenegarCSVParser.parse_csv(csv_content)
        assert len(records) == 1

    def test_parse_csv_english_headers(self):
        csv_content = (
            "messageid,sender,receptor,message,status\n"
            "456,10004346,989351234567,test message,delivered\n"
        )
        records = KavenegarCSVParser.parse_csv(csv_content)
        assert len(records) == 1
        assert records[0]["message_id"] == "456"

    def test_transform_to_sms_logs(self):
        records = [
            {
                "receptor": "989121234567",
                "content": "سلام",
                "status": "delivered",
                "message_id": "123",
                "send_date": datetime(2026, 4, 18),
                "cost": 250,
            },
        ]
        logs = KavenegarCSVParser.transform_to_sms_logs(records, TENANT_ID)
        assert len(logs) == 1
        assert logs[0]["provider_name"] == "kavenegar"
        assert logs[0]["status"] == "delivered"
        assert logs[0]["cost"] == 250


# ═══════════════════════════════════════════════════════════════════
# KavenegarConnector
# ═══════════════════════════════════════════════════════════════════


class TestKavenegarConnector:
    def _make_connector(self) -> KavenegarConnector:
        config = KavenegarConfig(api_key="test-key", sender="10004346")
        return KavenegarConnector(config)

    def test_parse_webhook_delivered(self):
        connector = self._make_connector()
        result = connector.parse_webhook({
            "messageid": "123456",
            "status": 10,
            "statustext": "Delivered",
            "receptor": "989121234567",
            "sender": "10004346",
        })
        assert result["is_delivered"] is True
        assert result["is_failed"] is False
        assert result["message_id"] == "123456"
        assert result["status"] == "delivered"

    def test_parse_webhook_failed(self):
        connector = self._make_connector()
        result = connector.parse_webhook({
            "messageid": "789",
            "status": 11,  # UNDELIVERED
            "receptor": "989121234567",
        })
        assert result["is_delivered"] is False
        assert result["is_failed"] is True

    def test_parse_webhook_blocked(self):
        connector = self._make_connector()
        result = connector.parse_webhook({
            "messageid": "999",
            "status": 14,  # BLOCKED
            "receptor": "989121234567",
        })
        assert result["is_failed"] is True

    def test_parse_webhook_unknown_status(self):
        connector = self._make_connector()
        result = connector.parse_webhook({
            "messageid": "111",
            "status": 999,  # Unknown → defaults to QUEUED
            "receptor": "989121234567",
        })
        assert result["status"] == "queued"
        assert result["is_delivered"] is False

    def test_import_csv(self):
        connector = self._make_connector()
        csv_content = (
            "messageid,sender,receptor,message,status\n"
            "100,10004346,989121234567,test,delivered\n"
        )
        logs = connector.import_csv(csv_content, TENANT_ID)
        assert len(logs) == 1
        assert logs[0]["provider_name"] == "kavenegar"

    @pytest.mark.asyncio
    async def test_connect(self):
        connector = self._make_connector()
        result = await connector.connect()
        assert result is True
        assert connector._client is not None

