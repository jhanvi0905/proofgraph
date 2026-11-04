.PHONY: setup test app

setup:
	uv sync --all-groups --python 3.11

test:
	uv run --python 3.11 pytest

app:
	PROOFGRAPH_GRAPH=1 PROOFGRAPH_SAMPLES=examples/samples/samples.json uv run --python 3.11 uvicorn app.server:app --port 8000
