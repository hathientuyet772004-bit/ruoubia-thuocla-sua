#!/bin/bash

# Deploy script cho Collector Tool
# Sử dụng: ./scripts/deploy.sh [environment]

set -e

ENVIRONMENT=${1:-development}

echo "🚀 Deploying Collector Tool to $ENVIRONMENT..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Kiểm tra environment
case $ENVIRONMENT in
    development|staging|production)
        echo -e "${GREEN}✅ Environment: $ENVIRONMENT${NC}"
        ;;
    *)
        echo -e "${RED}❌ Environment không hợp lệ. Chọn: development, staging, hoặc production${NC}"
        exit 1
        ;;
esac

# Kiểm tra .env file
if [ ! -f .env ]; then
    echo -e "${RED}❌ File .env không tồn tại. Chạy ./scripts/build.sh trước.${NC}"
    exit 1
fi

# Kiểm tra GEMINI_API_KEY
if grep -q "YOUR_API_KEY_HERE" .env; then
    echo -e "${RED}❌ Vui lòng cập nhật GEMINI_API_KEY trong file .env${NC}"
    exit 1
fi

# Tạo thư mục cần thiết
mkdir -p data logs ssl

# Backup database nếu đang chạy
if (docker compose ps 2>/dev/null || docker-compose ps) | grep -q "Up"; then
    echo -e "${YELLOW}💾 Backup database trước khi deploy...${NC}"
    if docker compose version &> /dev/null; then
        docker compose exec -T db sh -lc 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > backup_$(date +%Y%m%d_%H%M%S).sql
    else
        docker-compose exec -T db sh -lc 'pg_dump -U "$$POSTGRES_USER" "$$POSTGRES_DB"' > backup_$(date +%Y%m%d_%H%M%S).sql
    fi
fi

# Dừng services cũ
echo -e "${YELLOW}🛑 Dừng services cũ...${NC}"
if docker compose version &> /dev/null; then
    docker compose down
else
    docker-compose down
fi

# Pull latest images (cho production)
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}📥 Pull latest images...${NC}"
    if docker compose version &> /dev/null; then
        docker compose pull
    else
        docker-compose pull
    fi
fi

# Build images
echo -e "${YELLOW}🔨 Build images...${NC}"
./scripts/build.sh

# Khởi động services
echo -e "${YELLOW}▶️  Khởi động services...${NC}"
if docker compose version &> /dev/null; then
    docker compose up -d
else
    docker-compose up -d
fi

# Chờ services khởi động
echo -e "${YELLOW}⏳ Chờ services khởi động...${NC}"
sleep 30

# Kiểm tra health
echo -e "${YELLOW}🏥 Kiểm tra health...${NC}"

# Kiểm tra PostgreSQL
if (docker compose exec -T db sh -lc 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' 2>/dev/null || docker-compose exec -T db sh -lc 'pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'); then
    echo -e "${GREEN}✅ PostgreSQL: OK${NC}"
else
    echo -e "${RED}❌ PostgreSQL: FAILED${NC}"
fi

# Kiểm tra MinIO
if curl -f http://localhost:9000/minio/health/live &>/dev/null; then
    echo -e "${GREEN}✅ MinIO: OK${NC}"
else
    echo -e "${RED}❌ MinIO: FAILED${NC}"
fi

# Kiểm tra Backend
if curl -f http://localhost/api/health &>/dev/null; then
    echo -e "${GREEN}✅ Backend: OK${NC}"
else
    echo -e "${RED}❌ Backend: FAILED${NC}"
fi

# Kiểm tra Frontend
if curl -f http://localhost &>/dev/null; then
    echo -e "${GREEN}✅ Frontend: OK${NC}"
else
    echo -e "${RED}❌ Frontend: FAILED${NC}"
fi

echo ""
echo -e "${GREEN}🎉 Deploy hoàn thành!${NC}"
echo ""
echo -e "${YELLOW}📊 Services đang chạy:${NC}"
if docker compose version &> /dev/null; then
    docker compose ps
else
    docker-compose ps
fi

echo ""
echo -e "${YELLOW}🌐 URLs:${NC}"
echo "  Frontend (Nginx): http://localhost"
echo "  Backend API: http://localhost/api"
echo "  MinIO Console: http://localhost:9001"
echo "  PostgreSQL: localhost:5432"

echo ""
echo -e "${YELLOW}📋 Commands hữu ích:${NC}"
echo "  Logs: docker-compose logs -f"
echo "  Stop: docker-compose down"
echo "  Restart: docker-compose restart"
echo "  Update: ./scripts/deploy.sh $ENVIRONMENT"
