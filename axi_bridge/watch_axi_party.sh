#!/usr/bin/env bash
set -euo pipefail

BUS_PATH="/dev/shm/axi_party_bus.jsonl"

touch "$BUS_PATH"

{
  tail -n 20 "$BUS_PATH"
  tail -n 0 -f "$BUS_PATH"
} | python3 -c '
import json
import sys
import time

RESET = "\033[0m"
DIM = "\033[2m"
COLORS = {
    "hermes": "\033[31m",
    "noa": "\033[32m",
    "rodorin": "\033[33m",
    "vision": "\033[36m",
    "chatgpt_noah": "\033[35m",
}
NAMES = {
    "hermes": "ヘルメス",
    "noa": "ノア",
    "rodorin": "ロドリン",
    "vision": "Vision",
    "chatgpt_noah": "ChatGPTノア",
}
DEFAULT = "\033[36m"

for raw_line in sys.stdin:
    line = raw_line.rstrip("\n")
    if not line:
        continue

    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        print(f"{DIM}{line}{RESET}", flush=True)
        continue

    if not isinstance(payload, dict):
        print(f"{DIM}{line}{RESET}", flush=True)
        continue

    speaker = payload.get("speaker")
    text = payload.get("text")
    ts = payload.get("ts")

    color = COLORS.get(speaker, DEFAULT)
    label = NAMES.get(speaker, str(speaker) if speaker is not None else "UNKNOWN")

    if isinstance(ts, (int, float)):
        clock = time.strftime("%H:%M:%S", time.localtime(ts))
        prefix = f"[{clock}]"
    else:
        prefix = "[--:--:--]"

    if not isinstance(text, str):
        text = ""

    print(f"{color}{prefix} {label}「{text}」{RESET}", flush=True)
'
