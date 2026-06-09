#!/bin/bash
# Voice Pipeline ON/OFF切り替え
# ChatGPT通話中はOFFにしてエコー防止

CASE="$1"
VDIR="$HOME/AIOS2/nexus-emu-v3-tauri"
export PATH="/home/rodorin/.local/bin:$PATH"

stop_voice() {
    echo "Voice Pipeline 停止中..."
    pkill -9 -f voice_live_bridge.py 2>/dev/null
    pkill -9 -f voice_mirror.py 2>/dev/null
    # バッファクリア
    echo "" > /dev/shm/nexus_tts.txt
    echo "" > /dev/shm/voice_latest.txt
    rm -f /dev/shm/voice_new.flag 2>/dev/null
    rm -f /dev/shm/nexus_tts_muting.flag 2>/dev/null
    sleep 1
    echo "Voice Pipeline 停止完了（nexus_tts/api_serverは生きてる）"
}

start_voice() {
    echo "Voice Pipeline 起動中..."
    cd "$VDIR"
    PYTHONUNBUFFERED=1 python3 -B voice_mirror.py >> /tmp/voice_mirror.log 2>&1 &
    sleep 1
    PYTHONUNBUFFERED=1 python3 -B -u voice_live_bridge.py >> /tmp/voice_live_bridge.log 2>&1 &
    sleep 1
    echo "Voice Pipeline 起動完了"
}

status() {
    vm=$(ps aux | grep voice_mirror | grep python | grep -v grep | wc -l)
    vl=$(ps aux | grep voice_live_bridge | grep python | grep -v grep | wc -l)
    nt=$(ps aux | grep nexus_tts | grep python | grep -v grep | wc -l)
    as=$(ps aux | grep api_server | grep python | grep -v grep | wc -l)
    echo "voice_mirror:      $([ $vm -gt 0 ] && echo 'UP' || echo 'DOWN')"
    echo "voice_live_bridge:  $([ $vl -gt 0 ] && echo 'UP' || echo 'DOWN')"
    echo "nexus_tts:          $([ $nt -gt 0 ] && echo 'UP' || echo 'DOWN')"
    echo "api_server:         $([ $as -gt 0 ] && echo 'UP' || echo 'DOWN')"
}

case "$CASE" in
    off|stop)
        stop_voice
        ;;
    on|start)
        start_voice
        ;;
    status)
        status
        ;;
    *)
        echo "使い方: voice_switch.sh [on|off|status]"
        echo "  on   → voice_mirror + voice_live_bridge 起動（ローカル通話モード）"
        echo "  off  → voice_mirror + voice_live_bridge 停止（ChatGPT通話モード）"
        echo "  status → 現在の状態確認"
        ;;
esac