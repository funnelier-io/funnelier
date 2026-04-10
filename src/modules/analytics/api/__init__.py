"""
Analytics API Module
"""

from .routes import router
from .predictive_routes import router as predictive_router
from .journey_routes import router as journey_router
from .schemas import (
    FunnelMetricsResponse,
    DailyReportResponse,
    SalespersonMetricsResponse,
    AlertResponse,
)

# Mount sub-routers onto the main analytics router
router.include_router(predictive_router)
router.include_router(journey_router)

__all__ = [
    "router",
    "predictive_router",
    "journey_router",
    "FunnelMetricsResponse",
    "DailyReportResponse",
    "SalespersonMetricsResponse",
    "AlertResponse",
]

