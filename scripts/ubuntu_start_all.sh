#!/usr/bin/env bash
# Start both backend and frontend in parallel.
# Kill both when this script exits (Ctrl+C).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT INT TERM

echo "╔═══════════════════════════════════════╗"
echo "║   Defense LLM Console — Full Stack    ║"
echo "╠═══════════════════════════════════════╣"
echo "║  API  →  http://localhost:8000        ║"
echo "║  UI   →  http://localhost:5173        ║"
echo "╚═══════════════════════════════════════╝"
echo ""

bash "$SCRIPT_DIR/start_api.sh" &
BACKEND_PID=$!

sleep 1  # brief pause so uvicorn banner prints first

bash "$SCRIPT_DIR/start_web.sh" &
FRONTEND_PID=$!

wait "$BACKEND_PID" "$FRONTEND_PID"
