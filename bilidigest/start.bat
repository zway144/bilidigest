@echo off
echo ========================================
echo    BiliDigest 一键启动
echo ========================================
echo.

echo [1/4] 安装后端依赖...
cd /d "%~dp0backend"
pip install -r requirements.txt
echo.

echo [2/4] 启动后端服务...
start cmd /k "cd /d "%~dp0backend" && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
cd /d "%~dp0"
echo.

echo [3/4] 安装前端依赖...
cd /d "%~dp0frontend"
call npm install
echo.

echo [4/4] 启动前端服务...
start cmd /k "cd /d "%~dp0frontend" && npm run dev"
cd /d "%~dp0"
echo.

timeout /t 5 /nobreak >nul
start http://localhost:3000

echo ========================================
echo    启动完成！
echo    前端: http://localhost:3000
echo    后端: http://localhost:8000/docs
echo ========================================
pause
