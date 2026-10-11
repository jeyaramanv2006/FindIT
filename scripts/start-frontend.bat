@echo off
title FindIT - Frontend (Vite)
set "PROJECT_ROOT=%~dp0.."
echo ============================================================
echo   Starting FindIT Frontend Dev Server (React + Vite)
echo ============================================================
cd /d "%PROJECT_ROOT%\frontend"
npm run dev
pause
