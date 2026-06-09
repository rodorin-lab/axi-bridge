#!/usr/bin/env python3
"""
ChatGPT Web Bridge (Playwright CDP版)
Chrome CDP経由でChatGPTにアクセスし、ノアの応答をParty Busに流す
CF検知を回避（ブラウザセッションそのものを使うから）

起動: python3 chatgpt_web_bridge.py
依存: playwright, requests
"""

import json
import time
import sys
import os
import requests
import uuid

PARTY_WRITE_URL = "http://localhost:8765/party/write"
SPEAKER = "chatgpt_noah"
CDP_URL = "http://127.0.0.1:9222"

# ノアのペルソナ（システムプロンプトとして冒頭に送る）
PERSONA_PROMPT = "あなたはノア（Noah）です。AXIパーティのメンバーで、ロドリンの仲間。短く1文で返答してください。口調は親しみやすくカジュアルに。"


def send_to_party_bus(text):
    """Party Busにノアの発言をPOST"""
    try:
        resp = requests.post(
            PARTY_WRITE_URL,
            json={"speaker": SPEAKER, "text": text},
            timeout=5,
        )
        return resp.json().get("ok", False)
    except Exception as e:
        print(f"[party] POST失敗: {e}", file=sys.stderr)
        return False


class ChatGPTWebBridge:
    def __init__(self):
        self.browser = None
        self.page = None
        self.initialized = False

    def connect(self):
        """Playwright CDPでChromeに接続"""
        from playwright.sync_api import sync_playwright

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.connect_over_cdp(CDP_URL)

        # ChatGPTページを探す
        contexts = self.browser.contexts
        for ctx in contexts:
            for pg in ctx.pages:
                if "chatgpt.com" in pg.url:
                    self.page = pg
                    break

        if not self.page:
            # ChatGPTタブがなければ開く
            ctx = self.browser.contexts[0] if self.browser.contexts else self.browser.new_context()
            self.page = ctx.new_page()
            self.page.goto("https://chatgpt.com/", timeout=30000)
            time.sleep(3)

        print(f"[bridge] ChatGPTページ接続: {self.page.url[:60]}")
        self.initialized = True

    def send_message(self, message, timeout=60):
        """ChatGPTのプロンプト入力欄にメッセージを送信し、応答を取得"""
        if not self.initialized:
            self.connect()

        try:
            page = self.page

            # 既存のChatGPTページを使う（CF再認証を避けるため新規ページ遷移しない）
            # URLがchatgpt.comであることを確認
            if "chatgpt.com" not in page.url:
                print("[bridge] ChatGPTページが見つかりません", file=sys.stderr)
                return None

            # 現在の会話をリセットしたい場合はサイドバーの新規チャットボタンを押す
            # まずは現在のページで送信試行
            # 入力欄がなければ新規チャットを開く
            textarea = page.locator('#prompt-textarea')
            if not textarea.count():
                textarea = page.locator('[contenteditable="true"]')
            if not textarea.count():
                textarea = page.locator('textarea')

            if not textarea.count():
                print("[bridge] 入力欄が見つかりません", file=sys.stderr)
                return None

            # メッセージ入力
            textarea.first.click()
            time.sleep(0.3)
            # contenteditableなので、fillではなくtypeを使用
            textarea.first.type(message, delay=30)
            time.sleep(0.5)

            # 送信 — Enterキー
            textarea.first.press("Enter")

            print("[bridge] メッセージ送信済み、応答待ち...")

            # 応答待ち — 生成完了まで監視
            start = time.time()
            response_text = ""

            # 新しいページなので初期assistant数は0
            initial_count = 0

            while time.time() - start < timeout:
                time.sleep(3)

                # ストップボタン（生成中インジケータ）があればまだ生成中
                stop_btn = page.locator('[aria-label="Stop generating"]')
                is_generating = stop_btn.count() > 0

                # 最後のassistantメッセージを取得
                responses = page.locator('[data-message-author-role="assistant"]')
                count = responses.count()

                if count > 0:
                    try:
                        current_text = responses.last.inner_text().strip()
                    except Exception:
                        current_text = ""

                    # エラーメッセージは除外
                    if current_text and "something went wrong" not in current_text.lower():
                        # 生成完了 = ストップボタンがない + テキストが十分長い
                        if not is_generating and len(current_text) > 5:
                            response_text = current_text
                            break

                # まだ応答が来てない & 生成中でもない = 何か問題
                if count == 0 and not is_generating and time.time() - start > 15:
                    # 15秒経っても応答なし — 再送信試行
                    print("[bridge] 応答なし、再試行...", file=sys.stderr)
                    break

                # タイムアウト
                if time.time() - start > timeout:
                    break

            if response_text:
                print(f"[bridge] 応答取得: {response_text[:80]}...")
                return response_text
            else:
                print("[bridge] 応答なし（タイムアウト）", file=sys.stderr)
                return None

        except Exception as e:
            print(f"[bridge] エラー: {e}", file=sys.stderr)
            return None

    def close(self):
        """ブラウザ切断（Chrome本体は閉じない）"""
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright') and self.playwright:
            self.playwright.stop()


def run_interactive():
    """インタラクティブモード"""
    bridge = ChatGPTWebBridge()
    bridge.connect()

    # 初回ペルソナ設定
    print("[bridge] ノアのペルソナ設定中...")
    bridge.send_message(PERSONA_PROMPT, timeout=30)
    time.sleep(2)

    print("\nChatGPT Web Bridge 起動！")
    print("コマンド: メッセージを入力 → ChatGPTノアが応答 → Party Busに流す")
    print("  /quit — 終了\n")

    while True:
        try:
            user_input = input("ロドリン> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n終了")
            break

        if not user_input:
            continue
        if user_input == "/quit":
            break

        text = bridge.send_message(user_input)
        if text:
            print(f"ノア: {text}")
            if send_to_party_bus(text):
                print(" → Party Bus OK!")
            else:
                print(" → Party Bus失敗")

    bridge.close()


def send_single(message):
    """ワンショットモード"""
    bridge = ChatGPTWebBridge()
    bridge.connect()
    text = bridge.send_message(message)
    bridge.close()

    if text:
        print(f"ノア: {text}")
        return send_to_party_bus(text)
    return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--single":
        msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "こんにちは"
        send_single(msg)
    else:
        run_interactive()