"""
Asterisk VoIP Connector

Connector for integrating with self-hosted Asterisk PBX systems.
Supports call log extraction via AMI (Asterisk Manager Interface) or CDR database.
"""

import asyncio
from datetime import datetime
from typing import Any, AsyncIterator
from uuid import UUID
import json

from dataclasses import dataclass

from src.core.utils import normalize_phone_number


@dataclass
class AsteriskConfig:
    """Configuration for Asterisk connection."""
    host: str
    port: int = 5038  # AMI port
    username: str | None = None
    secret: str | None = None
    # CDR database connection (alternative)
    cdr_database_url: str | None = None
    cdr_table_name: str = "cdr"
    # Options
    use_ami: bool = True
    successful_call_threshold: int = 90


@dataclass
class AsteriskCallLog:
    """Asterisk call log record."""
    unique_id: str
    call_time: datetime
    source: str  # Caller number
    destination: str  # Called number
    duration: int  # In seconds
    billable_seconds: int
    disposition: str  # ANSWERED, NO ANSWER, BUSY, FAILED
    channel: str
    dst_channel: str
    recording_url: str | None = None
    account_code: str | None = None
    user_field: str | None = None


class AsteriskAMIClient:
    """Asterisk Manager Interface (AMI) client."""

    def __init__(self, config: AsteriskConfig):
        self.config = config
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._connected = False
        self._action_id = 0

    async def connect(self) -> bool:
        """Connect to Asterisk AMI."""
        try:
            self._reader, self._writer = await asyncio.open_connection(
                self.config.host,
                self.config.port,
            )

            # Read welcome message
            welcome = await self._reader.readline()
            if not welcome.startswith(b"Asterisk Call Manager"):
                return False

            # Login
            if self.config.username and self.config.secret:
                login_success = await self._login()
                if not login_success:
                    return False

            self._connected = True
            return True

        except Exception as e:
            print(f"Failed to connect to Asterisk AMI: {e}")
            return False

    async def _login(self) -> bool:
        """Login to AMI."""
        action_id = self._get_action_id()
        login_cmd = (
            f"Action: Login\r\n"
            f"ActionID: {action_id}\r\n"
            f"Username: {self.config.username}\r\n"
            f"Secret: {self.config.secret}\r\n"
            f"\r\n"
        )
        self._writer.write(login_cmd.encode())
        await self._writer.drain()

        # Read response
        response = await self._read_response()
        return response.get("Response") == "Success"

    async def disconnect(self) -> None:
        """Disconnect from AMI."""
        if self._connected and self._writer:
            # Logoff
            action_id = self._get_action_id()
            logoff_cmd = f"Action: Logoff\r\nActionID: {action_id}\r\n\r\n"
            self._writer.write(logoff_cmd.encode())
            await self._writer.drain()
            self._writer.close()
            await self._writer.wait_closed()
        self._connected = False

    def _get_action_id(self) -> str:
        """Generate unique action ID."""
        self._action_id += 1
        return f"funnelier-{self._action_id}"

    async def _read_response(self) -> dict[str, str]:
        """Read AMI response."""
        response = {}
        while True:
            line = await self._reader.readline()
            line = line.decode().strip()
            if not line:
                break
            if ":" in line:
                key, value = line.split(":", 1)
                response[key.strip()] = value.strip()
        return response

    async def get_cdr_entries(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get CDR entries via AMI command."""
        # Note: This is a simplified implementation
        # In production, you'd typically query the CDR database directly
        entries = []

        # Use DBGet or custom CLI command
        action_id = self._get_action_id()
        cmd = (
            f"Action: Command\r\n"
            f"ActionID: {action_id}\r\n"
            f"Command: cdr show\r\n"
            f"\r\n"
        )
        self._writer.write(cmd.encode())
        await self._writer.drain()

        response = await self._read_response()
        # Parse response...

        return entries


class AsteriskCDRConnector:
    """
    Connector for Asterisk CDR (Call Detail Records) database.

    This is the preferred method for extracting call logs as it provides
    direct database access to historical call data.
    """

    def __init__(self, config: AsteriskConfig):
        self.config = config
        self._pool = None

    async def connect(self) -> bool:
        """Connect to CDR database."""
        if not self.config.cdr_database_url:
            raise ValueError("CDR database URL not configured")

        try:
            # Using asyncpg for PostgreSQL or aiomysql for MySQL
            # This is a placeholder - actual implementation depends on database type
            if "postgresql" in self.config.cdr_database_url:
                import asyncpg
                self._pool = await asyncpg.create_pool(self.config.cdr_database_url)
            elif "mysql" in self.config.cdr_database_url:
                import aiomysql
                # Parse URL and create pool
                pass
            return True
        except Exception as e:
            print(f"Failed to connect to CDR database: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from CDR database."""
        if self._pool:
            await self._pool.close()

    async def get_call_logs(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[AsteriskCallLog]:
        """
        Get call logs from CDR database.

        Standard Asterisk CDR table columns:
        - calldate: Timestamp of the call
        - clid: Caller ID
        - src: Source (caller) number
        - dst: Destination (called) number
        - dcontext: Destination context
        - channel: Channel used
        - dstchannel: Destination channel
        - lastapp: Last application run
        - lastdata: Last application data
        - duration: Total duration (seconds)
        - billsec: Billable seconds
        - disposition: Call disposition
        - amaflags: AMA flags
        - accountcode: Account code
        - uniqueid: Unique call ID
        - userfield: User-defined field
        """
        if not self._pool:
            raise RuntimeError("Not connected to database")

        query = f"""
            SELECT
                uniqueid,
                calldate,
                src,
                dst,
                duration,
                billsec,
                disposition,
                channel,
                dstchannel,
                accountcode,
                userfield
            FROM {self.config.cdr_table_name}
            WHERE 1=1
        """
        params = []
        param_idx = 1

        if from_date:
            query += f" AND calldate >= ${param_idx}"
            params.append(from_date)
            param_idx += 1

        if to_date:
            query += f" AND calldate <= ${param_idx}"
            params.append(to_date)
            param_idx += 1

        query += f" ORDER BY calldate DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}"
        params.extend([limit, offset])

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        logs = []
        for row in rows:
            log = AsteriskCallLog(
                unique_id=row["uniqueid"],
                call_time=row["calldate"],
                source=row["src"],
                destination=row["dst"],
                duration=row["duration"],
                billable_seconds=row["billsec"],
                disposition=row["disposition"],
                channel=row["channel"],
                dst_channel=row["dstchannel"],
                account_code=row["accountcode"],
                user_field=row["userfield"],
            )
            logs.append(log)

        return logs


class AsteriskConnector:
    """
    Main Asterisk connector that provides a unified interface
    for both AMI and CDR database access.
    """

    def __init__(self, config: AsteriskConfig):
        self.config = config
        self._ami_client: AsteriskAMIClient | None = None
        self._cdr_connector: AsteriskCDRConnector | None = None

    async def connect(self) -> bool:
        """Connect to Asterisk."""
        if self.config.use_ami:
            self._ami_client = AsteriskAMIClient(self.config)
            return await self._ami_client.connect()
        else:
            self._cdr_connector = AsteriskCDRConnector(self.config)
            return await self._cdr_connector.connect()

    async def disconnect(self) -> None:
        """Disconnect from Asterisk."""
        if self._ami_client:
            await self._ami_client.disconnect()
        if self._cdr_connector:
            await self._cdr_connector.disconnect()

    async def get_call_logs(
        self,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get call logs and transform to standard format."""
        if self._cdr_connector:
            asterisk_logs = await self._cdr_connector.get_call_logs(
                from_date=from_date,
                to_date=to_date,
                limit=limit,
            )
        elif self._ami_client:
            raw_entries = await self._ami_client.get_cdr_entries(
                from_date=from_date,
                to_date=to_date,
            )
            asterisk_logs = [self._parse_ami_entry(e) for e in raw_entries]
        else:
            return []

        # Transform to standard call log format
        return [self._transform_to_standard(log) for log in asterisk_logs]

    def _parse_ami_entry(self, entry: dict[str, Any]) -> AsteriskCallLog:
        """Parse AMI response entry to AsteriskCallLog."""
        return AsteriskCallLog(
            unique_id=entry.get("uniqueid", ""),
            call_time=datetime.fromisoformat(entry.get("calldate", "")),
            source=entry.get("src", ""),
            destination=entry.get("dst", ""),
            duration=int(entry.get("duration", 0)),
            billable_seconds=int(entry.get("billsec", 0)),
            disposition=entry.get("disposition", ""),
            channel=entry.get("channel", ""),
            dst_channel=entry.get("dstchannel", ""),
        )

    def _transform_to_standard(self, log: AsteriskCallLog) -> dict[str, Any]:
        """Transform Asterisk call log to standard format."""
        is_answered = log.disposition == "ANSWERED"
        is_successful = is_answered and log.billable_seconds >= self.config.successful_call_threshold

        return {
            "phone_number": self._normalize_phone(log.destination),
            "contact_name": None,
            "call_type": "outbound",  # Can be determined from channel
            "source": "voip",
            "duration_seconds": log.billable_seconds,
            "call_time": log.call_time,
            "salesperson_phone": self._extract_extension(log.channel),
            "is_answered": is_answered,
            "is_successful": is_successful,
            "voip_unique_id": log.unique_id,
            "recording_url": log.recording_url,
            "metadata": {
                "disposition": log.disposition,
                "channel": log.channel,
                "account_code": log.account_code,
                "raw_duration": log.duration,
            },
        }

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number."""
        return normalize_phone_number(phone)

    def _extract_extension(self, channel: str) -> str | None:
        """Extract extension number from channel string."""
        # Channel format: SIP/extension-xxxxx or PJSIP/extension-xxxxx
        if "/" in channel:
            ext_part = channel.split("/")[1]
            if "-" in ext_part:
                return ext_part.split("-")[0]
            return ext_part
        return None


def parse_asterisk_json_export(json_content: str) -> list[dict[str, Any]]:
    """
    Parse Asterisk CDR JSON export.

    For tenants who export CDR data as JSON files.
    """
    data = json.loads(json_content)

    if isinstance(data, list):
        records = data
    elif isinstance(data, dict) and "records" in data:
        records = data["records"]
    else:
        records = [data]

    config = AsteriskConfig(host="", use_ami=False)
    connector = AsteriskConnector(config)

    result = []
    for record in records:
        log = AsteriskCallLog(
            unique_id=record.get("uniqueid", record.get("id", "")),
            call_time=datetime.fromisoformat(record.get("calldate", record.get("timestamp", ""))),
            source=record.get("src", record.get("caller", "")),
            destination=record.get("dst", record.get("destination", "")),
            duration=int(record.get("duration", 0)),
            billable_seconds=int(record.get("billsec", record.get("duration", 0))),
            disposition=record.get("disposition", record.get("status", "")),
            channel=record.get("channel", ""),
            dst_channel=record.get("dstchannel", ""),
            recording_url=record.get("recordingfile", record.get("recording_url")),
        )
        result.append(connector._transform_to_standard(log))

    return result

