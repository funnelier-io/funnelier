"""
Leads Module - Domain Layer
"""

from .entities import Contact, LeadCategory, LeadSourceConfig
from .repositories import IContactRepository, ILeadCategoryRepository, ILeadSourceRepository

__all__ = [
    "Contact",
    "LeadCategory",
    "LeadSourceConfig",
    "IContactRepository",
    "ILeadCategoryRepository",
    "ILeadSourceRepository",
]

