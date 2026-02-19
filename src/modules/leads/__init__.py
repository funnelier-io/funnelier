"""
Leads Module
"""

from .domain import (
    Contact,
    LeadCategory,
    LeadSourceConfig,
    IContactRepository,
    ILeadCategoryRepository,
    ILeadSourceRepository,
)

__all__ = [
    "Contact",
    "LeadCategory",
    "LeadSourceConfig",
    "IContactRepository",
    "ILeadCategoryRepository",
    "ILeadSourceRepository",
]

