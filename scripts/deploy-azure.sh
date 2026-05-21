#!/bin/bash

# Azure Deployment Script cho Collector Tool
# Sử dụng: ./scripts/deploy-azure.sh [resource-group] [location]

set -e

RESOURCE_GROUP=${1:-collector-rg}
LOCATION=${2:-southeastasia}

echo "🚀 Deploying Collector Tool to Azure..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Kiểm tra Azure CLI
if ! command -v az &> /dev/null; then
    echo -e "${RED}❌ Azure CLI chưa được cài đặt. Tải tại: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli${NC}"
    exit 1
fi

# Đăng nhập Azure
echo -e "${YELLOW}🔐 Đăng nhập Azure...${NC}"
az login --use-device-code

# Chọn subscription
echo -e "${YELLOW}📋 Chọn Azure subscription:${NC}"
az account list --output table
read -p "Nhập Subscription ID: " SUBSCRIPTION_ID
az account set --subscription $SUBSCRIPTION_ID

# Tạo resource group
echo -e "${YELLOW}📁 Tạo resource group: $RESOURCE_GROUP${NC}"
az group create --name $RESOURCE_GROUP --location $LOCATION

# Tạo Azure Container Registry
ACR_NAME="collectoracr$(date +%s | tail -c 6)"
echo -e "${YELLOW}🏗️  Tạo Azure Container Registry: $ACR_NAME${NC}"
az acr create --resource-group $RESOURCE_GROUP --name $ACR_NAME --sku Basic

# Login to ACR
echo -e "${YELLOW}🔑 Login to ACR...${NC}"
az acr login --name $ACR_NAME

# Build và push images
echo -e "${YELLOW}📦 Build và push images...${NC}"

# Backend
echo "Building backend image..."
docker build -f Dockerfile.backend -t $ACR_NAME.azurecr.io/collector-backend:latest .
echo "Pushing backend image..."
docker push $ACR_NAME.azurecr.io/collector-backend:latest

# Frontend
echo "Building frontend image..."
docker build -f Dockerfile.frontend -t $ACR_NAME.azurecr.io/collector-frontend:latest .
echo "Pushing frontend image..."
docker push $ACR_NAME.azurecr.io/collector-frontend:latest

# Tạo Azure Database for PostgreSQL
DB_SERVER_NAME="collector-db-$(date +%s | tail -c 8)"
DB_ADMIN_USER="collectoradmin"
DB_ADMIN_PASSWORD="$(openssl rand -base64 12)"

echo -e "${YELLOW}🗄️  Tạo Azure Database for PostgreSQL...${NC}"
az postgres flexible-server create \
    --resource-group $RESOURCE_GROUP \
    --name $DB_SERVER_NAME \
    --location $LOCATION \
    --admin-user $DB_ADMIN_USER \
    --admin-password $DB_ADMIN_PASSWORD \
    --sku-name Standard_B1ms \
    --tier Burstable \
    --storage-size 32 \
    --version 15

# Tạo database
az postgres flexible-server db create \
    --resource-group $RESOURCE_GROUP \
    --server-name $DB_SERVER_NAME \
    --database-name collector_db

# Tạo Azure Storage Account cho MinIO (hoặc sử dụng Azure Blob Storage)
STORAGE_ACCOUNT_NAME="collectorstorage$(date +%s | tail -c 10)"
echo -e "${YELLOW}🗂️  Tạo Azure Storage Account...${NC}"
az storage account create \
    --name $STORAGE_ACCOUNT_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION \
    --sku Standard_LRS \
    --kind StorageV2

# Tạo container
az storage container create \
    --name collector-data \
    --account-name $STORAGE_ACCOUNT_NAME \
    --auth-mode login

# Tạo Azure Container Apps Environment
ENV_NAME="collector-env"
echo -e "${YELLOW}🌐 Tạo Container Apps Environment...${NC}"
az containerapp env create \
    --name $ENV_NAME \
    --resource-group $RESOURCE_GROUP \
    --location $LOCATION

# Deploy Backend
echo -e "${YELLOW}🚀 Deploy Backend...${NC}"
az containerapp create \
    --name collector-backend \
    --resource-group $RESOURCE_GROUP \
    --environment $ENV_NAME \
    --image $ACR_NAME.azurecr.io/collector-backend:latest \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 10 \
    --cpu 0.5 \
    --memory 1.0 \
    --env-vars \
        DB_HOST=$DB_SERVER_NAME.postgres.database.azure.com \
        DB_PORT=5432 \
        DB_USER=$DB_ADMIN_USER \
        DB_PASSWORD=$DB_ADMIN_PASSWORD \
        DB_NAME=collector_db \
        MINIO_ENDPOINT=$STORAGE_ACCOUNT_NAME.blob.core.windows.net \
        MINIO_ACCESS_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT_NAME --query '[0].value' -o tsv) \
        MINIO_SECRET_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT_NAME --query '[1].value' -o tsv) \
        MINIO_BUCKET_NAME=collector-data \
        MINIO_SECURE=true \
        GEMINI_API_KEY=$GEMINI_API_KEY

# Deploy Frontend
echo -e "${YELLOW}🚀 Deploy Frontend...${NC}"
az containerapp create \
    --name collector-frontend \
    --resource-group $RESOURCE_GROUP \
    --environment $ENV_NAME \
    --image $ACR_NAME.azurecr.io/collector-frontend:latest \
    --target-port 5173 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 5 \
    --cpu 0.25 \
    --memory 0.5 \
    --env-vars \
        VITE_API_URL=https://collector-backend.$(az containerapp env show --name $ENV_NAME --resource-group $RESOURCE_GROUP --query 'properties.defaultDomain' -o tsv)

# Lấy URLs
BACKEND_URL=$(az containerapp show --name collector-backend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv)
FRONTEND_URL=$(az containerapp show --name collector-frontend --resource-group $RESOURCE_GROUP --query 'properties.configuration.ingress.fqdn' -o tsv)

echo ""
echo -e "${GREEN}🎉 Deploy hoàn thành!${NC}"
echo ""
echo -e "${BLUE}📊 Thông tin deployment:${NC}"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location: $LOCATION"
echo "  ACR: $ACR_NAME.azurecr.io"
echo "  Database: $DB_SERVER_NAME.postgres.database.azure.com"
echo "  Storage: $STORAGE_ACCOUNT_NAME.blob.core.windows.net"
echo ""
echo -e "${BLUE}🌐 URLs:${NC}"
echo "  Frontend: https://$FRONTEND_URL"
echo "  Backend: https://$BACKEND_URL"
echo ""
echo -e "${YELLOW}💡 Lưu thông tin này để sử dụng sau!${NC}"

# Lưu thông tin vào file
cat > azure-deployment-info.txt << EOF
Azure Deployment Information
===========================

Resource Group: $RESOURCE_GROUP
Location: $LOCATION
ACR: $ACR_NAME.azurecr.io
Database Server: $DB_SERVER_NAME.postgres.database.azure.com
Database User: $DB_ADMIN_USER
Storage Account: $STORAGE_ACCOUNT_NAME.blob.core.windows.net

URLs:
Frontend: https://$FRONTEND_URL
Backend: https://$BACKEND_URL

Environment Variables for local development:
DB_HOST=$DB_SERVER_NAME.postgres.database.azure.com
DB_USER=$DB_ADMIN_USER
DB_PASSWORD=$DB_ADMIN_PASSWORD
MINIO_ENDPOINT=$STORAGE_ACCOUNT_NAME.blob.core.windows.net
MINIO_ACCESS_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT_NAME --query '[0].value' -o tsv)
MINIO_SECRET_KEY=$(az storage account keys list --resource-group $RESOURCE_GROUP --account-name $STORAGE_ACCOUNT_NAME --query '[1].value' -o tsv)
EOF

echo -e "${GREEN}✅ Thông tin deployment đã được lưu vào azure-deployment-info.txt${NC}"