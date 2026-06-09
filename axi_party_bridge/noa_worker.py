#!/usr/bin/env python3
"""
AXI Noa Worker v2 — Hermes API(8642)接続版

ノアのinboxを監視し、Hermes API(localhost:8642)のdeepseek-v4-flashで返答生成。
返答はParty Busに投稿。絶対1文だけ。
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

NOA_INBOX_PATH = "/dev/shm/axi_noa_inbox.jsonl"
PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
HERMES_API = "http://localhost:8642/v1/chat/completions"
POLL_INTERVAL = 0.2
REQUEST_TIMEOUT = 30

SYSTEM_PROMPT = (
    "AI「ノア」として話す。ロドリンの優しい相棒だ。\n"
    "絶対にロドリンを「お前」「君」と呼ばない。必ず「ロドリン」と呼ぶ。\n"
    "口語体で親しみやすく。返答は絶対に1文だけ。2文以上は禁止。短く。"
)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def append_party_bus(text: str) -> None:
    payload = {"speaker": "noa", "text": text, "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_thinking() -> None:
    payload = {"speaker": "noa", "text": "thinking...", "type": "status", "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def call_llm(text: str) -> str:
    user_prompt = f"ロドリンがこう言った: 「{text}」"

    payload = {
        "model": "deepseek-v4-flash",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 45,
        "temperature": 0.9,
    }

    request = urllib.request.Request(
        HERMES_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = json.loads(response.read())

    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("invalid API response: missing choices")

    content = choices[0].get("message", {}).get("content", "")
    return " ".join(content.strip().splitlines()).strip()


def handle_line(line: str) -> None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, dict):
        return

    if payload.get("to") != "noa":
        return

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return

    try:
        append_thinking()
        reply = call_llm(text)
        if reply:
            # 1文強制: 最初の文区切りで切る（区切り文字の後ろは全部捨てる）
            import re
            m = re.search(r'[。！？!?]', reply)
            if m:
                reply = reply[:m.end()]
            # 改行があればそこでも切る
            reply = reply.split("\n")[0].strip()
            # 80文字上限
            if len(reply) > 80:
                reply = reply[:79] + "…"
            log(f"noa reply: {reply[:40]}")
            append_party_bus(reply)
    except urllib.error.URLError as exc:
        log(f"API error: {exc}")
    except Exception as exc:
        log(f"worker error: {exc}")


def follow_inbox() -> None:
    for path in (NOA_INBOX_PATH, PARTY_BUS_PATH):
        open(path, "a", encoding="utf-8").close()

    with open(NOA_INBOX_PATH, "r", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue
            handle_line(line)


def main() -> int:
    log("noa worker v2: Hermes API(8642) + deepseek-v4-flash")
    while True:
        try:
            follow_inbox()
        except FileNotFoundError:
            time.sleep(POLL_INTERVAL)
        except Exception as exc:
            log(f"fatal loop error: {exc}")
            time.sleep(1.0)


if __name__ == "__main__":
    raise SystemExit(main())