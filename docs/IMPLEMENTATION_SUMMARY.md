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
- 136 tests passing (91 unit + 45 integration)
- Task registration, phone normalization, helper functions, Celery config
- WebSocket ConnectionManager (connect, disconnect, broadcast, tenant isolation)
- Integration tests for all new HTTP endpoints

## Next Steps

1. **Data Import** - Run actual batch import of leads-numbers and call logs
2. **CRM/ERP Integration** - Connect to custom MongoDB-based CRM
3. **Kavenegar API Integration** - Live SMS sending and delivery tracking
4. **Dashboard Enhancements** - WebSocket-connected real-time updates in UI
5. **Kubernetes Deployment** - Production manifests and CI/CD pipeline
6. **Advanced Analytics** - Cohort analysis, A/B test tracking, ROI calculation

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (primary), MongoDB (tenant data)
- **Cache**: Redis
- **Task Queue**: Celery with Redis broker
- **Real-time**: WebSocket + Redis pub/sub
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic v2
- **VoIP**: Asterisk integration
- **SMS**: Kavenegar API

