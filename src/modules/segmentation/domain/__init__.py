"""
Segmentation Module - Domain Layer
"""

from .entities import (
    ContactRFMScore,
    ProductRecommendation,
    RFMConfig,
    SegmentDefinition,
    SegmentStats,
    TemplateRecommendation,
)
from .services import RFMCalculationService, SegmentRecommendationService

__all__ = [
    "RFMConfig",
    "ContactRFMScore",
    "SegmentDefinition",
    "SegmentStats",
    "ProductRecommendation",
    "TemplateRecommendation",
    "RFMCalculationService",
    "SegmentRecommendationService",
]

