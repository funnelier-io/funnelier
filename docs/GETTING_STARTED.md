# Getting Started with Funnelier

Funnelier (فانلیر) is a multi-tenant SaaS platform for B2B building-materials marketing funnel analytics.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- MongoDB 6+ (for invoice/payment data sources)
- Node.js 20+ (for the frontend)
- Docker & Docker Compose (recommended for infrastructure)

## Quick Setup

### 1. Clone & Create Virtual Environment

```bash
cd funnelier

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux

# Install backend with dev dependencies
pip install -e ".[dev]"

# Copy environment config and customise as needed
cp .env.example .env
```

### 2. Start Infrastructure (Docker Compose)

```bash
cd docker
docker compose up -d postgres redis mongodb
cd ..
```

This starts:
| Service    | Host Port | Container Port |
|------------|-----------|----------------|
| PostgreSQL | 5433      | 5432           |
| Redis      | 6384      | 6379           |
| MongoDB    | 27019     | 27017          |

### 3. Run Database Migrations

```bash
PYTHONPATH=. alembic upgrade head
```

### 4. Start the Backend API

```bash
PYTHONPATH=. uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**

- Swagger Docs: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc
- Health check: http://localhost:8000/health

A default **admin** user is seeded automatically:
- Username: `admin`
- Password: `admin1234`

### 5. Start the Frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:3000**.

### 6. Start Celery Worker (background tasks)

```bash
PYTHONPATH=. celery -A src.infrastructure.messaging.tasks worker --loglevel=info
```

## Authentication

All API endpoints (except `/health`, `/api/v1`, and auth routes) require a JWT bearer token.

```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin1234"}'

# Use the returned access_token
curl http://localhost:8000/api/v1/leads/stats/summary \
  -H "Authorization: Bearer <access_token>"
```

## Importing Data

### Import Leads from Excel

Place Excel files in `leads-numbers/` organised by category, then run:

```bash
PYTHONPATH=. python scripts/import_leads.py
```

### Import Call Logs from CSV

Place CSV files in `call logs/`, then run:

```bash
PYTHONPATH=. python scripts/import_call_logs.py
```

### Seed Salespeople

```bash
PYTHONPATH=. python scripts/seed_salespeople.py
```

### Trigger Analytics Recalculation

After importing data, trigger funnel snapshots and RFM scoring:

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/import/analytics/funnel-snapshot \
  -H "Authorization: Bearer <token>"
curl -X POST http://localhost:8000/api/v1/import/analytics/rfm-recalculate \
  -H "Authorization: Bearer <token>"
```

## Running Tests

```bash
# Unit tests
PYTHONPATH=. pytest tests/unit/ -v

# Integration tests (requires running PostgreSQL, Redis, MongoDB)
PYTHONPATH=. pytest tests/integration/ -v
```

## Project Structure

```
src/
├── api/          # FastAPI app, routes, middleware, schemas
├── core/         # Domain models, events, interfaces, config
├── infrastructure/
│   ├── connectors/   # Asterisk VoIP, Kavenegar SMS
│   ├── database/     # SQLAlchemy models, session, migrations
│   ├── etl/          # Excel, CSV, JSON, MongoDB, API extractors
│   └── messaging/    # Celery tasks, Redis pub/sub
├── modules/
│   ├── analytics/    # Funnel metrics, reports, alerts
│   ├── auth/         # JWT authentication, RBAC
│   ├── campaigns/    # SMS campaigns
│   ├── communications/ # SMS/call logs
│   ├── leads/        # Contact management
│   ├── sales/        # Products, invoices, payments
│   ├── segmentation/ # RFM analysis
│   ├── team/         # Salesperson management
│   └── tenants/      # Multi-tenant management
frontend/             # Next.js 16 + React 19 dashboard
```

## Funnel Stages

1. **lead_acquired** → 2. **sms_sent** → 3. **sms_delivered** → 4. **call_attempted** → 5. **call_successful** → 6. **invoice_sent** → 7. **payment_received**

## Environment Variables

See [.env.example](../.env.example) for all configuration options including database URLs, JWT secrets, Kavenegar API key, RFM thresholds, and funnel stage weights.
