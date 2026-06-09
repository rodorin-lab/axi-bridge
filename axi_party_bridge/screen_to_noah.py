#!/usr/bin/env python3
"""
Screen-to-Noah via Vision — スクリーンショットをVision APIでテキスト化してノアに送る
画像枚数制限なし！テキストだけ送るからノアの会話を消費しない

監視: ~/scrcpy-capture/latest.png の更新
流れ: スクショ → OpenRouter Vision(gemini-2.5-flash) → テキスト → ChatGPT textarea
"""

import os
import sys
import time
import subprocess
import base64
import requests

SCREENSHOT_PATH = os.path.expanduser("~/scrcpy-capture/latest.png")
SNAPSHOT_URL = "http://localhost:8646/snapshot"  # MJPEGサーバーからのJPEG取得
CDP_PORT = "http://127.0.0.1:9222"
SEND_INTERVAL = 8  # 8秒に1回（リアルタイム感向上）
VISION_PROMPT = "ゲーム画面の戦闘/選択状況を日本語で1文(20字以内)で。HP低下・状態異常・敵出現・コマンド選択中なら必ず書く。"

# API key取得
def get_api_key():
    try:
        result = subprocess.run(
            ["fish", "-c", "echo $OPENROUTER_API_KEY"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip()
    except:
        return ""

API_KEY = get_api_key()

def describe_screenshot(path):
    """Vision APIでスクショをテキスト化"""
    try:
        with open(path, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode()

        resp = requests.post('https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {API_KEY}'},
            json={
                'model': 'google/gemini-2.5-flash',
                'messages': [{'role': 'user', 'content': [
                    {'type': 'text', 'text': VISION_PROMPT},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}'}}
                ]}],
                'max_tokens': 80
            },
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()['choices'][0]['message']['content'].strip()
        else:
            print(f"[s2n-v] Vision API error: {resp.status_code}", file=sys.stderr)
            return None
    except Exception as e:
        print(f"[s2n-v] Vision error: {e}", file=sys.stderr)
        return None

def send_text_to_chatgpt(text):
    """Playwright CDPでChatGPTにテキスト送信"""
    try:
        script = f'''
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("{CDP_PORT}")
    sent = False
    for ctx in browser.contexts:
        for pg in ctx.pages:
            if "chatgpt.com" in pg.url:
                ta = pg.locator("#prompt-textarea")
                if ta.count() and ta.is_visible():
                    ta.fill("")
                    ta.type("{text}")
                    time.sleep(0.3)
                    pg.keyboard.press("Enter")
                    sent = True
                break
    browser.close()
print("OK" if sent else "FAIL")
'''
        result = subprocess.run(
            ["python3", "-c", script],
            capture_output=True, text=True, timeout=15
        )
        return "OK" in result.stdout
    except Exception as e:
        print(f"[s2n-v] 送信エラー: {e}", file=sys.stderr)
        return False

if __name__ == "__main__":
    print("[s2n-v] Screen→Noah via Vision 起動（ノアに目を与える）")
    last_sent = 0
    last_description = ""

    while True:
        try:
            now = time.time()
            if (now - last_sent) > SEND_INTERVAL:
                last_sent = now

                description = describe_screenshot(SCREENSHOT_PATH)
                if description and description != last_description:
                    last_description = description
                    print(f"[s2n-v] 画面: {description[:60]}")
                    # ノアが喋り終わるまで待つ（nexus_tts_muting参照）
                    tts_flag = "/dev/shm/nexus_tts_muting.flag"
                    wait_start = time.time()
                    while os.path.exists(tts_flag) and time.time() - wait_start < 10:
                        time.sleep(0.3)
                    send_text_to_chatgpt(f"[ 画面 ] {description}")
                    print(f"[s2n-v] → ノアに送信")
                else:
                    print(f"[s2n-v] 画面変化なし or Vision失敗")
        except Exception as e:
            print(f"[s2n-v] エラー: {e}", file=sys.stderr)

        time.sleep(10)  # 10秒ごとにチェック