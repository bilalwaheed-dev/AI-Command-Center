#!/usr/bin/env bash
# Onboarding script for PC-W2 inside WSL2 Ubuntu

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

SUPERVISOR_URL="${1:-http://192.168.2.2:5050}"
TOKEN="${2:-$COMMAND_CENTER_TOKEN}"

# If token not explicitly passed, attempt to read from shared data/auth_token.secret
if [ -z "$TOKEN" ] && [ -f "$SCRIPT_DIR/data/auth_token.secret" ]; then
  TOKEN="$(cat "$SCRIPT_DIR/data/auth_token.secret" | tr -d '\r\n')"
fi

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
