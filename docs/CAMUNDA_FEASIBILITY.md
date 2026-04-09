# Camunda BPMS Integration — Feasibility Analysis

> **Date**: April 2026  
> **Status**: Proposed  
> **Decision**: ✅ Feasible — Recommended Camunda 7 Platform with phased migration

---

## 1. Executive Summary

Replacing the self-implemented workflow logic with **Camunda 7 (Platform)** is feasible and brings
significant value for **campaign orchestration**, **user approval workflows**, and **per-tenant
funnel customization**. However, not all current processes should migrate — Celery Beat remains the
right tool for scheduled computations (RFM, funnel snapshots, alerts).

The integration uses Camunda's **REST API** + **Python External Task Workers**, keeping the existing
FastAPI backend as the primary API layer. Camunda runs as a single Docker container alongside the
current stack with minimal infrastructure impact.

---

## 2. Current Workflow Landscape

| Process | Current Implementation | Complexity |
|---|---|---|
| **Campaign lifecycle** | Status field + API endpoints (`Campaign.start()`, `.pause()`, etc.) | Simple state machine |
| **Funnel stage progression** | `Contact.update_stage()` + `ContactFunnelProgress.progress_to_stage()` | Per-contact state tracking |
| **ETL pipeline orchestration** | Celery Beat (6 cron schedules) | Simple cron jobs |
| **Alert processing** | `check_alerts` Celery task | Stateless threshold check |
| **User approval** | `is_approved` boolean field | No workflow logic |
| **Bulk SMS campaigns** | `send_bulk_sms_task` Celery task | Fire-and-forget |
| **ERP data sync** | `sync_erp_data_sources` Celery task (every 15 min) | Periodic pull |

### What's Missing Without a BPMS

- **Visual process monitoring** — No way to see where a campaign or contact is "stuck" in the pipeline
- **Per-tenant workflow customization** — `FunnelStageConfig` exists but transitions are hardcoded
- **Human task management** — User approval is a simple boolean, no task assignment or escalation
- **Compensation/rollback** — If bulk SMS partially fails, no automated retry orchestration
- **Timer-based escalation** — No auto-escalation if a campaign is stuck in "running" for too long
- **Audit trail** — Process history is scattered across multiple tables

---

## 3. Camunda 7 vs Camunda 8 Comparison

| Criterion | Camunda 7 (Platform) | Camunda 8 (Zeebe) |
|---|---|---|
| **Deployment** | Single Docker container | 4-6 containers (Zeebe, Gateway, Operate, Tasklist, Elasticsearch) |
| **RAM overhead** | ~512MB | ~2-4GB minimum |
| **REST API** | Mature, well-documented | gRPC-native; REST via gateway (newer) |
| **Python SDK** | `camunda-external-task-client-python3` (stable) | `pyzeebe` (active but less mature) |
| **Multi-tenancy** | Process-variable or definition-key based | Native tenant support in 8.3+ (complex) |
| **Human tasks** | Built-in Tasklist UI | Separate Tasklist app |
| **Database** | Shares PostgreSQL | Requires Elasticsearch |
| **Learning curve** | Moderate (REST API focused) | Steeper (gRPC, Operate UI) |
| **License** | Community Edition (free, Apache 2.0) | Community Edition (free, Zeebe Protocol License) |

### ✅ Recommendation: **Camunda 7 (Platform)**

- Lighter footprint (1 container vs 4-6)
- Mature REST API ideal for Python integration
- Can use own PostgreSQL instance (no shared infra changes)
- Community Python external-task client is battle-tested
- Cockpit web UI for process monitoring out of the box
- Camunda 8/Zeebe is overkill for current scale

---

## 4. Process Migration Analysis

### 4.1 Processes to MIGRATE to Camunda (High Value)

#### Campaign Lifecycle → `campaign_lifecycle.bpmn`
```
[Create] → [Review/Approve] → [Schedule] → [Send SMS] → [Track Delivery] → [Measure] → [Complete]
              (human task)     (timer event)  (ext. task)  (message events)   (ext. task)
```
**Why Camunda**: Visual orchestration, timer-based auto-transitions, human approval before sending,
per-tenant campaign workflow variants, built-in retry for failed sends.

#### User Approval → `user_approval.bpmn`
```
[Register] → [Pending Review] → [Admin Decision] → [Approve] / [Reject] → [Notify User]
                                   (human task)
```
**Why Camunda**: Classic human-task pattern, escalation timers (auto-reject after N days),
task assignment to specific admins.

#### Funnel Stage Progression → `funnel_journey.bpmn`
```
[Lead Acquired] → (wait: SMS sent) → (wait: SMS delivered) → (wait: call answered)
                                                              → (wait: invoice issued)
                                                              → (wait: payment received)
```
**Why Camunda**: Message correlation for domain events, per-tenant BPMN variants using
`FunnelStageConfig`, visual monitoring of contact pipeline.

> ⚠️ **Volume consideration**: With potentially 100K+ contacts per tenant, creating a process
> instance per contact may strain the engine. Consider: (a) only create instances for contacts
> entering active campaigns, or (b) batch correlation patterns.

#### Bulk SMS Orchestration → sub-process within campaign lifecycle
```
[Prepare Recipients] → [Send Batch] → [Wait for Delivery] → [Report Results]
     (ext. task)       (ext. task)    (message correlation)    (ext. task)
```
**Why Camunda**: Orchestrates the multi-step process with proper error handling and compensation.

### 4.2 Processes to KEEP as Celery (Low Value for Camunda)

| Process | Reason to Keep |
|---|---|
| **ETL cron jobs** (6 schedules) | Simple fire-and-forget computations, no branching or human decisions |
| **Alert processing** | Stateless threshold check → notification, no workflow state |
| **ERP data sync** (periodic) | Simple periodic pull, no state machine needed |
| **RFM calculation** | Pure computation, no orchestration needed |
| **Daily reports** | Cron-triggered generation, no workflow |
| **SMS delivery polling** | Simple fallback polling, no state machine |

### 4.3 Future Candidates (Phase 3+)

| Process | Trigger for Migration |
|---|---|
| **ERP sync escalation** | When repeated failures need manager notification workflow |
| **Lead assignment workflow** | When assignment needs approval or round-robin with capacity checks |
| **Invoice follow-up** | When overdue invoices need automated reminder sequences |

---

## 5. Integration Architecture

```
┌─────────────────────┐   REST API    ┌──────────────────────┐
│  FastAPI Backend     │──────────────▶│  Camunda 7 Engine    │
│  :8000               │◀──────────────│  :8085               │
│                      │               │  (Docker container)  │
│  ┌────────────────┐  │               │  ┌────────────────┐  │
│  │ Campaign API   │──┼─── start ────▶│  │ campaign.bpmn  │  │
│  │ Auth API       │──┼─── start ────▶│  │ approval.bpmn  │  │
│  │ Leads API      │──┼─── correlate ▶│  │ funnel.bpmn    │  │
│  └────────────────┘  │               │  └────────────────┘  │
└──────────┬───────────┘               └──────────┬───────────┘
           │                                      │
           │                                      │ External Tasks
           │                                      │ (poll & execute)
           ▼                                      ▼
┌─────────────────────┐               ┌──────────────────────┐
│  Celery Workers      │               │  Camunda Task Workers │
│  (ETL, RFM, alerts,  │               │  (Python processes)   │
│   cron jobs)         │               │                      │
│                      │               │  - send_sms_worker   │
│  Stays unchanged     │               │  - delivery_worker   │
│                      │               │  - approval_worker   │
│                      │               │  - funnel_worker     │
└─────────────────────┘               └──────────────────────┘
```

### 5.1 New Python Module: `src/infrastructure/camunda/`

```
src/infrastructure/camunda/
├── __init__.py
├── client.py              # REST API wrapper for Camunda Engine
├── config.py              # Camunda connection settings
├── deployment.py          # BPMN deployment on app startup
├── workers/
│   ├── __init__.py
│   ├── base.py            # Base external task worker
│   ├── campaign_worker.py # Campaign-specific task handlers
│   ├── sms_worker.py      # SMS send/delivery task handlers
│   ├── approval_worker.py # Human task resolution helpers
│   └── funnel_worker.py   # Funnel progression handlers
└── bpmn/
    ├── campaign_lifecycle.bpmn
    ├── user_approval.bpmn
    ├── funnel_journey.bpmn
    └── bulk_sms.bpmn
```

### 5.2 Python Dependencies

```toml
# pyproject.toml additions
"camunda-external-task-client-python3>=4.4.0"  # External task worker
"httpx>=0.27.0"                                 # Already used, for Camunda REST calls
```

### 5.3 API Flow Example: Starting a Campaign

```python
# Current (direct state mutation):
@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: UUID, ...):
    model = await repo.get_model(campaign_id)
    updated = await repo.update_status(campaign_id, "running", started_at=datetime.utcnow())
    return _model_to_response(updated)

# With Camunda (process orchestration):
@router.post("/{campaign_id}/start")
async def start_campaign(campaign_id: UUID, ...):
    model = await repo.get_model(campaign_id)
    # Start BPMN process instance
    process = await camunda_client.start_process(
        process_key="campaign_lifecycle",
        business_key=str(campaign_id),
        variables={
            "tenant_id": str(tenant_id),
            "campaign_id": str(campaign_id),
            "total_recipients": model.total_recipients,
            "message_content": model.message_content,
        }
    )
    await repo.update_status(campaign_id, "running",
                             started_at=datetime.utcnow(),
                             process_instance_id=process.id)
    return _model_to_response(model)
```

### 5.4 External Task Worker Example

```python
# src/infrastructure/camunda/workers/sms_worker.py
from camunda.external_task.external_task_worker import ExternalTaskWorker

def handle_send_sms(task):
    """External task handler: Send SMS batch for a campaign."""
    variables = task.get_variables()
    campaign_id = variables["campaign_id"]
    tenant_id = variables["tenant_id"]

    # Reuse existing business logic
    from src.infrastructure.messaging.tasks import send_bulk_sms_task
    result = send_bulk_sms_task.delay(
        phone_numbers=variables["phone_numbers"],
        content=variables["message_content"],
        tenant_id=tenant_id,
        campaign_id=campaign_id,
    )

    return task.complete({
        "sms_task_id": result.id,
        "sent_count": 0,  # Will be updated via message correlation
    })

worker = ExternalTaskWorker(
    worker_id="funnelier-sms-worker",
    base_url="http://localhost:8085/engine-rest",
    config={"maxTasks": 10, "lockDuration": 30000}
)
worker.subscribe("send-campaign-sms", handle_send_sms)
```

---

## 6. Multi-Tenant Strategy

### Approach: Process Variables + Definition Key Naming

```python
# Starting a process with tenant isolation
await camunda_client.start_process(
    process_key="campaign_lifecycle",  # or "campaign_lifecycle_TENANT_UUID" for custom flows
    business_key=str(campaign_id),
    variables={
        "tenant_id": {"value": str(tenant_id), "type": "String"},
        # ... other variables
    }
)

# Querying processes filtered by tenant
instances = await camunda_client.get_process_instances(
    process_definition_key="campaign_lifecycle",
    variables=[{"name": "tenant_id", "value": str(tenant_id), "operator": "eq"}]
)
```

### Per-Tenant Custom Workflows

Tenants with custom `FunnelStageConfig` (from tenant settings) get a dynamically generated BPMN:

```python
# On tenant settings update:
if tenant.funnel_stages != default_stages:
    bpmn_xml = generate_funnel_bpmn(tenant.funnel_stages)
    await camunda_client.deploy(
        name=f"funnel_journey_{tenant.id}",
        bpmn_xml=bpmn_xml,
        tenant_id=str(tenant.id),  # Camunda deployment tenant
    )
```

---

## 7. Infrastructure Requirements

### Docker Container (Funnelier-specific compose)

```yaml
# docker/docker-compose.yml addition
camunda:
  image: camunda/camunda-bpm-platform:7.21.0
  container_name: funnelier-camunda
  ports:
    - "8085:8080"  # Avoid conflict with FastAPI :8000
  environment:
    - DB_DRIVER=org.postgresql.Driver
    - DB_URL=jdbc:postgresql://host.docker.internal:5435/funnelier_camunda
    - DB_USERNAME=funnelier_camunda
    - DB_PASSWORD=funnelier_camunda
    - WAIT_FOR=host.docker.internal:5435
  depends_on:
    - postgres  # Only if using Funnelier's own postgres
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8080/engine-rest/engine"]
    interval: 30s
    timeout: 10s
    retries: 5
```

### Database Options

| Option | Pros | Cons |
|---|---|---|
| **A. Separate PostgreSQL database** on shared infra port 5435 | Clean isolation, proper schema | Requires modifying shared `/Users/univers/projects/infra/postgres/init.sql` (15+ projects impacted) |
| **B. H2 embedded** (dev only) | Zero infrastructure changes | Not suitable for production; data lost on restart |
| **C. Funnelier's own PostgreSQL** in docker-compose | Full isolation, no shared infra changes | Extra container, extra resource usage |

**Recommendation**: Option **A** for production (with user approval for shared infra change),
Option **B** for initial development/PoC (zero shared infra impact).

### Resource Footprint

| Component | RAM | CPU | Disk |
|---|---|---|---|
| Camunda Engine | ~512MB | 0.5 core | ~200MB (Docker image) |
| External Task Workers (Python) | ~128MB each | 0.2 core | Minimal |
| **Total additional** | **~768MB** | **~0.9 core** | **~200MB** |

### Ports Summary (updated)

| Service | Port | Purpose |
|---|---|---|
| FastAPI Backend | 8000 | Main API (unchanged) |
| Next.js Frontend | 3003 | Dashboard (unchanged) |
| **Camunda Engine** | **8085** | **REST API + Cockpit/Tasklist UI** |
| PostgreSQL | 5435 | Shared infra (unchanged) |
| Redis | 6381 | Shared infra (unchanged) |

---

## 8. Risks and Trade-offs

### Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **JVM in Python stack** | Debugging complexity, different log formats | Structured logging adapter, Cockpit UI for monitoring |
| **REST API latency** | ~5-20ms per Camunda call | Acceptable for workflow ops; avoid for hot paths |
| **Python SDK maturity** | Less polished than Java/JS | Write thin wrapper, pin version, contribute patches |
| **Migration cutover** | In-flight campaigns need state transfer | Dual-write period, or manual migration script |
| **High-volume funnel** | 100K+ process instances per tenant | Only create instances for active campaign contacts |
| **Shared infra changes** | PostgreSQL schema change affects 15+ projects | Use H2 for dev, request approval for production |
| **Team learning curve** | BPMN modeling, Camunda Cockpit | 2-day workshop, pair programming on first BPMN |

### Trade-offs

| Aspect | Without Camunda | With Camunda |
|---|---|---|
| **Simplicity** | ✅ Simple status fields | ❌ Additional service + BPMN files |
| **Visual monitoring** | ❌ Manual DB queries | ✅ Cockpit shows all process states |
| **Per-tenant workflows** | ❌ Hardcoded stage logic | ✅ Deploy different BPMN per tenant |
| **Human tasks** | ❌ Custom implementation needed | ✅ Built-in task management |
| **Audit trail** | ❌ Scattered across modules | ✅ Complete process history in Camunda |
| **Compensation** | ❌ Manual error handling | ✅ BPMN compensation events |
| **Development speed** | ✅ Just code Python | ❌ Model BPMN + code workers |
| **Enterprise readiness** | ❌ Custom, needs explaining | ✅ Industry-standard BPMS |

---

## 9. Implementation Roadmap

### Phase 32: Camunda Infrastructure Setup (1 week)
- Add Camunda 7 Docker container to `docker/docker-compose.yml`
- Create `src/infrastructure/camunda/` module with REST client
- Deploy "hello world" BPMN process
- Verify external task worker pattern in Python
- Add Camunda health check to `/health/ready` endpoint
- Unit tests for REST client

### Phase 33: Campaign Workflow Migration (2-3 weeks)
- Design `campaign_lifecycle.bpmn` in Camunda Modeler
- Build external task workers: prepare recipients, send SMS, track delivery
- Migrate campaign API endpoints to start/correlate Camunda processes
- Add `process_instance_id` to CampaignModel
- Cockpit integration for campaign monitoring
- Keep existing API interface unchanged (backward compatible)

### Phase 34: User Approval Workflow (1-2 weeks)
- Design `user_approval.bpmn` with human task
- Build approval task worker
- Migrate register → approve/reject flow to Camunda
- Add timer-based escalation (auto-notify after 48h, auto-reject after 7d)
- Frontend: approval UI remains the same, backed by Camunda

### Phase 35: Funnel Journey Orchestration (3-4 weeks)
- Design `funnel_journey.bpmn` with message correlation events
- Message correlation for: SMS delivered, call answered, invoice issued, payment received
- Per-tenant BPMN generation from `FunnelStageConfig`
- Batch creation patterns for high-volume imports
- Visual funnel monitoring in Cockpit

### Phase 36: Advanced Process Features (2 weeks)
- Compensation sub-processes for failed SMS sends
- Timer events for stale campaign auto-completion
- ERP sync failure escalation workflow
- Dashboard widget showing process instance overview

---

## 10. Decision Matrix

| Factor | Weight | Score (1-5) | Weighted |
|---|---|---|---|
| Enterprise readiness | 5 | 5 | 25 |
| Per-tenant customization | 5 | 5 | 25 |
| Visual process monitoring | 4 | 5 | 20 |
| Human task management | 4 | 4 | 16 |
| Integration complexity | 3 | 3 | 9 |
| Infrastructure overhead | 3 | 3 | 9 |
| Team learning curve | 2 | 3 | 6 |
| **Total** | | | **110/140 (79%)** |

**Verdict**: Strong positive — the enterprise value and per-tenant customization justify the
additional complexity. The phased approach minimizes risk.

---

## 11. Quick Start (PoC in 1 Day)

```bash
# 1. Start Camunda (H2 embedded, zero config)
docker run -d --name funnelier-camunda \
  -p 8085:8080 \
  camunda/camunda-bpm-platform:7.21.0

# 2. Verify
curl http://localhost:8085/engine-rest/engine
# → [{"name":"default"}]

# 3. Access Cockpit UI
open http://localhost:8085/camunda/app/cockpit/default/
# Login: demo / demo

# 4. Install Python client
pip install camunda-external-task-client-python3

# 5. Deploy a test BPMN via REST API
curl -X POST http://localhost:8085/engine-rest/deployment/create \
  -F "deployment-name=test" \
  -F "campaign_lifecycle.bpmn=@bpmn/campaign_lifecycle.bpmn"
```

---

## Appendix A: BPMN Process Sketches

### Campaign Lifecycle

```
  ┌─────────┐    ┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
  │  Draft   │───▶│ Schedule │───▶│  Review  │───▶│  Running  │───▶│ Complete │
  └─────────┘    └──────────┘    │ (human)  │    │           │    └──────────┘
                   ▲  (timer)     └──────────┘    │  ┌──────┐ │
                   │                    │         │  │Paused│ │
                   │                    ▼         │  └──┬───┘ │
                   │              ┌──────────┐    │     │     │
                   │              │ Rejected │    │◀────┘     │
                   │              └──────────┘    │           │
                   │                              │  ┌──────┐ │
                   └──────────────────────────────┼──│Cancel│◀┘
                                                  │  └──────┘
                                                  └───────────┘
```

### User Approval

```
  ┌──────────┐    ┌───────────┐    ┌──────────────┐    ┌──────────┐
  │ Register │───▶│  Pending  │───▶│ Admin Review │───▶│ Approved │
  └──────────┘    │  (48h     │    │ (human task) │    └──────────┘
                  │  reminder)│    └──────┬───────┘         │
                  └───────────┘           │                 ▼
                       │                  ▼           ┌──────────┐
                       │            ┌──────────┐      │  Notify  │
                       └──(7d)─────▶│ Rejected │      │   User   │
                                    └──────────┘      └──────────┘
```

### Funnel Journey (per contact)

```
  ┌──────────────┐   msg:sms_sent   ┌──────────┐   msg:sms_delivered   ┌───────────┐
  │ Lead Acquired │────────────────▶│ SMS Sent │────────────────────▶│SMS Delivered│
  └──────────────┘                  └──────────┘                     └─────┬───────┘
                                                                          │
                                      msg:call_answered                   │msg:call_attempted
                                    ┌──────────────┐    ┌──────────────┐  │
                                    │Call Answered  │◀───│Call Attempted │◀┘
                                    └──────┬───────┘    └──────────────┘
                                           │
                              msg:invoice   │    msg:payment
                            ┌──────────┐    │   ┌─────────────┐
                            │ Invoice  │◀───┘──▶│  Payment    │
                            │ Issued   │────────│  Received ✓ │
                            └──────────┘        └─────────────┘
```

