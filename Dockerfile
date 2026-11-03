FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
RUN pip install --no-cache-dir uv
WORKDIR /app

# Dependencies first, so a code change does not reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY proofgraph proofgraph
COPY app app
COPY prompts prompts
COPY examples/samples examples/samples
COPY docker docker
RUN uv sync --frozen --no-dev

# CACHE_DIR holds the model cache, the spend ledger and the saved reviews: mount a persistent disk there.
ENV PROOFGRAPH_SAMPLES=/app/examples/samples/samples.json
EXPOSE 8000
CMD ["sh", "/app/docker/entrypoint.sh"]
