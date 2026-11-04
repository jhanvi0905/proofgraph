"""Warm the sample packets once, on the machine that serves them, so their first view is already cached.

  python -m app.warm

Runs every sample in PROOFGRAPH_SAMPLES (samples.json) through the review once and leaves a marker in CACHE_DIR, so
a restart does not repeat it. The marker is tied to the manifest and to the graph flag, so changing either warms
again. A seed built on another machine cannot do this job: the cache key of a scanned page's transcription depends on
the rendered pixels, which differ between platforms. A failed run leaves no marker; the next start tries again.
One warm-up costs about $0.1 with the graph off and about $0.5 with it on, and respects SPEND_LIMIT_USD.
Set WARM_SAMPLES=0 to skip it.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path


def marker_for(manifest: Path, cache: Path) -> Path:
    digest = hashlib.sha256(Path(manifest).read_bytes()).hexdigest()[:12]
    return Path(cache) / f"sample-warm-{digest}-{'graph' if os.environ.get('PROOFGRAPH_GRAPH') == '1' else 'plain'}"


def warm(manifest: Path, cache: Path, muse=None) -> int:
    """Run each sample once; returns how many ran, and 0 when already warm or when one failed."""
    manifest, cache = Path(manifest), Path(cache)
    marker = marker_for(manifest, cache)
    if marker.exists():
        return 0
    from proofgraph.review.run import AllDone, default_muse, run_review

    muse = muse if muse is not None else default_muse()
    ran = 0
    for sample in json.loads(manifest.read_text())["samples"]:
        review = None
        for event in run_review(sample["claim"], [manifest.parent / f for f in sample["files"]], muse):
            if isinstance(event, AllDone):
                review = event.result.review
        if review is None or review.status in ("error", "checking"):
            print(f"warm-up: sample {sample['id']} did not finish ({review.status if review else 'no review'}); will retry next start", flush=True)
            return 0
        print(f"warm-up: sample {sample['id']} cached ({review.status})", flush=True)
        ran += 1
    cache.mkdir(parents=True, exist_ok=True)
    marker.write_text("ok\n")
    return ran


def main() -> int:
    manifest = os.environ.get("PROOFGRAPH_SAMPLES", "")
    if os.environ.get("WARM_SAMPLES") == "0" or not manifest or not Path(manifest).is_file():
        return 0
    warm(Path(manifest), Path(os.environ.get("CACHE_DIR") or "cache"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
