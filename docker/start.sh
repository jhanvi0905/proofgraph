#!/bin/sh
# Fetch the sources by pinned URL and sha256: the Gillette SEC filing (SEC asks for a contact in SEC_USER_AGENT)
# and public copies of the ISO forms, which are never stored in the repository or the image. A source that cannot
# be fetched, or whose bytes changed, only switches its worked examples off; the app still starts.
python -m proofgraph.cli fetch || true
mkdir -p "${PROOFGRAPH_STATE:-/app/data}"
exec uvicorn app.server:app --host 0.0.0.0 --port "${PORT:-8000}"
