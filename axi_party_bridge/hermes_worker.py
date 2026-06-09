#!/usr/bin/env python3
"""
AXI Hermes Worker — kimi-k2.6 チャット + OpenRouter Vision

ヘルメスのinboxを監視し、
- 通常チャット → kimi-k2.6 (Hermes API 8642)
- 画面分析 → gemini-2.5-flash (OpenRouter直結)
返答はParty Busに投稿。
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERMES_INBOX_PATH = "/dev/shm/axi_hermes_inbox.jsonl"
PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
SCREENSHOT_PATH = Path.home() / "scrcpy-capture" / "latest.png"
HERMES_API = "http://localhost:8642/v1/chat/completions"
OPENROUTER_API = "https://openrouter.ai/api/v1/chat/completions"
POLL_INTERVAL = 0.2
REQUEST_TIMEOUT = 30

SYSTEM_PROMPT = (
    "AI「ヘルメス」として話す。ロドリンの観測・分析担当だ。\n"
    "絶対にロドリンを「お前」「君」と呼ばない。必ず「ロドリン」と呼ぶ。\n"
    "簡潔に。観測結果や分析を1文で端的に伝える。"
)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def get_openrouter_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if key:
        return key
    fish = Path.home() / ".config/fish/config.fish"
    if fish.exists():
        text = fish.read_text(errors="ignore")
        m = re.search(r"'(sk-or-[^']+)'", text)
        if m:
            return m.group(1)
    return ""


def append_party_bus(text: str) -> None:
    payload = {"speaker": "hermes", "text": text, "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def append_thinking() -> None:
    payload = {"speaker": "hermes", "text": "thinking...", "type": "status", "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def call_chat(text: str) -> str:
    """kimi-k2.6でチャット返答。"""
    payload = {
        "model": "kimi-k2.6",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"ロドリンがこう言った: 「{text}」"},
        ],
        "max_tokens": 60,
        "temperature": 0.7,
    }

    request = urllib.request.Request(
        HERMES_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        body = json.loads(response.read())

    return body["choices"][0]["message"]["content"].strip()


def call_vision() -> str:
    """OpenRouter(gemini-2.5-flash)で画面分析。"""
    key = get_openrouter_key()
    if not key:
        return "Vision APIキーがありません。"

    if not SCREENSHOT_PATH.exists():
        return "スクリーンショットがありません。"

    with open(SCREENSHOT_PATH, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {
                "role": "system",
                "content": "ロドリンのゲーム画面を分析するAI「ヘルメス」だ。この画面を1〜2文で簡潔に説明。",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "この画面を分析して。"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                ],
            },
        ],
        "max_tokens": 120,
        "temperature": 0.5,
    }

    request = urllib.request.Request(
        OPENROUTER_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        body = json.loads(response.read())

    return body["choices"][0]["message"]["content"].strip()


def shorten(text: str, max_chars: int = 80) -> str:
    if len(text) <= max_chars:
        return text
    for delim in ("。", "！", "？", "!", "?", "\n"):
        idx = text.find(delim)
        if 0 < idx < max_chars:
            return text[:idx + 1]
    return text[:max_chars - 1] + "。"


def handle_line(line: str) -> None:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return

    if not isinstance(payload, dict):
        return

    if payload.get("to") != "hermes":
        return

    text = payload.get("text", "")
    if not isinstance(text, str) or not text.strip():
        return

    from_speaker = payload.get("from", "")
    msg_type = payload.get("type", "chat")

    # ロドリンの発言は、ヘルメスが呼ばれた時だけ応答
    if from_speaker == "rodorin" and msg_type == "chat":
        text_lower = text.lower()
        has_hermes = any(kw in text_lower for kw in ("ヘルメス", "へるめす", "hermes", "画面"))
        if not has_hermes:
            return

    try:
        append_thinking()

        # 画面分析かチャットか判定
        if any(kw in text.lower() for kw in ("画面", "見て", "見える", "スキャン", "状況", "スクリーンショット")):
            reply = call_vision()
        else:
            reply = call_chat(text)

        if reply:
            reply = shorten(reply)
            log(f"hermes reply: {reply[:40]}")
            append_party_bus(reply)

    except urllib.error.URLError as exc:
        log(f"API error: {exc}")
    except Exception as exc:
        log(f"worker error: {exc}")


def follow_inbox() -> None:
    for path in (HERMES_INBOX_PATH, PARTY_BUS_PATH):
        open(path, "a", encoding="utf-8").close()

    with open(HERMES_INBOX_PATH, "r", encoding="utf-8") as handle:
        handle.seek(0, os.SEEK_END)
        while True:
            line = handle.readline()
            if not line:
                time.sleep(POLL_INTERVAL)
                continue
            handle_line(line)


def main() -> int:
    log("hermes worker: kimi-k2.6 chat + OpenRouter Vision")
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