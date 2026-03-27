"""
Simple test script to run Funnelier API without database dependency.
"""

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events - without database."""
    print("Starting Funnelier API (test mode - no database)")
    yield
    print("Shutting down Funnelier API")


def create_test_app() -> FastAPI:
    """Create and configure the FastAPI application for testing."""

    app = FastAPI(
        title=settings.app_name,
        description="Marketing Funnel Analytics Platform (Test Mode)",
        version=settings.app_version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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
                "message": str(exc),
            },
        )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": settings.app_version,
            "environment": settings.env,
            "mode": "test",
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
                "communications": "/api/v1/communications",
                "sales": "/api/v1/sales",
                "analytics": "/api/v1/analytics",
                "segments": "/api/v1/segments",
                "campaigns": "/api/v1/campaigns",
                "team": "/api/v1/team",
                "tenants": "/api/v1/tenants",
            },
        }

    # Register routers
    from src.api.routes import (
        leads_router,
        communications_router,
        sales_router,
        analytics_router,
        segments_router,
        campaigns_router,
        team_router,
        tenants_router,
    )

    # API Routes
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
app = create_test_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "scripts.run_test:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )

