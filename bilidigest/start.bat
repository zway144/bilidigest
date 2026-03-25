@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================
echo    BiliDigest 一键启动
echo ========================================
echo.

:: ── 0. 错误时暂停 ──
set EXIT_ON_ERROR=0

:: ── 1. 清理旧进程 ──
echo [1/4] 清理旧进程...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":8000 "') do (
    echo   关闭端口 8000 PID=%%a
    taskkill /F /PID %%a >nul 2>&1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr ":3000 "') do (
    echo   关闭端口 3000 PID=%%a
    taskkill /F /PID %%a >nul 2>&1
)

if exist "frontend\.next\dev" (
    echo   清理 Next.js 锁文件
    rmdir /s /q "frontend\.next\dev" >nul 2>&1
)

timeout /t 2 /nobreak >nul

:: 验证端口已释放
netstat -ano 2>nul | findstr "LISTENING" | findstr ":8000 " >nul 2>&1
if %errorlevel%==0 (
    echo [错误] 端口 8000 仍被占用!
    echo.
    echo 请先手动关闭占用 8000 端口的程序，然后重新运行本脚本
    pause
    exit /b 1
)

netstat -ano 2>nul | findstr "LISTENING" | findstr ":3000 " >nul 2>&1
if %errorlevel%==0 (
    echo [错误] 端口 3000 仍被占用!
    echo.
    echo 请先手动关闭占用 3000 端口的程序，然后重新运行本脚本
    pause
    exit /b 1
)

echo   端口 8000、3000 已释放
echo.

:: ── 2. 启动后端 ──
echo [2/4] 启动后端服务...

:: 检测 curl 是否可用
curl --version >nul 2>&1
if %errorlevel%==0 (
    set CURL=curl
) else (
    set CURL= powershell -NoProfile -Command
)

cd backend
start "BiliDigest-Backend" cmd /k "title BiliDigest-Backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

echo   后端启动中，等待就绪...

:: ── 3. 等待后端 ready ──
echo [3/4] 等待后端就绪...
set WAIT_COUNT=0

:wait_backend
%CURL% -s -o nul http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel%==0 (
    echo   后端就绪!
    goto :backend_ready
)
set /a WAIT_COUNT+=1
if %WAIT_COUNT% GEQ 30 (
    echo.
    echo [错误] 后端启动超时（30秒）
    echo.
    echo 请查看 BiliDigest-Backend 黑色窗口中的错误信息
    echo 常见原因：
    echo   - pip 依赖未安装：先运行 pip install -r backend/requirements.txt
    echo   - .env 配置缺失：复制 backend/.env.example 为 backend/.env
    echo   - 端口仍被占用
    echo.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto :wait_backend

:backend_ready

:: ── 4. 启动前端 ──
echo [4/4] 启动前端服务...
cd frontend
start "BiliDigest-Frontend" cmd /k "title BiliDigest-Frontend && npm run dev"
cd ..

echo.
echo ========================================
echo    启动完成!
echo.
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000
echo ========================================
echo.
echo 如需停止服务，关闭标题为
echo   BiliDigest-Backend
echo   BiliDigest-Frontend
echo 的两个黑色窗口即可
echo.
pause
