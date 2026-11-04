# Deploying ProofGraph

The app is one container: `uvicorn app.server:app`, built from the `Dockerfile`. `render.yaml` describes it as a Render web service with a persistent disk.

## Settings

| Variable | What it does |
| --- | --- |
| `MODEL_API_KEY` | Secret. The key for the Meta models. Set it in the host's dashboard, never in the repository. |
| `BASETEN_API_KEY` | Secret. The blind second reader (Muse Spark Open) runs on Baseten. Without it the second read is unavailable and a supported answer passes unchecked, so set it. |
| `MUSE_MODEL`, `CHECKER_MODEL`, `SAM_MODEL`, `BASETEN_BASE_URL` | The model names and the Baseten address. The blueprint pins them to the values the evaluation used; the code defaults are the same. |
| `SPEND_LIMIT_USD` | Cap on model spend. When it is reached the app refuses any call that would be paid for; answers already in the cache (the worked example) still load. |
| `PROOFGRAPH_GRAPH` | `1` runs the evidence graph and shows its review page; empty or `0` runs the original pipeline. |
| `LIVE_RUNS_PER_HOUR` | Live runs (an upload, or a new claim on an uploaded packet) allowed per visitor per hour, 3 by default; `0` turns it off. The worked example is never limited. The visitor is the first `X-Forwarded-For` address. State is in memory, so a restart clears it. |
| `MODEL_CALL_LOG` | `1` prints one `[meta-api]` line per real model call to the host's Logs: time, stage (`read-scan`, `split-claim`, `extract-graph`, `link-entities`, `read-part`, `relate-part`, `label-evidence`, `compare-values`, `blind-reread`, `blind-check`), model name the API returned, token counts and duration. No request text, header or key. Cached results make no call, so they print nothing; a packet that has not been reviewed before shows the full sequence. The blueprint sets it to `1`. |
| `APP_PASSCODE` | Optional. When set, every run asks for it. |
| `CACHE_DIR` | Where the model cache, the spend ledger and saved reviews live. Put it on a persistent disk. |
| `PROOFGRAPH_SAMPLES` | Path to the sample manifest. The image sets it. |
| `WARM_SAMPLES` | `0` skips the first-start warm-up of the sample. |

## The sample packet

`examples/samples/` holds one synthetic packet. On first start the container runs it once in the background (`app/warm.py`) and caches the result on the persistent disk, so afterwards the sample answers from the cache. The first view through the app may add about two cents; later views cost nothing. The warm-up leaves a marker, so a restart does not repeat it; changing the manifest or `PROOFGRAPH_GRAPH` warms again. It costs about $0.1 with the graph off and about $0.5 with it on, respects `SPEND_LIMIT_USD`, and `WARM_SAMPLES=0` skips it. Progress is in `$CACHE_DIR/warm.log`. The first minutes after a deploy are the warm-up: a sample opened before it ends runs live.

It runs on the serving machine because a scanned page's cache key depends on how the platform renders it, so a cache built on another machine would not match. Only synthetic documents belong in the manifest.

## Runs on a visitor's own key

The entrance has a collapsed "Test with your own Meta Model API key" section, so a judge can test their own packet when the demo's spend cap or the per-visitor limit has been reached. The key (and an optional Baseten key for the second reader) is posted as the form fields `meta_api_key` and `baseten_api_key` on `POST /api/review`, `POST /api/review/{id}/ask` and `POST /api/sample/{id}`.

- The key builds a client for that one request (`app/keyed.py`). It is not read from or written to the environment, and it is not part of any cache key, so the cached worked example loads for everyone as before.
- Those runs skip the live-run limit and the spend cap, and add nothing to the spend ledger: the key's owner pays.
- Without a Baseten key the second reader is skipped for that run; the server's `BASETEN_API_KEY` is never used for it.
- The key is never logged, echoed, put in an event, a saved review or an error message; anything a model call raises is stripped of it first. A key Meta rejects ends the run with a plain refusal and saves nothing.
- `APP_PASSCODE`, when set, is still required.
- Behind a proxy, make sure request bodies are not logged. The model-call log (`MODEL_CALL_LOG`) never holds a key.

## Check a running deploy

    uv run python scripts/smoke_deploy.py https://your-service.onrender.com
    uv run python scripts/smoke_deploy.py URL --live-claim "..." --live-file packet.pdf   # a live run, costs spend
