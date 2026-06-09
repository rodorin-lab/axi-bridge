#!/usr/bin/env bash
set -euo pipefail

BUS_PATH="/dev/shm/axi_party_bus.jsonl"
NOA_INBOX_PATH="/dev/shm/axi_noa_inbox.jsonl"
HERMES_INBOX_PATH="/dev/shm/axi_hermes_inbox.jsonl"
PID_PATH="/dev/shm/axi_party_pids.txt"

touch "$BUS_PATH"
touch "$NOA_INBOX_PATH"
touch "$HERMES_INBOX_PATH"

python3 axi_message_bridge.py &
BRIDGE_PID=$!

python3 noa_worker.py &
WORKER_PID=$!

printf '%s\n%s\n' "$BRIDGE_PID" "$WORKER_PID" > "$PID_PATH"

exec tail -f "$BUS_PATH"
