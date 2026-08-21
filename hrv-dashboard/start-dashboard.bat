@echo off
title HRV Dashboard - Launcher
set "DIR=%~dp0"
cd /d "%DIR%"
echo Starting Vite dev server...
start "HRV Dashboard Server" cmd /k "cd /d "%DIR%" && npm run dev"
echo Waiting for server to be ready...
timeout /t 6 /nobreak >nul
start "" "http://localhost:5173"
echo Dashboard opened in browser.
