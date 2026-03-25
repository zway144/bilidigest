@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo Starting backend...
cd backend
start "backend" cmd /k "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

echo Waiting for backend...
timeout /t 3 /nobreak >nul

echo Starting frontend...
cd frontend
start "frontend" cmd /k "npm run dev"
cd ..

echo.
echo Done!
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
pause
