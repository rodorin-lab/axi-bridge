#!/usr/bin/env python3
"""
Crystal-to-Noah Bridge
クリスタルのTTS応答を監視して、ChatGPT通話モードのノアにもテキスト送信する
ノアに「クリスタルがこう言った」を伝える

監視: /dev/shm/nexus_tts_done.txt（TTS再生完了時）
送信: Playwright CDP → ChatGPT textarea → Enter
"""

import os
import sys
import time
import subprocess

TTS_DONE = "/dev/shm/nexus_tts_done.txt"
CDP_PORT = "http://127.0.0.1:9222"
LAST_SENT = ""
POLL_INTERVAL = 0.5

def send_to_chatgpt(text):
    """Playwright CDP経由でChatGPTの入力欄にテキスト送信"""
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
        output = result.stdout.strip()
        if "OK" in output:
            print(f"[c2n] ChatGPT送信OK: {text[:50]}")
        else:
            print(f"[c2n] ChatGPT送信FAIL: {output}")
        return "OK" in output
    except Exception as e:
        print(f"[c2n] 送信エラー: {e}", file=sys.stderr)
        return False

def wait_for_noah_silence(timeout=15):
    """ノア（Chrome）が喋り終わるまで待つ"""
    chrome_was_active = False
    start = time.time()
    # Chrome音声があった → なくなるまで待つ
    while time.time() - start < timeout:
        chrome_active = os.path.exists("/dev/shm/chrome_audio_active.flag")
        if chrome_active:
            chrome_was_active = True
            time.sleep(0.3)
        elif chrome_was_active:
            # Chrome音声が終わった後、1秒余裕を見る
            time.sleep(1.0)
            return True
        else:
            # Chrome音声なし → すぐ送信OK
            return True
    return False  # タイムアウト

if __name__ == "__main__":
    print("[c2n] Crystal→Noah Bridge 起動")
    last_content = ""
    
    while True:
        try:
            if os.path.exists(TTS_DONE):
                with open(TTS_DONE, "r") as f:
                    content = f.read().strip()
                
                if content and content != last_content and content != LAST_SENT:
                    last_content = content
                    LAST_SENT = content
                    # クリスタルが新しい発言をした！
                    print(f"[c2n] クリスタル発言検知: {content[:60]}")
                    # ノアが喋り終わるまで待つ
                    wait_for_noah_silence()
                    print(f"[c2n] ノア静寂確認、送信する")
                    send_to_chatgpt(f"[ Crystal ] {content}")
            else:
                last_content = ""
        except Exception as e:
            print(f"[c2n] 監視エラー: {e}", file=sys.stderr)
        
        time.sleep(POLL_INTERVAL)