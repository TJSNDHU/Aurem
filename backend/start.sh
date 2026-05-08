#!/bin/bash
# AUREM Production Startup Script
# Ensures backend is healthy before frontend serves traffic

set -e

PORT=${PORT:-8001}
HOST=${HOST:-0.0.0.0}
HEALTH_CHECK_URL="http://localhost:${PORT}/api/health"
MAX_WAIT=60
WAIT_INTERVAL=2

echo "[AUREM] Starting backend on ${HOST}:${PORT}..."

# Start uvicorn in background
cd /app/backend
uvicorn server:app --host ${HOST} --port ${PORT} --workers 1 &
UVICORN_PID=$!

echo "[AUREM] Uvicorn started with PID: ${UVICORN_PID}"

# Wait for backend to be ready
echo "[AUREM] Waiting for backend health check..."
ELAPSED=0
BACKEND_READY=false
while [ $ELAPSED -lt $MAX_WAIT ]; do
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        echo "[AUREM] ERROR: Uvicorn process died"
        exit 1
    fi

    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_CHECK_URL}" 2>/dev/null || echo "000")

    if [ "$HTTP_CODE" = "200" ]; then
        echo "[AUREM] Backend ready after ${ELAPSED}s"
        BACKEND_READY=true
        break
    fi

    echo "[AUREM] Attempt $((ELAPSED / WAIT_INTERVAL + 1))/$((MAX_WAIT / WAIT_INTERVAL)) — waiting... (HTTP: ${HTTP_CODE})"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ "$BACKEND_READY" = false ]; then
    echo "[AUREM] WARNING: Backend not ready after ${MAX_WAIT}s, starting frontend anyway"
fi

# Start frontend
echo "[AUREM] Starting frontend on port 3000..."
cd /app/frontend
if [ -d "build" ]; then
    npx serve -s build -l 3000 &
else
    yarn start &
fi
FRONTEND_PID=$!

echo "[AUREM] Frontend started with PID: ${FRONTEND_PID}"
echo "[AUREM] All services running. Backend PID=${UVICORN_PID}, Frontend PID=${FRONTEND_PID}"

# Wait for either process to exit
wait -n $UVICORN_PID $FRONTEND_PID 2>/dev/null || wait $UVICORN_PID
