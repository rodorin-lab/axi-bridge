#!/usr/bin/env python3
import json
import sys
import time


BUS_PATH = "/dev/shm/axi_party_bus.jsonl"


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: python3 axi_bridge_client.py <speaker> "<text>"', file=sys.stderr)
        return 1

    speaker = sys.argv[1]
    text = sys.argv[2]
    payload = {
        "speaker": speaker,
        "text": text,
        "ts": time.time(),
    }

    with open(BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
