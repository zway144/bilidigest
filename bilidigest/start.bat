@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    BiliDigest Startup
echo ========================================
echo.

:: 1. Kill old processes on 8000 and 3000
echo [1/4] Cleaning old processes...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue | " ^
    "ForEach-Object { Write-Host ('Killing port ' + $_.LocalPort + ' PID=' + $_.OwningProcess); " ^
    "Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

if exist "frontend\.next" (
    echo   Cleaning Next.js lock file
    rmdir /s /q "frontend\.next" >nul 2>&1
)

powershell -NoProfile -Command "Start-Sleep -Seconds 2"

:: 2. Start backend
echo [2/4] Starting backend...
cd backend
start "BiliDigest-Backend" cmd /k "title BiliDigest-Backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

:: 3. Wait for backend to be ready
echo [3/4] Waiting for backend to be ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$failed = $false; 1..30 | ForEach-Object { " ^
    "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; " ^
    "if ($r.StatusCode -eq 200) { Write-Host '  Backend ready!'; $failed = $true; return } } catch {}; " ^
    "if ($_ -eq 30) { Write-Host '[ERROR] Backend startup timeout (30s)'; exit 1 } " ^
    "Start-Sleep -Seconds 1 }"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Check the BiliDigest-Backend window for details.
    echo Common causes: pip dependencies not installed, .env missing.
    pause
    exit /b 1
)

:: 4. Start frontend
echo [4/4] Starting frontend...
cd frontend
start "BiliDigest-Frontend" cmd /k "title BiliDigest-Frontend && npm run dev"
cd ..

echo.
echo ========================================
echo    Startup complete!
echo.
echo    Frontend: http://localhost:3000
echo    Backend:  http://localhost:8000
echo ========================================
echo.
echo To stop services, close these windows:
echo   - BiliDigest-Backend
echo   - BiliDigest-Frontend
echo.
pause
