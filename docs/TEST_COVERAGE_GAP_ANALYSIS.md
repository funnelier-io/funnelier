# Funnelier — Test Coverage Report & Gap Analysis

> **Date:** April 18, 2026
> **Method:** Static analysis (source ↔ test mapping)
> **Total Unit Tests:** 447+ (across 18 test files)
> **Total Source Modules:** 14 bounded contexts + core/infrastructure

---

## 1. Test Inventory (Unit Tests)

| Test File | # Tests | Covers |
|---|---|---|
| `test_camunda.py` | 103 | Camunda client, config, deployment, 9 workers |
| `test_funnel_journey.py` | 45 | FunnelJourneyService, message correlation, DB fallback |
| `test_tasks.py` | 42 | Celery tasks (all modules) |
| `test_team_rfm.py` | 31 | Team helpers, RFM calculation, segment assignment |
| `test_campaign_workflow.py` | 31 | CampaignWorkflowService, Camunda + fallback |
| `test_performance.py` | 29 | PerformanceStats, percentiles, pool tuning |
| `test_segmentation.py` | 25 | RFM domain entities, services, schemas |
| `test_user_approval_workflow.py` | 23 | UserApprovalWorkflowService, BPMN + fallback |
| `test_predictive.py` | 23 | Churn, lead scoring, A/B test, ROI, retention |
| `test_billing.py` | 23 | Plans, feature gating, usage metering, enforcement |
| `test_rate_limit_cache.py` | 22 | Sliding-window rate limit, response cache, throttle |
| `test_user_management.py` | 20 | Auth schemas, entities, role hierarchy |
| `test_logging_metrics.py` | 16 | Structured logging, Prometheus metrics |
| `test_notifications.py` | 15 | Notification entities, schemas |
| `test_audit_trail.py` | 15 | Audit entities, schemas, constants |
| `test_auth.py` | 12 | JWT, login, token decode, RBAC |
| `test_domain.py` | 11 | Core domain entities, value objects |
| `test_websocket.py` | 10 | ConnectionManager, WebSocket endpoint |
| `test_etl_pipeline.py` | 50 | ETL helpers (phone normalization, duration parsing, column detection), filename extraction, schemas |
| `test_leads.py` | 28 | Contact entity lifecycle, domain events, ContactService, CategoryService, LeadSourceService, schemas |
| `test_sales.py` | 29 | Product/Invoice/Payment entities, InvoiceService, ProductService, schemas |
| `test_export.py` | 36 | CSV/XLSX/PDF generation, column defs, Persian headers, summary reports, schemas |

**Total: ~639 test functions** (Sprint 1: +143 new tests)

---

## 2. Coverage Matrix: Source Module → Test Coverage

### Legend
- ✅ **Covered** — dedicated test file with meaningful assertions
- ⚠️ **Partial** — some paths tested (indirectly or minimal)
- ❌ **No tests** — no unit test coverage found

### 2.1 Bounded Context Modules (`src/modules/`)

| Module | API Routes | Application/Service | Domain | Infrastructure/Repo | Test Status |
|---|---|---|---|---|---|
| **analytics** | routes, predictive_routes, journey_routes | funnel_service, predictive_service, alert_service, funnel_journey_service, reporting_service | entities, services | repositories | ⚠️ Partial — predictive + journey tested; **funnel_service, alert_service, reporting_service untested** |
| **audit** | routes | — | entities | repositories | ⚠️ Partial — entities/schemas only; **route handlers & repository untested** |
| **auth** | routes | user_approval_service | auth_service, entities | repositories | ✅ Good — auth + user mgmt + approval workflow covered |
| **campaigns** | routes | campaign_workflow_service | entities | repositories | ✅ Good — workflow service well tested |
| **communications** | routes, webhook_routes | services | entities, repositories | repositories | ⚠️ Partial — only via `test_tasks.py`; **service layer, webhook handlers, templates untested** |
| **etl** | routes | — | — | — | ❌ **No dedicated tests** — ETL routes, scan/history/stats endpoints untested |
| **export** | routes | service | schemas | — | ❌ **No tests** — export service, file generation untested |
| **leads** | routes | services | entities, repositories | repositories | ❌ **No dedicated tests** — contact CRUD, bulk import, stats untested |
| **notifications** | routes | — | entities | repositories | ⚠️ Partial — entities/schemas only; **route handlers, read/unread logic untested** |
| **sales** | routes, erp_routes | services | entities, repositories | crm_connector, erp_sync_service, repositories | ❌ **No dedicated tests** — sales CRUD, ERP sync, CRM connector untested |
| **segmentation** | routes | recommendation_service, rfm_application_service | entities, services | — | ✅ Good — RFM logic well tested |
| **team** | routes | — | — | — | ✅ Good — via `test_team_rfm.py` |
| **tenants** | routes | billing_service | entities | — | ✅ Good — via `test_billing.py` |

### 2.2 Core & API Layer (`src/api/`, `src/core/`)

| Component | Test Status |
|---|---|
| `src/api/main.py` (app factory, lifespan) | ❌ No tests |
| `src/api/cache_routes.py` | ⚠️ Indirectly via `test_rate_limit_cache.py` |
| `src/api/metrics.py` | ✅ via `test_logging_metrics.py` |
| `src/api/middleware/rate_limit.py` | ✅ via `test_rate_limit_cache.py` |
| `src/api/middleware/response_cache.py` | ✅ via `test_rate_limit_cache.py` |
| `src/api/middleware/import_throttle.py` | ✅ via `test_rate_limit_cache.py` |
| `src/api/middleware/request_logging.py` | ✅ via `test_logging_metrics.py` |
| `src/api/middleware/usage_enforcement.py` | ✅ via `test_billing.py` |
| `src/api/routes/processes.py` | ⚠️ Partially via Camunda tests |
| `src/api/search.py` | ❌ No tests |
| `src/api/websocket.py` | ✅ via `test_websocket.py` |
| `src/core/config.py` | ⚠️ Indirectly (used everywhere) |
| `src/core/cache.py` | ⚠️ Indirectly |
| `src/core/domain/` | ✅ via `test_domain.py` |
| `src/core/logging.py` | ✅ via `test_logging_metrics.py` |
| `src/core/perf_utils.py` | ✅ via `test_performance.py` |

### 2.3 Infrastructure (`src/infrastructure/`)

| Component | Test Status |
|---|---|
| `camunda/client.py` | ✅ 103 tests |
| `camunda/workers/` (9 workers) | ✅ Well tested |
| `camunda/deployment.py` | ✅ Tested |
| `messaging/celery_app.py` | ✅ via `test_tasks.py` |
| `messaging/tasks.py` | ✅ 42 tests |
| `messaging/alerts.py` | ⚠️ Partially |
| `database/session.py` | ❌ No tests (session factory) |
| `database/models/` (10 model files) | ❌ No model-level tests |
| `redis_pool.py` | ❌ No tests |
| `etl/pipeline.py` | ❌ No tests |
| `etl/scheduler.py` | ❌ No tests |
| `etl/extractors/` (6 extractors) | ❌ No tests |
| `etl/transformers/` (5 transformers) | ❌ No tests |
| `etl/loaders/` (5 loaders) | ❌ No tests |
| `connectors/kavenegar_connector.py` | ❌ No tests |
| `connectors/asterisk_connector.py` | ❌ No tests |
| `connectors/sms/kavenegar_provider.py` | ❌ No tests |
| `connectors/erp/` (4 adapters) | ❌ No tests |
| `connectors/excel_connector.py` | ❌ No tests |
| `connectors/csv_connector.py` | ❌ No tests |
| `connectors/mongodb_connector.py` | ❌ No tests |

---

## 3. Critical Gaps (Priority Order)

### 🔴 P0 — ✅ RESOLVED (Sprint 1 Completed)

| Gap | Status | Tests Added |
|---|---|---|
| **ETL Pipeline** (helpers, schemas, validation) | ✅ Covered | 50 tests in `test_etl_pipeline.py` |
| **Leads module** (entity lifecycle, services, schemas) | ✅ Covered | 28 tests in `test_leads.py` |
| **Sales module** (entities, services, schemas) | ✅ Covered | 29 tests in `test_sales.py` |
| **Export service** (CSV/XLSX/PDF, schemas) | ✅ Covered | 36 tests in `test_export.py` |

### 🟡 P1 — Partial Coverage, Needs Expansion

| Gap | Current State | Needed |
|---|---|---|
| **Communications** (service, webhooks, templates) | Only Celery task wrappers tested | 15-20 tests: SMS send/receive, webhook handling, template vars |
| **Analytics** (funnel_service, alert_service, reporting) | Predictive + journey covered | 15-20 tests: funnel aggregation, alert rule CRUD, report generation |
| **Notifications** (route handlers, mark-read, preferences) | Entities only | 10-15 tests: CRUD operations, bulk mark-read, preference management |
| **Audit** (route handlers, repository queries) | Entities only | 10-15 tests: log creation, filtering, pagination |
| **Connectors** (Kavenegar, Asterisk, ERP adapters) | Zero coverage | 20-25 tests: mock external APIs, error handling, retries |

### 🟢 P2 — Nice to Have

| Gap | Notes |
|---|---|
| `src/api/main.py` (app factory) | Integration test territory; low unit-test value |
| `src/api/search.py` | Test search query building |
| `database/models/` | Model validation tests (constraints, defaults) |
| `redis_pool.py` | Connection pool lifecycle |

---

## 4. Coverage Estimate

| Category | Source Files | Lines (est.) | Tested | Coverage (est.) |
|---|---|---|---|---|
| Core domain & config | 8 | ~800 | ✅ | ~70% |
| Auth & RBAC | 6 | ~1,200 | ✅ | ~80% |
| Camunda & workflows | 14 | ~2,500 | ✅ | ~85% |
| Middleware (rate limit, cache, etc.) | 5 | ~800 | ✅ | ~75% |
| Segmentation & RFM | 6 | ~900 | ✅ | ~80% |
| Billing & tenants | 4 | ~700 | ✅ | ~75% |
| Predictive analytics | 4 | ~800 | ✅ | ~70% |
| Celery tasks | 3 | ~600 | ✅ | ~70% |
| **ETL pipeline** | **16** | **~3,000** | ⚠️ | **~35%** (helpers + schemas; route handlers need integration tests) |
| **Leads module** | **6** | **~1,200** | ✅ | **~65%** (entities, services, schemas covered) |
| **Sales module** | **9** | **~2,500** | ✅ | **~60%** (entities, services, schemas covered) |
| **Export module** | **3** | **~600** | ✅ | **~70%** (CSV/XLSX/PDF gen, schemas, column defs) |
| **Communications** | **7** | **~1,500** | ⚠️ | **~15%** |
| **Connectors** | **10** | **~2,000** | ❌ | **~0%** |
| Notifications | 4 | ~500 | ⚠️ | ~30% |
| Audit | 4 | ~400 | ⚠️ | ~30% |
| Analytics (non-predictive) | 6 | ~1,500 | ⚠️ | ~25% |

**Estimated Overall Line Coverage: ~55-60%**
**Target for v0.2.0: 70%+**

---

## 5. Action Plan

### Sprint 1 ✅ COMPLETED (April 18, 2026) — P0 Gaps Closed

1. ✅ **`tests/unit/test_etl_pipeline.py`** — 50 tests: phone normalization, duration parsing, column detection, filename extraction, schemas
2. ✅ **`tests/unit/test_leads.py`** — 28 tests: Contact entity lifecycle, domain events, ContactService, CategoryService, LeadSourceService, schemas
3. ✅ **`tests/unit/test_sales.py`** — 29 tests: Product/Invoice/Payment entities, InvoiceService, ProductService, schemas
4. ✅ **`tests/unit/test_export.py`** — 36 tests: CSV/XLSX/PDF generation, column defs, Persian headers, summary reports, schemas

**Result: +143 tests → ~639 total (exceeded +90 target by 59%)**

### Sprint 2 (Weeks 3-4) — Close P1 Gaps

5. **`tests/unit/test_communications.py`** — SMS service, webhooks, templates
6. **`tests/unit/test_analytics_full.py`** — Funnel service, alerts, reporting
7. **`tests/unit/test_connectors.py`** — Kavenegar, Asterisk, ERP adapters (mocked)
8. Expand `test_notifications.py` and `test_audit_trail.py` with route/repo tests

**Target: +80 tests → ~620 total**

### Sprint 3 (Weeks 5-6) — Polish & Integration

9. Add integration tests for critical flows (ETL → leads → analytics)
10. Set up `pytest-cov` with `--cov-fail-under=65` in CI
11. Update this document with actual coverage numbers

**Target: 70%+ line coverage, ~650+ tests**

---

## 6. CI Integration Recommendation

```yaml
# Add to .github/workflows/ci.yml
- name: Run tests with coverage
  run: |
    pip install pytest-cov
    python -m pytest tests/unit/ --cov=src --cov-report=html --cov-report=term --cov-fail-under=65
```

---

*This document is part of the Q2 2026 Stabilization milestone. Update after each sprint.*

