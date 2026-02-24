#!/usr/bin/env bash
# Start the Defense LLM React frontend dev server
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
WEB_DIR="$PROJECT_ROOT/web"

cd "$WEB_DIR"

if [ ! -d "node_modules" ]; then
  echo "Installing npm dependencies..."
  npm install
fi

echo "Starting Defense LLM UI on http://localhost:5173"
echo "(API proxy → http://localhost:8000)"
echo ""
npm run dev
