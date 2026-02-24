#!/usr/bin/env bash
# Start the Defense LLM FastAPI backend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ensure data dirs exist
mkdir -p "$PROJECT_ROOT/data/logs"

# Default paths (can be overridden via env)
export DEFENSE_LLM_DB_PATH="${DEFENSE_LLM_DB_PATH:-$PROJECT_ROOT/data/defense.db}"
export DEFENSE_LLM_INDEX_PATH="${DEFENSE_LLM_INDEX_PATH:-$PROJECT_ROOT/data/defense.index}"
export DEFENSE_LLM_LOG_PATH="${DEFENSE_LLM_LOG_PATH:-$PROJECT_ROOT/data/logs}"

echo "Starting Defense LLM API on http://localhost:8000"
echo "  DB:    $DEFENSE_LLM_DB_PATH"
echo "  Index: $DEFENSE_LLM_INDEX_PATH"
echo ""

cd "$PROJECT_ROOT"

# Use conda env python if available
PYTHON="${DEFENSE_LLM_PYTHON:-/home/rtv-24n10/anaconda3/envs/defensellm/bin/python}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="python"
fi

"$PYTHON" -m uvicorn src.defense_llm.api.main:app --host 0.0.0.0 --port 8000 --reload
