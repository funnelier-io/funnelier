"""
Campaigns API Routes

FastAPI routes for campaign management — wired to PostgreSQL via CampaignRepository.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.dependencies import (
    get_current_tenant_id,
    get_campaign_repository,
    get_campaign_recipient_repository,
    get_campaign_workflow_service,
)
from src.modules.campaigns.infrastructure.repositories import (
    CampaignRepository,
    CampaignRecipientRepository,
)
from src.modules.campaigns.application.campaign_workflow_service import (
    CampaignWorkflowService,
)

from .schemas import (
    ABTestResultsResponse,
    CampaignListResponse,
    CampaignRecipientResponse,
    CampaignRecipientsListResponse,
    CampaignResponse,
    CampaignStatsResponse,
    CampaignTargetingSchema,
    CreateABTestCampaignRequest,
    CreateCampaignRequest,
    UpdateCampaignRequest,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


# ============================================================================
# Helpers
# ============================================================================

def _model_to_response(model) -> CampaignResponse:
    """Convert CampaignModel to CampaignResponse."""
    return CampaignResponse(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        description=model.description,
        campaign_type=model.campaign_type or "sms",
        template_id=model.template_id,
        content=model.message_content,
        targeting=CampaignTargetingSchema(**(model.targeting or {})) if model.targeting else CampaignTargetingSchema(),
        schedule=model.schedule,
        status=model.status,
        process_instance_id=getattr(model, "process_instance_id", None),
        is_active=model.is_active,
        total_recipients=model.total_recipients,
        sent_count=model.total_sent,
        delivered_count=model.total_delivered,
        failed_count=model.total_failed,
        response_count=model.total_calls_received,
        conversion_count=model.total_conversions,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
        metadata=model.metadata_ or {},
    )


# ============================================================================
# Campaign CRUD Endpoints
# ============================================================================

@router.get("", response_model=CampaignListResponse)
async def list_campaigns(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    campaign_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
):
    """List campaigns with filtering."""
    skip = (page - 1) * page_size
    models, total = await repo.list_campaigns(
        skip=skip,
        limit=page_size,
        status=status,
        campaign_type=campaign_type,
        search=search,
    )

    return CampaignListResponse(
        campaigns=[_model_to_response(m) for m in models],
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=CampaignResponse, status_code=201)
async def create_campaign(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateCampaignRequest,
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Create a new campaign."""
    from src.infrastructure.database.models.campaigns import CampaignModel

    model = CampaignModel(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        campaign_type=request.campaign_type,
        template_id=request.template_id,
        message_content=request.content,
        targeting=request.targeting.model_dump() if request.targeting else {},
        schedule=request.schedule.model_dump(mode="json") if request.schedule else None,
        status="draft",
        is_active=request.is_active,
        metadata_=request.metadata,
    )
    repo._session.add(model)
    await repo._session.flush()
    await repo._session.refresh(model)

    return _model_to_response(model)


@router.get("/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Get campaign by ID."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _model_to_response(model)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: UpdateCampaignRequest,
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Update a campaign (only draft/scheduled)."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if model.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail="Only draft/scheduled campaigns can be edited")

    if request.name is not None:
        model.name = request.name
    if request.description is not None:
        model.description = request.description
    if request.template_id is not None:
        model.template_id = request.template_id
    if request.content is not None:
        model.message_content = request.content
    if request.targeting is not None:
        model.targeting = request.targeting.model_dump()
    if request.schedule is not None:
        model.schedule = request.schedule.model_dump(mode="json")
    if request.is_active is not None:
        model.is_active = request.is_active
    if request.metadata is not None:
        model.metadata_ = request.metadata

    merged = await repo._session.merge(model)
    await repo._session.flush()
    await repo._session.refresh(merged)
    return _model_to_response(merged)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Delete a campaign."""
    exists = await repo.exists(campaign_id)
    if not exists:
        raise HTTPException(status_code=404, detail="Campaign not found")
    await repo.delete(campaign_id)


# ============================================================================
# Campaign Actions
# ============================================================================

@router.post("/{campaign_id}/start", response_model=CampaignResponse)
async def start_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Start a campaign."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if model.status not in ("draft", "scheduled"):
        raise HTTPException(status_code=400, detail=f"Cannot start campaign in status '{model.status}'")

    updated = await repo.update_status(
        campaign_id, "running", started_at=datetime.utcnow()
    )
    return _model_to_response(updated)


@router.post("/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    workflow: CampaignWorkflowService = Depends(get_campaign_workflow_service),
):
    """Pause a running campaign (suspends Camunda process when enabled)."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if model.status != "running":
        raise HTTPException(status_code=400, detail="Can only pause running campaigns")

    updated = await workflow.pause_campaign(campaign_id)
    return _model_to_response(updated)


@router.post("/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    workflow: CampaignWorkflowService = Depends(get_campaign_workflow_service),
):
    """Resume a paused campaign (activates Camunda process when enabled)."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if model.status != "paused":
        raise HTTPException(status_code=400, detail="Can only resume paused campaigns")

    updated = await workflow.resume_campaign(campaign_id)
    return _model_to_response(updated)


@router.post("/{campaign_id}/cancel", response_model=CampaignResponse)
async def cancel_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    workflow: CampaignWorkflowService = Depends(get_campaign_workflow_service),
):
    """Cancel a campaign (deletes Camunda process when enabled)."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")
    if model.status == "completed":
        raise HTTPException(status_code=400, detail="Cannot cancel completed campaigns")

    updated = await workflow.cancel_campaign(campaign_id)
    return _model_to_response(updated)


@router.post("/{campaign_id}/duplicate", response_model=CampaignResponse)
async def duplicate_campaign(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    new_name: str | None = Query(default=None),
):
    """Duplicate a campaign."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")

    from src.infrastructure.database.models.campaigns import CampaignModel

    dup = CampaignModel(
        id=uuid4(),
        tenant_id=tenant_id,
        name=new_name or f"{model.name} (کپی)",
        description=model.description,
        campaign_type=model.campaign_type,
        template_id=model.template_id,
        message_content=model.message_content,
        targeting=model.targeting,
        schedule=model.schedule,
        target_segment=model.target_segment,
        target_filters=model.target_filters,
        status="draft",
        is_active=True,
        metadata_=model.metadata_ or {},
    )
    repo._session.add(dup)
    await repo._session.flush()
    await repo._session.refresh(dup)
    return _model_to_response(dup)


# ============================================================================
# Campaign Statistics & Recipients
# ============================================================================

@router.get("/{campaign_id}/stats", response_model=CampaignStatsResponse)
async def get_campaign_stats(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Get campaign statistics."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")

    sent = model.total_sent or 0
    delivered = model.total_delivered or 0
    failed = model.total_failed or 0
    responses = model.total_calls_received or 0
    conversions = model.total_conversions or 0
    revenue = model.total_revenue or 0
    cost = model.actual_cost or model.estimated_cost or 0

    return CampaignStatsResponse(
        campaign_id=model.id,
        campaign_name=model.name,
        status=model.status,
        total_recipients=model.total_recipients,
        sent_count=sent,
        delivered_count=delivered,
        delivery_rate=delivered / sent if sent else 0.0,
        failed_count=failed,
        response_count=responses,
        response_rate=responses / delivered if delivered else 0.0,
        conversion_count=conversions,
        conversion_rate=conversions / delivered if delivered else 0.0,
        cost=cost,
        revenue=revenue,
        roi=(revenue - cost) / cost if cost else 0.0,
        by_segment=[],
        by_day=[],
    )


@router.get("/{campaign_id}/recipients", response_model=CampaignRecipientsListResponse)
async def get_campaign_recipients(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    recip_repo: CampaignRecipientRepository = Depends(get_campaign_recipient_repository),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
):
    """Get campaign recipients."""
    campaign = await repo.get_model(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    skip = (page - 1) * page_size
    models, total = await recip_repo.get_by_campaign(
        campaign_id, skip=skip, limit=page_size, status=status,
    )

    return CampaignRecipientsListResponse(
        recipients=[
            CampaignRecipientResponse(
                contact_id=m.contact_id,
                phone_number=m.phone_number,
                name=m.name,
                segment=m.segment,
                status=m.status,
                sent_at=m.sent_at,
                delivered_at=m.delivered_at,
                responded_at=m.responded_at,
                converted_at=m.converted_at,
            )
            for m in models
        ],
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{campaign_id}/preview-recipients", response_model=dict)
async def preview_campaign_recipients(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    limit: int = Query(default=100, ge=1, le=1000),
):
    """Preview recipients that match campaign targeting."""
    campaign = await repo.get_model(campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    # TODO: query contacts matching targeting filters
    return {
        "total_matching": 0,
        "sample_recipients": [],
    }


# ============================================================================
# A/B Testing
# ============================================================================

@router.post("/ab-test", response_model=CampaignResponse, status_code=201)
async def create_ab_test_campaign(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateABTestCampaignRequest,
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Create an A/B test campaign."""
    from src.infrastructure.database.models.campaigns import CampaignModel

    model = CampaignModel(
        id=uuid4(),
        tenant_id=tenant_id,
        name=request.name,
        description=request.description,
        campaign_type=request.campaign_type,
        template_id=request.template_id,
        message_content=request.content,
        targeting=request.targeting.model_dump() if request.targeting else {},
        schedule=request.schedule.model_dump(mode="json") if request.schedule else None,
        status="draft",
        is_active=request.is_active,
        is_ab_test=True,
        metadata_={**(request.metadata or {}), "ab_test_config": request.ab_test_config.model_dump()},
    )
    repo._session.add(model)
    await repo._session.flush()
    await repo._session.refresh(model)
    return _model_to_response(model)


@router.get("/{campaign_id}/ab-test-results", response_model=ABTestResultsResponse)
async def get_ab_test_results(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
):
    """Get A/B test results."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return ABTestResultsResponse(
        campaign_id=campaign_id,
        variants=(model.metadata_ or {}).get("ab_test_variants", []),
        winner=None,
        confidence_level=None,
        test_completed=model.status == "completed",
    )


@router.post("/{campaign_id}/select-winner", response_model=dict)
async def select_ab_test_winner(
    campaign_id: UUID,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: CampaignRepository = Depends(get_campaign_repository),
    variant_name: str = Query(...),
):
    """Manually select A/B test winner."""
    model = await repo.get_model(campaign_id)
    if not model:
        raise HTTPException(status_code=404, detail="Campaign not found")

    return {
        "campaign_id": str(campaign_id),
        "selected_winner": variant_name,
        "status": "winner_selected",
    }


# ============================================================================
# Campaign Templates & Suggestions
# ============================================================================

@router.get("/suggestions/for-segment/{segment}", response_model=dict)
async def get_campaign_suggestions_for_segment(
    segment: str,
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get campaign suggestions for an RFM segment."""
    suggestions = {
        "champions": {
            "campaign_types": ["loyalty_reward", "referral", "vip_access"],
            "message_tone": "exclusive",
            "discount_range": "0-5%",
            "frequency": "bi-weekly",
        },
        "loyal": {
            "campaign_types": ["cross_sell", "upsell", "loyalty_program"],
            "message_tone": "appreciation",
            "discount_range": "5-10%",
            "frequency": "weekly",
        },
        "at_risk": {
            "campaign_types": ["win_back", "special_offer", "feedback_request"],
            "message_tone": "urgent",
            "discount_range": "15-25%",
            "frequency": "immediate",
        },
        "hibernating": {
            "campaign_types": ["reactivation", "big_discount", "new_product"],
            "message_tone": "reminder",
            "discount_range": "20-30%",
            "frequency": "once",
        },
        "lost": {
            "campaign_types": ["last_chance", "survey"],
            "message_tone": "reconnect",
            "discount_range": "25-40%",
            "frequency": "one-time",
        },
    }

    return suggestions.get(segment, {
        "campaign_types": ["general"],
        "message_tone": "neutral",
        "discount_range": "10-15%",
        "frequency": "weekly",
    })


@router.get("/templates/recommended", response_model=list)
async def get_recommended_templates(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    segment: str | None = Query(default=None),
    campaign_type: str | None = Query(default=None),
):
    """Get recommended templates for campaign."""
    from src.api.dependencies import get_sms_template_repository, get_db_session
    from src.infrastructure.database.models.communications import SMSTemplateModel
    from sqlalchemy import select
    from src.infrastructure.database.session import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = (
            select(SMSTemplateModel)
            .where(SMSTemplateModel.tenant_id == tenant_id)
            .where(SMSTemplateModel.is_active.is_(True))
        )
        if segment:
            from sqlalchemy import cast, type_coerce, text
            from sqlalchemy.dialects.postgresql import JSONB
            # Use raw SQL for JSON containment since column is JSON not JSONB
            stmt = stmt.where(
                cast(SMSTemplateModel.target_segments, JSONB).contains([segment])
            )
        stmt = stmt.order_by(SMSTemplateModel.times_used.desc()).limit(20)
        result = await session.execute(stmt)
        templates = result.scalars().all()

    return {
        "templates": [
            {
                "id": str(t.id),
                "name": t.name,
                "content": t.content,
                "description": t.description,
                "category": t.category,
                "target_segments": t.target_segments,
                "times_used": t.times_used,
                "total_delivered": t.total_delivered,
                "total_conversions": t.total_conversions,
            }
            for t in templates
        ],
    }
