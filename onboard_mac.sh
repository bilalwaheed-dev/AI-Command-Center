#!/usr/bin/env bash
# Onboarding script for Mac Workers (MAC-W1, MAC-W2, MAC-W3)

WORKER_ID="${1:-MAC-W1}"
SUPERVISOR_URL="${2:-http://192.168.2.2:5050}"
TOKEN="${3:-cc_tok_85E2nYpua07B6MXwO8MKJ5PXVd2xySDv}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

echo "=========================================================="
echo "Starting $WORKER_ID Worker Daemon [DARWIN-NATIVE]..."
echo "Supervisor: $SUPERVISOR_URL"
echo "=========================================================="

python3 "$SCRIPT_DIR/worker_daemon.py" \
  --server "$SUPERVISOR_URL" \
  --worker-id "$WORKER_ID" \
  --machine "$(hostname -s)" \
  --env DARWIN-NATIVE \
  --token "$TOKEN" \
  --poll-interval 3 \
  --heartbeat-interval 10
