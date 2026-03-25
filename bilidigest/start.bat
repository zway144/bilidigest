@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    BiliDigest Startup
echo ========================================
echo.

:: ── 0. Dependency checks ──
echo [0/5] Checking dependencies...

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed. Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check pip
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] pip is not installed. Try: python -m ensurepip
    pause
    exit /b 1
)

:: Check FFmpeg
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] FFmpeg is not found in PATH.
    echo   Download from: https://www.gyan.dev/ffmpeg/builds/
    echo   After install, run: start.bat again
    pause
)

:: ── 1. Kill old processes on 8000 and 3000 ──
echo [1/5] Cleaning old processes...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-NetTCPConnection -LocalPort 8000,3000 -State Listen -ErrorAction SilentlyContinue | " ^
    "ForEach-Object { Write-Host ('Killing port ' + $_.LocalPort + ' PID=' + $_.OwningProcess); " ^
    "Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"

if exist "frontend\.next" (
    rmdir /s /q "frontend\.next" >nul 2>&1
)

powershell -NoProfile -Command "Start-Sleep -Seconds 2"

:: ── 2. Install backend Python dependencies ──
echo [2/5] Installing backend dependencies...
cd backend
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [ERROR] pip install failed. Try manually: pip install -r requirements.txt
    pause
    exit /b 1
)
cd ..

:: ── 3. Install frontend Node dependencies ──
echo [3/5] Installing frontend dependencies...
if not exist "frontend\node_modules" (
    cd frontend
    call npm install
    cd ..
)

:: ── 4. Start backend ──
echo [4/5] Starting backend...
cd backend
start "BiliDigest-Backend" cmd /k "title BiliDigest-Backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

:: ── 5. Wait for backend to be ready ──
echo [5/5] Waiting for backend to be ready...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$t = 0; while ($t -lt 30) { " ^
    "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop; " ^
    "if ($r.StatusCode -eq 200) { Write-Host '  Backend ready!'; break } } catch {}; " ^
    "Start-Sleep -Seconds 1; $t++; " ^
    "if ($t -ge 30) { Write-Host '[ERROR] Backend startup timeout (30s)'; exit 1 } }"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Check the BiliDigest-Backend window for details.
    echo Common causes: .env missing, HF_ENDPOINT not set (for China users).
    pause
    exit /b 1
)

:: ── Start frontend ──
echo Starting frontend...
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

