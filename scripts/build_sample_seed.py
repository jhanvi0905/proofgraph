"""Build the seed cache for the sample packets, so a fresh deploy answers them without a model call.

  uv run python scripts/build_sample_seed.py

Runs every sample in `examples/samples/samples.json` once with the graph on and once with it off, into a clean
cache directory (`examples/samples/seed/`), then drops the spend ledger and lock files. The container copies the
seed onto its persistent disk at start (`docker/entrypoint.sh`). Needs MODEL_API_KEY; one sample costs about $0.5.
Only synthetic packets belong in the manifest: the seed holds the model's answers about their text.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples" / "samples"
SEED = SAMPLES / "seed"


def main() -> int:
    shutil.rmtree(SEED, ignore_errors=True)
    SEED.mkdir(parents=True)
    os.environ["CACHE_DIR"] = str(SEED)
    os.environ.setdefault("SPEND_LIMIT_USD", "2")
    sys.path.insert(0, str(ROOT))
    from proofgraph.review.run import AllDone, default_muse, run_review

    for sample in json.loads((SAMPLES / "samples.json").read_text())["samples"]:
        for flag in ("1", "0"):
            os.environ["PROOFGRAPH_GRAPH"] = flag
            done = None
            for event in run_review(sample["claim"], [SAMPLES / f for f in sample["files"]], default_muse()):
                if isinstance(event, AllDone):
                    done = event.result.review
            print(f"{sample['id']} graph={'on' if flag == '1' else 'off'}: {done.status if done else 'no review'}")
    for junk in [*SEED.glob("spend.ledger*"), *SEED.glob("*.lock"), *SEED.glob(".*lock*")]:
        junk.unlink()
    files = [f for f in SEED.rglob("*") if f.is_file()]
    print(f"seed: {len(files)} files, {sum(f.stat().st_size for f in files) // 1024} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
