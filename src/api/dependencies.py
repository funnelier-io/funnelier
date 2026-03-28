"""
API Dependency Injection

FastAPI dependency providers for database sessions, repositories, and services.
Centralizes tenant resolution and provides graceful fallback when DB is unavailable.
"""

from typing import Annotated, AsyncGenerator
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_session_factory

# Default tenant for development/testing
DEFAULT_TENANT_ID = UUID("00000000-0000-0000-0000-000000000001")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_tenant_id(
    x_tenant_id: str | None = Header(None, alias="X-Tenant-ID"),
) -> UUID:
    """
    Extract tenant ID from request header.
    Falls back to default tenant for development.
    """
    if x_tenant_id:
        try:
            return UUID(x_tenant_id)
        except ValueError:
            pass
    return DEFAULT_TENANT_ID


# ──────────────────────── Auth Dependencies ─────────────────────────
# Re-export auth dependencies from the auth module for use across all routes.

def get_current_user():
    """
    Get current authenticated user from JWT token.
    Import lazily to avoid circular imports.
    """
    from src.modules.auth.api.routes import get_current_user as _get_current_user
    return _get_current_user


def require_auth():
    """
    Require authenticated user.
    Import lazily to avoid circular imports.
    """
    from src.modules.auth.api.routes import require_auth as _require_auth
    return _require_auth


def require_admin():
    """
    Require admin role.
    Import lazily to avoid circular imports.
    """
    from src.modules.auth.api.routes import require_admin as _require_admin
    return _require_admin


# ──────────────────────── Leads Repositories ────────────────────────


async def get_contact_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.leads.infrastructure.repositories import ContactRepository
    return ContactRepository(session, tenant_id)


async def get_category_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.leads.infrastructure.repositories import LeadCategoryRepository
    return LeadCategoryRepository(session, tenant_id)


async def get_lead_source_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.leads.infrastructure.repositories import LeadSourceRepository
    return LeadSourceRepository(session, tenant_id)


# ──────────────────── Communications Repositories ───────────────────


async def get_sms_log_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.communications.infrastructure.repositories import SMSLogRepository
    return SMSLogRepository(session, tenant_id)


async def get_call_log_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.communications.infrastructure.repositories import CallLogRepository
    return CallLogRepository(session, tenant_id)


async def get_sms_template_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.communications.infrastructure.repositories import SMSTemplateRepository
    return SMSTemplateRepository(session, tenant_id)


# ──────────────────────── Sales Repositories ────────────────────────


async def get_product_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.sales.infrastructure.repositories import ProductRepository
    return ProductRepository(session, tenant_id)


async def get_invoice_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.sales.infrastructure.repositories import InvoiceRepository
    return InvoiceRepository(session, tenant_id)


async def get_payment_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.sales.infrastructure.repositories import PaymentRepository
    return PaymentRepository(session, tenant_id)


# ──────────────────── Analytics Repositories ────────────────────


async def get_funnel_snapshot_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.analytics.infrastructure.repositories import FunnelSnapshotRepository
    return FunnelSnapshotRepository(session, tenant_id)


async def get_alert_rule_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.analytics.infrastructure.repositories import AlertRuleRepository
    return AlertRuleRepository(session, tenant_id)


async def get_alert_instance_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.analytics.infrastructure.repositories import AlertInstanceRepository
    return AlertInstanceRepository(session, tenant_id)


async def get_import_log_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.analytics.infrastructure.repositories import ImportLogRepository
    return ImportLogRepository(session, tenant_id)


# ──────────────────── Campaign Repositories ─────────────────────


async def get_campaign_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.campaigns.infrastructure.repositories import CampaignRepository
    return CampaignRepository(session, tenant_id)


async def get_campaign_recipient_repository(
    session: AsyncSession = Depends(get_db_session),
    tenant_id: UUID = Depends(get_current_tenant_id),
):
    from src.modules.campaigns.infrastructure.repositories import CampaignRecipientRepository
    return CampaignRecipientRepository(session, tenant_id)


