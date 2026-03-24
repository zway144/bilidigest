@echo off
echo ========================================
echo   BiliDigest Start
echo ========================================
echo.

echo [1/2] Starting backend...
cd /d "%~dp0backend"
start /b cmd /c "python -m uvicorn main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul

echo [2/2] Starting frontend...
cd /d "%~dp0frontend"
start /b cmd /c "npx next dev --port 3000"
timeout /t 5 /nobreak >nul

echo.
echo Opening browser...
start http://localhost:3000

echo.
echo ========================================
echo   Backend: http://localhost:8000
echo   Frontend: http://localhost:3000
echo   Close this window to stop all services
echo ========================================
echo.
pause
