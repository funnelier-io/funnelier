# Funnelier — Agent Instructions

> Instructions for AI coding agents working on this project.
> Read this file FIRST before making any changes.

## Project Identity

**Funnelier** (فانلیر) is a multi-tenant SaaS platform for B2B marketing funnel analytics.  
Domain: building materials industry (Iran market). Persian-first UI with English i18n.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2 |
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS 4, Recharts, Zustand, next-intl |
| Database | PostgreSQL 15 (primary), MongoDB 7 (tenant CRM data) |
| Cache/Broker | Redis 7 (caching, rate limiting, Celery broker, WebSocket pub/sub) |
| Task Queue | Celery with Redis broker |
| Testing | pytest (backend), Playwright (E2E) |
| CI/CD | GitHub Actions, Docker, Kubernetes |

## Shared Dev Infrastructure

This project uses a **shared dev infrastructure** managed at `/Users/univers/projects/infra/`.  
See the [Infra ONBOARDING guide](/Users/univers/projects/infra/ONBOARDING.md) for full details.

### Starting Infrastructure

```bash
cd /Users/univers/projects/infra
DOCKER_HOST="unix://${HOME}/.docker/run/docker.sock" docker compose up -d
```

### Service Ports (shared infra)

| Service | Host Port | Project Usage |
|---|---|---|
| PostgreSQL | `5435` | `DATABASE_URL=postgresql+asyncpg://funnelier:funnelier@localhost:5435/funnelier` |
| Redis | `6381` | `REDIS_URL=redis://localhost:6381/0` (cache/rate-limit), `/1` (Celery broker), `/2` (Celery results) |
| MongoDB | `27017` | `MONGODB_URL=mongodb://mongo:mongo@localhost:27017/funnelier_tenant` |
| Traefik | `80` | `http://funnelier.localhost` (frontend), `http://api.funnelier.localhost` (backend) |

### Traefik Routes

Funnelier is registered in Traefik at `/Users/univers/projects/infra/traefik/routes/funnelier.yml`:
- Frontend: `http://funnelier.localhost` → `localhost:3003`
- Backend: `http://api.funnelier.localhost` → `localhost:8000`

## Running the Application

### Backend

```bash
cd /Users/univers/projects/funnelier

# Activate virtualenv (if not already)
source venv/bin/activate  # or use the project interpreter

# Run database migrations
PYTHONPATH=. alembic upgrade head

# Start backend
PYTHONPATH=. uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```bash
cd /Users/univers/projects/funnelier/frontend
npm install  # only on first run or after package.json changes
npm run dev -- -p 3003
```

### Quick alternative (Makefile)

```bash
make dev-backend    # Backend on :8000
make dev-frontend   # Frontend on :3003
```

## Authentication

Default admin credentials (auto-seeded on startup):
- **Username:** `admin`
- **Password:** `admin1234`
- **Tenant ID:** `00000000-0000-0000-0000-000000000001`

Get a token:
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin1234"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
```

## Project Structure

```
src/
├── api/              # FastAPI app, routes, middleware, WebSocket
│   ├── main.py       # Application factory & lifespan
│   ├── middleware/    # Rate limiting, caching, usage enforcement
│   ├── dependencies.py
│   └── routes.py     # Router aggregation
├── core/             # Config, domain base classes, cache utils
│   ├── config.py     # Pydantic settings (all env vars)
│   ├── cache.py      # Redis cache helpers
│   └── domain.py     # Base Entity, ValueObject
├── infrastructure/
│   ├── database/     # SQLAlchemy models, session, migrations
│   ├── redis_pool.py # Shared async Redis connection pool
│   ├── connectors/   # VoIP (Asterisk), SMS (Kavenegar)
│   ├── etl/          # Data extractors (Excel, CSV, JSON, MongoDB)
│   └── messaging/    # Celery tasks, providers (IMessagingProvider, IERPConnector)
├── modules/          # DDD bounded contexts
│   ├── analytics/    # Funnel metrics, predictive analytics, alerts
│   ├── auth/         # JWT, RBAC (5 roles)
│   ├── campaigns/    # SMS campaigns
│   ├── communications/ # SMS/call logs, webhook handlers
│   ├── leads/        # Contact CRUD, bulk import, categories
│   ├── notifications/ # In-app notification center
│   ├── sales/        # Products, invoices, payments, ERP sync
│   ├── segmentation/ # RFM analysis & recommendations
│   ├── team/         # Salesperson management
│   └── tenants/      # Multi-tenant, billing, usage metering
frontend/
├── src/app/[locale]/(dashboard)/  # Next.js pages (fa/en)
├── src/components/                # Shared UI components
├── src/lib/                       # API client, hooks, utils, constants
├── src/types/                     # TypeScript type definitions
├── messages/fa.json               # Persian translations
└── messages/en.json               # English translations
```

## Conventions

### Backend
- **DDD Modular Monolith**: each module has `api/`, `domain/`, `application/`, `infrastructure/` layers
- **Async everywhere**: all DB operations use `async/await` with SQLAlchemy async sessions
- **Tenant-scoped repositories**: every repository takes `(session, tenant_id)` at init
- **Config via pydantic-settings**: all env vars defined in `src/core/config.py`
- **Tests**: `tests/unit/` (no DB), `tests/integration/` (with DB). Use `pytest-asyncio` for async tests

### Frontend
- **App Router**: pages in `src/app/[locale]/(dashboard)/`
- **i18n**: all user-visible strings in `messages/fa.json` and `messages/en.json` via `next-intl`
- **API client**: `src/lib/api-client.ts` — all requests go through `api<T>(method, path, body?)` which auto-attaches JWT from localStorage
- **Hooks**: `useApi<T>(path)` for GET requests with SWR-like caching
- **Components**: `StatCard`, charts (Recharts), tables are in `src/components/`
- **Nav items**: add to `src/lib/constants.ts` NAV_ITEMS array + both translation files

### Adding a New Feature
1. Backend: create/update module in `src/modules/`, add route, register in `src/api/main.py`
2. Frontend: create page in `src/app/[locale]/(dashboard)/<name>/page.tsx`
3. Types: add to `frontend/src/types/`
4. Nav: add to `frontend/src/lib/constants.ts`
5. i18n: add keys to both `messages/fa.json` and `messages/en.json`
6. Tests: add unit tests in `tests/unit/test_<name>.py`

## Testing

```bash
# Run all unit tests (249 currently passing)
python -m pytest tests/unit/ -q

# Run a specific test file
python -m pytest tests/unit/test_billing.py -v

# Frontend build check
cd frontend && npx next build

# E2E tests
cd frontend && npx playwright test
```

## Key Endpoints

| Endpoint | Description |
|---|---|
| `POST /api/v1/auth/login` | Get JWT token |
| `GET /api/v1/analytics/funnel` | Funnel metrics |
| `GET /api/v1/analytics/predictive/churn` | Churn prediction |
| `GET /api/v1/segments/distribution` | RFM segment distribution |
| `GET /api/v1/leads/contacts` | List contacts (paginated) |
| `GET /api/v1/tenants/me/usage/detailed` | Usage metrics |
| `GET /api/v1/tenants/me/billing/plans` | Available plans |
| `DELETE /api/v1/cache/invalidate` | Clear response cache |
| `GET /health` | Liveness probe |
| `GET /health/ready` | Readiness probe (checks DB+Redis) |

## Important Notes

- **CORS**: origins configured in `.env` `CORS_ORIGINS` — includes `funnelier.localhost` and `api.funnelier.localhost`
- **Redis databases**: `0` = cache/rate-limit, `1` = Celery broker, `2` = Celery results
- **Middleware order** (outermost first): CORS → RateLimitMiddleware → ResponseCacheMiddleware → UsageEnforcementMiddleware
- **JWT**: tokens contain `sub` (user_id), `tenant_id`, `role` — decoded via `decode_access_token()`
- **Git commits**: use `git commit -F /tmp/funnelier_commit.txt` to avoid shell quoting issues with multi-line messages
- **Frontend port**: `3003` (not default 3000, to avoid conflicts with other projects)

