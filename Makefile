.PHONY: help up down dev-backend dev-frontend migrate seed test lint fmt build docker-build
help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'
up: ## Start docker services
	cd docker && DOCKER_HOST="unix://$${HOME}/.docker/run/docker.sock" docker compose up -d
down: ## Stop docker services
	cd docker && DOCKER_HOST="unix://$${HOME}/.docker/run/docker.sock" docker compose down
dev-backend: ## Start backend with reload
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev -- -p 3003
migrate: ## Run Alembic migrations
	alembic upgrade head
seed: ## Seed default data
	python -c "import asyncio; from src.api.main import _seed_default_tenant; asyncio.run(_seed_default_tenant())"
import-leads: ## Import lead Excel files
	python scripts/import_leads.py
sync-crm: ## Sync MongoDB CRM data
	python scripts/sync_mongodb_crm.py
test: ## Run all tests
	pytest
lint: ## Lint all code
	ruff check src/ || true
	cd frontend && npx eslint . || true
fmt: ## Format backend code
	ruff format src/
build: ## Build frontend
	cd frontend && npm run build
docker-build: ## Build all Docker images
	cd docker && DOCKER_HOST="unix://$${HOME}/.docker/run/docker.sock" docker compose build
