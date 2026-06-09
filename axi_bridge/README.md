# AXI Message Bridge MVP

## 起動方法

```bash
cd ~/AXI/axi_bridge
chmod +x start_axi_bridge.sh
./start_axi_bridge.sh
```

## テスト方法

別ターミナルで以下を実行します。

```bash
python3 axi_bridge_client.py hermes "敵右。HP低下。"
tail -n 5 /dev/shm/axi_noa_inbox.jsonl

python3 axi_bridge_client.py noa "回復優先。"
tail -n 5 /dev/shm/axi_hermes_inbox.jsonl

python3 axi_bridge_client.py rodorin "二人で相談して"
tail -n 5 /dev/shm/axi_noa_inbox.jsonl
```
