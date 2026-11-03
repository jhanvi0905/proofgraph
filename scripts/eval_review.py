"""Review eval runner (M3): run the 29 gate cases and write `runs/review-<arm>.jsonl`.

One line per case: {"case": "<gold id>", "review": <Review JSON>}, the format `report_review.py` reads.
The arm is set by the environment, not a flag here: run once as-is (flag off) and once with
PROOFGRAPH_GRAPH=1. Re-running resumes: cases already in the output file are skipped. A run stops before
the next case once the ledger has grown by `--budget` dollars. The model cache makes repeats free.

  uv run python scripts/eval_review.py --out runs/review-off.jsonl
  PROOFGRAPH_GRAPH=1 uv run python scripts/eval_review.py --out runs/review-on.jsonl

Cases: the 21 suite cases (claim.txt + evidence packet under --dataset) and the eight final-set packs
(pack.json claim + upload/ under --packs). Only this script reads claims and paths; gold stays with the scorer.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proofgraph.review.run import AllDone, default_muse, run_review  # noqa: E402

DATASET = Path("/Users/jhanviarora/Downloads/Dataset")
PACKS = Path("/Users/jhanviarora/proofgraph/data/handoff-2026-10-31/packs")
SUITE = [4, 10, 11, 12, 14, 16, 17, 18, 20, 22, 23, 25, 27, 37, 38, 40, 41, 43, 44, 45, 46]
BAR_PACKS = ["frt-03", "frt-07", "fin-08", "aipm-05", "frt-01", "frt-05", "fin-07", "leg-02"]
KINDS = {".pdf", ".png"}


def suite_case(n: int, dataset: Path) -> tuple[str, str, list[Path]]:
    packet = dataset / "Test Cases" / f"Test Case {n}"
    claim = (packet / "claim.txt").read_text().strip()
    files = sorted(p for p in (packet / "Evidence Packet").iterdir() if p.suffix.lower() in KINDS)
    if not files:  # Word-only packets: the exact full-page PDF conversions of the same names
        converted = dataset / "Format Conversions" / "LegalReasonBench"
        files = [converted / f"{p.stem}.pdf" for p in sorted((packet / "Evidence Packet").glob("*.docx"))]
    return f"TC{n}", claim, files


def pack_case(key: str, packs: Path) -> tuple[str, str, list[Path]]:
    folder = next(packs.glob(f"*/{key}-*"))
    pack = json.loads((folder / "pack.json").read_text())
    return key, pack["claim"], sorted((folder / "upload").iterdir())


def cases(dataset: Path, packs: Path) -> list[tuple[str, str, list[Path]]]:
    return [suite_case(n, dataset) for n in SUITE] + [pack_case(k, packs) for k in BAR_PACKS]


def spent(cache: Path) -> float:
    path = cache / "spend.ledger"
    return float(json.loads(path.read_text())["total_usd"]) if path.exists() else 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--packs", type=Path, default=PACKS)
    ap.add_argument("--only", nargs="*", help="case ids to run, e.g. TC17 frt-03")
    ap.add_argument("--budget", type=float, default=5.0, help="stop once this many dollars were spent this run")
    args = ap.parse_args()

    muse = default_muse()
    cache = muse.cache.directory
    done = set()
    if args.out.exists():
        done = {json.loads(line)["case"] for line in args.out.read_text().splitlines() if line.strip()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    start = spent(cache)

    for case, claim, files in cases(args.dataset, args.packs):
        if case in done or (args.only and case not in args.only):
            continue
        missing = [p for p in files if not p.exists()]
        if missing or not files:
            print(f"{case}: SKIPPED, no files {missing or ''}", file=sys.stderr)
            continue
        if spent(cache) - start >= args.budget:
            print(f"stopped before {case}: budget ${args.budget:.2f} reached", file=sys.stderr)
            return 3
        t = time.time()
        review = None
        for event in run_review(claim, files, muse):
            if isinstance(event, AllDone):
                review = event.result.review
        if review is None:
            print(f"{case}: no review", file=sys.stderr)
            continue
        with args.out.open("a") as fh:
            fh.write(json.dumps({"case": case, "review": review.model_dump(mode="json")}) + "\n")
        print(f"{case}: {review.status:12} {time.time() - t:5.0f}s  spent ${spent(cache) - start:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
