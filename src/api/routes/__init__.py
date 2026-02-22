"""
API Routes Module

Exports all API routers for the application.
"""

# Import actual routers from modules
from src.modules.auth.api import router as auth_router
from src.modules.leads.api import router as leads_router
from src.modules.communications.api import router as communications_router
from src.modules.sales.api import router as sales_router
from src.modules.analytics.api import router as analytics_router
from src.modules.segmentation.api import router as segments_router
from src.modules.campaigns.api import router as campaigns_router
from src.modules.team.api import router as team_router
from src.modules.tenants.api import router as tenants_router

__all__ = [
    "auth_router",
    "leads_router",
    "communications_router",
    "sales_router",
    "analytics_router",
    "segments_router",
    "campaigns_router",
    "team_router",
    "tenants_router",
]

