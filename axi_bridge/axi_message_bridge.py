#!/usr/bin/env python3
import json
import os
import time


BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
NOA_INBOX_PATH = "/dev/shm/axi_noa_inbox.jsonl"
HERMES_INBOX_PATH = "/dev/shm/axi_hermes_inbox.jsonl"
POLL_INTERVAL = 0.2


def append_jsonl(path: str, payload: dict) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_consult_message(latest_hermes_text: str) -> dict:
    return {
        "from": "bridge",
        "to": "noa",
        "type": "consult",
        "text": f"ヘルメスの最新報告: {latest_hermes_text}ロドリンに短く助言して。",
        "ts": time.time(),
    }


def process_message(message: dict, latest_hermes_text: str) -> str:
    speaker = message.get("speaker")
    text = message.get("text")
    ts = message.get("ts", time.time())

    if not isinstance(speaker, str) or not isinstance(text, str):
        return latest_hermes_text

    if speaker == "hermes":
        append_jsonl(
            NOA_INBOX_PATH,
            {
                "from": "hermes",
                "to": "noa",
                "type": "report",
                "text": text,
                "ts": ts,
            },
        )
        return text

    if speaker == "noa":
        append_jsonl(
            HERMES_INBOX_PATH,
            {
                "from": "noa",
                "to": "hermes",
                "type": "request",
                "text": text,
                "ts": ts,
            },
        )
        return latest_hermes_text

    if speaker == "rodorin" and "二人で相談して" in text and latest_hermes_text:
        append_jsonl(NOA_INBOX_PATH, build_consult_message(latest_hermes_text))

    return latest_hermes_text


def follow_bus() -> None:
    latest_hermes_text = ""

    with open(BUS_PATH, "a+", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            if isinstance(message, dict):
                latest_hermes_text = process_message(message, latest_hermes_text)


def main() -> int:
    for path in (BUS_PATH, NOA_INBOX_PATH, HERMES_INBOX_PATH):
        open(path, "a", encoding="utf-8").close()

    follow_bus()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
