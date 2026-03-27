"""
Kavenegar SMS Connector

Connector for integrating with Kavenegar SMS service provider.
Supports sending SMS and receiving delivery reports.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID
import csv
import io
from dataclasses import dataclass
from enum import Enum

from src.core.utils import normalize_phone_number

import httpx


class KavenegarStatus(Enum):
    """Kavenegar delivery status codes."""
    QUEUED = 1
    SCHEDULED = 2
    SENT_TO_TELCO = 4
    SENT_TO_TELCO_2 = 5
    DELIVERED = 10
    UNDELIVERED = 11
    CANCELLED = 13
    BLOCKED = 14
    INVALID_ID = 100


@dataclass
class KavenegarConfig:
    """Configuration for Kavenegar connection."""
    api_key: str
    sender: str | None = None
    base_url: str = "https://api.kavenegar.com/v1"


@dataclass
class SMSMessage:
    """SMS message for sending."""
    receptor: str
    message: str
    sender: str | None = None
    date: datetime | None = None  # For scheduled messages
    type: int = 1  # 1=simple, 2=flash
    localid: str | None = None


@dataclass
class SMSDeliveryReport:
    """SMS delivery report from Kavenegar."""
    message_id: str
    status: KavenegarStatus
    status_text: str
    receptor: str
    sender: str
    message: str
    cost: int
    date: datetime
    sent_date: datetime | None
    delivery_date: datetime | None


class KavenegarClient:
    """
    Kavenegar API client.

    API Documentation: https://kavenegar.com/rest.html
    """

    def __init__(self, config: KavenegarConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    def _get_url(self, method: str) -> str:
        """Build API URL."""
        return f"{self.config.base_url}/{self.config.api_key}/{method}.json"

    async def send(self, messages: list[SMSMessage]) -> list[dict[str, Any]]:
        """
        Send SMS messages.

        Returns list of message results with message_id and status.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        results = []

        for msg in messages:
            data = {
                "receptor": msg.receptor,
                "message": msg.message,
                "sender": msg.sender or self.config.sender,
            }

            if msg.date:
                data["date"] = int(msg.date.timestamp())
            if msg.localid:
                data["localid"] = msg.localid

            try:
                response = await self._client.post(
                    self._get_url("sms/send"),
                    data=data,
                )
                result = response.json()

                if result.get("return", {}).get("status") == 200:
                    entries = result.get("entries", [])
                    for entry in entries:
                        results.append({
                            "success": True,
                            "message_id": str(entry.get("messageid")),
                            "receptor": entry.get("receptor"),
                            "status": entry.get("status"),
                            "cost": entry.get("cost", 0),
                        })
                else:
                    results.append({
                        "success": False,
                        "receptor": msg.receptor,
                        "error": result.get("return", {}).get("message", "Unknown error"),
                    })
            except Exception as e:
                results.append({
                    "success": False,
                    "receptor": msg.receptor,
                    "error": str(e),
                })

        return results

    async def send_bulk(
        self,
        receptors: list[str],
        message: str,
        sender: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Send same message to multiple receptors.
        """
        data = {
            "receptor": ",".join(receptors),
            "message": message,
            "sender": sender or self.config.sender,
        }

        response = await self._client.post(
            self._get_url("sms/sendarray"),
            data=data,
        )
        result = response.json()

        if result.get("return", {}).get("status") == 200:
            return [
                {
                    "success": True,
                    "message_id": str(entry.get("messageid")),
                    "receptor": entry.get("receptor"),
                    "status": entry.get("status"),
                    "cost": entry.get("cost", 0),
                }
                for entry in result.get("entries", [])
            ]
        else:
            return [{
                "success": False,
                "error": result.get("return", {}).get("message", "Unknown error"),
            }]

    async def status(self, message_ids: list[str]) -> list[SMSDeliveryReport]:
        """
        Get delivery status for messages.
        """
        data = {
            "messageid": ",".join(message_ids),
        }

        response = await self._client.post(
            self._get_url("sms/status"),
            data=data,
        )
        result = response.json()

        reports = []
        if result.get("return", {}).get("status") == 200:
            for entry in result.get("entries", []):
                status_code = entry.get("status", 0)
                try:
                    status = KavenegarStatus(status_code)
                except ValueError:
                    status = KavenegarStatus.QUEUED

                report = SMSDeliveryReport(
                    message_id=str(entry.get("messageid")),
                    status=status,
                    status_text=entry.get("statustext", ""),
                    receptor=entry.get("receptor", ""),
                    sender=entry.get("sender", ""),
                    message=entry.get("message", ""),
                    cost=entry.get("cost", 0),
                    date=datetime.fromtimestamp(entry.get("date", 0)),
                    sent_date=datetime.fromtimestamp(entry["send"]) if entry.get("send") else None,
                    delivery_date=None,
                )
                reports.append(report)

        return reports

    async def get_account_info(self) -> dict[str, Any]:
        """Get account information including credit."""
        response = await self._client.get(self._get_url("account/info"))
        result = response.json()

        if result.get("return", {}).get("status") == 200:
            entries = result.get("entries", {})
            return {
                "credit": entries.get("remaincredit", 0),
                "expire_date": entries.get("expiredate"),
                "type": entries.get("type"),
            }
        return {}


class KavenegarCSVParser:
    """
    Parser for Kavenegar CSV export files.

    Kavenegar provides CSV exports with the following columns:
    - شماره پیام (Message ID)
    - فرستنده (Sender)
    - گیرنده (Receptor)
    - متن پیام (Message)
    - وضعیت (Status)
    - تاریخ ارسال (Send Date)
    - هزینه (Cost)
    """

    @staticmethod
    def parse_csv(csv_content: str) -> list[dict[str, Any]]:
        """
        Parse Kavenegar CSV export.
        """
        records = []

        # Handle BOM if present
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]

        reader = csv.DictReader(io.StringIO(csv_content))

        for row in reader:
            # Try to identify columns by content (headers may be in Persian)
            record = {}

            for key, value in row.items():
                key_lower = key.strip().lower()

                # Map Persian/English column names
                if "شماره" in key or "messageid" in key_lower or "id" == key_lower:
                    record["message_id"] = value.strip()
                elif "فرستنده" in key or "sender" in key_lower:
                    record["sender"] = value.strip()
                elif "گیرنده" in key or "receptor" in key_lower or "receiver" in key_lower:
                    record["receptor"] = value.strip()
                elif "متن" in key or "message" in key_lower or "content" in key_lower:
                    record["content"] = value.strip()
                elif "وضعیت" in key or "status" in key_lower:
                    record["status"] = KavenegarCSVParser._parse_status(value.strip())
                elif "تاریخ" in key or "date" in key_lower:
                    record["send_date"] = KavenegarCSVParser._parse_date(value.strip())
                elif "هزینه" in key or "cost" in key_lower:
                    record["cost"] = int(value.strip()) if value.strip().isdigit() else 0

            if record.get("receptor"):
                records.append(record)

        return records

    @staticmethod
    def _parse_status(status_text: str) -> str:
        """Parse status text to standard status."""
        status_lower = status_text.lower()

        if "تحویل" in status_text or "delivered" in status_lower:
            return "delivered"
        elif "ارسال" in status_text or "sent" in status_lower:
            return "sent"
        elif "نشده" in status_text or "failed" in status_lower or "undelivered" in status_lower:
            return "failed"
        elif "صف" in status_text or "queued" in status_lower or "pending" in status_lower:
            return "pending"
        else:
            return "unknown"

    @staticmethod
    def _parse_date(date_str: str) -> datetime | None:
        """Parse date string (supports various formats)."""
        if not date_str:
            return None

        # Try different formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%Y-%m-%d",
            "%Y/%m/%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        # Try timestamp
        try:
            return datetime.fromtimestamp(int(date_str))
        except (ValueError, OSError):
            pass

        return None

    @staticmethod
    def transform_to_sms_logs(
        records: list[dict[str, Any]],
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """
        Transform parsed CSV records to SMS log format.
        """
        logs = []

        for record in records:
            log = {
                "tenant_id": str(tenant_id),
                "phone_number": KavenegarCSVParser._normalize_phone(record.get("receptor", "")),
                "direction": "outbound",
                "content": record.get("content", ""),
                "status": record.get("status", "unknown"),
                "provider_message_id": record.get("message_id"),
                "sent_at": record.get("send_date"),
                "delivered_at": record.get("send_date") if record.get("status") == "delivered" else None,
                "provider_name": "kavenegar",
                "cost": record.get("cost", 0),
            }
            logs.append(log)

        return logs

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """Normalize Iranian phone number."""
        return normalize_phone_number(phone)


class KavenegarConnector:
    """
    High-level connector for Kavenegar SMS operations.

    Provides a unified interface for:
    - Sending SMS (single and bulk)
    - Checking delivery status
    - Importing CSV exports
    - Webhook handling for delivery reports
    """

    def __init__(self, config: KavenegarConfig):
        self.config = config
        self._client: KavenegarClient | None = None

    async def connect(self) -> bool:
        """Initialize the client."""
        try:
            self._client = KavenegarClient(self.config)
            return True
        except Exception as e:
            print(f"Failed to initialize Kavenegar client: {e}")
            return False

    async def send_sms(
        self,
        phone_number: str,
        content: str,
        sender: str | None = None,
    ) -> dict[str, Any]:
        """Send a single SMS."""
        async with KavenegarClient(self.config) as client:
            message = SMSMessage(
                receptor=phone_number,
                message=content,
                sender=sender,
            )
            results = await client.send([message])
            return results[0] if results else {"success": False, "error": "No result"}

    async def send_bulk_sms(
        self,
        phone_numbers: list[str],
        content: str,
        sender: str | None = None,
    ) -> list[dict[str, Any]]:
        """Send SMS to multiple recipients."""
        async with KavenegarClient(self.config) as client:
            return await client.send_bulk(phone_numbers, content, sender)

    async def check_delivery_status(
        self,
        message_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Check delivery status for messages."""
        async with KavenegarClient(self.config) as client:
            reports = await client.status(message_ids)
            return [
                {
                    "message_id": r.message_id,
                    "status": r.status.name.lower(),
                    "receptor": r.receptor,
                    "sent_date": r.sent_date,
                    "cost": r.cost,
                }
                for r in reports
            ]

    def import_csv(
        self,
        csv_content: str,
        tenant_id: UUID,
    ) -> list[dict[str, Any]]:
        """Import SMS logs from CSV export."""
        records = KavenegarCSVParser.parse_csv(csv_content)
        return KavenegarCSVParser.transform_to_sms_logs(records, tenant_id)

    async def get_credit(self) -> int:
        """Get remaining credit."""
        async with KavenegarClient(self.config) as client:
            info = await client.get_account_info()
            return info.get("credit", 0)

    def parse_webhook(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Parse Kavenegar delivery webhook payload.

        Webhook payload structure:
        {
            "messageid": "123456",
            "status": 10,
            "statustext": "Delivered",
            "receptor": "989123456789",
            "sender": "10004346"
        }
        """
        status_code = int(data.get("status", 0))
        try:
            status = KavenegarStatus(status_code)
        except ValueError:
            status = KavenegarStatus.QUEUED

        return {
            "message_id": str(data.get("messageid", "")),
            "status": status.name.lower(),
            "receptor": data.get("receptor", ""),
            "sender": data.get("sender", ""),
            "is_delivered": status == KavenegarStatus.DELIVERED,
            "is_failed": status in [
                KavenegarStatus.UNDELIVERED,
                KavenegarStatus.CANCELLED,
                KavenegarStatus.BLOCKED,
            ],
        }

