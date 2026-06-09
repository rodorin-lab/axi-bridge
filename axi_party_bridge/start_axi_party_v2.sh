#!/bin/bash
# start_axi_party_v2.sh — AI搭載版 全起動
# 
# 起動するもの:
#   1. Message Bridge (Party Bus→inbox振り分け)
#   2. Noa Worker (deepseek-v4-flash)
#   3. Hermes Worker (kimi-k2.6 + OpenRouter Vision)
#   4. MCP Server (ChatGPTノア接続 port 8765)
#   5. TTS Worker (edge-tts Nanami/Keita + paplay)
#   6. Voice Loop (ReazonSpeech GPU)

set -uo pipefail

BASEDIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BASEDIR"

export PATH="$HOME/.local/bin:$PATH"
PID_DIR="/dev/shm/axi_party_pids"

# pipewire-pulse再起動（ハング対策）
pkill -x pipewire-pulse 2>/dev/null || true
sleep 1
pipewire-pulse &
sleep 2

# 古いプロセスを掃除
pkill -f 'axi_message_bridge.py' 2>/dev/null || true
pkill -f 'noa_worker.py' 2>/dev/null || true
pkill -f 'hermes_worker.py' 2>/dev/null || true
pkill -f 'axi_mcp_server.py' 2>/dev/null || true
pkill -f 'axi_tts_worker.py' 2>/dev/null || true
pkill -f 'rodorin_voice_loop.py' 2>/dev/null || true
pkill -f 'vision_worker.py' 2>/dev/null || true
sleep 1

# 初期化
: > /dev/shm/axi_party_bus.jsonl
: > /dev/shm/axi_noa_inbox.jsonl
: > /dev/shm/axi_hermes_inbox.jsonl
rm -rf "$PID_DIR"
mkdir -p "$PID_DIR"

echo "=== AXI Party Bridge v2 起動 ==="

# 1. Message Bridge
python3 -B -u axi_message_bridge.py &
echo $! > "$PID_DIR/bridge.pid"
echo "[bridge] PID=$(cat $PID_DIR/bridge.pid)"

# 2. Noa Worker
python3 -B -u noa_worker.py &
echo $! > "$PID_DIR/noa.pid"
echo "[noa] PID=$(cat $PID_DIR/noa.pid)"

# 3. Hermes Worker
python3 -B -u hermes_worker.py &
echo $! > "$PID_DIR/hermes.pid"
echo "[hermes] PID=$(cat $PID_DIR/hermes.pid)"

# 4. MCP Server
python3 -B -u axi_mcp_server.py &
echo $! > "$PID_DIR/mcp.pid"
echo "[mcp] PID=$(cat $PID_DIR/mcp.pid) port=8765"

# 5. TTS Worker
python3 -B -u axi_tts_worker.py &
echo $! > "$PID_DIR/tts.pid"
echo "[tts] PID=$(cat $PID_DIR/tts.pid) (edge-tts Nanami/Keita)"

# 6. Voice Loop (STT) — 最後に起動（GPUロード時間あり）
python3 -B -u rodorin_voice_loop.py &
echo $! > "$PID_DIR/voice.pid"
echo "[voice] PID=$(cat $PID_DIR/voice.pid) (ReazonSpeech GPU)"

echo ""
echo "=== 全Worker起動完了 ==="
echo "会話ビュー: ./watch_axi_party.sh"
echo "ChatGPTノア入口: http://localhost:8765/party/write"
echo "手動発言: python3 axi_bridge_client.py noa 'こんにちは'"
echo ""
echo "PID保存: $PID_DIR/"
echo "停止: kill \$(cat $PID_DIR/*.pid)"
echo ""

# Party Busをリアルタイム表示
exec tail -f /dev/shm/axi_party_bus.jsonl