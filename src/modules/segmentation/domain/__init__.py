"""
Segmentation Module - Domain Layer
RFM Analysis and Customer Segmentation
"""

from src.core.domain import RFMSegment

from .entities import (
    ContactRFMProfile,
    RFMAnalysisResult,
    RFMConfig,
    RFMScore,
    SEGMENT_RECOMMENDATIONS,
    SegmentRecommendation,
    SegmentSummary,
)
from .services import RFMCalculationService, SegmentRecommendationService

__all__ = [
    # Entities
    "RFMScore",
    "RFMSegment",
    "ContactRFMProfile",
    "RFMConfig",
    "SegmentRecommendation",
    "SEGMENT_RECOMMENDATIONS",
    "SegmentSummary",
    "RFMAnalysisResult",
    # Services
    "RFMCalculationService",
    "SegmentRecommendationService",
]

