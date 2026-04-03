# Funnelier Implementation Summary

## Project Overview

Funnelier is a comprehensive multi-tenant SaaS platform for marketing funnel analytics, designed to track the complete customer journey from lead acquisition through payment. This document summarizes the implemented components.

## Architecture

The application follows **Domain-Driven Design (DDD)** with a **Modular Monolith** architecture:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              API Layer                                   │
│                         FastAPI Application                             │
├─────────────────────────────────────────────────────────────────────────┤
│  Leads   │ Communications │  Sales  │ Analytics │ Segments │ Campaigns │
│  Module  │    Module      │ Module  │  Module   │  Module  │  Module   │
├─────────────────────────────────────────────────────────────────────────┤
│                         Core Domain                                      │
│              Entities, Value Objects, Domain Events                      │
├─────────────────────────────────────────────────────────────────────────┤
│                       Infrastructure                                     │
│       Database │ Connectors │ ETL │ Messaging │ External APIs           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Implemented Modules

### 1. Leads Module (`/api/v1/leads`)
- Contact CRUD operations
- Bulk import from CSV/Excel files
- Category and source management
- Salesperson assignment (manual and auto)
- Search and filtering

**Key Endpoints:**
- `GET /contacts` - List contacts with pagination
- `POST /contacts/bulk-import` - Bulk import contacts
- `POST /contacts/import-file` - Import from CSV/Excel
- `POST /contacts/auto-assign` - Auto-assign to salespeople
- `GET /categories` - List lead categories
- `GET /sources` - List lead sources

### 2. Communications Module (`/api/v1/communications`)
- SMS sending (single and bulk)
- SMS template management
- Call log tracking (mobile and VoIP)
- Delivery status tracking
- Communication timeline per contact

**Key Endpoints:**
- `POST /sms/send` - Send single SMS
- `POST /sms/send-bulk` - Bulk SMS sending
- `GET /templates` - List SMS templates
- `GET /calls` - List call logs
- `POST /calls/import-csv` - Import call logs
- `POST /voip/sync` - Sync VoIP call logs
- `GET /timeline/{contact_id}` - Communication history

### 3. Sales Module (`/api/v1/sales`)
- Product catalog management
- Invoice/pre-invoice creation
- Payment recording
- Data source integration (MongoDB)
- Sales statistics

**Key Endpoints:**
- `GET /products` - List products
- `GET /invoices` - List invoices
- `POST /invoices` - Create invoice
- `POST /invoices/{id}/payments` - Record payment
- `GET /data-sources` - List data sources
- `POST /data-sources/{id}/sync` - Sync from data source
- `GET /stats/top-customers` - Top customers by revenue

### 4. Analytics Module (`/api/v1/analytics`)
- Funnel metrics and conversion rates
- Daily/weekly reports
- Salesperson performance tracking
- Cohort analysis
- Optimization recommendations
- Alerting system

**Key Endpoints:**
- `GET /funnel` - Funnel metrics
- `GET /funnel/trend` - Daily funnel snapshots
- `GET /reports/daily` - Daily summary
- `GET /salespeople` - Team performance
- `GET /cohorts` - Cohort analysis
- `GET /alerts` - Active alerts

### 5. Segmentation Module (`/api/v1/segments`)
- RFM score calculation
- Segment distribution
- Product recommendations per segment
- Message template suggestions
- Segment migration tracking

**RFM Segments:**
- Champions (قهرمانان)
- Loyal (وفادار)
- Potential Loyalist (وفادار بالقوه)
- New Customers (مشتریان جدید)
- At Risk (در خطر)
- Hibernating (خواب)
- Lost (از دست رفته)

**Key Endpoints:**
- `GET /distribution` - Segment distribution
- `POST /analyze` - Run RFM analysis
- `GET /recommendations/{segment}` - Segment recommendations
- `GET /products/{contact_id}` - Product recommendations
- `GET /migration-report` - Segment migration

### 6. Campaigns Module (`/api/v1/campaigns`)
- Campaign creation and management
- A/B testing support
- Recipient targeting
- Campaign statistics
- Segment-based suggestions

**Key Endpoints:**
- `GET /campaigns` - List campaigns
- `POST /campaigns` - Create campaign
- `POST /campaigns/{id}/start` - Start campaign
- `GET /campaigns/{id}/stats` - Campaign statistics
- `POST /campaigns/ab-test` - Create A/B test
- `GET /suggestions/for-segment/{segment}` - Campaign suggestions

### 7. Team Module (`/api/v1/team`)
- Salesperson management
- Performance tracking
- Activity logging
- Assignment rules
- Sales targets

**Key Endpoints:**
- `GET /salespeople` - List salespeople
- `GET /performance` - Team performance
- `GET /salespeople/{id}/performance` - Individual performance
- `GET /performance/leaderboard` - Performance ranking
- `GET /targets` - Sales targets
- `GET /assignment-rules` - Assignment rules

### 8. Tenants Module (`/api/v1/tenants`)
- Multi-tenant configuration
- Tenant settings (funnel stages, RFM config)
- Data source management
- Integration configuration
- Usage and billing

**Key Endpoints:**
- `GET /me` - Current tenant info
- `GET /me/settings` - Tenant settings
- `PUT /me/settings` - Update settings
- `GET /me/data-sources` - Data sources
- `GET /me/integrations` - Integrations
- `GET /me/usage` - Usage statistics

## Infrastructure Components

### Connectors
1. **Asterisk VoIP Connector** - Self-hosted Asterisk PBX integration
   - AMI (Asterisk Manager Interface) support
   - CDR database direct access
   - JSON export parsing

2. **Kavenegar SMS Connector** - SMS provider integration
   - Send single/bulk SMS
   - Delivery status tracking
   - CSV report parsing
   - Webhook handling

3. **MongoDB Connector** - Invoice/payment data sync
4. **CSV/Excel Connectors** - Lead and call log imports

### ETL Pipeline
- Extractors for multiple data sources
- Transformers for data normalization
- Loaders for database insertion
- Scheduler for batch processing

### Alerts & Notifications
- Threshold-based alert rules
- Multiple notification channels (email, SMS, webhook, dashboard)
- Default alert rules for common scenarios

## Web Dashboard
Basic dashboard with:
- KPI cards (leads, SMS, calls, revenue)
- Funnel visualization
- RFM segment distribution
- Team performance table
- Recent activity feed

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Leads     │────▶│    SMS      │────▶│    Call     │
│  (Excel)    │     │ (Kavenegar) │     │ (CSV/VoIP)  │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────┐
│                  Contact Record                      │
│        (phone_number is the primary key)            │
└─────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  Invoice    │────▶│  Payment    │
│ (MongoDB)   │     │ (MongoDB)   │
└─────────────┘     └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────────────────────────────────────────────┐
│                  RFM Calculation                     │
│    Recency │ Frequency │ Monetary → Segment         │
└─────────────────────────────────────────────────────┘
```

## Configuration

### Funnel Stages (Customizable per tenant)
1. Lead Acquired (سرنخ جدید)
2. SMS Sent (پیامک ارسال شده)
3. SMS Delivered (پیامک تحویل شده)
4. Call Attempted (تماس گرفته شده)
5. Call Answered (تماس پاسخ داده شده) - ≥90 seconds
6. Invoice Issued (پیش‌فاکتور صادر شده)
7. Payment Received (پرداخت دریافت شده)

### RFM Thresholds (Customizable)
- Recency: 7, 14, 30, 60, 90 days
- Frequency: 1, 2, 4, 8, 16 purchases
- Monetary: 100M, 500M, 1B, 2B, 5B IRR
- High-value threshold: 1B IRR
- Recent period: 14 days

## Completed Phases

1. ✅ **Phase 1** - Core DDD architecture, domain entities, modules, ETL connectors
2. ✅ **Phase 2** - PostgreSQL persistence layer, SQLAlchemy repositories, migrations
3. ✅ **Phase 3** - Test infrastructure, integration tests, bug fixes
4. ✅ **Phase 4** - JWT authentication with RBAC, user management
5. ✅ **Phase 5** - Web dashboard with live API data, Chart.js charts
6. ✅ **Phase 6** - Celery background tasks, WebSocket real-time updates, async imports
7. ✅ **Phase 7** - Wire real data, fix ETL pipeline, analytics & segmentation wired to DB
8. ✅ **Phase 8** - Sales frontend page, responsive layout, new UI components
9. ✅ **Phase 9** - Date filtering, skeleton loading, Docker frontend, utility polish
10. ✅ **Phase 15** - Global Search & Command Palette (⌘+K), unified multi-entity search API

## Phase 6 Details: Background Tasks & Real-time

### Celery App (`src/infrastructure/messaging/celery_app.py`)
- Redis-backed Celery with task routing (imports, analytics, notifications, sync queues)
- Beat schedule for periodic tasks:
  - Daily funnel snapshot (1:00 AM)
  - Daily RFM recalculation (2:00 AM)
  - Hourly alert check
  - Daily report generation (6:00 AM)

### Background Tasks (`src/infrastructure/messaging/tasks.py`)
- **Import Tasks**: `import_leads_excel`, `import_call_logs_csv`, `import_sms_logs_csv`, `import_voip_json`, `import_leads_batch`
- **Analytics Tasks**: `calculate_daily_funnel_snapshot`, `calculate_rfm_segments`
- **Report Tasks**: `generate_daily_report`
- **Alert Tasks**: `check_alerts`
- **Sync Tasks**: `sync_mongodb_invoices`
- **Notification Tasks**: `send_sms_notification`
- All tasks publish events to WebSocket via Redis pub/sub

### WebSocket (`src/api/websocket.py`)
- Real-time event streaming via `/ws` endpoint
- ConnectionManager with tenant-scoped broadcasting
- Redis pub/sub listener for cross-process event delivery
- Task status polling via `GET /api/v1/tasks/{task_id}`

### Async Import Endpoints
- `POST /api/v1/import/leads/upload-async` - Background Excel import
- `POST /api/v1/import/calls/upload-async` - Background CSV call log import
- `POST /api/v1/import/sms/upload-async` - Background SMS log import
- `POST /api/v1/import/voip/upload-async` - Background VoIP JSON import
- `POST /api/v1/import/leads/batch-async` - Background batch import all leads
- `POST /api/v1/import/analytics/funnel-snapshot` - Trigger funnel snapshot
- `POST /api/v1/import/analytics/rfm-recalculate` - Trigger RFM recalculation

### Test Coverage
- 100 unit tests passing
- Task registration, phone normalization, helper functions, Celery config
- WebSocket ConnectionManager (connect, disconnect, broadcast, tenant isolation)
- Integration tests for all HTTP endpoints

---

## Phase 7: Wire Real Data, Fix ETL Pipeline, Analytics & Segmentation

### ETL Pipeline Fixes (`src/modules/etl/api/routes.py`, `src/infrastructure/messaging/tasks.py`)
- Fixed all broken imports: `src.infrastructure.database.repositories.leads` → `src.modules.leads.infrastructure.repositories`
- Fixed all broken imports: `src.infrastructure.database.repositories.communications` → `src.modules.communications.infrastructure.repositories`
- Fixed all broken imports: `src.infrastructure.database.repositories.sales` → `src.modules.sales.infrastructure.repositories`
- Replaced `repo.create(dict)` / `repo.find_by_field(...)` with proper domain entity construction + `repo.add(entity)` / `repo.get_by_phone(phone)`
- All 6 sync ETL routes, 6 Celery tasks, and 1 batch route now use correct repositories with tenant-scoped sessions
- Construct proper `Contact`, `CallLog`, `SMSLog`, `Invoice` domain entities in all import paths

### New Database Models + Migration
- `FunnelSnapshotModel` — daily funnel stage counts, conversion rates, revenue (`funnel_snapshots` table)
- `AlertRuleModel` — configurable alert rules with thresholds, severity, notification channels (`alert_rules` table)
- `AlertInstanceModel` — triggered alert instances with status tracking (`alert_instances` table)
- `ImportLogModel` — import job tracking with status, results, timing (`import_logs` table)
- Alembic migration `b0a6f0d6de83` adds all 4 tables with proper indexes and constraints

### Analytics Wired to Real Database (`src/modules/analytics/api/routes.py`)
- `GET /api/v1/analytics/funnel` — real stage counts from contacts table
- `GET /api/v1/analytics/funnel/trend` — snapshots from `funnel_snapshots` table
- `GET /api/v1/analytics/funnel/by-source` — contacts grouped by source_name
- `GET /api/v1/analytics/reports/daily` — real lead counts, SMS stats, call stats
- `GET /api/v1/analytics/reports/weekly` — real week-over-week comparison
- `GET /api/v1/analytics/salespeople` — real salesperson data from DB
- `GET /api/v1/analytics/cohorts` — real cohort analysis from contact creation dates
- `GET /api/v1/analytics/optimization` — bottleneck detection from actual stage counts
- `GET /api/v1/analytics/alerts` — alerts from `alert_instances` table
- `POST /api/v1/analytics/alerts/rules` — create alert rules persisted to DB
- `GET /api/v1/analytics/alerts/rules` — list all alert rules
- `POST /api/v1/analytics/alerts/{id}/acknowledge` — acknowledge alerts

### Segmentation Wired to Real Database (`src/modules/segmentation/api/routes.py`)
- `POST /api/v1/segments/analyze` — RFM distribution from contacts table
- `GET /api/v1/segments/distribution` — real segment counts per RFM segment
- `GET /api/v1/segments/profiles` — paginated contact profiles with RFM scores
- `GET /api/v1/segments/profiles/{id}` — individual contact RFM profile
- `GET /api/v1/segments/products/{id}` — product recommendations based on real segment
- `POST /api/v1/segments/campaign-contacts` — contacts by target segments from DB
- `GET /api/v1/segments/high-priority` — at_risk + cant_lose contacts from DB

### Analytics Infrastructure Repositories (`src/modules/analytics/infrastructure/repositories.py`)
- `FunnelSnapshotRepository` — upsert snapshots, query by date range, get latest
- `AlertRuleRepository` — CRUD for alert rules
- `AlertInstanceRepository` — create, get active/all, acknowledge, resolve, count
- `ImportLogRepository` — create, update status, get by task/type, stats summary

### Contact Repository Analytics Methods (`src/modules/leads/infrastructure/repositories.py`)
- `get_stage_counts()` — count contacts per funnel stage
- `count_new_contacts()` — count contacts created in date range
- `get_contacts_with_stages()` — contacts with stage info for funnel calculation
- `get_contacts_grouped_by_source()` — group contacts by source_name
- `get_contacts_grouped_by_category()` — group contacts by category_name
- `get_stage_transitions()` — stage transition counts
- `get_salespeople()` — distinct salespeople from assigned contacts
- `get_rfm_distribution()` — count contacts per RFM segment

### Call Log Repository Enhancement
- `get_daily_stats()` — call stats for daily report (total, answered, successful, rates)

### Celery Task Enhancements
- Funnel snapshot task now persists to `funnel_snapshots` table via `FunnelSnapshotRepository`
- RFM calculation task now persists segment assignments back to contact records
- All import tasks use proper domain entities and tenant-scoped repositories

### Import History
- `GET /api/v1/import/history` — paginated import job history with type filtering
- `GET /api/v1/import/stats` — import statistics summary

### Route Prefix Fixes
- Fixed double-prefix issue on analytics routes (`/api/v1/analytics/analytics/...` → `/api/v1/analytics/...`)
- Fixed double-prefix issue on segmentation routes (`/api/v1/segments/segmentation/...` → `/api/v1/segments/...`)

### Dependency Injection (`src/api/dependencies.py`)
- Added `get_funnel_snapshot_repository`
- Added `get_alert_rule_repository`
- Added `get_alert_instance_repository`
- Added `get_import_log_repository`

## Phase 8: Sales Frontend & Dashboard Polish

### Sales Page (`/sales`)
- Full Sales dashboard with three tabs: Invoices, Products, Payments
- **Invoices tab**: paginated invoice list with status filtering (draft, issued, paid, overdue, cancelled), summary banner showing total amounts and payments, Persian status labels and color-coded badges
- **Products tab**: product catalog with category summary cards, availability status, recommended segments, pricing (base & current), unit display
- **Payments tab**: payment transactions list with total amount summary, payment method, reference numbers, dates
- KPI stat cards: total invoices, total revenue, paid count, average order value with conversion rate

### Types & Constants
- `types/sales.ts`: Product, ProductListResponse, Invoice, InvoiceLineItem, InvoiceListResponse, Payment, PaymentListResponse, SalesStats
- Added `INVOICE_STATUS_LABELS` and `INVOICE_STATUS_COLORS` to constants
- Added Sales nav item (`💰 فروش`) to sidebar navigation
- Exported all sales types from `types/index.ts`

### Dashboard Pages Summary (all 11 pages complete)
1. `/` — Main dashboard with KPIs, funnel chart, RFM doughnut, trend line, optimization insights, recent alerts
2. `/leads` — Contact list with search, stage/segment filters, contact detail panel with communication timeline
3. `/funnel` — Funnel visualization, stage details, conversion rate table, daily trend chart
4. `/segments` — RFM distribution chart, segment details list, marketing recommendations per segment
5. `/communications` — Call logs and SMS logs with tabs, call/SMS stats, pagination
6. `/sales` — Invoices, products, and payments with tabs, status filtering, category summaries
7. `/campaigns` — Campaign CRUD, status tabs, A/B testing, recipient targeting
8. `/imports` — File scan, upload, import history, top categories breakdown
9. `/alerts` — Alert instances with acknowledge, alert rules CRUD, severity indicators
10. `/team` — Team performance table, KPI cards, top performers & improvement needed
11. `/settings` — Data source status cards, file scanner, file upload with drag-drop, import history

### Responsive Layout
- **Mobile sidebar**: collapsible sidebar with hamburger menu, backdrop overlay, auto-close on route change
- **Desktop**: sidebar always visible with `lg:translate-x-0`, main content offset with `lg:mr-60`
- **Mobile header**: sticky top bar with hamburger button and centered branding
- **Responsive padding**: `p-4 lg:p-6` for main content area

### New UI Components
- `ErrorAlert` — inline error alert with optional retry button, red theme
- `EmptyState` — zero-data placeholder with icon, title, description, and optional CTA button
- `SalesBarChart` — vertical bar chart for revenue/sales data with Persian currency formatting

## Phase 9: Date Filtering, Skeleton Loading, Docker & Polish

### Date Range Picker (`DateRangePicker` component)
- Reusable compact date-range picker with preset buttons (۷ روز, ۳۰ روز, ۹۰ روز, ۱ سال) and custom date inputs
- Integrated into **Dashboard** (`/`) — funnel & trend API calls now pass `start_date` / `end_date` query params
- Integrated into **Funnel** (`/funnel`) — same date filtering for funnel metrics and trend data
- Presets auto-detect active range; custom mode shows native date inputs
- Zero external dependencies — uses native `<input type="date">`

### DataTable Skeleton Loading
- Replaced plain-text loading state with animated skeleton rows
- 5 placeholder rows with `animate-pulse` Tailwind shimmer effect
- Column headers visible during loading for layout stability
- Variable-width bars per cell for natural appearance

### Settings Page — Wired Data Sources
- Replaced 6 hardcoded `DataSourceCard` blocks with dynamic data from `GET /tenants/me/data-sources`
- Merges API-returned data sources with static infrastructure list (PostgreSQL, Redis, MongoDB, Kavenegar, Asterisk, Excel)
- Shows last sync time and records synced when available from API
- Graceful fallback: infrastructure cards show sensible defaults when API returns empty list

### Utility: `fmtPercentRaw`
- Added `fmtPercentRaw(n)` for values already in 0–100 range (e.g., `85 → ۸۵.۰٪`)
- Eliminated error-prone `fmtPercent(x / 100)` workaround in Funnel and Segments pages
- Existing `fmtPercent(n)` unchanged for 0–1 ratio inputs

### Frontend Dockerfile & Docker Compose
- Created `docker/Dockerfile.frontend` — multi-stage build (deps → build → runner) with `node:20-alpine`
- Uses Next.js `output: "standalone"` for optimized Docker image (~150MB vs ~1GB)
- Added `frontend` service to `docker-compose.yml` — port 3000, depends on API, passes `NEXT_PUBLIC_API_URL`
- Added `make docker-build` target to Makefile
- `next.config.ts` updated with `output: "standalone"` (compatible with both dev and production)

### Build Status
- ✅ 15 pages compiled successfully (TypeScript strict mode)
- ✅ All 11 dashboard pages + login + 404 + layout functional

## Next Steps

1. **Global Search & Command Palette** - Ctrl+K shortcut, multi-entity search (leads, campaigns, invoices)
2. **Import Call Logs & SMS Data** - Run actual import of call logs CSV and SMS delivery reports
3. **Run RFM Calculation** - Execute RFM segmentation task to score all contacts
4. **CRM/ERP Integration** - Connect to custom MongoDB-based CRM for invoice/payment sync
5. **Kavenegar API Integration** - Live SMS sending and delivery tracking
6. **Kubernetes Deployment** - Production manifests and CI/CD pipeline

## Tech Stack

- **Backend**: FastAPI, SQLAlchemy 2.0 (async), Pydantic v2
- **Frontend**: Next.js 16, React 19, Tailwind CSS 4, Recharts 3, Zustand 5
- **Database**: PostgreSQL (primary), MongoDB (tenant data)
- **Cache**: Redis
- **Task Queue**: Celery with Redis broker
- **Real-time**: WebSocket + Redis pub/sub
- **VoIP**: Asterisk integration
- **SMS**: Kavenegar API
- **Deployment**: Docker Compose (backend + frontend + Celery + PostgreSQL + Redis + MongoDB)

