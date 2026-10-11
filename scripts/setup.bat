@echo off
setlocal enabledelayedexpansion
title FindIT - One-Click Environment Setup
echo =====================================================================
echo                FindIT - Automatic Environment Setup
echo =====================================================================
echo.
echo This script will set up everything needed to run FindIT:
echo   1. Check Python and Node.js prerequisites
echo   2. Create Python virtual environment in backend\.venv
echo   3. Install backend Python dependencies (with CUDA auto-detection)
echo   4. Install frontend npm packages in frontend\
echo.
echo =====================================================================

:: Resolve project root (parent directory of scripts/)
set "PROJECT_ROOT=%~dp0.."

:: 1. Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: 2. Check Node.js / npm
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm / Node.js was not found in PATH!
    echo Please install Node.js (LTS) from https://nodejs.org/
    pause
    exit /b 1
)

echo [OK] Python and Node.js found on system.
echo.

:: 3. Setup Backend Virtual Environment
echo ---------------------------------------------------------------------
echo [1/3] Setting up Python Virtual Environment (backend\.venv)...
echo ---------------------------------------------------------------------
cd /d "%PROJECT_ROOT%\backend"

if not exist ".venv" (
    echo Creating virtual environment in backend\.venv ...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment!
        pause
        exit /b 1
    )
    echo Virtual environment created.
) else (
    echo Virtual environment already exists at backend\.venv.
)

echo.
echo ---------------------------------------------------------------------
echo [2/3] Installing Backend Dependencies...
echo ---------------------------------------------------------------------
call .venv\Scripts\activate.bat

echo Upgrading pip...
python -m pip install --upgrade pip --quiet

echo Installing requirements from backend\requirements.txt ...
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install backend dependencies!
    pause
    exit /b 1
)

:: Check for NVIDIA GPU and install CUDA PyTorch if available
where nvidia-smi >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo.
    echo [NVIDIA GPU Detected] Installing PyTorch with CUDA acceleration (cu124)...
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
) else (
    echo.
    echo [CPU Mode] Standard CPU PyTorch installed.
)

echo [OK] Backend setup complete!
echo.

:: 4. Setup Frontend
echo ---------------------------------------------------------------------
echo [3/3] Installing Frontend Dependencies (frontend\node_modules)...
echo ---------------------------------------------------------------------
cd /d "%PROJECT_ROOT%\frontend"
call npm install
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install frontend dependencies!
    pause
    exit /b 1
)

echo [OK] Frontend setup complete!
echo.

:: Done!
echo =====================================================================
echo               FindIT Setup Completed Successfully!
echo =====================================================================
echo.
pause
