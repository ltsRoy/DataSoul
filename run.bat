@echo off
title DataSoul Runner
cd /d "%~dp0"

echo ===================================================
echo Starting DataSoul Application
echo ===================================================
echo.

echo [1/2] Starting FastAPI Backend...
cd backend
start "DataSoul Backend" cmd /k "if exist .\.venv\Scripts\activate.bat (call .\.venv\Scripts\activate.bat) & uvicorn main:app --reload"
cd ..

echo [2/2] Starting Next.js Frontend...
cd frontend
start "DataSoul Frontend" cmd /k "npm run dev"
cd ..

echo.
echo ===================================================
echo All services are launching in separate windows!
echo.
echo Frontend URL: http://localhost:3000
echo Backend URL:  http://localhost:8000
echo ===================================================
echo You can close this window now. The servers will keep
echo running in their respective command prompt windows.
pause
