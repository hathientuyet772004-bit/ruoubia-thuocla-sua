#!/bin/bash

# Build script cho Collector Tool
# Sử dụng: ./scripts/build.sh

set -e

echo "🚀 Bắt đầu build Collector Tool..."

# Colors cho output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Kiểm tra Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker chưa được cài đặt. Vui lòng cài đặt Docker trước.${NC}"
    exit 1
fi

# Kiểm tra Docker Compose
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose chưa được cài đặt.${NC}"
    exit 1
fi

# Tạo .env file nếu chưa có
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  File .env không tồn tại. Tạo file mẫu...${NC}"
    if [ -f .env.example ]; then
        cp .env.example .env
        echo -e "${GREEN}✅ Đã copy .env.example -> .env${NC}"
    else
        cat > .env << EOF
# ── APP & ENV ───────────────────────────────────────────────
ENV=development
LOG_LEVEL=info
DEBUG=true

# ── DATABASE (PostgreSQL) ───────────────────────────────────
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=collector_db
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin

# ── MINIO OBJECT STORAGE ────────────────────────────────────
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET_NAME=collector-data
MINIO_SECURE=false

# ── REDIS ───────────────────────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379

# ── LLM (Gemini) ───────────────────────────────────────────
GEMINI_API_KEY=YOUR_API_KEY_HERE
GEMINI_MODEL=gemini-1.5-flash
USE_MOCK_MODE=true
EOF
        echo -e "${GREEN}✅ Đã tạo file .env mẫu${NC}"
    fi
    echo -e "${YELLOW}⚠️  Vui lòng cập nhật GEMINI_API_KEY trong file .env${NC}"
fi

# Build images (ưu tiên docker compose, fallback docker-compose)
echo -e "${YELLOW}🔨 Building Docker images...${NC}"
if docker compose version &> /dev/null; then
    docker compose build
else
    docker-compose build
fi

echo -e "${GREEN}✅ Build hoàn thành!${NC}"

# Hiển thị thông tin
echo ""
echo -e "${GREEN}📦 Images đã build:${NC}"
docker images | grep collector || true

echo ""
echo -e "${YELLOW}💡 Để chạy hệ thống, sử dụng:${NC}"
echo "  docker-compose up -d   (hoặc: docker compose up -d)"
echo ""
echo -e "${YELLOW}💡 Để xem logs:${NC}"
echo "  docker-compose logs -f"
