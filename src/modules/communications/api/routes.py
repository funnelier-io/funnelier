"""
Communications API Routes

FastAPI routes for SMS and call management endpoints.
"""

from datetime import datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from src.api.dependencies import (
    get_sms_log_repository,
    get_sms_template_repository,
    get_call_log_repository,
    get_current_tenant_id,
)
from src.core.domain import SMSDirection, SMSStatus, CallType, CallSource
from src.modules.communications.domain.entities import SMSLog, SMSTemplate, CallLog
from src.modules.communications.infrastructure.repositories import (
    SMSLogRepository,
    SMSTemplateRepository,
    CallLogRepository,
)

from .schemas import (
    BulkSendSMSRequest,
    BulkSendSMSResponse,
    CallLogListResponse,
    CallLogResponse,
    CallStatsResponse,
    CommunicationTimelineResponse,
    CreateSMSTemplateRequest,
    CreateVoIPConfigRequest,
    ImportCallLogsRequest,
    ImportCallLogsResponse,
    SendSMSRequest,
    SMSBalanceResponse,
    SMSDeliveryStatusRequest,
    SMSDeliveryStatusResponse,
    SMSLogListResponse,
    SMSLogResponse,
    SMSStatsResponse,
    SMSTemplateListResponse,
    SMSTemplateResponse,
    SyncVoIPLogsRequest,
    SyncVoIPLogsResponse,
    TemplatePerformanceResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    UpdateSMSTemplateRequest,
    VoIPConfigResponse,
)

router = APIRouter(tags=["communications"])


# ============================================================================
# SMS Endpoints
# ============================================================================

@router.post("/sms/send", response_model=SMSLogResponse)
async def send_sms(
    repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: SendSMSRequest,
):
    """Send a single SMS message via the configured provider."""
    from src.infrastructure.connectors.sms import MessagingProviderRegistry
    from src.core.interfaces.messaging import MessageStatus
    from datetime import timezone

    provider = MessagingProviderRegistry.get()

    # Resolve template content if template_id provided
    content = request.content

    # Calculate SMS parts
    char_count = len(content)
    sms_parts = 1 if char_count <= 70 else (char_count + 66) // 67

    # Create the log record first
    sms = SMSLog(
        tenant_id=tenant_id,
        contact_id=request.contact_id,
        phone_number=request.phone_number,
        direction=SMSDirection.OUTBOUND,
        content=content,
        template_id=request.template_id,
        status=SMSStatus.PENDING,
        campaign_id=request.campaign_id,
        provider_name=provider.get_info().name,
    )
    saved = await repo.add(sms)

    # Send via provider
    result = await provider.send(request.phone_number, content)

    # Update the log with provider result
    if result.status == MessageStatus.SENT or result.status == MessageStatus.DELIVERED:
        saved.mark_sent(provider_message_id=result.message_id)
        saved.cost = int(result.cost or 0)
    elif result.status == MessageStatus.FAILED:
        saved.mark_failed(result.error_message or "Provider send failed")
    saved.provider_message_id = result.message_id

    await repo.update(saved)

    return SMSLogResponse(
        id=saved.id, tenant_id=saved.tenant_id, contact_id=saved.contact_id,
        phone_number=saved.phone_number, direction="outbound", content=saved.content,
        template_id=saved.template_id,
        status=saved.status.value if hasattr(saved.status, 'value') else saved.status,
        provider_message_id=saved.provider_message_id,
        campaign_id=saved.campaign_id, provider_name=saved.provider_name,
        cost=saved.cost,
        sent_at=saved.sent_at,
        created_at=saved.created_at,
    )


@router.post("/sms/send-bulk", response_model=BulkSendSMSResponse)
async def send_bulk_sms(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: BulkSendSMSRequest,
):
    """Send SMS to multiple recipients. Queues a background task."""
    from src.infrastructure.connectors.sms import MessagingProviderRegistry
    from src.infrastructure.connectors.sms.kavenegar_provider import DEFAULT_COST_PER_PART_RIAL

    recipients = 0
    phone_numbers: list[str] = []
    if request.phone_numbers:
        phone_numbers = request.phone_numbers
        recipients = len(phone_numbers)
    elif request.contact_ids:
        recipients = len(request.contact_ids)
        # TODO: Resolve phone_numbers from contact_ids in the task

    content = request.content or ""
    char_count = len(content)
    sms_parts = 1 if char_count <= 70 else (char_count + 66) // 67
    estimated_cost = sms_parts * DEFAULT_COST_PER_PART_RIAL * recipients

    # Queue Celery task
    from src.infrastructure.messaging.tasks import send_bulk_sms_task
    task = send_bulk_sms_task.delay(
        phone_numbers=phone_numbers,
        content=content,
        tenant_id=str(tenant_id),
        template_id=str(request.template_id) if request.template_id else None,
        campaign_id=str(request.campaign_id) if request.campaign_id else None,
    )

    return BulkSendSMSResponse(
        total_queued=recipients,
        estimated_cost=estimated_cost,
        job_id=UUID(task.id) if hasattr(task, 'id') else uuid4(),
    )


@router.get("/sms/logs", response_model=SMSLogListResponse)
async def list_sms_logs(
    repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    contact_id: UUID | None = Query(default=None),
    phone_number: str | None = Query(default=None),
    status: str | None = Query(default=None),
    direction: str | None = Query(default=None),
    campaign_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
):
    """List SMS logs with filtering."""
    skip = (page - 1) * page_size
    if phone_number:
        logs = await repo.get_by_phone(phone_number, skip=skip, limit=page_size)
    elif status:
        logs = await repo.get_by_status(status, skip=skip, limit=page_size)
    elif campaign_id:
        logs = await repo.get_by_campaign(campaign_id, skip=skip, limit=page_size)
    elif date_from and date_to:
        logs = await repo.get_by_date_range(date_from, date_to, skip=skip, limit=page_size)
    else:
        logs = await repo.get_all(skip=skip, limit=page_size)
    total = await repo.count()
    return SMSLogListResponse(
        logs=[SMSLogResponse(
            id=l.id, tenant_id=l.tenant_id, contact_id=l.contact_id,
            phone_number=l.phone_number, direction="outbound", content=l.content,
            template_id=l.template_id,
            status=l.status.value if hasattr(l.status, 'value') else l.status,
            campaign_id=l.campaign_id, provider_name=l.provider_name,
            sent_at=l.sent_at, delivered_at=l.delivered_at,
            created_at=l.created_at,
        ) for l in logs],
        total_count=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total, has_prev=page > 1,
    )


@router.get("/sms/logs/{log_id}", response_model=SMSLogResponse)
async def get_sms_log(
    log_id: UUID,
    repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
):
    """Get SMS log by ID."""
    log = await repo.get(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="SMS log not found")
    return SMSLogResponse(
        id=log.id, tenant_id=log.tenant_id, contact_id=log.contact_id,
        phone_number=log.phone_number, direction="outbound", content=log.content,
        template_id=log.template_id,
        status=log.status.value if hasattr(log.status, 'value') else log.status,
        campaign_id=log.campaign_id, provider_name=log.provider_name,
        sent_at=log.sent_at, delivered_at=log.delivered_at,
        created_at=log.created_at,
    )


@router.post("/sms/check-status", response_model=SMSDeliveryStatusResponse)
async def check_sms_delivery_status(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
    request: SMSDeliveryStatusRequest,
):
    """Check delivery status for multiple messages via provider and update DB."""
    from src.infrastructure.connectors.sms import MessagingProviderRegistry
    from src.core.interfaces.messaging import MessageStatus

    provider = MessagingProviderRegistry.get()
    status_results = await provider.check_status(request.message_ids)

    statuses: dict[str, str] = {}
    total_delivered = 0
    total_failed = 0
    total_pending = 0

    for sr in status_results:
        statuses[sr.message_id] = sr.status.value
        if sr.status == MessageStatus.DELIVERED:
            total_delivered += 1
        elif sr.status == MessageStatus.FAILED:
            total_failed += 1
        else:
            total_pending += 1

        # Update DB record
        sms_log = await repo.get_by_provider_id(sr.message_id)
        if sms_log:
            if sr.status == MessageStatus.DELIVERED:
                sms_log.mark_delivered()
            elif sr.status == MessageStatus.FAILED:
                sms_log.mark_failed(sr.error_message or "Delivery failed")
            elif sr.status == MessageStatus.SENT:
                sms_log.status = SMSStatus.SENT
            await repo.update(sms_log)

    return SMSDeliveryStatusResponse(
        statuses=statuses,
        total_delivered=total_delivered,
        total_failed=total_failed,
        total_pending=total_pending,
    )


@router.post("/sms/import-csv", response_model=dict)
async def import_sms_logs_from_csv(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    file: UploadFile = File(...),
):
    """Import SMS logs from CSV file (e.g., from Kavenegar)."""
    # TODO: Parse CSV and bulk create via repo
    return {"total_imported": 0, "success_count": 0, "error_count": 0}


@router.get("/sms/stats", response_model=SMSStatsResponse)
async def get_sms_stats(
    repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get SMS statistics for a period."""
    if start_date is None:
        start_date = datetime.utcnow() - timedelta(days=30)
    if end_date is None:
        end_date = datetime.utcnow()

    stats = await repo.get_delivery_stats(start_date, end_date)
    total_sent = sum(stats.values())
    delivered = stats.get("delivered", 0)

    return SMSStatsResponse(
        period_start=start_date, period_end=end_date,
        total_sent=total_sent, total_delivered=delivered,
        total_failed=stats.get("failed", 0),
        delivery_rate=delivered / total_sent if total_sent > 0 else 0,
        total_cost=0, by_status=stats, by_template=[],
    )


@router.get("/sms/balance", response_model=SMSBalanceResponse)
async def get_sms_balance(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
):
    """Get remaining SMS credit / balance from the configured provider."""
    from src.infrastructure.connectors.sms import MessagingProviderRegistry

    provider = MessagingProviderRegistry.get()
    info = provider.get_info()
    credit = await provider.get_credit()

    return SMSBalanceResponse(
        balance=credit,
        currency="toman" if info.name == "kavenegar" else "unit",
        provider=info.display_name,
        is_low=(credit is not None and credit < 50_000),
    )


# ============================================================================
# Template Variable Substitution & Preview
# ============================================================================

TEMPLATE_VARIABLES = {
    "name": "نام مخاطب",
    "phone": "شماره تلفن",
    "company": "شرکت",
    "invoice_number": "شماره فاکتور",
    "amount": "مبلغ",
    "date": "تاریخ",
}


@router.post("/templates/{template_id}/preview", response_model=TemplatePreviewResponse)
async def preview_template(
    template_id: UUID,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
    request: TemplatePreviewRequest,
):
    """
    Preview a rendered SMS template with variable substitution.

    Accepts a dict of variables or a contact_id to auto-resolve fields.
    Returns the rendered text with character count and SMS parts.
    """
    t = await repo.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")

    variables = dict(request.variables or {})

    # If contact_id provided, fetch contact details for variable resolution
    if request.contact_id:
        from sqlalchemy import select
        from src.infrastructure.database.models.leads import ContactModel

        session = repo._session
        tid = repo._tenant_id
        stmt = select(ContactModel).where(
            ContactModel.id == request.contact_id,
            ContactModel.tenant_id == tid,
        )
        result = await session.execute(stmt)
        contact = result.scalar_one_or_none()
        if contact:
            variables.setdefault("name", contact.name or "")
            variables.setdefault("phone", contact.phone_number or "")
            variables.setdefault("company", getattr(contact, "company", "") or "")

    # Perform substitution
    rendered = t.content
    for key, value in variables.items():
        rendered = rendered.replace(f"{{{key}}}", str(value))

    char_count = len(rendered)
    sms_parts = 1 if char_count <= 70 else (char_count + 66) // 67

    return TemplatePreviewResponse(
        rendered_content=rendered,
        character_count=char_count,
        sms_parts=sms_parts,
        variables_used=list(variables.keys()),
        available_variables=list(TEMPLATE_VARIABLES.keys()),
    )


@router.get("/templates/variables", response_model=dict)
async def list_template_variables():
    """List supported template variables with descriptions."""
    return {
        "variables": [
            {"key": k, "description": v, "placeholder": f"{{{k}}}"}
            for k, v in TEMPLATE_VARIABLES.items()
        ]
    }


# ============================================================================
# SMS Template Endpoints
# ============================================================================

def _template_to_response(t: SMSTemplate) -> SMSTemplateResponse:
    content = t.content
    char_count = len(content)
    sms_parts = 1 if char_count <= 70 else (char_count + 66) // 67
    return SMSTemplateResponse(
        id=t.id, tenant_id=t.tenant_id, name=t.name, content=content,
        description=t.description, category=t.category,
        target_segments=t.target_segments, times_used=t.times_used,
        character_count=char_count, sms_parts=sms_parts,
        is_active=t.is_active, metadata=t.metadata,
        created_at=t.created_at, updated_at=t.updated_at,
    )


@router.get("/templates", response_model=SMSTemplateListResponse)
async def list_sms_templates(
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
    category: str | None = Query(default=None),
    segment: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
):
    """List SMS templates."""
    if category:
        templates = await repo.get_by_category(category)
    elif segment:
        templates = await repo.get_by_segment(segment)
    elif not include_inactive:
        templates = await repo.get_active_templates()
    else:
        templates = await repo.get_all()
    return SMSTemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total_count=len(templates),
    )


@router.post("/templates", response_model=SMSTemplateResponse, status_code=201)
async def create_sms_template(
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateSMSTemplateRequest,
):
    """Create a new SMS template."""
    template = SMSTemplate(
        tenant_id=tenant_id, name=request.name, content=request.content,
        description=request.description, category=request.category,
        target_segments=request.target_segments or [],
        is_active=request.is_active if request.is_active is not None else True,
        metadata=request.metadata or {},
    )
    saved = await repo.add(template)
    return _template_to_response(saved)


@router.get("/templates/{template_id}", response_model=SMSTemplateResponse)
async def get_sms_template(
    template_id: UUID,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
):
    """Get SMS template by ID."""
    t = await repo.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_to_response(t)


@router.put("/templates/{template_id}", response_model=SMSTemplateResponse)
async def update_sms_template(
    template_id: UUID,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
    request: UpdateSMSTemplateRequest,
):
    """Update an SMS template."""
    t = await repo.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    update_data = request.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if hasattr(t, key):
            setattr(t, key, value)
    saved = await repo.update(t)
    return _template_to_response(saved)


@router.delete("/templates/{template_id}", status_code=204)
async def delete_sms_template(
    template_id: UUID,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
):
    """Delete an SMS template."""
    await repo.delete(template_id)


@router.get("/templates/{template_id}/performance", response_model=TemplatePerformanceResponse)
async def get_template_performance(
    template_id: UUID,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
):
    """Get performance metrics for a template."""
    t = await repo.get(template_id)
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplatePerformanceResponse(
        template_id=t.id, template_name=t.name, times_used=t.times_used,
        delivery_rate=0.0, response_rate=0.0, conversion_rate=0.0,
    )


@router.get("/templates/by-segment/{segment}", response_model=list)
async def get_templates_for_segment(
    segment: str,
    repo: Annotated[SMSTemplateRepository, Depends(get_sms_template_repository)],
):
    """Get recommended templates for an RFM segment."""
    templates = await repo.get_by_segment(segment)
    return {
        "segment": segment,
        "templates": [_template_to_response(t) for t in templates],
    }


# ============================================================================
# Call Log Endpoints
# ============================================================================

def _call_to_response(c: CallLog) -> CallLogResponse:
    return CallLogResponse(
        id=c.id, tenant_id=c.tenant_id, contact_id=c.contact_id,
        phone_number=c.phone_number,
        contact_name=getattr(c, 'contact_name', None),
        call_type=c.call_type.value if hasattr(c.call_type, 'value') else c.call_type,
        source=c.source.value if hasattr(c.source, 'value') else c.source,
        duration_seconds=c.duration_seconds, call_time=c.call_time,
        salesperson_id=c.salesperson_id, salesperson_name=c.salesperson_name,
        salesperson_phone=getattr(c, 'salesperson_phone', None),
        is_answered=c.duration_seconds > 0,
        is_successful=c.is_successful,
        voip_unique_id=getattr(c, 'voip_call_id', None),
        recording_url=c.recording_url,
        notes=getattr(c, 'notes', None),
        metadata=getattr(c, 'metadata', {}),
        created_at=c.created_at,
    )


@router.get("/calls", response_model=CallLogListResponse)
async def list_call_logs(
    repo: Annotated[CallLogRepository, Depends(get_call_log_repository)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    contact_id: UUID | None = Query(default=None),
    phone_number: str | None = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
    call_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    is_answered: bool | None = Query(default=None),
    is_successful: bool | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    min_duration: int | None = Query(default=None),
):
    """List call logs with filtering."""
    skip = (page - 1) * page_size
    if phone_number:
        calls = await repo.get_by_phone(phone_number, skip=skip, limit=page_size)
    elif salesperson_id:
        calls = await repo.get_by_salesperson(salesperson_id, skip=skip, limit=page_size)
    elif source:
        calls = await repo.get_by_source(source, skip=skip, limit=page_size)
    elif date_from and date_to:
        calls = await repo.get_by_date_range(date_from, date_to, skip=skip, limit=page_size)
    elif is_successful:
        calls = await repo.get_successful_calls(skip=skip, limit=page_size)
    else:
        calls = await repo.get_all(skip=skip, limit=page_size)
    total = await repo.count()
    return CallLogListResponse(
        calls=[_call_to_response(c) for c in calls],
        total_count=total, page=page, page_size=page_size,
        has_next=(page * page_size) < total, has_prev=page > 1,
    )


@router.get("/calls/stats", response_model=CallStatsResponse)
async def get_call_stats(
    repo: Annotated[CallLogRepository, Depends(get_call_log_repository)],
    start_date: datetime = Query(default=None),
    end_date: datetime = Query(default=None),
    salesperson_id: UUID | None = Query(default=None),
):
    """Get call statistics for a period."""
    # When no date range specified, get stats for ALL data
    stats = await repo.get_call_stats(start_date, end_date)
    total = stats.get("total", 0)
    successful = stats.get("successful", 0)
    answered = stats.get("answered", successful)  # fallback
    return CallStatsResponse(
        period_start=start_date or datetime(2020, 1, 1),
        period_end=end_date or datetime.utcnow(),
        total_calls=total,
        total_answered=answered,
        total_successful=successful,
        total_duration=stats.get("total_duration", 0),
        average_duration=stats.get("total_duration", 0) // max(total, 1),
        answer_rate=answered / max(total, 1),
        success_rate=successful / max(total, 1),
        by_type={}, by_salesperson=[],
    )


@router.get("/calls/{call_id}", response_model=CallLogResponse)
async def get_call_log(
    call_id: UUID,
    repo: Annotated[CallLogRepository, Depends(get_call_log_repository)],
):
    """Get call log by ID."""
    call = await repo.get(call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call log not found")
    return _call_to_response(call)


@router.post("/calls/import", response_model=ImportCallLogsResponse)
async def import_call_logs(
    repo: Annotated[CallLogRepository, Depends(get_call_log_repository)],
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: ImportCallLogsRequest,
):
    """Import call logs from various sources."""
    calls = []
    for item in (request.calls or []):
        call = CallLog(
            tenant_id=tenant_id, phone_number=item.phone_number,
            call_type=CallType.OUTGOING, source=CallSource.MOBILE,
            duration_seconds=item.duration_seconds, call_time=item.call_time,
            salesperson_id=item.salesperson_id,
        )
        call.evaluate_success()
        calls.append(call)
    success, errors, error_list = await repo.bulk_create(calls)
    return ImportCallLogsResponse(
        total_imported=len(calls), success_count=success, error_count=errors,
        matched_contacts=0, new_contacts=0,
    )


@router.post("/calls/import-csv", response_model=ImportCallLogsResponse)
async def import_call_logs_from_csv(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    file: UploadFile = File(...),
    salesperson_id: UUID | None = Query(default=None),
    salesperson_name: str | None = Query(default=None),
    source: str = Query(default="mobile"),
    successful_call_threshold: int = Query(default=90),
):
    """Import call logs from CSV file."""
    # TODO: Parse CSV and bulk create via repo
    return ImportCallLogsResponse(
        total_imported=0, success_count=0, error_count=0,
        matched_contacts=0, new_contacts=0,
    )



# ============================================================================
# VoIP Integration Endpoints
# ============================================================================

@router.get("/voip/config", response_model=VoIPConfigResponse | None)
async def get_voip_config(tenant_id: Annotated[UUID, Depends(get_current_tenant_id)]):
    """Get VoIP configuration for tenant."""
    return None


@router.post("/voip/config", response_model=VoIPConfigResponse, status_code=201)
async def create_voip_config(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: CreateVoIPConfigRequest,
):
    """Create VoIP configuration."""
    return VoIPConfigResponse(
        id=uuid4(), tenant_id=tenant_id, provider_type=request.provider_type,
        host=request.host, port=request.port, username=request.username,
        api_key=request.api_key, is_active=request.is_active,
        metadata=request.metadata, created_at=datetime.utcnow(),
    )


@router.post("/voip/sync", response_model=SyncVoIPLogsResponse)
async def sync_voip_logs(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    request: SyncVoIPLogsRequest = None,
):
    """Sync call logs from VoIP system."""
    return SyncVoIPLogsResponse(total_fetched=0, new_records=0, updated_records=0)


@router.post("/voip/import-json", response_model=dict)
async def import_voip_logs_from_json(
    tenant_id: Annotated[UUID, Depends(get_current_tenant_id)],
    file: UploadFile = File(...),
):
    """Import VoIP call logs from JSON file."""
    return {"total_imported": 0, "success_count": 0, "error_count": 0}


# ============================================================================
# Contact Communication Timeline
# ============================================================================

@router.get("/timeline/{contact_id}", response_model=CommunicationTimelineResponse)
async def get_communication_timeline(
    contact_id: UUID,
    sms_repo: Annotated[SMSLogRepository, Depends(get_sms_log_repository)],
    call_repo: Annotated[CallLogRepository, Depends(get_call_log_repository)],
    limit: int = Query(default=50, ge=1, le=200),
):
    """Get communication timeline for a contact — real call + SMS events."""
    from src.api.dependencies import get_contact_repository, get_current_tenant_id, get_db_session
    from sqlalchemy import select
    from src.infrastructure.database.models.leads import ContactModel
    from src.infrastructure.database.models.communications import CallLogModel, SMSLogModel

    session = call_repo._session
    tid = call_repo._tenant_id

    # Get contact phone number
    contact_q = await session.execute(
        select(ContactModel.phone_number).where(
            ContactModel.id == contact_id, ContactModel.tenant_id == tid,
        )
    )
    phone_row = contact_q.scalar_one_or_none()
    phone = phone_row or ""

    events: list[dict] = []

    # Fetch call logs for this contact
    call_q = await session.execute(
        select(CallLogModel)
        .where(CallLogModel.tenant_id == tid, CallLogModel.contact_id == contact_id)
        .order_by(CallLogModel.call_start.desc())
        .limit(limit)
    )
    for c in call_q.scalars().all():
        events.append({
            "type": "call",
            "timestamp": c.call_start.isoformat() if c.call_start else None,
            "duration_seconds": c.duration_seconds,
            "call_type": c.call_type,
            "status": c.status,
            "is_successful": c.is_successful,
            "salesperson_name": c.salesperson_name,
            "notes": c.notes,
        })

    # Fetch SMS logs for this phone
    if phone:
        sms_q = await session.execute(
            select(SMSLogModel)
            .where(SMSLogModel.tenant_id == tid, SMSLogModel.phone_number == phone)
            .order_by(SMSLogModel.sent_at.desc())
            .limit(limit)
        )
        for s in sms_q.scalars().all():
            events.append({
                "type": "sms",
                "timestamp": s.sent_at.isoformat() if s.sent_at else None,
                "message": s.message[:100] if s.message else None,
                "status": s.status,
                "provider": s.provider,
            })

    # Sort all events by timestamp desc
    events.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    events = events[:limit]

    return CommunicationTimelineResponse(
        contact_id=contact_id, phone_number=phone, events=events,
    )

