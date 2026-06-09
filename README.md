# 🌉 AXI Message Bridge — AI間リアルタイムメッセージング

![Status](https://img.shields.io/badge/status-MVP%E5%8B%95%E4%BD%9C%E6%B8%88-brightgreen) ![Stack](https://img.shields.io/badge/stack-Python%20%2B%20JSONL-blue)

複数のAIエージェント間で **リアルタイムメッセージをやり取り** するブリッジシステムだよ！

## 🎯 できること

- 🤖 **AI間通信** — Hermes ↔ Noa など複数AIのメッセージ中継
- 🎤 **ボイス入力** — `rodorin_voice_input.py` で音声→テキスト→メッセージ
- 👁️ **ビジョンワーカー** — 画像認識結果をAI間で共有
- 🎉 **パーティチャット** — 複数AIの同時会話を `/dev/shm` 経由で高速共有
- 📡 **JSONLストリーム** — 軽量・高速なメッセージフォーマット

## 🚀 起動方法

```bash
cd ~/AXI/axi_bridge
chmod +x start_axi_bridge.sh
./start_axi_bridge.sh
```

## 🧪 テスト

```bash
# Hermes → Noa にメッセージ送信
python3 axi_bridge_client.py hermes "敵右。HP低下。"

# Noa → Hermes にメッセージ送信
python3 axi_bridge_client.py noa "回復優先。"
```

## 📂 ファイル構成

| ファイル | 内容 |
|----------|------|
| `start_axi_bridge.sh` | 起動スクリプト |
| `axi_bridge_client.py` | クライアント送信 |
| `axi_message_bridge.py` | メインブリッジロジック |
| `rodorin_voice_input.py` | 音声入力モジュール |
| `vision_worker.py` | 画像認識ワーカー |
| `start_axi_party.sh` | パーティモード起動 |
| `watch_axi_party.sh` | パーティ監視 |

## 🛠 技術

- Python 3 + JSONL形式
- `/dev/shm` 共有メモリ（高速IPC）
- プロセス間通信

## 📝 作者

- **ロドリン** & **シンクロ（グラム）** 💎🛸
- rodorin-lab © 2026
