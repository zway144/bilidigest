#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "   BiliDigest 一键启动"
echo "========================================"
echo

# ── 1. 清理旧进程 ──
echo "[1/4] 清理旧进程..."

# 杀掉占用 8000 端口的进程
if lsof -ti:8000 >/dev/null 2>&1; then
    echo "  关闭端口 8000 上的进程..."
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

# 杀掉占用 3000 端口的进程
if lsof -ti:3000 >/dev/null 2>&1; then
    echo "  关闭端口 3000 上的进程..."
    lsof -ti:3000 | xargs kill -9 2>/dev/null || true
fi

sleep 1

# ── 2. 检查依赖 ──
if [ ! -d "frontend/node_modules" ]; then
    echo "[*] 首次运行，安装前端依赖..."
    cd frontend && npm install && cd ..
fi

# ── 3. 启动后端 ──
echo
echo "[2/4] 启动后端服务..."
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# ── 4. 等待后端 ready ──
echo "[3/4] 等待后端就绪..."
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "  后端已就绪!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "  [错误] 后端启动超时（30秒），请检查错误信息"
        echo "  常见原因：pip 依赖未安装、.env 配置缺失、端口仍被占用"
        exit 1
    fi
    sleep 1
done

# ── 5. 启动前端 ──
echo "[4/4] 启动前端服务..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo
echo "========================================"
echo "   启动完成!"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:8000"
echo "   API文档: http://localhost:8000/docs"
echo "========================================"
echo
echo "按 Ctrl+C 停止所有服务"

# 捕获 Ctrl+C，同时停止前后端
trap "echo '正在停止服务...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM
wait
