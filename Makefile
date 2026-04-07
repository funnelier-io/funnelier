.PHONY: help up down dev-backend dev-frontend migrate seed test lint fmt build \
       docker-build docker-push deploy-staging deploy-prod import-leads sync-crm \
       test-unit test-integration test-e2e ci pre-commit-install

DOCKER_HOST_FLAG=DOCKER_HOST="unix://$${HOME}/.docker/run/docker.sock"
REGISTRY ?= ghcr.io
IMAGE_NAME ?= $(shell basename $(CURDIR))
TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "latest")

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────
up: ## Start docker dev services (postgres, redis)
	cd docker && $(DOCKER_HOST_FLAG) docker compose up -d postgres redis
down: ## Stop docker services
	cd docker && $(DOCKER_HOST_FLAG) docker compose down
dev-backend: ## Start backend with hot-reload
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev -- -p 3003
dev: ## Start both backend and frontend (requires tmux or two terminals)
	@echo "Run 'make dev-backend' and 'make dev-frontend' in separate terminals"
migrate: ## Run Alembic database migrations
	alembic upgrade head
seed: ## Seed default tenant and admin user
	python -c "import asyncio; from src.api.main import _seed_default_tenant; asyncio.run(_seed_default_tenant())"
import-leads: ## Import lead Excel files
	python scripts/import_leads.py
sync-crm: ## Sync MongoDB CRM data
	python scripts/sync_mongodb_crm.py

# ── Testing ──────────────────────────────────────────
test: ## Run all tests
	pytest
test-unit: ## Run unit tests only
	python -m pytest tests/unit/ -v --tb=short -q --no-header
test-integration: ## Run integration tests only
	python -m pytest tests/integration/ -v --tb=short -q --no-header
test-e2e: ## Run Playwright E2E tests
	cd frontend && npx playwright test
test-cov: ## Run tests with coverage report
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term-missing

# ── Code Quality ─────────────────────────────────────
lint: ## Lint all code (backend + frontend)
	ruff check src/ || true
	cd frontend && npx eslint . || true
fmt: ## Format backend code
	ruff format src/
typecheck: ## Run mypy type checking
	mypy src/ --ignore-missing-imports || true
pre-commit-install: ## Install pre-commit hooks
	pre-commit install
	pre-commit install --hook-type pre-push

# ── CI Pipeline (runs locally, mirrors GitHub Actions) ─
ci: lint test-unit test-integration ## Run full CI pipeline locally
	@echo "✅ CI passed"

# ── Docker ───────────────────────────────────────────
build: ## Build frontend for production
	cd frontend && npm run build
docker-build: ## Build all Docker images
	cd docker && $(DOCKER_HOST_FLAG) docker compose build
docker-build-prod: ## Build production Docker images with tags
	$(DOCKER_HOST_FLAG) docker build -t $(REGISTRY)/$(IMAGE_NAME)/api:$(TAG) -f docker/Dockerfile .
	$(DOCKER_HOST_FLAG) docker build -t $(REGISTRY)/$(IMAGE_NAME)/frontend:$(TAG) -f docker/Dockerfile.frontend frontend/
docker-push: ## Push Docker images to registry
	docker push $(REGISTRY)/$(IMAGE_NAME)/api:$(TAG)
	docker push $(REGISTRY)/$(IMAGE_NAME)/frontend:$(TAG)

# ── Production ───────────────────────────────────────
prod-up: ## Start production stack
	cd docker && $(DOCKER_HOST_FLAG) docker compose -f docker-compose.prod.yml up -d
prod-down: ## Stop production stack
	cd docker && $(DOCKER_HOST_FLAG) docker compose -f docker-compose.prod.yml down
prod-logs: ## Tail production logs
	cd docker && $(DOCKER_HOST_FLAG) docker compose -f docker-compose.prod.yml logs -f --tail=100
prod-migrate: ## Run migrations in production
	cd docker && $(DOCKER_HOST_FLAG) docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# ── Kubernetes ───────────────────────────────────────
k8s-apply-staging: ## Apply K8s manifests to staging
	kubectl apply -f k8s/base/ -n funnelier-staging
	kubectl apply -f k8s/overlays/staging/ -n funnelier-staging
k8s-apply-prod: ## Apply K8s manifests to production
	kubectl apply -f k8s/base/ -n funnelier-production
	kubectl apply -f k8s/overlays/production/ -n funnelier-production
k8s-status: ## Show K8s deployment status
	kubectl get pods,svc,ing -n funnelier-production -o wide
k8s-rollback: ## Rollback API deployment
	kubectl rollout undo deployment/funnelier-api -n funnelier-production

# ── Deploy ───────────────────────────────────────────
deploy-staging: docker-build-prod docker-push k8s-apply-staging ## Build, push, deploy to staging
	@echo "🚀 Deployed $(TAG) to staging"
deploy-prod: docker-build-prod docker-push k8s-apply-prod ## Build, push, deploy to production
	@echo "🚀 Deployed $(TAG) to production"
