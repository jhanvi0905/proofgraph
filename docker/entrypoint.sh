#!/bin/sh
# Container start: put the sample seed on the persistent disk, then serve.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
sh "$ROOT/docker/seed.sh" "$ROOT/examples/samples/seed" "${CACHE_DIR:-cache}"
cd "$ROOT"
exec "$ROOT/.venv/bin/uvicorn" app.server:app --host 0.0.0.0 --port "${PORT:-8000}"
