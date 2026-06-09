#!/usr/bin/env bash
set -euo pipefail

touch /dev/shm/axi_party_bus.jsonl
touch /dev/shm/axi_noa_inbox.jsonl
touch /dev/shm/axi_hermes_inbox.jsonl

exec python3 axi_message_bridge.py
