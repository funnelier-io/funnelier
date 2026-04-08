See [AGENTS.md](../../AGENTS.md) in the project root for full agent instructions.

## Quick Reference

- **Backend**: FastAPI + SQLAlchemy async + Pydantic v2 (Python 3.11+)
- **Frontend**: Next.js 16 + React 19 + Tailwind CSS 4 + next-intl
- **Infra**: Shared dev infra at `/Users/univers/projects/infra/` — start with `docker compose up -d`
- **Ports**: PostgreSQL `5435`, Redis `6381`, MongoDB `27017`, Backend `8000`, Frontend `3003`
- **Auth**: `admin/admin1234` → `POST /api/v1/auth/login`
- **Tests**: `python -m pytest tests/unit/ -q` (294 passing)
- **i18n**: all strings in `messages/fa.json` + `messages/en.json`

## Shared Infra Warning

> **⚠️ DO NOT modify files under `/Users/univers/projects/infra/`** without explicit user approval.
> 15+ projects share the same PostgreSQL, Redis, MongoDB, Kafka, RabbitMQ, and Traefik instances.
> See the [Infra ONBOARDING guide](/Users/univers/projects/infra/ONBOARDING.md) for details.

