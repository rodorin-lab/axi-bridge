#!/bin/bash
# 3人会話モード切替
# on  → ノアが喋ってる間はクリスタルのマイクをミュート
# off → 通常モード（クリスタル＋ロドリンだけ）

FLAG="/dev/shm/chrome_audio_active.flag"

case "$1" in
    on|1)
        touch "$FLAG"
        echo "3人会話モード ON（ノア喋り中→クリスタルミュート）"
        ;;
    off|0)
        rm -f "$FLAG"
        echo "3人会話モード OFF（通常モード）"
        ;;
    status)
        if [ -f "$FLAG" ]; then
            echo "3人会話モード: ON"
        else
            echo "3人会話モード: OFF"
        fi
        ;;
    *)
        echo "使い方: party_mode.sh [on|off|status]"
        echo "  on   → ノア喋り中にクリスタルのマイクミュート"
        echo "  off  → 通常モード"
        ;;
esac