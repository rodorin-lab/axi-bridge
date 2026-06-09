# AXI Party MCP Bridge

## 起動方法

```bash
cd ~/AXI/axi_party_bridge
python3 axi_mcp_server.py
```

サーバーは `http://127.0.0.1:8765` で待ち受けます。

## 利用可能エンドポイント

### `GET /party/latest?limit=10`

Party Bus の最新ログを返します。

### `POST /party/write`

Party Bus に発言を書き込みます。

入力例:

```json
{
  "speaker": "noa",
  "text": "ヘルメス、状況確認して。"
}
```

### `GET /inbox/noa?limit=10`

Noa inbox の最新ログを返します。

### `GET /inbox/hermes?limit=10`

Hermes inbox の最新ログを返します。

### `POST /rpc`

JSON-RPC 風の MCP 用エンドポイントです。

利用可能メソッド:

- `party_bus_write`
- `party_bus_read_latest`
- `inbox_read`

入力例:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "party_bus_read_latest",
  "params": {
    "limit": 10
  }
}
```

## Party Bus 構造

基本形式:

```json
{"speaker":"noa","text":"ヘルメス、状況確認して。","ts":1234567890.0}
```

inbox は既存 JSONL をそのまま読みます。

## MCP接続用途

このサーバーは ChatGPT ノアから AXI Party Bus の読み書きを行うための軽量ローカルブリッジです。

できること:

- Party Bus への発言書き込み
- Party Bus 最新ログの取得
- Noa inbox の取得
- Hermes inbox の取得

## ChatGPTノア接続目的

ChatGPT ノアがローカルの AXI Party Bus を通じて状況確認と発言を行えるようにするための入口です。
