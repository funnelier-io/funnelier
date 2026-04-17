# Funnelier — API & Frontend Audit Report

> **Date**: April 17, 2026
> **Scope**: Backend API endpoints, OpenAPI documentation, frontend pages & dependencies
> **Baseline**: v0.1.0 (39 commits on `main`)

---

## 1. Backend API Summary

| Metric | Value |
|---|---|
| **Total Endpoints** | 264 |
| **Modules with routes** | 17 route files across 12 DDD modules + 4 infrastructure routes |
| **Auth-protected** | 248 (94%) |
| **Public** | 16 (health, login, register, refresh, webhooks, metrics, WebSocket) |
| **OpenAPI docs** | `/api/docs` (Swagger), `/api/redoc`, `/api/openapi.json` |

### Endpoints by Module

| Module | Endpoints | Prefix |
|---|---|---|
| Sales | 31 | `/api/v1/sales` |
| Leads | 29 | `/api/v1/leads` |
| Communications | 27 | `/api/v1/communications` |
| Tenants | 21 | `/api/v1/tenants` |
| Campaigns | 18 | `/api/v1/campaigns` |
| Team | 17 | `/api/v1/team` |
| ETL/Import | 16 | `/api/v1/import` |
| Auth | 16 | `/api/v1/auth` |
| ERP Sync | 13 | `/api/v1/sales/erp` |
| Export | 13 | `/api/v1/export` |
| Segmentation | 12 | `/api/v1/segments` |
| Analytics | 12 | `/api/v1/analytics` |
| Camunda BPMS | 12 | `/api/v1/processes` |
| Notifications | 9 | `/api/v1/notifications` |
| Journey | 7 | `/api/v1/analytics/funnel/journeys` |
| Predictive | 5 | `/api/v1/analytics/predictive` |
| Audit | 2 | `/api/v1/audit` |
| Cache | 2 | `/api/v1/cache` |
| Search | 1 | `/api/v1/search` |
| Metrics | 1 | `/metrics` |

---

## 2. Issues Found

### 🔴 High Priority

#### ~~H1. Missing `response_model` on 43 endpoints~~ ✅ FIXED
All 264 endpoints now have `response_model`, `status_code=204`, or `responses=` annotations.
- 39 endpoints: added `response_model=dict` or `response_model=list`
- 8 export endpoints: added `responses={200: {"content": {"application/octet-stream": {}}}}` for file downloads

#### H2. Webhook route uses `webhook_router` variable (not `router`)
`src/modules/communications/api/webhook_routes.py` uses `webhook_router` instead of `router`, which is why automated grep missed it. The endpoint exists and works (`POST /api/v1/webhooks/kavenegar/delivery`). No action needed — just a naming inconsistency for audit purposes.

### 🟡 Medium Priority

#### M1. Duplicate `/sources/{source_id}` pattern across 3 modules
The same path pattern exists in:
- `leads/api/routes.py` → lead sources
- `sales/api/erp_routes.py` → ERP data sources
- `tenants/api/routes.py` → tenant data source configs

While they're mounted under different prefixes (`/leads`, `/sales`, `/tenants`), this creates confusion in:
- OpenAPI docs (multiple identically-named parameters)
- Frontend developers guessing which "source" is which

**Fix**: Consider renaming to `/lead-sources`, `/erp-sources`, `/tenant-sources` in a future breaking change.

#### M2. Four `/stats` endpoints across modules
`audit`, `etl`, `leads`, and `sales` all have a `/stats` GET endpoint. This is fine since they're under different prefixes, but the `etl/stats` and `cache/stats` lack response models.

**Fix**: Add response models to ensure OpenAPI completeness.

#### M3. `api/v1` info endpoint has stale endpoint list
The `/api/v1` endpoint in `main.py` hardcodes an endpoint map that's missing:
- `/api/v1/processes` (Camunda BPMS)
- `/api/v1/audit`

**Fix**: Update the endpoint map or auto-generate from registered routers.

#### M4. Export endpoints return file streams without OpenAPI docs
The 7 export endpoints (CSV/XLSX/PDF) return `StreamingResponse` but lack `responses={200: {"content": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {}}}}` annotations.

**Fix**: Add proper `responses` dict for file download content types.

### 🟢 Low Priority

#### L1. Inconsistent `status_code` on POST endpoints
Most POST endpoints use `status_code=201` but some (password reset, campaign actions like start/pause/resume/cancel, read-all notifications) return 200. This is semantically correct (they're actions, not resource creation) but worth documenting the pattern.

#### L2. `products/{contact_id}` in segmentation routes is confusing
`GET /segments/products/{contact_id}` returns product recommendations for a contact — the path reads as if `contact_id` is a `product_id`.

**Fix**: Consider `/segments/contacts/{contact_id}/product-recommendations`.

#### L3. Webhook routes mounted without auth but no rate limiting annotation
Webhooks bypass auth (correct) but should have explicit rate-limiting or signature validation documentation in OpenAPI.

---

## 3. Frontend Audit

### Pages (18 total)

| Page | Route |
|---|---|
| Dashboard (home) | `/(dashboard)` |
| Leads | `/(dashboard)/leads` |
| Communications | `/(dashboard)/communications` |
| Sales | `/(dashboard)/sales` |
| Campaigns | `/(dashboard)/campaigns` |
| Funnel | `/(dashboard)/funnel` |
| Segments | `/(dashboard)/segments` |
| Predictive | `/(dashboard)/predictive` |
| Alerts | `/(dashboard)/alerts` |
| Team | `/(dashboard)/team` |
| Imports | `/(dashboard)/imports` |
| Data Sync | `/(dashboard)/data-sync` |
| Reports | `/(dashboard)/reports` |
| Settings | `/(dashboard)/settings` |
| Usage | `/(dashboard)/usage` |
| Users | `/(dashboard)/users` |
| Activity/Audit | `/(dashboard)/activity` |
| Login | `/login` |

### Dependencies (lean — 7 production, 8 dev)

| Dependency | Version | Status |
|---|---|---|
| next | 16.1.6 | ✅ Current |
| react / react-dom | 19.2.3 | ✅ Current (React 19) |
| next-intl | 4.9.0+ | ✅ Current |
| recharts | 3.7.0+ | ✅ Current |
| zustand | 5.0.11+ | ✅ Current |
| jalaali-js | 1.2.8+ | ✅ Current (Jalali calendar) |
| tailwindcss | 4+ | ✅ Current (v4) |
| typescript | 5+ | ✅ Current |
| @playwright/test | 1.59.1+ | ✅ Current |
| babel-plugin-react-compiler | 1.0.0 | ✅ React Compiler |

**Verdict**: Zero unnecessary dependencies. Very clean `package.json`.

### Missing Frontend Pages (vs API)

| API Module | Frontend Page | Status |
|---|---|---|
| Notifications | — | ⚠️ No dedicated page (bell icon only) |
| Camunda/Processes | — | ❌ Not yet (planned: Phase 42) |
| Export | — | ⚠️ Triggered from other pages, no dedicated page |
| ERP Sync detail | — | ⚠️ Covered partially by data-sync page |

### Frontend Library Analysis

| File | Purpose | LOC |
|---|---|---|
| `api-client.ts` | JWT-attached fetch wrapper | Core |
| `hooks.ts` | `useApi<T>` SWR-like hook | Core |
| `constants.ts` | NAV_ITEMS, config | Core |
| `format.ts` | Number/date formatting | Utility |
| `use-format.ts` | i18n-aware formatting hook | Utility |
| `use-websocket.ts` | WebSocket connection hook | Feature |
| `utils.ts` | Misc helpers | Utility |

**Verdict**: Clean, minimal library layer. No dead code detected.

---

## 4. Recommendations (Prioritized)

### Immediate (before v0.2.0)

1. **Add `response_model` to all 43 missing endpoints** — improves OpenAPI docs, catches serialization bugs
2. **Update `/api/v1` endpoint map** — add processes, audit
3. **Verify webhook routes** — ensure they're functional and documented

### Short-term (Q3 2026)

4. **Add `responses` annotations for file-download endpoints** — proper OpenAPI for exports
5. **Phase 42: Process Monitoring Dashboard** — already planned
6. **Add notifications page** — list view beyond just the bell dropdown

### Long-term (Q4 2026)

7. **Rename ambiguous source routes** in a v2 API prefix
8. **API versioning strategy** — plan for `/api/v2` when breaking changes accumulate
9. **OpenAPI client generation** — auto-generate TypeScript types from `openapi.json`

---

## 5. Security Checklist

| Check | Status |
|---|---|
| All CRUD endpoints require auth | ✅ (via `Depends(require_auth)`) |
| Webhooks use separate validation | ✅ (shared secret) |
| Rate limiting on all routes | ✅ (RateLimitMiddleware) |
| CORS configured | ✅ (from `.env`) |
| Tenant isolation in repos | ✅ (tenant_id scoped) |
| Input validation (Pydantic) | ✅ (request models) |
| SQL injection prevention | ✅ (SQLAlchemy ORM) |
| JWT token validation | ✅ (decode_access_token) |
| Password hashing | ✅ (bcrypt via passlib) |
| Health endpoints unauthenticated | ✅ (intentional) |
| Metrics endpoint unauthenticated | ⚠️ Consider restricting in production |

---

*Generated by API Audit — April 17, 2026*


