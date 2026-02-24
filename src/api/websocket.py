"""
WebSocket Support

Provides real-time event streaming to dashboard clients via WebSocket.
Uses Redis pub/sub to receive events published by Celery tasks.
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

ws_router = APIRouter()


class ConnectionManager:
    """
    Manages active WebSocket connections grouped by tenant.
    Supports broadcasting events to all connected clients of a tenant.
    """

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._global_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, tenant_id: str | None = None):
        """Accept and register a WebSocket connection."""
        await websocket.accept()
        if tenant_id:
            if tenant_id not in self._connections:
                self._connections[tenant_id] = []
            self._connections[tenant_id].append(websocket)
        else:
            self._global_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, tenant_id: str | None = None):
        """Remove a WebSocket connection."""
        if tenant_id and tenant_id in self._connections:
            self._connections[tenant_id] = [
                ws for ws in self._connections[tenant_id] if ws != websocket
            ]
            if not self._connections[tenant_id]:
                del self._connections[tenant_id]
        else:
            self._global_connections = [
                ws for ws in self._global_connections if ws != websocket
            ]

    async def broadcast(self, message: dict[str, Any],
                        tenant_id: str | None = None):
        """Broadcast a message to all connections (optionally filtered by tenant)."""
        data = json.dumps(message, default=str)

        targets = list(self._global_connections)
        if tenant_id and tenant_id in self._connections:
            targets += self._connections[tenant_id]

        disconnected = []
        for ws in targets:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_text(data)
            except Exception:
                disconnected.append(ws)

        # Clean up broken connections
        for ws in disconnected:
            self.disconnect(ws, tenant_id)

    @property
    def connection_count(self) -> int:
        """Total number of active connections."""
        count = len(self._global_connections)
        for conns in self._connections.values():
            count += len(conns)
        return count


# Global connection manager instance
manager = ConnectionManager()


# ─── WebSocket Endpoint ──────────────────────────────────────────────────────

@ws_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    tenant_id: str | None = Query(None),
):
    """
    WebSocket endpoint for real-time event streaming.

    Clients connect with optional tenant_id query parameter to receive
    tenant-specific events. Events include:
    - import_started / import_completed
    - batch_import_completed
    - funnel_snapshot_completed
    - rfm_calculation_completed
    - daily_report_generated
    - alerts_triggered
    - sync_completed
    """
    await manager.connect(websocket, tenant_id)

    try:
        # Keep connection alive; receive pings/commands from client
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0)

                # Handle client commands
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    elif msg.get("type") == "subscribe":
                        # Allow client to subscribe to specific tenant
                        new_tenant = msg.get("tenant_id")
                        if new_tenant:
                            manager.disconnect(websocket, tenant_id)
                            tenant_id = new_tenant
                            await manager.connect(websocket, tenant_id)
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_text(
                        json.dumps({"type": "keepalive"}))
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket, tenant_id)


# ─── Redis Pub/Sub Listener ─────────────────────────────────────────────────

async def start_redis_listener():
    """
    Start a background task that listens to Redis pub/sub channel
    and broadcasts events to WebSocket clients.

    Should be called during app startup.
    """
    try:
        import redis.asyncio as aioredis
        from src.core.config import settings

        redis_client = aioredis.from_url(settings.redis.url)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe("funnelier:ws:events")

        logger.info("WebSocket Redis listener started")

        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    tenant_id = data.get("payload", {}).get("tenant_id")
                    await manager.broadcast(data, tenant_id)
                except Exception as e:
                    logger.warning(f"WebSocket broadcast error: {e}")

    except Exception as e:
        logger.warning(f"Redis pub/sub listener failed: {e}")


# ─── Task Status Endpoint ───────────────────────────────────────────────────

@ws_router.get("/api/v1/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get the status and result of a Celery task."""
    from src.infrastructure.messaging.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "status": result.status,
        "ready": result.ready(),
    }

    if result.ready():
        if result.successful():
            response["result"] = result.result
        elif result.failed():
            response["error"] = str(result.result)
    elif result.status == "PROGRESS":
        response["progress"] = result.info

    return response


@ws_router.get("/api/v1/ws/status")
async def ws_status():
    """Get WebSocket connection status."""
    return {
        "connections": manager.connection_count,
        "status": "active",
    }

