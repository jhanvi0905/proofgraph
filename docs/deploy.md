# Deploying ProofGraph

The app is one container: `uvicorn app.server:app`, built from the `Dockerfile`. `render.yaml` describes it as a Render web service with a persistent disk.

## Settings

| Variable | What it does |
| --- | --- |
| `MODEL_API_KEY` | Secret. The key for the Meta models. Set it in the host's dashboard, never in the repository. |
| `BASETEN_API_KEY` | Secret. The blind second reader (Muse Spark Open) runs on Baseten. Without it the second read is unavailable and a supported answer passes unchecked, so set it. |
| `SPEND_LIMIT_USD` | Cap on model spend. When it is reached the app refuses new requests, including cached ones. |
| `PROOFGRAPH_GRAPH` | `1` runs the evidence graph and shows its review page; empty or `0` runs the original pipeline. |
| `APP_PASSCODE` | Optional. When set, every run asks for it. |
| `CACHE_DIR` | Where the model cache, the spend ledger and saved reviews live. Put it on a persistent disk. |
| `PROOFGRAPH_SAMPLES` | Path to the sample manifest. The image sets it. |

## The sample packet

`examples/samples/` holds one synthetic packet and a seed cache built from one real run of it (`scripts/build_sample_seed.py`). At start the container copies the seed onto the cache disk without overwriting anything, so the sample answers with no model call, in either graph mode. Only synthetic documents belong there.

## Check a running deploy

    uv run python scripts/smoke_deploy.py https://your-service.onrender.com
    uv run python scripts/smoke_deploy.py URL --live-claim "..." --live-file packet.pdf   # a live run, costs spend
