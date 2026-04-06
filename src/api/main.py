"""
Funnelier API - Main Application
FastAPI application entry point
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.infrastructure.database import close_database, init_database

logger = logging.getLogger(__name__)


async def _seed_default_tenant():
    """Create default tenant and admin user if they don't exist."""
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import TenantModel, TenantUserModel

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select

        tenant_id = UUID("00000000-0000-0000-0000-000000000001")

        # Seed default tenant
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            tenant = TenantModel(
                id=tenant_id,
                name="فانلیر",
                slug="funnelier-default",
                email="admin@funnelier.ir",
                plan="professional",
                max_contacts=100000,
                max_sms_per_month=50000,
                max_users=20,
            )
            session.add(tenant)
            await session.flush()

        # Seed default admin user
        stmt = select(TenantUserModel).where(TenantUserModel.username == "admin")
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            admin_user = TenantUserModel(
                id=UUID("00000000-0000-0000-0000-000000000002"),
                tenant_id=tenant_id,
                email="admin@funnelier.ir",
                username="admin",
                name="مدیر سیستم",
                password_hash=pwd_context.hash("admin1234"),
                role="super_admin",
                is_active=True,
                is_approved=True,
                permissions=[],
            )
            session.add(admin_user)

        await session.commit()


_redis_listener_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global _redis_listener_task

    # Startup
    await init_database()
    await _seed_default_tenant()

    # Start WebSocket Redis pub/sub listener (non-blocking)
    try:
        from src.api.websocket import start_redis_listener
        _redis_listener_task = asyncio.create_task(start_redis_listener())
        logger.info("WebSocket Redis listener task started")
    except Exception as e:
        logger.warning(f"Could not start WebSocket Redis listener: {e}")

    yield

    # Shutdown
    if _redis_listener_task and not _redis_listener_task.done():
        _redis_listener_task.cancel()
        try:
            await _redis_listener_task
        except asyncio.CancelledError:
            pass
    await close_database()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title=settings.app_name,
        description="Marketing Funnel Analytics Platform",
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "message": str(exc) if settings.debug else "An error occurred",
            },
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.env,
        }

    # API info endpoint
    @app.get("/api/v1")
    async def api_info() -> dict[str, Any]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "description": "Marketing Funnel Analytics Platform",
            "endpoints": {
                "leads": "/api/v1/leads",
                "contacts": "/api/v1/leads/contacts",
                "communications": "/api/v1/communications",
                "sales": "/api/v1/sales",
                "analytics": "/api/v1/analytics",
                "segments": "/api/v1/segments",
                "campaigns": "/api/v1/campaigns",
                "team": "/api/v1/team",
                "tenants": "/api/v1/tenants",
                "auth": "/api/v1/auth",
                "import": "/api/v1/import",
                "search": "/api/v1/search",
                "tasks": "/api/v1/tasks/{task_id}",
                "webhooks": "/api/v1/webhooks",
                "export": "/api/v1/export",
                "notifications": "/api/v1/notifications",
                "audit": "/api/v1/audit",
                "websocket": "/ws",
            },
        }

    # Register routers
    from src.api.routes import (
        auth_router,
        import_router,
        leads_router,
        communications_router,
        sales_router,
        analytics_router,
        segments_router,
        campaigns_router,
        team_router,
        tenants_router,
        export_router,
        notifications_router,
        audit_router,
    )
    from src.api.search import router as search_router
    from src.api.websocket import ws_router
    from src.modules.auth.api.routes import require_auth
    from src.modules.communications.api.webhook_routes import webhook_router
    from src.modules.sales.api.erp_routes import router as erp_router

    # WebSocket & Task Status
    app.include_router(ws_router, tags=["WebSocket"])

    # Auth Routes (no auth required — login/register are public)
    app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])

    # Webhook Routes (no auth — validated via shared secret)
    app.include_router(webhook_router, prefix="/api/v1", tags=["Webhooks"])

    # Protected API Routes — require authenticated user
    app.include_router(
        import_router, prefix="/api/v1",
        tags=["Import"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        leads_router, prefix="/api/v1/leads",
        tags=["Leads"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        communications_router, prefix="/api/v1/communications",
        tags=["Communications"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        sales_router, prefix="/api/v1/sales",
        tags=["Sales"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        analytics_router, prefix="/api/v1/analytics",
        tags=["Analytics"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        segments_router, prefix="/api/v1/segments",
        tags=["Segments"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        campaigns_router, prefix="/api/v1",
        tags=["Campaigns"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        team_router, prefix="/api/v1",
        tags=["Team"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        tenants_router, prefix="/api/v1",
        tags=["Tenants"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        search_router, prefix="/api/v1",
        tags=["Search"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        erp_router, prefix="/api/v1/sales",
        tags=["ERP Sync"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        export_router, prefix="/api/v1",
        tags=["Export & Reporting"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        notifications_router, prefix="/api/v1",
        tags=["Notifications"], dependencies=[Depends(require_auth)],
    )
    app.include_router(
        audit_router, prefix="/api/v1",
        tags=["Audit Trail"], dependencies=[Depends(require_auth)],
    )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
    )

