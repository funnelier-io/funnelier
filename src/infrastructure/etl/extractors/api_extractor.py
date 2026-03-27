"""
API Extractor

Extracts data from REST APIs, supporting:
- Kavenegar SMS provider
- Generic REST APIs
- OAuth and API key authentication
- Pagination handling
"""

from datetime import datetime
from typing import Any, AsyncIterator

import httpx

from src.core.utils import normalize_phone_strict

from src.core.interfaces import APISourceConfig, DataRecord

from .base import BaseExtractor, ExtractorRegistry


@ExtractorRegistry.register("api")
class APIExtractor(BaseExtractor):
    """
    Extractor for REST APIs.
    Supports various authentication methods and pagination strategies.
    """

    def __init__(self, config: APISourceConfig, tenant_id: str | None = None):
        super().__init__(config, tenant_id)
        self._api_config: APISourceConfig = config
        self._client: httpx.AsyncClient | None = None
        self._headers: dict[str, str] = {}

    @property
    def source_type(self) -> str:
        return "api"

    async def connect(self) -> bool:
        """Initialize HTTP client with authentication."""
        try:
            self._headers = dict(self._api_config.headers)

            # Set up authentication
            auth_type = self._api_config.auth_type
            auth_config = self._api_config.auth_config

            if auth_type == "bearer":
                token = auth_config.get("token")
                if token:
                    self._headers["Authorization"] = f"Bearer {token}"
            elif auth_type == "api_key":
                key_name = auth_config.get("key_name", "X-API-Key")
                key_value = auth_config.get("key_value")
                key_location = auth_config.get("key_location", "header")
                if key_location == "header" and key_value:
                    self._headers[key_name] = key_value

            self._client = httpx.AsyncClient(
                base_url=self._api_config.base_url,
                headers=self._headers,
                timeout=30.0,
            )

            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
        self._client = None
        self._connected = False

    async def test_connection(self) -> tuple[bool, str]:
        """Test API connection."""
        try:
            if not self._client:
                success = await self.connect()
                if not success:
                    return False, "Failed to initialize HTTP client"

            # Make a test request
            response = await self._client.request(
                method=self._api_config.method,
                url=self._api_config.endpoint,
            )

            if response.status_code in (200, 201):
                return True, "Successfully connected to API"
            elif response.status_code == 401:
                return False, "Authentication failed"
            elif response.status_code == 403:
                return False, "Access forbidden"
            else:
                return False, f"API returned status {response.status_code}"
        except httpx.RequestError as e:
            return False, f"Request error: {str(e)}"

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records from API."""
        if not self._connected:
            await self.connect()

        params = kwargs.get("params", {})
        pagination_type = self._api_config.pagination_type

        if pagination_type:
            async for batch in self._extract_paginated(params, batch_size):
                yield batch
        else:
            records = await self._fetch_single(params)
            if records:
                yield records

    async def _fetch_single(
        self,
        params: dict[str, Any],
    ) -> list[DataRecord]:
        """Fetch a single page of results."""
        response = await self._client.request(
            method=self._api_config.method,
            url=self._api_config.endpoint,
            params=params if self._api_config.method == "GET" else None,
            json=params if self._api_config.method != "GET" else None,
        )

        if response.status_code not in (200, 201):
            return []

        data = response.json()

        # Navigate to data path if specified
        data_path = self._api_config.metadata.get("data_path")
        if data_path:
            for key in data_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])

        if isinstance(data, dict):
            data = [data]
        elif not isinstance(data, list):
            data = []

        return [
            self._create_record(item, raw_data=item)
            for item in data
            if isinstance(item, dict)
        ]

    async def _extract_paginated(
        self,
        params: dict[str, Any],
        batch_size: int,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract records with pagination."""
        pagination_config = self._api_config.pagination_config
        pagination_type = self._api_config.pagination_type

        if pagination_type == "offset":
            offset_param = pagination_config.get("offset_param", "offset")
            limit_param = pagination_config.get("limit_param", "limit")
            offset = 0

            while True:
                page_params = {
                    **params,
                    offset_param: offset,
                    limit_param: batch_size,
                }
                records = await self._fetch_single(page_params)

                if not records:
                    break

                yield records
                offset += len(records)

                if len(records) < batch_size:
                    break

        elif pagination_type == "page":
            page_param = pagination_config.get("page_param", "page")
            page_size_param = pagination_config.get("page_size_param", "page_size")
            page = 1

            while True:
                page_params = {
                    **params,
                    page_param: page,
                    page_size_param: batch_size,
                }
                records = await self._fetch_single(page_params)

                if not records:
                    break

                yield records
                page += 1

                if len(records) < batch_size:
                    break

        elif pagination_type == "cursor":
            cursor_param = pagination_config.get("cursor_param", "cursor")
            cursor_response_path = pagination_config.get("cursor_response_path", "next_cursor")
            cursor = None

            while True:
                page_params = dict(params)
                if cursor:
                    page_params[cursor_param] = cursor

                response = await self._client.request(
                    method=self._api_config.method,
                    url=self._api_config.endpoint,
                    params=page_params if self._api_config.method == "GET" else None,
                    json=page_params if self._api_config.method != "GET" else None,
                )

                if response.status_code not in (200, 201):
                    break

                data = response.json()

                # Get next cursor
                cursor = data
                for key in cursor_response_path.split("."):
                    if isinstance(cursor, dict):
                        cursor = cursor.get(key)
                    else:
                        cursor = None
                        break

                # Extract records
                records = await self._fetch_single(page_params)
                if records:
                    yield records

                if not cursor:
                    break

    async def get_schema(self) -> dict[str, Any]:
        """Get schema from API response."""
        if not self._connected:
            await self.connect()

        records = await self._fetch_single({})
        if not records:
            return {"fields": []}

        fields = set()
        for record in records[:10]:
            fields.update(record.data.keys())

        return {
            "fields": list(fields),
            "sample_count": len(records[:10]),
            "base_url": self._api_config.base_url,
            "endpoint": self._api_config.endpoint,
        }

    async def get_record_count(self) -> int | None:
        """Record count typically not available for APIs."""
        return None


@ExtractorRegistry.register("kavenegar")
class KavenegarExtractor(APIExtractor):
    """
    Specialized extractor for Kavenegar SMS provider.
    Extracts sent SMS history with delivery status.
    """

    KAVENEGAR_BASE_URL = "https://api.kavenegar.com/v1"

    def __init__(self, config: APISourceConfig, tenant_id: str | None = None):
        # Configure for Kavenegar
        config.base_url = self.KAVENEGAR_BASE_URL
        super().__init__(config, tenant_id)
        self._api_key = config.auth_config.get("api_key")

    async def connect(self) -> bool:
        """Initialize Kavenegar client."""
        if not self._api_key:
            return False

        # Kavenegar uses API key in URL path
        self._client = httpx.AsyncClient(
            base_url=f"{self.KAVENEGAR_BASE_URL}/{self._api_key}",
            timeout=30.0,
        )
        self._connected = True
        return True

    async def extract(
        self,
        batch_size: int = 1000,
        **kwargs: Any,
    ) -> AsyncIterator[list[DataRecord]]:
        """Extract SMS records from Kavenegar."""
        if not self._connected:
            await self.connect()

        # Kavenegar endpoints
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        # Get sent messages
        endpoint = "/sms/latestoutbox.json"
        params = {"pagesize": min(batch_size, 3000)}  # Kavenegar max is 3000

        if start_date:
            params["startdate"] = int(start_date.timestamp())
        if end_date:
            params["enddate"] = int(end_date.timestamp())

        response = await self._client.get(endpoint, params=params)

        if response.status_code != 200:
            return

        data = response.json()
        if data.get("return", {}).get("status") != 200:
            return

        entries = data.get("entries", [])

        batch: list[DataRecord] = []
        for entry in entries:
            normalized = self._normalize_sms_record(entry)
            batch.append(self._create_record(normalized, raw_data=entry))

            if len(batch) >= batch_size:
                yield batch
                batch = []

        if batch:
            yield batch

    def _normalize_sms_record(self, data: dict[str, Any]) -> dict[str, Any]:
        """Normalize Kavenegar SMS record to standard format."""
        # Kavenegar status codes
        status_map = {
            1: "queued",
            2: "scheduled",
            4: "sent_to_carrier",
            5: "sent_to_carrier",
            6: "failed",
            10: "delivered",
            11: "undelivered",
            13: "canceled",
            14: "blocked",
            100: "unknown",
        }

        status_code = data.get("status")
        is_delivered = status_code == 10

        # Parse timestamp
        send_date = data.get("date")
        if send_date:
            send_date = datetime.fromtimestamp(send_date)

        return {
            "message_id": data.get("messageid"),
            "phone_number": self._normalize_phone(data.get("receptor")),
            "sender": data.get("sender"),
            "message": data.get("message"),
            "status": status_map.get(status_code, "unknown"),
            "status_code": status_code,
            "cost": data.get("cost"),
            "sent_at": send_date.isoformat() if send_date else None,
            "delivered": is_delivered,
            "raw_data": data,
        }

    def _normalize_phone(self, phone: str | None) -> str | None:
        """Normalize phone number."""
        if not phone:
            return None
        return normalize_phone_strict(str(phone))

    async def get_delivery_status(
        self,
        message_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Get delivery status for specific messages."""
        if not self._connected:
            await self.connect()

        endpoint = "/sms/status.json"
        params = {"messageid": ",".join(message_ids)}

        response = await self._client.get(endpoint, params=params)

        if response.status_code != 200:
            return {}

        data = response.json()
        if data.get("return", {}).get("status") != 200:
            return {}

        results = {}
        for entry in data.get("entries", []):
            msg_id = str(entry.get("messageid"))
            results[msg_id] = self._normalize_sms_record(entry)

        return results

    async def test_connection(self) -> tuple[bool, str]:
        """Test Kavenegar API connection."""
        try:
            if not self._connected:
                success = await self.connect()
                if not success:
                    return False, "API key not configured"

            # Check account info
            response = await self._client.get("/account/info.json")

            if response.status_code != 200:
                return False, f"API returned status {response.status_code}"

            data = response.json()
            if data.get("return", {}).get("status") == 200:
                account = data.get("entries", {})
                return True, f"Connected. Credit: {account.get('remaincredit', 'N/A')}"
            else:
                return False, data.get("return", {}).get("message", "Unknown error")
        except Exception as e:
            return False, f"Connection error: {str(e)}"

