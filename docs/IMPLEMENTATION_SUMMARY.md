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

## Next Steps

1. **Database Implementation** - Create SQLAlchemy repository implementations
2. **Authentication** - Implement JWT-based auth with tenant isolation
3. **Background Jobs** - Celery tasks for ETL and scheduled reports
4. **Real-time Updates** - WebSocket support for dashboard
5. **Testing** - Unit and integration tests
6. **Deployment** - Kubernetes manifests for production

## Tech Stack

- **Framework**: FastAPI
- **Database**: PostgreSQL (primary), MongoDB (tenant data)
- **Cache**: Redis
- **Task Queue**: Celery
- **ORM**: SQLAlchemy 2.0 (async)
- **Validation**: Pydantic v2
- **VoIP**: Asterisk integration
- **SMS**: Kavenegar API

