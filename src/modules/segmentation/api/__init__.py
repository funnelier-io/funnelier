"""
Segmentation API Module
"""

from .routes import router
from .schemas import (
    RFMProfileResponse,
    SegmentDistributionResponse,
    SegmentRecommendationResponse,
)

__all__ = [
    "router",
    "RFMProfileResponse",
    "SegmentDistributionResponse",
    "SegmentRecommendationResponse",
]

