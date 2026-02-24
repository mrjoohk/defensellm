#!/usr/bin/env bash
# scripts/download_rag_docs.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Running python downloader script..."
/home/rtv-24n10/anaconda3/envs/defensellm/bin/python "$SCRIPT_DIR/download_rag_docs.py"
