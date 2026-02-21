"""
Web Dashboard Application

FastAPI application for serving the web dashboard.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from src.core.config import settings


def create_dashboard_app() -> FastAPI:
    """Create and configure the dashboard FastAPI application."""

    app = FastAPI(
        title=f"{settings.app_name} Dashboard",
        description="Web Dashboard for Marketing Funnel Analytics",
        version=settings.app_version,
        docs_url=None,
        redoc_url=None,
    )

    # Setup static files and templates
    static_path = Path(__file__).parent / "static"
    templates_path = Path(__file__).parent / "templates"

    if static_path.exists():
        app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

    # Register dashboard routes
    from .routes import dashboard_router
    app.include_router(dashboard_router)

    return app


# Templates instance for use in routes
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

