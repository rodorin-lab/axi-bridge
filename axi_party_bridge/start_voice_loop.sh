#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
exec python3 rodorin_voice_loop.py "$@"
