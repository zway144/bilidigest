@echo off
chcp 65001 >nul
title BiliDigest 启动器

echo ========================================
echo    BiliDigest 一键启动
echo ========================================
echo.

:: 获取脚本所在目录（项目根目录）
set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

echo 项目根目录: %ROOT%
echo.

:: ── 检查 Python ──
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 python，请先安装 Python 3.10+
    pause
    exit /b 1
)

:: ── 检查 Node.js ──
where node >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 node，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/2] 启动后端 (端口 8000)...
start "BiliDigest-Backend" cmd /k "chcp 65001 >nul && cd /d "%BACKEND%" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: 等待后端起来
echo     等待后端启动...
timeout /t 3 /nobreak >nul

echo [2/2] 启动前端 (端口 3000)...
start "BiliDigest-Frontend" cmd /k "chcp 65001 >nul && cd /d "%FRONTEND%" && npm run dev"

echo.
echo 等待服务就绪（约10秒）...
timeout /t 10 /nobreak >nul

echo.
echo ========================================
echo    启动完成！
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000/docs
echo ========================================
echo.
echo 正在打开浏览器...
start http://localhost:3000

echo.
echo 此窗口可以关闭，两个服务窗口请保持开启。
pause
