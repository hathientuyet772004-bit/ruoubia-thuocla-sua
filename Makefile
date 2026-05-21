# Makefile cho Collector Tool
# Sử dụng: make <command>

.PHONY: help build deploy clean logs test

# Default target
help:
	@echo "Collector Tool - Available commands:"
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
	@echo "Azure:"
	@echo "  make azure-deploy   - Deploy to Azure"
	@echo ""
	@echo "Testing:"
	@echo "  make test           - Run tests"
	@echo "  make test-backend   - Run backend tests"
	@echo "  make test-frontend  - Run frontend tests"
	@echo ""
	@echo "Maintenance:"
	@echo "  make backup         - Backup database"
	@echo "  make restore        - Restore database from backup"
	@echo "  make migrate        - Run database migrations"

# Development commands
build:
	@echo "🔨 Building Docker images..."
	./scripts/build.sh

deploy:
	@echo "🚀 Deploying to local Docker..."
	./scripts/deploy.sh development

dev: build deploy
	@echo "✅ Development environment ready!"

logs:
	docker-compose logs -f

stop:
	docker-compose down

clean:
	docker-compose down -v --remove-orphans
	docker system prune -f

# Production commands
prod-build:
	@echo "🏗️  Building for production..."
	docker build -f Dockerfile.backend -t collector-backend:prod .
	docker build -f Dockerfile.frontend -t collector-frontend:prod .

prod-deploy:
	@echo "🚀 Deploying to production..."
	./scripts/deploy.sh production

# Azure deployment
azure-deploy:
	@echo "☁️  Deploying to Azure..."
	./scripts/deploy-azure.sh

# Testing
test: test-backend test-frontend

test-backend:
	@echo "🧪 Running backend tests..."
	docker-compose exec backend python -m pytest

test-frontend:
	@echo "🧪 Running frontend tests..."
	docker-compose exec frontend npm test

# Database operations
backup:
	@echo "💾 Creating database backup..."
	docker-compose exec -T db sh -lc 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > backup_$(shell date +%Y%m%d_%H%M%S).sql

restore:
	@echo "🔄 Restoring database..."
	@read -p "Enter backup file name: " file; \
	docker-compose exec -T db sh -lc 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"' < $$file

migrate:
	@echo "🗄️  Running database migrations..."
	docker-compose exec backend python -c "from collector.database import Base, engine; Base.metadata.create_all(bind=engine)"

# Utility commands
shell-backend:
	docker-compose exec backend bash

shell-frontend:
	docker-compose exec frontend sh

shell-db:
	docker-compose exec db sh -lc 'psql -U "$$POSTGRES_USER" "$$POSTGRES_DB"'

status:
	docker-compose ps

health:
	@echo "🏥 Health check..."
	@curl -f http://localhost/api/health && echo "✅ Backend OK" || echo "❌ Backend FAILED"
	@curl -f http://localhost && echo "✅ Frontend OK" || echo "❌ Frontend FAILED"
	@curl -f http://localhost:9000/minio/health/live && echo "✅ MinIO OK" || echo "❌ MinIO FAILED"
