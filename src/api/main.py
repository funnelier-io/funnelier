"""
Funnelier API - Main Application
FastAPI application entry point
"""

from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings
from src.infrastructure.database import close_database, init_database


async def _seed_default_tenant():
    """Create default tenant if it doesn't exist."""
    from src.infrastructure.database.session import get_session_factory
    from src.infrastructure.database.models.tenants import TenantModel

    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import select
        stmt = select(TenantModel).where(
            TenantModel.id == UUID("00000000-0000-0000-0000-000000000001")
        )
        result = await session.execute(stmt)
        if not result.scalar_one_or_none():
            tenant = TenantModel(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="فانلیر",
                slug="funnelier-default",
                email="admin@funnelier.ir",
                plan="professional",
                max_contacts=100000,
                max_sms_per_month=50000,
                max_users=20,
            )
            session.add(tenant)
            await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_database()
    await _seed_default_tenant()
    yield
    # Shutdown
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
            },
        }

    # Register routers
    from src.api.routes import (
        auth_router,
        leads_router,
        communications_router,
        sales_router,
        analytics_router,
        segments_router,
        campaigns_router,
        team_router,
        tenants_router,
    )
    from src.web.routes import dashboard_router

    # Web Dashboard
    app.include_router(dashboard_router, tags=["Dashboard"])

    # API Routes
    app.include_router(auth_router, prefix="/api/v1", tags=["Auth"])
    app.include_router(leads_router, prefix="/api/v1/leads", tags=["Leads"])
    app.include_router(communications_router, prefix="/api/v1/communications", tags=["Communications"])
    app.include_router(sales_router, prefix="/api/v1/sales", tags=["Sales"])
    app.include_router(analytics_router, prefix="/api/v1/analytics", tags=["Analytics"])
    app.include_router(segments_router, prefix="/api/v1/segments", tags=["Segments"])
    app.include_router(campaigns_router, prefix="/api/v1", tags=["Campaigns"])
    app.include_router(team_router, prefix="/api/v1", tags=["Team"])
    app.include_router(tenants_router, prefix="/api/v1", tags=["Tenants"])

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

