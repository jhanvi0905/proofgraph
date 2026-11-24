# ProofGraph web app. No source document enters the image (data/raw is in .dockerignore): the server fetches them
# by pinned URL and sha256 when it starts (docker/start.sh), as `pgrun fetch` does locally.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app HF_HOME=/app/cache/hf
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv==0.13.0
WORKDIR /app

# Dependencies first, so a code change does not reinstall them. The versions come from uv.lock; torch is the CPU
# build (the lock's Linux torch pulls several GB of CUDA libraries a CPU host never uses).
COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
 && grep -viE '^(nvidia-|cuda-|triton==|torch==)' /tmp/req.txt > /tmp/req-cpu.txt \
 && uv pip install --system --no-cache --index-url https://download.pytorch.org/whl/cpu torch==2.15.0 \
 && uv pip install --system --no-cache -r /tmp/req-cpu.txt

# The pinned embedding model, baked in so the first check does not download it.
RUN python -c "from sentence_transformers import SentenceTransformer as S; S('sentence-transformers/all-MiniLM-L6-v2', device='cpu', revision='1110a243fdf4706b3f48f1d95db1a4f5529b4d41')"

COPY proofgraph proofgraph
COPY app app
COPY data data
COPY docker docker

# PROOFGRAPH_STATE holds saved results and uploads: point it at a persistent disk (render.yaml does).
EXPOSE 8000
CMD ["sh", "/app/docker/start.sh"]
