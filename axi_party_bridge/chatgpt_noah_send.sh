#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ]; then
  echo 'usage: ./chatgpt_noah_send.sh "ヘルメス、状況確認して。"' >&2
  exit 1
fi

text="$*"
json_payload=$(python3 -c 'import json, sys; print(json.dumps({"speaker": "chatgpt_noah", "text": sys.argv[1]}, ensure_ascii=False))' "$text")

curl -sS \
  -X POST "http://127.0.0.1:8765/party/write" \
  -H "Content-Type: application/json; charset=utf-8" \
  --data-binary "$json_payload"
