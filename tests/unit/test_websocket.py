"""
Unit Tests for WebSocket Module

Tests the ConnectionManager and WebSocket endpoint logic.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.websocket import ConnectionManager


# ─── ConnectionManager Tests ────────────────────────────────────────────────

class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager."""

    @pytest.fixture
    def manager(self):
        return ConnectionManager()

    def _make_ws(self, connected=True):
        """Create a mock WebSocket."""
        from starlette.websockets import WebSocketState
        ws = AsyncMock()
        ws.client_state = WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_global(self, manager):
        ws = self._make_ws()
        await manager.connect(ws, tenant_id=None)
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_connect_with_tenant(self, manager):
        ws = self._make_ws()
        await manager.connect(ws, tenant_id="tenant-1")
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_global(self, manager):
        ws = self._make_ws()
        await manager.connect(ws, tenant_id=None)
        manager.disconnect(ws, tenant_id=None)
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_tenant(self, manager):
        ws = self._make_ws()
        await manager.connect(ws, tenant_id="tenant-1")
        manager.disconnect(ws, tenant_id="tenant-1")
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_broadcast_to_global(self, manager):
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast({"type": "test"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()

        data = json.loads(ws1.send_text.call_args[0][0])
        assert data["type"] == "test"

    @pytest.mark.asyncio
    async def test_broadcast_to_tenant(self, manager):
        ws_global = self._make_ws()
        ws_tenant = self._make_ws()
        await manager.connect(ws_global)
        await manager.connect(ws_tenant, tenant_id="t1")

        await manager.broadcast({"type": "test"}, tenant_id="t1")

        # Both global and tenant-specific should receive
        ws_global.send_text.assert_called_once()
        ws_tenant.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_handles_disconnected(self, manager):
        ws = self._make_ws()
        ws.send_text.side_effect = Exception("disconnected")
        await manager.connect(ws)

        await manager.broadcast({"type": "test"})

        # Should remove broken connection
        assert manager.connection_count == 0

    @pytest.mark.asyncio
    async def test_multiple_tenants_isolated(self, manager):
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        await manager.connect(ws1, tenant_id="t1")
        await manager.connect(ws2, tenant_id="t2")

        assert manager.connection_count == 2

        manager.disconnect(ws1, tenant_id="t1")
        assert manager.connection_count == 1

    @pytest.mark.asyncio
    async def test_empty_broadcast(self, manager):
        # Should not raise even with no connections
        await manager.broadcast({"type": "test"})

    @pytest.mark.asyncio
    async def test_connection_count_mixed(self, manager):
        ws1 = self._make_ws()
        ws2 = self._make_ws()
        ws3 = self._make_ws()
        await manager.connect(ws1)
        await manager.connect(ws2, tenant_id="t1")
        await manager.connect(ws3, tenant_id="t1")
        assert manager.connection_count == 3

