#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "========================================"
echo "   BiliDigest Startup"
echo "========================================"
echo

# ── Helper: kill process on port ──
kill_port() {
    local port=$1
    local pids
    if command -v lsof >/dev/null 2>&1; then
        pids=$(lsof -ti:"$port" 2>/dev/null || true)
    elif command -v fuser >/dev/null 2>&1; then
        pids=$(fuser "$port/tcp" 2>/dev/null | tr -s ' ' '\n' || true)
    else
        pids=$(ss -tlnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || true)
    fi
    if [ -n "$pids" ]; then
        echo "  Killing port $port PID: $(echo $pids | tr '\n' ' ')..."
        for pid in $pids; do
            kill -9 -- -"$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
        done
        sleep 1
    fi
}

# ── 0. Check dependencies ──
echo "[0/5] Checking dependencies..."

command -v python >/dev/null 2>&1 || { echo "[ERROR] Python not found: https://www.python.org/downloads/"; exit 1; }
command -v pip  >/dev/null 2>&1 || { echo "[ERROR] pip not found: try: python -m ensurepip"; exit 1; }
command -v node  >/dev/null 2>&1 || { echo "[ERROR] Node.js not found: https://nodejs.org/"; exit 1; }
command -v npm   >/dev/null 2>&1 || { echo "[ERROR] npm not found"; exit 1; }
command -v ffmpeg >/dev/null 2>&1 || echo "[WARNING] FFmpeg not found - video processing will fail. Download: https://www.gyan.dev/ffmpeg/builds/"
echo "  Python, pip, node, npm: OK"

# ── 1. Kill old processes ──
echo "[1/5] Cleaning old processes..."
kill_port 8000
kill_port 3000
rm -rf frontend/.next/dev 2>/dev/null || true
echo "  Ports 8000 and 3000 cleaned"

# ── 2. Install backend Python dependencies ──
echo "[2/5] Installing backend dependencies..."
cd backend
pip install -r requirements.txt -q
cd ..
echo "  Python dependencies installed"

# ── 3. Install frontend Node dependencies ──
echo "[3/5] Installing frontend dependencies..."
if [ ! -d "frontend/node_modules" ]; then
    cd frontend && npm install && cd ..
fi
echo "  Node dependencies ready"

# ── 4. Start backend ──
echo "[4/5] Starting backend..."
cd backend
export HF_ENDPOINT="${HF_ENDPOINT:-}"  # Set HF_ENDPOINT=https://hf-mirror.com for China
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Wait for backend to be ready
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:8000/health >/dev/null 2>&1; then
        echo "  Backend ready!"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[ERROR] Backend startup timeout (30s)"
        echo "  Check the backend window for details."
        echo "  Common causes: .env missing, HF_ENDPOINT not set (for China users)"
        kill $BACKEND_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# ── 5. Start frontend ──
echo "[5/5] Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

sleep 3

echo
echo "========================================"
echo "   Startup complete!"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "========================================"
echo
echo "Press Ctrl+C to stop all services"

cleanup() {
    echo 'Stopping services...'
    kill $FRONTEND_PID 2>/dev/null || true
    kill $BACKEND_PID 2>/dev/null || true
    kill_port 3000
    kill_port 8000
    exit 0
}
trap cleanup INT TERM
wait
