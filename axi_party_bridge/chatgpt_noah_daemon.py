#!/usr/bin/env python3
"""
ChatGPT Noah Daemon — Party Busのinbox/noaを監視してChatGPT Webに自動応答
ロドリンが話す → Voice Bridge → Party Bus → inbox/noa → このデーモン → ChatGPT Web → Party Bus

起動: python3 chatgpt_noah_daemon.py
依存: playwright, requests
"""

import json
import time
import sys
import os
import requests
import threading

PARTY_BASE = "http://localhost:8765"
INBOX_URL = f"{PARTY_BASE}/inbox/noa"
WRITE_URL = f"{PARTY_BASE}/party/write"
SPEAKER = "chatgpt_noah"
POLL_INTERVAL = 1.5  # inbox取得間隔(秒)
RESPONSE_COOLDOWN = 3  # 連続応答の最小間隔(秒)

# ChatGPT Web Bridge インポート
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from chatgpt_web_bridge import ChatGPTWebBridge


class NoaDaemon:
    def __init__(self):
        self.bridge = ChatGPTWebBridge()
        self.last_ts = 0
        self.last_response_ts = 0
        self.processed_ids = set()

    def _fetch_party_context(self):
        """Party Busの最新会話を取得（ノアに文脈を与えるため）"""
        try:
            resp = requests.get(f"{PARTY_BASE}/party/latest?limit=10", timeout=5)
            data = resp.json()
            items = data.get("items", [])
            lines = []
            for m in items:
                s = m.get("speaker", "?")
                t = m.get("text", "").strip()
                if t and s != SPEAKER:  # 自分の発言は除く
                    lines.append(f"{s}: {t}")
            return "\n".join(lines)
        except Exception:
            return ""

    def start(self):
        """デーモン開始"""
        print("[noah] ChatGPTノアデーモン起動...")
        self.bridge.connect()
        print("[noah] ChatGPT接続OK!")

        # inboxの既存メッセージをスキップ（二重応答防止）
        existing = self._fetch_inbox()
        for m in existing:
            mid = m.get("ts", 0) + hash(m.get("text", ""))
            self.processed_ids.add(mid)
            if m.get("ts", 0) > self.last_ts:
                self.last_ts = m.get("ts", 0)
        print(f"[noah] 既存メッセージ {len(existing)}件 スキップ済み")

        print("[noah] 監視開始！ロドリンが話しかけたらChatGPTからノアが応答する")

        while True:
            try:
                self._poll_and_respond()
            except Exception as e:
                print(f"[noah] エラー: {e}", file=sys.stderr)
            time.sleep(POLL_INTERVAL)

    def _fetch_inbox(self):
        """inbox/noaの最新メッセージ取得"""
        try:
            resp = requests.get(f"{INBOX_URL}?limit=10", timeout=5)
            data = resp.json()
            items = data.get("items", [])
            # inbox format: {"from": "rodorin", "to": "noa", "type": "chat", "text": "...", "ts": ...}
            # party/write format: {"speaker": "rodorin", "text": "...", "ts": ...}
            # 統一して "speaker" フィールドを使う
            normalized = []
            for m in items:
                m["speaker"] = m.get("from", m.get("speaker", "unknown"))
                normalized.append(m)
            return normalized
        except Exception as e:
            print(f"[noah] inbox取得失敗: {e}", file=sys.stderr)
            return []

    def _poll_and_respond(self):
        """inboxをポーリングして新メッセージに応答"""
        messages = self._fetch_inbox()

        for msg in reversed(messages):
            mid = msg.get("ts", 0) + hash(msg.get("text", ""))

            # 処理済みはスキップ
            if mid in self.processed_ids:
                continue

            # 古いメッセージはスキップ（30秒以上前）
            if msg.get("ts", 0) < time.time() - 30:
                self.processed_ids.add(mid)
                continue

            # 自分の発言はスキップ
            if msg.get("speaker") == SPEAKER:
                self.processed_ids.add(mid)
                continue

            # クールダウン確認
            if time.time() - self.last_response_ts < RESPONSE_COOLDOWN:
                self.processed_ids.add(mid)
                continue

            text = msg.get("text", "").strip()
            speaker = msg.get("speaker", "unknown")

            if not text or len(text) < 2:
                self.processed_ids.add(mid)
                continue

            # 新しいメッセージ発見！
            print(f"[noah] {speaker}: {text[:60]}")
            self.processed_ids.add(mid)

            # Party Busの文脈を取得
            context = self._fetch_party_context()
            if context:
                prompt = f"""【Party Busの最新会話】
{context}

【{speaker}の発言】{text}

ノアとして1文で応答してください。"""
            else:
                prompt = text

            # ChatGPT Webに送信
            response = self.bridge.send_message(prompt, timeout=45)

            if response:
                # Party Busに送信
                print(f"[noah] ChatGPT応答: {response[:60]}")
                try:
                    resp = requests.post(
                        WRITE_URL,
                        json={"speaker": SPEAKER, "text": response},
                        timeout=5,
                    )
                    bus_ok = resp.json().get("ok")
                    if bus_ok:
                        print("[noah] → Party Bus送信OK!")
                except Exception as e:
                    print(f"[noah] Party Bus送信失敗: {e}", file=sys.stderr)

                # TTS音声出力（nexus_tts.txtに書き込むと自動再生）
                try:
                    with open("/dev/shm/nexus_tts.txt", "w") as f:
                        f.write(response)
                    print("[noah] → TTS音声キューOK!")
                except Exception as e:
                    print(f"[noah] TTS書き込み失敗: {e}", file=sys.stderr)
            else:
                print("[noah] ChatGPT応答なし", file=sys.stderr)

            self.last_response_ts = time.time()

        # processed_idsが大きくなりすぎたら扫除
        if len(self.processed_ids) > 500:
            self.processed_ids = set(list(self.processed_ids)[-200:])


if __name__ == "__main__":
    daemon = NoaDaemon()
    daemon.start()