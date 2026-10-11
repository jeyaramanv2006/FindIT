@echo off
title FindIT - Backend (FastAPI)
set "PROJECT_ROOT=%~dp0.."
echo ============================================================
echo   Starting FindIT Backend Server (FastAPI + PyTorch CUDA)
echo ============================================================
cd /d "%PROJECT_ROOT%\backend"
call .venv\Scripts\activate.bat
python run.py
pause
