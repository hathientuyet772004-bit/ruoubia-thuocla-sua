@echo off
setlocal
echo 🕸️ Starting Collector Dashboard...

REM Ensure imports work (shared.*, modules.*)
set "PROJECT_ROOT=%~dp0.."
set "PYTHONPATH=%PROJECT_ROOT%\src;%PYTHONPATH%"

streamlit run "%PROJECT_ROOT%\src\apps\dashboard\app.py"
pause
