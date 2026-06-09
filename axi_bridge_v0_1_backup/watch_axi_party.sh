#!/usr/bin/env bash
set -euo pipefail

exec tail -f /dev/shm/axi_party_bus.jsonl
