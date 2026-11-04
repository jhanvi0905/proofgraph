#!/bin/sh
# Container start: warm the sample packet in the background (once per disk), then serve.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="${CACHE_DIR:-cache}"
mkdir -p "$CACHE"
cd "$ROOT"
"$ROOT/.venv/bin/python" -m app.warm >> "$CACHE/warm.log" 2>&1 &
exec "$ROOT/.venv/bin/uvicorn" app.server:app --host 0.0.0.0 --port "${PORT:-8000}"
