#!/bin/bash
set -e

# Start backend
export PYTHONPATH="/home/runner/workspace/src"
cd /home/runner/workspace/src/apps/admin_center/backend
python -m uvicorn main:app --host localhost --port 8000 &
BACKEND_PID=$!

# Start frontend
cd /home/runner/workspace/src/apps/admin_center/frontend
npm run dev &
FRONTEND_PID=$!

# Wait for both
wait $BACKEND_PID $FRONTEND_PID
