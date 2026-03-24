#!/bin/bash
echo "========================================"
echo "   BiliDigest 一键启动"
echo "========================================"

echo "[1/4] 安装后端依赖..."
cd "$(dirname "$0")/backend"
pip install -r requirements.txt

echo "[2/4] 启动后端服务..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
cd ..

echo "[3/4] 安装前端依赖..."
cd frontend
npm install

echo "[4/4] 启动前端服务..."
npm run dev &
cd ..

echo "========================================"
echo "   启动完成！"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000/docs"
echo "========================================"
