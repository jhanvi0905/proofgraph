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
| `WARM_SAMPLES` | `0` skips the first-start warm-up of the sample. |

## The sample packet

`examples/samples/` holds one synthetic packet. On first start the container runs it once in the background (`app/warm.py`) and caches the result on the persistent disk, so afterwards the sample answers from the cache. The first view through the app may add about two cents; later views cost nothing. The warm-up leaves a marker, so a restart does not repeat it; changing the manifest or `PROOFGRAPH_GRAPH` warms again. It costs about $0.1 with the graph off and about $0.5 with it on, respects `SPEND_LIMIT_USD`, and `WARM_SAMPLES=0` skips it. Progress is in `$CACHE_DIR/warm.log`. The first minutes after a deploy are the warm-up: a sample opened before it ends runs live.

It runs on the serving machine because a scanned page's cache key depends on how the platform renders it, so a cache built on another machine would not match. Only synthetic documents belong in the manifest.

## Check a running deploy

    uv run python scripts/smoke_deploy.py https://your-service.onrender.com
    uv run python scripts/smoke_deploy.py URL --live-claim "..." --live-file packet.pdf   # a live run, costs spend
