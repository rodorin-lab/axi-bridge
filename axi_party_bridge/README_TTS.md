# AXI TTS Worker

## 起動方法

```bash
cd ~/AXI/axi_party_bridge
./start_tts_worker.sh
```

## 動作

- `/dev/shm/axi_party_bus.jsonl` を監視します。
- 読み上げ対象 speaker:
  - `noa`
  - `chatgpt_noah`
  - `hermes`
- `rodorin` は読み上げません。
- 同じ発言の連続再生を防ぎます。
- 利用可能な TTS が無い場合でも標準出力に発話内容を出します。

## 読み上げ形式

```text
ノア「右から行こう。」
ヘルメス「敵接近。」
```
