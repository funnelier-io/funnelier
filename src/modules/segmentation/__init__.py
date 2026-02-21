"""
Segmentation Module
RFM Analysis and Customer Segmentation
"""

from .domain import (
    ContactRFMProfile,
    RFMAnalysisResult,
    RFMConfig,
    RFMScore,
    RFMSegment,
    SEGMENT_RECOMMENDATIONS,
    SegmentRecommendation,
    SegmentSummary,
    RFMCalculationService,
    SegmentRecommendationService,
)

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

