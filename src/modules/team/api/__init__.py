"""
Team API Module
"""

from .routes import router
from .schemas import (
    SalespersonResponse,
    SalespersonListResponse,
    CreateSalespersonRequest,
    SalespersonPerformanceResponse,
)

__all__ = [
    "router",
    "SalespersonResponse",
    "SalespersonListResponse",
    "CreateSalespersonRequest",
    "SalespersonPerformanceResponse",
]

