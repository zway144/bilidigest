@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    BiliDigest 一键启动
echo ========================================
echo.

:: ── 1. 清理旧进程 ──
echo [1/4] 清理旧进程...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 "') do (
    echo   关闭端口 8000 上的进程 PID=%%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":3000 "') do (
    echo   关闭端口 3000 上的进程 PID=%%a
    taskkill /F /PID %%a >nul 2>&1
)

timeout /t 2 /nobreak >nul

:: ── 2. 启动后端 ──
echo.
echo [2/4] 启动后端服务...
cd backend
start "BiliDigest-Backend" cmd /c "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

:: ── 3. 等待后端 ready（最多30秒）──
echo [3/4] 等待后端就绪...
set WAIT_COUNT=0

:wait_backend
curl -s -o nul http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo   后端已就绪!
    goto backend_ready
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo.
    echo   [错误] 后端启动超时，请检查 BiliDigest-Backend 窗口的错误信息
    echo   常见原因：pip 依赖未安装、.env 配置缺失、端口仍被占用
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_backend

:backend_ready

:: ── 4. 启动前端 ──
echo [4/4] 启动前端服务...
cd frontend
start "BiliDigest-Frontend" cmd /c "npm run dev"
cd ..

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo    启动完成!
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000
echo ========================================
echo.
echo 如需停止，关闭 BiliDigest-Backend 和 BiliDigest-Frontend 窗口
echo.
pause
