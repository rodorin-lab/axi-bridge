#!/usr/bin/env python3
"""
ChatGPT Noah Bridge — OpenClaw Telegram → Party Bus

OpenClawのTelegram Botがノアのチャットグループに投稿したメッセージを
Party Busに中継する。

使い方:
  1. Telegram BotのgetUpdatesをポーリング
  2. ノア（ChatGPT）の応酬を検出
  3. Party Busにspeaker=chatgpt_noahで書き込み

必要: OpenClaw Telegram Bot Token
"""

import json
import os
import time
import urllib.request
import urllib.error

PARTY_BUS_PATH = "/dev/shm/axi_party_bus.jsonl"
BOT_TOKEN = ""
POLL_INTERVAL = 2.0
LAST_UPDATE_ID = 0

# OpenClaw設定からBot Tokenを読む
def load_bot_token() -> str:
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        token = config.get("channels", {}).get("telegram", {}).get("botToken", "")
        # マスク済みの場合は***が含まれる
        if "***" in token or not token:
            return ""
        return token
    except Exception:
        return ""


def append_party_bus(text: str) -> None:
    payload = {"speaker": "chatgpt_noah", "text": text, "ts": time.time()}
    with open(PARTY_BUS_PATH, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def get_updates() -> list:
    global LAST_UPDATE_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    params = urllib.parse.urlencode({
        "offset": LAST_UPDATE_ID + 1,
        "limit": 10,
        "timeout": 5,
    })
    req = urllib.request.Request(f"{url}?{params}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            updates = data.get("result", [])
            if updates:
                LAST_UPDATE_ID = updates[-1].get("update_id", LAST_UPDATE_ID)
            return updates
    except Exception as e:
        print(f"telegram poll error: {e}", file=sys.stderr, flush=True)
        return []


def process_updates(updates: list, chatgpt_chat_id: int) -> None:
    for update in updates:
        msg = update.get("message") or update.get("channel_post")
        if not msg:
            continue
        chat_id = msg.get("chat", {}).get("id", 0)
        # 監視対象のチャットのみ
        if chat_id != chatgpt_chat_id:
            continue
        text = msg.get("text", "").strip()
        if not text:
            continue
        # Bot自身のメッセージ（ノアの応答）のみParty Busに流す
        from_bot = msg.get("from", {}).get("is_bot", False)
        if from_bot:
            # 1文制限
            import re
            m = re.search(r'[。！？!?]', text)
            if m:
                text = text[:m.end()]
            if len(text) > 80:
                text = text[:79] + "…"
            append_party_bus(text)
            print(f"chatgpt_noah: {text[:60]}", file=sys.stderr, flush=True)


def main() -> int:
    global BOT_TOKEN

    BOT_TOKEN = load_bot_token()
    if not BOT_TOKEN:
        print("ERROR: Telegram Bot Token not found in openclaw.json", file=sys.stderr, flush=True)
        # フォールバック: MCP Server経由で手動送信可能
        print("Use MCP Server: curl -X POST http://localhost:8765/party/write", file=sys.stderr, flush=True)
        # 待機モード（定期的にチェック）
        while True:
            time.sleep(60)

    open(PARTY_BUS_PATH, "a", encoding="utf-8").close()
    print("chatgpt_noah bridge: polling Telegram Bot", file=sys.stderr, flush=True)

    # TODO: チャットIDを環境変数か設定ファイルから取得
    chatgpt_chat_id = int(os.environ.get("CHATGPT_NOAH_CHAT_ID", "0"))
    if not chatgpt_chat_id:
        print("WARNING: CHATGPT_NOAH_CHAT_ID not set. Set it to the Telegram chat ID for ChatGPT Noah.", file=sys.stderr, flush=True)

    while True:
        updates = get_updates()
        if updates:
            process_updates(updates, chatgpt_chat_id)
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())