#!/bin/bash
# 3モード切替スクリプト
# 1. solo   — クリスタル＋ロドリン（音声パイプラインON）
# 2. party  — ノア＋クリスタル＋ロドリン（3人会話、エコーガード付き）
# 3. noah   — ノア＋ロドリンのみ（音声パイプラインOFF）

VDIR="$HOME/AIOS2/nexus-emu-v3-tauri"
PDIR="$HOME/AXI/axi_party_bridge"
export PATH="/home/rodorin/.local/bin:$PATH"

stop_voice() {
    pkill -9 -f voice_mirror.py 2>/dev/null
    pkill -9 -f voice_live_bridge.py 2>/dev/null
    echo "" > /dev/shm/nexus_tts.txt
    echo "" > /dev/shm/voice_latest.txt
    rm -f /dev/shm/voice_new.flag /dev/shm/nexus_tts_muting.flag 2>/dev/null
}

start_voice() {
    stop_voice
    cd "$VDIR"
    PYTHONUNBUFFERED=1 python3 -B voice_mirror.py >> /tmp/voice_mirror.log 2>&1 &
    sleep 1
    PYTHONUNBUFFERED=1 python3 -B -u voice_live_bridge.py >> /tmp/voice_live_bridge.log 2>&1 &
    sleep 1
}

case "$1" in
    solo)
        # クリスタル＋ロドリン（通常モード）
        rm -f /dev/shm/chrome_audio_active.flag
        start_voice
        echo "=== SOLOモード === クリスタル＋ロドリン"
        ;;
    party)
        # 3人会話モード（ノア＋クリスタル＋ロドリン）
        # voice ON（クリスタル応答あり）+ エコーガード
        # chrome_audio_active.flagはecho_guardが管理
        rm -f /dev/shm/chrome_audio_active.flag
        start_voice
        # echo_guard起動
        pkill -9 -f echo_guard 2>/dev/null
        cd "$PDIR" && PYTHONUNBUFFERED=1 python3 -u echo_guard.py >> /tmp/echo_guard.log 2>&1 &
        sleep 1
        # crystal_to_noah bridge起動
        pkill -9 -f crystal_to_noah 2>/dev/null
        cd "$PDIR" && PYTHONUNBUFFERED=1 python3 -u crystal_to_noah.py >> /tmp/crystal_to_noah.log 2>&1 &
        sleep 1
        echo "=== PARTYモード === ノア＋クリスタル＋ロドリン"
        ;;
    noah)
        # ノア＋ロドリンのみ（クリスタルOFF）
        stop_voice
        touch /dev/shm/chrome_audio_active.flag
        # bridgeも止める
        pkill -9 -f crystal_to_noah 2>/dev/null
        pkill -9 -f echo_guard 2>/dev/null
        echo "=== NOAHモード === ノア＋ロドリン"
        ;;
    status)
        vm=$(ps aux | grep voice_mirror | grep python | grep -v grep | wc -l)
        vl=$(ps aux | grep voice_live_bridge | grep python | grep -v grep | wc -l)
        eg=$(ps aux | grep echo_guard | grep python | grep -v grep | wc -l)
        cn=$(ps aux | grep crystal_to_noah | grep python | grep -v grep | wc -l)
        cf=$(test -f /dev/shm/chrome_audio_active.flag && echo "ON" || echo "OFF")
        echo "voice_mirror:      $([ $vm -gt 0 ] && echo UP || echo DOWN)"
        echo "voice_live_bridge:  $([ $vl -gt 0 ] && echo UP || echo DOWN)"
        echo "echo_guard:         $([ $eg -gt 0 ] && echo UP || echo DOWN)"
        echo "crystal_to_noah:    $([ $cn -gt 0 ] && echo UP || echo DOWN)"
        echo "chrome_mute_flag:   $cf"
        ;;
    *)
        echo "使い方: axi_mode.sh [solo|party|noah|status]"
        echo ""
        echo "  solo   — クリスタル＋ロドリン（音声ON、ノアなし）"
        echo "  party  — ノア＋クリスタル＋ロドリン（3人会話）"
        echo "  noah   — ノア＋ロドリン（クリスタルOFF）"
        echo "  status — 現在の状態"
        ;;
esac