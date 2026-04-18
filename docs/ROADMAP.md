# Funnelier — Project Roadmap

> **Platform:** Funnelier (فانلیر) — Multi-tenant SaaS for B2B Marketing Funnel Analytics
> **Domain:** Building materials industry (Iran market)
> **Architecture:** DDD Modular Monolith — FastAPI + Next.js
> **Created:** April 16, 2026

---

##  Current State Summary

| Metric | Value |
|---|---|
| Total Commits | 39 (on `main`) |
| Current Branch | `main` + `dev` (remote: `funnelier-io/funnelier`) |
| Tags | `v0.1.0` |
| Phases Completed | 36 of 36 planned |
| Backend Unit Tests | 721+ (Sprint 1: +143, Sprint 2: +82) |
| Frontend Pages | 14+ dashboard pages |
| Unstaged Work | None — all phases committed |

---

## ✅ Completed Phases

| # | Phase | Description | Tests Added |
|---|---|---|---|
| 1 | Initial Commit | DDD architecture, core domain, all modules, ETL, RFM, funnel tracking | baseline |
| 2 | Database Persistence | PostgreSQL, Alembic migrations, 15 tables, tenant-scoped repos | 19 E2E |
| 2b | Wire All Modules | Communications, Sales wired to DB, dependency cleanup | 35 E2E |
| 3 | Test Infrastructure | pytest-asyncio upgrade, integration tests, bug fixes | 60 total |
| 4 | Auth & RBAC | JWT, 5 roles, admin seeding, login/register/refresh | 81 total |
| 5 | Web Dashboard | Chart.js, 7 pages, live API data, RTL layout | — |
| 6 | Celery & WebSocket | 10 background tasks, Redis pub/sub, beat schedule, async imports | 136 total |
| 7 | Wire Real Data | Fix ETL pipeline, analytics from DB, new models (snapshots, alerts) | — |
| 8 | Call Log Import | 23,177 call logs from 5 CSVs, funnel stage updates | 100 unit |
| 9 | Dashboard Polish | Date filtering, skeleton loading, Docker frontend | — |
| 10 | Next.js Frontend | Campaigns, alerts, enhanced dashboard, settings | — |
| 11 | Campaigns → PostgreSQL | RFM calculation, SMS templates | — |
| 12 | Data Linkage | Link calls→contacts, funnel stages, RFM calc, imports page | — |
| 13 | Team Setup | 5 salespeople, call log linkage, tab UI, pagination | 131 unit |
| 14 | Enhanced Leads | Filters, contact detail panel, RFM badges | — |
| 15 | Communication Timeline | Timeline endpoint, contact panel integration | — |
| 16 | Sales Page & UI | Sales tabs, Command Palette, responsive layout, components | 131 unit |
| 17 | i18n & Connectors | next-intl, Persian/English, pluggable SMS/ERP interfaces | — |
| 18 | Kavenegar SMS | Live SMS, webhooks, Celery tasks, ERP sync API | — |
| 19 | ERP Sync Dashboard | Data sync page, scheduled jobs | — |
| 20 | Export & Reporting | PDF/Excel/CSV export, scheduled reports | — |
| 21 | Notification Center | Bell icon, read/unread, preferences | 15 tests |
| 22 | User Management UI | Admin CRUD, role assignment, password reset | 20 tests |
| 23 | Audit Trail | Activity log, change history, audit API | 15 tests |
| 24 | E2E Browser Tests | Playwright, 26 tests (auth, nav, leads, i18n) | 26 E2E |
| 25 | CI/CD & Production | GitHub Actions, K8s manifests, Docker, HPA, pre-commit | — |
| 26 | Predictive Analytics | Churn, lead scoring, A/B test, ROI, retention curves | 204 unit |
| 27 | Rate Limiting & Caching | Redis sliding-window, response cache, import throttle | 226 unit |
| 28 | Billing & Usage | 4 plans, feature gating, usage metering, enforcement | 249 unit |
| 29 | Structured Logging | structlog JSON, request logging, Prometheus metrics | 265 unit |
| 30 | Performance Testing | Locust scripts, query optimization, pool tuning | — |
| 31 | Multilingual Deep Dive | Jalali calendar, useFormat hook, 21 page migration | 294 unit |
| 32 | Camunda Infrastructure | REST client, external task workers, health checks | 348 unit |
| 33 | Campaign Workflow | BPMN process, 4 workers, Camunda-or-fallback | 379 unit |
| 34 | User Approval Workflow | BPMN, 5 workers, 48h timer, admin review task | 402 unit |
| 35 | Funnel Journey | Message correlation, DB fallback, journey API | 447 unit |
| 36 | Advanced Process Features | SMS compensation, stale-stage notify, ERP escalation BPMN | 447+ unit |

---

##  In Progress (Uncommitted)

None — all phases committed.

---

## ️ Upcoming Roadmap

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### Q2 2026 — Stabilization & Git Hygiene
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Milestone | Target |
|---|---|
| ✅ Complete Phase 36 (Advanced Process Features) | Apr 2026 |
| ✅ Set up GitHub remote, push all history → `funnelier-io/funnelier` | Apr 2026 |
| ✅ Establish branching strategy (see GIT_STRATEGY.md) | Apr 2026 |
| ✅ Tag `v0.1.0` baseline release | Apr 2026 |
| ✅ Create `dev` branch, enable branch protection on `main` | Apr 2026 |
| API endpoint audit & OpenAPI doc review | ✅ Apr 2026 |
| Frontend build audit (dead code, unused deps) | ✅ Apr 2026 |
| Test coverage report & gap analysis | ✅ Apr 2026 |
| Sprint 1: P0 test gaps closed (ETL, leads, sales, export) | ✅ Apr 18, 2026 (+143 tests) |
| Sprint 2: P1 test gaps closed (communications, analytics, connectors) | ✅ Apr 18, 2026 (+82 tests) |
| Sprint 3: Integration tests + pytest-cov CI gate at 65% | May 2026 |

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### Q3 2026 — Feature Hardening & UX Polish
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Milestone | Target |
|---|---|
| Phase 37: Multi-tenant onboarding wizard | Jul 2026 |
| Phase 38: Advanced RFM segmentation UI (drag-and-drop rules) | Jul–Aug 2026 |
| Phase 39: Campaign A/B split testing (live, not calculator) | Aug 2026 |
| Phase 40: Real-time dashboard with WebSocket push | Aug–Sep 2026 |
| Phase 41: Mobile-responsive audit & PWA | Sep 2026 |
| Phase 42: Camunda Process Monitoring Dashboard | Sep 2026 |
| Frontend E2E test expansion (target: 80+ Playwright tests) | Ongoing |
| Tag `v0.2.0` | Sep 2026 |

#### Phase 42: Camunda Process Monitoring Dashboard (NEW)
Frontend dashboard widget and dedicated page showing:
- Active / completed / failed process instance counts per workflow type
- Campaign pipeline visual — which BPMN step each campaign is at
- Stale process alerts — campaigns or contacts stuck beyond expected duration
- ERP escalation status overview with resolution actions
- Quick actions: pause / resume / cancel campaigns from the UI
- Links to Camunda Cockpit for detailed drill-down (admin only)

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### Q4 2026 — Production Readiness
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Milestone | Target |
|---|---|
| Security audit (auth, RBAC, input validation, SQL injection) | Oct 2026 |
| Load testing at production scale (1000+ concurrent tenants) | Oct 2026 |
| Data backup & disaster recovery plan | Nov 2026 |
| Monitoring stack (Grafana dashboards from Prometheus metrics) | Nov 2026 |
| SSL/TLS, domain configuration, CDN | Dec 2026 |
| Tag `v0.9.0` (release candidate) | Dec 2026 |

### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
### Q1 2027 — Launch
### ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

| Milestone | Target |
|---|---|
| Beta program with 3-5 pilot tenants | Jan 2027 |
| Feedback iteration & bug fixes | Jan–Feb 2027 |
| Operations runbook & on-call docs | Feb 2027 |
| Tag `v1.0.0`  **Production Launch** | Mar 2027 |

---

##  Notes

- **GitHub remote**: `funnelier-io/funnelier` (public). All 38 commits pushed.
- `main` branch is protected: requires 1 PR review, no force pushes.
- `dev` branch created for feature development.
- CI/CD workflows (`.github/workflows/ci.yml`, `cd.yml`) exist but have never been triggered.
- K8s manifests exist but are untested against a real cluster.
- See `docs/GIT_STRATEGY.md` for the full git versioning and GitHub sync plan.
- See `docs/IMPLEMENTATION_SUMMARY.md` for detailed phase descriptions.
- See `docs/CAMUNDA_FEASIBILITY.md` for the Camunda BPMS analysis.

