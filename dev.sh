#!/usr/bin/env bash
# Start DukaanPulse backend (FastAPI :8000) and frontend (Vite :5173).
set -e
cd "$(dirname "$0")"

export PATH="$PWD/tools/node/bin:$PATH"

echo "Starting backend on http://127.0.0.1:8000 ..."
backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --app-dir backend &
BACKEND_PID=$!

echo "Starting frontend on http://127.0.0.1:5173 ..."
(cd frontend && npm run dev -- --host 127.0.0.1) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
