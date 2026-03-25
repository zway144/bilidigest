@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    BiliDigest 一键启动
echo ========================================
echo.

:: ── 检测 curl 是否可用，不可用则用 powershell ──
set CURL=curl
curl --version >nul 2>&1 || set CURL= powershell -NoProfile -Command

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

if exist "frontend\.next\dev" (
    echo   清理 Next.js 锁文件...
    rmdir /s /q "frontend\.next\dev" >nul 2>&1
)

timeout /t 2 /nobreak >nul

:: 验证端口 8000
netstat -ano 2>nul | findstr "LISTENING" | findstr ":8000 " >nul 2>&1
if %errorlevel%==0 (
    echo   [错误] 端口 8000 仍被占用
    pause
    exit /b 1
)

:: 验证端口 3000
netstat -ano 2>nul | findstr "LISTENING" | findstr ":3000 " >nul 2>&1
if %errorlevel%==0 (
    echo   [错误] 端口 3000 仍被占用
    pause
    exit /b 1
)

echo   端口 8000、3000 已释放

:: ── 2. 启动后端 ──
echo.
echo [2/4] 启动后端服务...
cd backend
start "BiliDigest-Backend" cmd /k "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

:: ── 3. 等待后端就绪 ──
echo [3/4] 等待后端就绪...
set WAIT_COUNT=0

:wait_backend
%CURL% -s -o nul http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo   后端已就绪!
    goto backend_ready
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo.
    echo   [错误] 后端启动超时（30秒）
    echo   请检查 BiliDigest-Backend 窗口的错误信息
    echo   常见原因：pip 依赖未安装、.env 配置缺失
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto wait_backend

:backend_ready

:: 二次确认端口 3000
netstat -ano 2>nul | findstr "LISTENING" | findstr ":3000 " >nul 2>&1
if %errorlevel%==0 (
    echo   [错误] 端口 3000 被其他进程占用
    pause
    exit /b 1
)

:: ── 4. 启动前端 ──
echo [4/4] 启动前端服务...
cd frontend
start "BiliDigest-Frontend" cmd /k "npm run dev"
cd ..

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo    启动完成!
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000
echo ========================================
echo.
echo 如需停止，请关闭标题为 BiliDigest-Backend
echo 和 BiliDigest-Frontend 的黑色窗口
echo.
pause
