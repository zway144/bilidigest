#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "   BiliDigest 一键启动"
echo "========================================"
echo

# ── 清理指定端口上的所有进程 ──
kill_port() {
    local port=$1
    local pids
    # 优先用 lsof，fallback 到 fuser
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti:"$port" 2>/dev/null || true)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$port/tcp" 2>/dev/null | tr -s ' ' '\n' || true)
    else
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || true)
    fi

    if [ -n "$pids" ]; then
        echo "  关闭端口 $port 上的进程 (PID: $(echo $pids | tr '\n' ' '))..."
        for pid in $pids; do
            # 杀掉整个进程组（包括 node 子进程）
            kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
}

# ── 验证端口已释放 ──
check_port_free() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:"$port" >/dev/null 2>&1 && return 1 || return 0
    elif command -v fuser >/dev/null 2>&1; then
        fuser "$port/tcp" >/dev/null 2>&1 && return 1 || return 0
    else
        ss -tlnp "sport = :$port" 2>/dev/null | grep -q LISTEN && return 1 || return 0
    fi
}

# ── 1. 清理旧进程 ──
echo "[1/4] 清理旧进程..."

kill_port 8000
kill_port 3000

# 清理 Next.js 残留的 PID 锁文件（防止 "Another next dev server is already running"）
if [ -d "frontend/.next" ]; then
    rm -rf frontend/.next/dev 2>/dev/null || true
    echo "  清理 Next.js 锁文件"
fi

# 验证端口已释放
if ! check_port_free 8000; then
    echo "  [错误] 端口 8000 仍被占用，请手动检查: lsof -ti:8000"
    exit 1
fi
if ! check_port_free 3000; then
    echo "  [错误] 端口 3000 仍被占用，请手动检查: lsof -ti:3000"
    exit 1
fi
echo "  端口 8000、3000 已释放"

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
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# ── 5. 启动前端前二次确认端口 ──
if ! check_port_free 3000; then
    echo "  [错误] 端口 3000 在等待期间被其他进程占用"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

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
echo "========================================"
echo
echo "按 Ctrl+C 停止所有服务"

# 捕获 Ctrl+C，同时停止前后端
cleanup() {
    echo '正在停止服务...'
    kill $FRONTEND_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    # 确保子进程也被清理
    kill_port 3000
    kill_port 8000
    exit 0
}
trap cleanup INT TERM
wait
