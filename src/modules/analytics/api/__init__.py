"""
Analytics API Module
"""

from .routes import router
from .predictive_routes import router as predictive_router
from .schemas import (
    FunnelMetricsResponse,
    DailyReportResponse,
    SalespersonMetricsResponse,
    AlertResponse,
)

# Mount predictive sub-router onto the main analytics router
router.include_router(predictive_router)

__all__ = [
    "router",
    "predictive_router",
    "FunnelMetricsResponse",
    "DailyReportResponse",
    "SalespersonMetricsResponse",
    "AlertResponse",
]

