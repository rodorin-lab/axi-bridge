#!/usr/bin/env python3
"""
Echo Guard v2 — スピーカー出力レベル監視でノアの声を検知
Chromeのsink-inputの有無ではなく、実際のスピーカー音量で判定
ノアが喋ってる → 音量大 → ミュートフラグON
ノアが黙ってる → 音量小 → ミュートフラグOFF
"""

import subprocess
import time
import os
import sys
import struct
import math

MUTE_FLAG = "/dev/shm/chrome_audio_active.flag"
MONITOR_SOURCE = "alsa_output.usb-Razer_Kraken_Ultimate_00000000-00.analog-stereo.monitor"
CHECK_DURATION = 0.3  # 秒間サンプリング
THRESHOLD_DB = -30    # -30dB以上で「ノア喋り中」
SILENCE_AFTER = 1.5  # 音が止まってからフラグを外すまでの秒数

def get_peak_db():
    """スピーカーモニターから0.3秒だけサンプリングしてピークdB取得"""
    try:
        result = subprocess.run(
            ["parec", "--device", MONITOR_SOURCE, "--format=s16le", "--rate=48000", "--channels=2",
             f"--process-time={int(CHECK_DURATION*1000)}"],
            capture_output=True, timeout=2
        )
        data = result.stdout
        if len(data) < 4:
            return -100
        # サンプルのピークを計算
        peak = 0
        for i in range(0, min(len(data), 9600), 2):  # 最大0.1秒分
            sample = abs(struct.unpack('<h', data[i:i+2])[0])
            if sample > peak:
                peak = sample
        if peak == 0:
            return -100
        db = 20 * math.log10(peak / 32768.0)
        return db
    except:
        return -100

if __name__ == "__main__":
    sys.stdout.write("[echo-guard-v2] スピーカーレベル監視開始\n")
    sys.stdout.flush()
    
    last_speaking = False
    silence_start = None
    
    while True:
        try:
            db = get_peak_db()
            speaking = db > THRESHOLD_DB
            
            if speaking:
                silence_start = None
                if not os.path.exists(MUTE_FLAG):
                    open(MUTE_FLAG, 'w').close()
                    sys.stdout.write(f"[echo-guard-v2] 音声検知 {db:.1f}dB → ミュートON\n")
                    sys.stdout.flush()
            else:
                if os.path.exists(MUTE_FLAG):
                    if silence_start is None:
                        silence_start = time.time()
                    elif time.time() - silence_start > SILENCE_AFTER:
                        os.remove(MUTE_FLAG)
                        silence_start = None
                        sys.stdout.write(f"[echo-guard-v2] 静寂 {db:.1f}dB → ミュートOFF\n")
                        sys.stdout.flush()
                else:
                    silence_start = None
        except Exception as e:
            sys.stderr.write(f"[echo-guard-v2] エラー: {e}\n")
            sys.stderr.flush()
        
        time.sleep(0.2)