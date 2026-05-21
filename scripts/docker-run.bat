@echo off
setlocal enabledelayedexpansion

echo 🚀 Iniciando Trình Duyệt Giả Lập en Docker...
echo.

REM Verificar si Docker está instalado
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker no está instalado. Por favor, instala Docker Desktop.
    pause
    exit /b 1
)

echo ✓ Docker detectado
echo.

REM Detener contenedores previos
echo Limpiando contenedores previos...
docker-compose down 2>nul

REM Construir imágenes
echo 📦 Construyendo imágenes...
docker-compose build --no-cache
if errorlevel 1 (
    echo ❌ Error al construir imágenes
    pause
    exit /b 1
)

REM Iniciar servicios
echo 🔨 Iniciando servicios...
docker-compose up -d
if errorlevel 1 (
    echo ❌ Error al iniciar servicios
    pause
    exit /b 1
)

REM Esperar a que estén listos
echo ⏳ Esperando a que los servicios se inicien...
timeout /t 5 /nobreak

REM Mostrar estado
echo 🏥 Estado de los servicios:
docker-compose ps

echo.
echo ✅ ¡Aplicación iniciada correctamente!
echo.
echo URLs disponibles:
echo   🌐 Frontend:  http://localhost
echo   🔌 Backend:   http://localhost/api
echo   📊 Nginx:     http://localhost:80
echo.
echo Comandos útiles:
echo   Ver logs:     docker-compose logs -f
echo   Ver backend:  docker-compose logs -f backend
echo   Ver frontend: docker-compose logs -f frontend
echo   Ver nginx:    docker-compose logs -f nginx
echo   Detener:      docker-compose down
echo   Reiniciar:    docker-compose restart
echo.
echo Presiona cualquier tecla para continuar...
pause >nul
