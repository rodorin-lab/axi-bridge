#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec python3 axi_tts_worker.py
