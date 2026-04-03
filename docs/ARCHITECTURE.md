# Funnelier - Marketing Funnel Analytics Platform

## Architecture Overview

Funnelier is a **multi-tenant SaaS platform** for marketing funnel analytics, designed following **Domain-Driven Design (DDD)** principles with a **Modular Monolith** architecture that can evolve into microservices.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              WEB DASHBOARD                                   │
│                    (React/Next.js + TypeScript)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                               API GATEWAY                                    │
│                      (FastAPI + Authentication)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                           APPLICATION LAYER                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Leads     │ │   Funnel    │ │     RFM     │ │  Campaign   │           │
│  │   Module    │ │   Module    │ │   Module    │ │   Module    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │   Sales     │ │  Products   │ │  Analytics  │ │   Alerts    │           │
│  │   Module    │ │   Module    │ │   Module    │ │   Module    │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────────────────────┤
│                          INFRASTRUCTURE LAYER                                │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │    ETL      │ │  Connectors │ │   Events    │ │   Queue     │           │
│  │   Engine    │ │   (Adapters)│ │    Bus      │ │   (Celery)  │           │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘           │
├─────────────────────────────────────────────────────────────────────────────┤
│                            DATA SOURCES                                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│  │ CSV  │ │ Excel│ │ JSON │ │MongoDB│ │ MySQL│ │ API  │ │ VoIP │           │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘ └──────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Domain Model

### Bounded Contexts

1. **Lead Management** - Managing lead sources, phone numbers, categories
2. **Communication Tracking** - SMS, Calls (mobile + VoIP), delivery status
3. **Sales Pipeline** - Pre-invoices, payments, conversions
4. **Analytics** - Funnel metrics, conversion rates, trends
5. **Segmentation** - RFM analysis, customer segments, recommendations
6. **Campaign Management** - SMS templates, targeting, scheduling
7. **Team Performance** - Sales team metrics, assignments, KPIs
8. **Tenant Management** - Multi-tenant configuration, data isolation

### Core Entities

```
┌─────────────────────────────────────────────────────────────────┐
│                        TENANT (Root)                             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐      │
│  │  Lead   │───▶│ Contact │───▶│  Event  │───▶│ Invoice │      │
│  │ Source  │    │ (Phone) │    │  (SMS/  │    │         │      │
│  │         │    │         │    │  Call)  │    │         │      │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘      │
│       │              │              │              │            │
│       │              │              │              ▼            │
│       │              │              │         ┌─────────┐      │
│       │              │              │         │ Payment │      │
│       │              │              │         └─────────┘      │
│       │              │              │                          │
│       ▼              ▼              ▼                          │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                    │
│  │Category │    │ Segment │    │Salesperson                   │
│  │         │    │  (RFM)  │    │         │                    │
│  └─────────┘    └─────────┘    └─────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Funnel Stages

```
┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐    ┌────────────┐
│   LEAD     │───▶│    SMS     │───▶│    CALL    │───▶│  INVOICE   │───▶│  PAYMENT   │
│  ACQUIRED  │    │    SENT    │    │  ANSWERED  │    │   ISSUED   │    │  RECEIVED  │
│            │    │            │    │  (≥90sec)  │    │            │    │            │
└────────────┘    └────────────┘    └────────────┘    └────────────┘    └────────────┘
      │                │                 │                 │                 │
      │                │                 │                 │                 │
      ▼                ▼                 ▼                 ▼                 ▼
   Stage 1          Stage 2           Stage 3          Stage 4           Stage 5
   
   Conversion Rates:
   - SMS Rate: Stage2 / Stage1
   - Call Rate: Stage3 / Stage2  
   - Invoice Rate: Stage4 / Stage3
   - Payment Rate: Stage5 / Stage4
   - Overall: Stage5 / Stage1
```

## RFM Segmentation Model

### Scoring (1-5 scale)

| Score | Recency (days) | Frequency (purchases) | Monetary (IRR) |
|-------|----------------|----------------------|----------------|
| 5     | 0-3            | 10+                  | 1B+            |
| 4     | 4-7            | 5-9                  | 500M-1B        |
| 3     | 8-14           | 3-4                  | 100M-500M      |
| 2     | 15-30          | 2                    | 50M-100M       |
| 1     | 30+            | 1                    | <50M           |

### Customer Segments

| Segment | RFM Pattern | Description | Recommended Action |
|---------|-------------|-------------|-------------------|
| Champions | 555, 554, 545 | Best customers | Exclusive offers, VIP treatment |
| Loyal | 435, 534, 443 | Regular buyers | Upsell, cross-sell |
| Potential Loyalist | 512, 513, 412 | Recent with potential | Build relationship |
| New Customers | 511, 411, 311 | Just acquired | Welcome sequence |
| Promising | 312, 313, 321 | Showing interest | Convert to loyal |
| Need Attention | 333, 332, 323 | Above average, slipping | Re-engage |
| About to Sleep | 233, 232, 223 | Below average | Win-back campaign |
| At Risk | 155, 154, 145 | High value, not recent | Urgent re-activation |
| Can't Lose | 255, 254, 245 | Best but leaving | Aggressive win-back |
| Hibernating | 111, 112, 121 | Lowest engagement | Cost-effective reactivation |
| Lost | 211, 111, 122 | Long gone | Remove or last attempt |

## Technology Stack

### Backend
- **Python 3.11+** - Primary language
- **FastAPI** - API framework (async, high performance)
- **SQLAlchemy 2.0** - ORM with async support
- **PostgreSQL** - Primary database (multi-tenant)
- **Redis** - Caching, session management
- **Celery** - Background tasks, scheduling
- **Apache Airflow** - ETL orchestration (optional)

### Frontend
- **Next.js 16** - React framework (App Router, React Compiler, standalone Docker output)
- **React 19** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS 4** - Utility-first styling, RTL support
- **Recharts 3** - Data visualization (bar, line, pie, doughnut)
- **Zustand 5** - Lightweight state management (auth store)
- **Custom `useApi` hook** - SWR-style data fetching with JWT auto-refresh
- **WebSocket** - Real-time event streaming with auto-reconnect
- **UI Components** - StatCard, DataTable (skeleton loading), DateRangePicker, ErrorAlert, EmptyState, ContactDetailPanel, ToastContainer

### Infrastructure
- **Docker** - Containerization
- **Docker Compose** - Local development
- **Traefik** - Reverse proxy (via shared infra)

## Multi-Tenancy Strategy

- **Database per tenant schema** - Data isolation with shared infrastructure
- **Tenant identification** via subdomain or header
- **Configurable connectors** per tenant for different data sources

## Directory Structure

```
funnelier/
├── src/
│   ├── core/                    # Shared kernel
│   │   ├── domain/              # Base entities, value objects
│   │   ├── events/              # Domain events
│   │   ├── interfaces/          # Abstract interfaces
│   │   └── utils/               # Shared utilities
│   │
│   ├── modules/                 # Bounded contexts
│   │   ├── leads/               # Lead management
│   │   ├── communications/      # SMS, Calls tracking
│   │   ├── sales/               # Invoices, Payments
│   │   ├── analytics/           # Funnel, metrics
│   │   ├── segmentation/        # RFM, segments
│   │   ├── campaigns/           # SMS campaigns
│   │   ├── team/                # Sales team
│   │   └── tenants/             # Multi-tenant
│   │
│   ├── infrastructure/          # Technical concerns
│   │   ├── database/            # DB connections
│   │   ├── connectors/          # Data source adapters
│   │   ├── etl/                 # ETL pipelines
│   │   ├── messaging/           # Event bus, queues
│   │   └── external/            # Third-party integrations
│   │
│   ├── api/                     # API layer
│   │   ├── routes/              # API endpoints
│   │   ├── middleware/          # Auth, tenant resolution
│   │   └── schemas/             # Request/Response DTOs
│   │
│   └── web/                     # Frontend (Next.js)
│
├── tests/                       # Test suites
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── docs/                        # Documentation
├── scripts/                     # Utility scripts
└── docker/                      # Docker configs
```

## Key Features

1. **Flexible Data Ingestion**
   - CSV/Excel file uploads
   - API integrations (Kavenegar, etc.)
   - Database connections (MongoDB, MySQL, etc.)
   - Real-time webhooks
   - Scheduled batch imports

2. **Funnel Analytics**
   - Customizable funnel stages
   - Daily/weekly/monthly conversion tracking
   - Stage-by-stage drop-off analysis
   - Cohort analysis

3. **RFM Segmentation**
   - Automatic scoring
   - Custom segment definitions
   - Product recommendations per segment
   - Segment migration tracking

4. **Campaign Management**
   - Template management
   - Segment targeting
   - A/B testing support
   - Scheduling and automation

5. **Team Performance**
   - Per-salesperson metrics
   - Lead assignment tracking
   - Conversion leaderboards
   - Activity logging

6. **Alerting & Notifications**
   - Threshold-based alerts
   - Anomaly detection
   - Email/SMS/Webhook notifications
   - Custom alert rules

## API Design

RESTful API with OpenAPI specification:

```
/api/v1/
├── /tenants                    # Tenant management
├── /leads                      # Lead sources & contacts
├── /communications             # SMS & Call logs
│   ├── /sms
│   └── /calls
├── /sales                      # Invoices & Payments
│   ├── /invoices
│   └── /payments
├── /analytics                  # Funnel & metrics
│   ├── /funnel
│   ├── /conversion
│   └── /trends
├── /segments                   # RFM & segmentation
├── /campaigns                  # Campaign management
├── /team                       # Sales team
├── /connectors                 # Data source configs
├── /etl                        # ETL jobs
└── /alerts                     # Alert management
```

