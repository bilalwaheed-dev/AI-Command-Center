#!/usr/bin/env bash
# Onboarding script for PC-W2 inside WSL2 Ubuntu

SUPERVISOR_URL="${1:-http://192.168.2.2:5050}"
TOKEN="${2:-cc_tok_85E2nYpua07B6MXwO8MKJ5PXVd2xySDv}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "=========================================================="
echo "Starting PC-W2 Worker Daemon [WSL2-UBUNTU]..."
echo "Supervisor: $SUPERVISOR_URL"
echo "=========================================================="

python3 "$SCRIPT_DIR/worker_daemon.py" \
  --server "$SUPERVISOR_URL" \
  --worker-id PC-W2 \
  --machine BIG-PC \
  --env WSL2-UBUNTU \
  --token "$TOKEN" \
  --poll-interval 3 \
  --heartbeat-interval 10
