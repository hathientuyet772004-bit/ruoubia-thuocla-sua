# Makefile cho Admin Center
# Sử dụng: make <command>

.PHONY: help build deploy clean logs test

# Default target
BATCH_BASE_URL ?= http://localhost

help:
	@echo "Admin Center - Available commands:"
	@echo ""
	@echo "Development:"
	@echo "  make build          - Build Docker images"
	@echo "  make deploy         - Deploy to local Docker"
	@echo "  make dev            - Build and deploy for development"
	@echo "  make logs           - Show logs from all services"
	@echo "  make stop           - Stop all services"
	@echo "  make clean          - Remove containers and volumes"
	@echo ""
	@echo "Production:"
	@echo "  make prod-build     - Build for production"
	@echo "  make prod-deploy    - Deploy to production"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run tests"
	@echo "  make test-backend   - Run backend tests"
	@echo "  make test-frontend  - Run frontend tests"
	@echo "  make smoke-docker   - Build stack and check nginx endpoints"
	@echo "  make validate-env   - Validate .env runtime config"
	@echo "  make batch-gemini    - Run Gemini extraction over one or more domains"
	@echo ""
	@echo "Maintenance:"

# Development commands
build:
	@echo "🔨 Building Docker images..."
	docker compose build

deploy:
	@echo "🚀 Deploying to local Docker..."
	docker compose up -d

dev: build deploy
	@echo "✅ Development environment ready!"

logs:
	docker compose logs -f

stop:
	docker compose down

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

# Production commands
prod-build:
	@echo "🏗️  Building for production..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml build

prod-deploy:
	@echo "🚀 Deploying to production..."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Testing
test: test-backend test-frontend

validate-env:
	@echo "🔎 Validating environment config..."
	python scripts/validate-env.py --env-file .env

test-backend:
	@echo "🧪 Running backend tests..."
	PYTHONPATH=src python -m unittest tests.test_admin_center_api tests.test_admin_center_frontend_routes

test-frontend:
	@echo "🧪 Building frontend..."
	cd src/apps/admin_center/frontend && npm run build

smoke-docker:
	@echo "🧪 Running Docker smoke checks..."
	powershell -ExecutionPolicy Bypass -File scripts/smoke-docker.ps1

batch-gemini:
	@echo "🧪 Running Gemini batch analysis..."
	python scripts/batch-gemini-analyze.py --base-url $(BATCH_BASE_URL) $(foreach d,$(BATCH_DOMAINS),--domain $(d)) $(if $(BATCH_DOMAINS_FILE),--domains-file $(BATCH_DOMAINS_FILE),) $(if $(BATCH_OUTPUT),--output $(BATCH_OUTPUT),)

# Utility commands
shell-backend:
	docker compose exec backend bash

shell-frontend:
	docker compose exec frontend sh

status:
	docker compose ps

health:
	@echo "🏥 Health check..."
	@curl -f http://localhost/api/health && echo "✅ Backend OK" || echo "❌ Backend FAILED"
	@curl -f http://localhost && echo "✅ Frontend OK" || echo "❌ Frontend FAILED"
