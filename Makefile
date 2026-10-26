.PHONY: setup test

setup:
	uv sync --all-groups --python 3.11

test:
	uv run --python 3.11 pytest
