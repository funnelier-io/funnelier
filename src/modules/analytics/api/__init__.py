"""
Analytics API Module
"""

from .routes import router
from .schemas import (
    FunnelMetricsResponse,
    DailyReportResponse,
    SalespersonMetricsResponse,
    AlertResponse,
)

__all__ = [
    "router",
    "FunnelMetricsResponse",
    "DailyReportResponse",
    "SalespersonMetricsResponse",
    "AlertResponse",
]

