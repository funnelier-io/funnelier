"""
Integration test configuration.

Uses session-scoped event loop to share DB engine across all tests.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def app():
    """Create app once for all integration tests, resetting DB engine."""
    # Reset the engine so it's created in the session event loop
    from src.infrastructure.database import session as db_session
    db_session._engine = None
    db_session._session_factory = None

    from src.api.main import create_app
    _app = create_app()
    yield _app

    # Cleanup engine
    if db_session._engine:
        await db_session._engine.dispose()


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def client(app):
    """Session-scoped async HTTP client (unauthenticated)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def admin_headers(client):
    """Login as default admin and return Authorization headers dict."""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "admin1234",
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def authed_client(app, admin_headers):
    """Session-scoped async HTTP client with admin auth headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers=admin_headers,
    ) as ac:
        yield ac
