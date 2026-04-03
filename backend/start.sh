#!/bin/bash
# ReRoots Backend Startup Script
# This script starts the FastAPI backend and waits for it to be healthy

set -e

PORT=${PORT:-8001}
HOST=${HOST:-0.0.0.0}
HEALTH_CHECK_URL="http://localhost:${PORT}/health"
MAX_WAIT=120
WAIT_INTERVAL=2

echo "Starting FastAPI backend on ${HOST}:${PORT}..."

# Start uvicorn in background
cd /app/backend
uvicorn server:app --host ${HOST} --port ${PORT} &
UVICORN_PID=$!

echo "Uvicorn started with PID: ${UVICORN_PID}"

# Wait for health check to pass
ELAPSED=0
while [ $ELAPSED -lt $MAX_WAIT ]; do
    # Check if uvicorn is still running
    if ! kill -0 $UVICORN_PID 2>/dev/null; then
        echo "ERROR: Uvicorn process died"
        exit 1
    fi
    
    # Try health check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${HEALTH_CHECK_URL}" 2>/dev/null || echo "000")
    
    if [ "$HTTP_CODE" = "200" ]; then
        echo "Health check passed! Server is ready."
        echo "Backend running on http://${HOST}:${PORT}"
        # Keep the script running to keep uvicorn alive
        wait $UVICORN_PID
        exit 0
    fi
    
    echo "Waiting for backend... (${ELAPSED}s, HTTP: ${HTTP_CODE})"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

echo "ERROR: Backend failed to start within ${MAX_WAIT}s"
kill $UVICORN_PID 2>/dev/null || true
exit 1
