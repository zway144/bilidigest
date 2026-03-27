@echo off
echo ========================================
echo    BiliDigest Startup
echo ========================================
echo.

rem Check Python version (prefer 3.11)
set PYTHON_CMD=py -3.11
py -3.11 --version >nul 2>&1
if %errorlevel% neq 0 (
    set PYTHON_CMD=python
)
echo Using: %PYTHON_CMD%

rem Start backend
echo [1/3] Starting backend...
start "BiliDigest-Backend" cmd /k "cd /d %~dp0backend && %PYTHON_CMD% -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

rem Wait for backend
echo [2/3] Waiting for backend...
timeout /t 5 /nobreak >nul

rem Start frontend
echo [3/3] Starting frontend...
if exist "%~dp0frontend\.next" rmdir /s /q "%~dp0frontend\.next"
start "BiliDigest-Frontend" cmd /k "cd /d %~dp0frontend && set NEXT_DISABLE_OPEN=1 && npm run dev"

rem Wait and open browser
timeout /t 10 /nobreak >nul
start http://localhost:3000

echo ========================================
echo    Started!
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo ========================================
pause
