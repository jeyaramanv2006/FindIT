@echo off
setlocal enabledelayedexpansion
title FindIT - Unified Runner
echo =====================================================================
echo                     FindIT - Universal Launcher
echo =====================================================================

set "PROJECT_ROOT=%~dp0"

:: Check if backend virtualenv or frontend node_modules is missing
set "NEED_SETUP=0"
if not exist "%PROJECT_ROOT%backend\.venv" set "NEED_SETUP=1"
if not exist "%PROJECT_ROOT%frontend\node_modules" set "NEED_SETUP=1"

if "%NEED_SETUP%"=="1" (
    echo.
    echo [FIRST RUN DETECTED] Virtual environment or packages missing.
    echo Running automated setup first...
    echo.
    call "%PROJECT_ROOT%scripts\setup.bat"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Setup encountered an error.
        pause
        exit /b 1
    )
    echo.
    echo Setup completed! Proceeding to launch FindIT...
    echo.
)

:: Launch Backend and Frontend in separate dedicated windows
echo Starting FindIT Backend (FastAPI + GPU) ...
start "FindIT Backend" cmd /k "cd /d "%PROJECT_ROOT%backend" && call .venv\Scripts\activate.bat && python run.py"

echo Starting FindIT Frontend (React + Vite) ...
start "FindIT Frontend" cmd /k "cd /d "%PROJECT_ROOT%frontend" && npm run dev"

echo.
echo =====================================================================
echo   FindIT is running!
echo   - Backend:  http://127.0.0.1:8000
echo   - Frontend: http://localhost:5173
echo =====================================================================
echo.
echo Launching FindIT in your browser...
timeout /t 3 /nobreak >nul
start http://localhost:5173
exit
