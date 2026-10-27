.PHONY: setup test app

setup:
	uv sync --all-groups --python 3.11

test:
	uv run --python 3.11 pytest

app:
	uv run --python 3.11 streamlit run app/streamlit_app.py
