#!/bin/bash
set -e

echo "🚀 Iniciando Trình Duyệt Giả Lập en Docker..."
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar si Docker está instalado
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no está instalado. Por favor, instala Docker Desktop."
    exit 1
fi

echo -e "${BLUE}✓ Docker detectado${NC}"

# Detener contenedores previos si existen
echo -e "${YELLOW}Limpiando contenedores previos...${NC}"
docker-compose down 2>/dev/null || true

# Construir imágenes
echo -e "${BLUE}📦 Construyendo imágenes...${NC}"
docker-compose build --no-cache

# Iniciar servicios
echo -e "${BLUE}🔨 Iniciando servicios...${NC}"
docker-compose up -d

# Esperar a que los servicios estén listos
echo -e "${YELLOW}⏳ Esperando a que los servicios se inicien...${NC}"
sleep 5

# Verificar salud
echo -e "${BLUE}🏥 Verificando estado de servicios...${NC}"
docker-compose ps

echo ""
echo -e "${GREEN}✅ ¡Aplicación iniciada correctamente!${NC}"
echo ""
echo -e "${BLUE}URLs disponibles:${NC}"
echo -e "  🌐 Frontend:  ${GREEN}http://localhost${NC}"
echo -e "  🔌 Backend:   ${GREEN}http://localhost/api${NC}"
echo -e "  📊 Nginx:     ${GREEN}http://localhost:80${NC}"
echo ""
echo -e "${BLUE}Comandos útiles:${NC}"
echo "  Ver logs:     docker-compose logs -f"
echo "  Ver backend:  docker-compose logs -f backend"
echo "  Ver frontend: docker-compose logs -f frontend"
echo "  Ver nginx:    docker-compose logs -f nginx"
echo "  Detener:      docker-compose down"
echo "  Reiniciar:    docker-compose restart"
echo ""
