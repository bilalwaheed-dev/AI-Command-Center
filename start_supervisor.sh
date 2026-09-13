#!/usr/bin/env bash
set -e
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "==================================================="
echo "Starting AI Command Center Supervisor (WSL/Linux/macOS)..."
echo "==================================================="
python3 supervisor.py --host 0.0.0.0 --port 5050
