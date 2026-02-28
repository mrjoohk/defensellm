#!/usr/bin/env bash
# Stop Defense LLM API and UI servers (UF-000)

echo "╔═══════════════════════════════════════╗"
echo "║   Defense LLM — Shutdown Script       ║"
echo "╚═══════════════════════════════════════╝"

# 1. Stop API (Python uvicorn)
echo "Stopping API (uvicorn)..."
if pkill -f "uvicorn defense_llm.api.main:app" ; then
    echo "  [OK] API process terminated."
else
    echo "  [SKIP] API process not found or already stopped."
fi

# 2. Stop UI (Vite/Node)
echo "Stopping UI (vite)..."
# We kill node processes running vite and the npm manager
if pkill -f "node.*/vite" || pkill -f "npm exec vite" ; then
    echo "  [OK] UI (Vite) process terminated."
else
    echo "  [SKIP] UI process not found or already stopped."
fi

echo ""
echo "All Defense LLM services have been requested to stop."
