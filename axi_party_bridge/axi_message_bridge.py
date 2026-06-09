#!/usr/bin/env python3
"""
AXI Message Bridge v2 — ループ防止版

ルール:
- rodorinの発言 → noa inbox + hermes inbox（両方通知）
- hermesの発言 → Party Busに記録するだけでinbox転送しない
- noaの発言 → Party Busに記録するだけでinbox転送しない
- chatgpt_noahの発言 → noa inboxに通知（ノアが反応できる）
- 「二人で相談して」→ noaにconsult送信
- thinking... / type=status → 全スキップ
"""

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
    msg_type = message.get("type", "")

    if not isinstance(speaker, str) or not isinstance(text, str):
        return latest_hermes_text

    # thinking/statusは完全スキップ
    if msg_type == "status" or text.strip() == "thinking...":
        return latest_hermes_text

    # ロドリンの発言 → 両方に通知
    if speaker == "rodorin":
        append_jsonl(NOA_INBOX_PATH, {
            "from": "rodorin", "to": "noa", "type": "chat", "text": text, "ts": ts,
        })
        append_jsonl(HERMES_INBOX_PATH, {
            "from": "rodorin", "to": "hermes", "type": "chat", "text": text, "ts": ts,
        })
        if "二人で相談して" in text and latest_hermes_text:
            append_jsonl(NOA_INBOX_PATH, build_consult_message(latest_hermes_text))
        return latest_hermes_text

    # ヘルメスの発言 → 記録のみ（inbox転送しない＝ループ防止）
    if speaker == "hermes":
        return text  # latest_hermes_text更新

    # ノアの発言 → 記録のみ
    if speaker == "noa":
        return latest_hermes_text

    # chatgpt_noahの発言 → ノアに通知（会話に参加）
    if speaker == "chatgpt_noah":
        append_jsonl(NOA_INBOX_PATH, {
            "from": "chatgpt_noah", "to": "noa", "type": "chat", "text": text, "ts": ts,
        })
        return latest_hermes_text

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