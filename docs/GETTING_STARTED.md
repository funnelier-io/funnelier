# Getting Started with Funnelier

Funnelier (فانلیر) is a multi-tenant SaaS platform for B2B building-materials marketing funnel analytics.

## Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- Docker & Docker Compose (for shared dev infrastructure)

## Quick Setup

### 1. Start Shared Dev Infrastructure

Funnelier uses a shared dev infrastructure for databases and reverse proxy.

```bash
cd /Users/univers/projects/infra
DOCKER_HOST="unix://${HOME}/.docker/run/docker.sock" docker compose up -d
```

This starts PostgreSQL (5435), Redis (6381), MongoDB (27017), and Traefik (80).  
See [Infra ONBOARDING](/Users/univers/projects/infra/ONBOARDING.md) for details.

### 2. Clone & Create Virtual Environment

```bash
cd /Users/univers/projects/funnelier

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate   # macOS/Linux

# Install backend with dev dependencies
pip install -e ".[dev]"
```

### 3. Run Database Migrations

```bash
PYTHONPATH=. alembic upgrade head
```

### 4. Start the Backend API

```bash
PYTHONPATH=. uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Direct: **http://localhost:8000**
- Via Traefik: **http://api.funnelier.localhost**
- Swagger Docs: http://localhost:8000/api/docs
- Health check: http://localhost:8000/health

A default **admin** user is seeded automatically:
- Username: `admin`
- Password: `admin1234`

### 5. Start the Frontend

```bash
cd frontend
npm install
npm run dev -- -p 3003
```

Frontend runs at:
- Direct: **http://localhost:3003**
- Via Traefik: **http://funnelier.localhost**

### 6. Start Celery Worker (background tasks, optional)

```bash
PYTHONPATH=. celery -A src.infrastructure.messaging.tasks worker --loglevel=info
```

### Quick alternative (Makefile)

```bash
make dev-backend    # Backend on :8000
make dev-frontend   # Frontend on :3003
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
