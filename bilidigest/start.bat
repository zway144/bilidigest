@echo off
chcp 65001 >nul
title BiliDigest 启动器
echo 正在启动...
pause

:: 把启动命令写入临时脚本，彻底绕开嵌套引号问题
set "ROOT=%~dp0"

echo @echo off > "%TEMP%\bd_backend.bat"
echo chcp 65001 ^>nul >> "%TEMP%\bd_backend.bat"
echo cd /d "%ROOT%backend" >> "%TEMP%\bd_backend.bat"
echo python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload >> "%TEMP%\bd_backend.bat"

echo @echo off > "%TEMP%\bd_frontend.bat"
echo chcp 65001 ^>nul >> "%TEMP%\bd_frontend.bat"
echo cd /d "%ROOT%frontend" >> "%TEMP%\bd_frontend.bat"
echo npm run dev >> "%TEMP%\bd_frontend.bat"

echo.
echo [1/2] 启动后端 (端口 8000)...
start "BiliDigest-Backend" cmd /k "%TEMP%\bd_backend.bat"

timeout /t 3 /nobreak >nul

echo [2/2] 启动前端 (端口 3000)...
start "BiliDigest-Frontend" cmd /k "%TEMP%\bd_frontend.bat"

echo.
echo 等待服务就绪（约10秒）...
timeout /t 10 /nobreak >nul

start http://localhost:3000

echo.
echo ========================================
echo    启动完成！
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000/docs
echo ========================================
pause
