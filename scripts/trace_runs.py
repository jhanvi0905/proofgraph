"""Trace the flag-on gate run: per case, gold against answer, with the graph's reasoning.

  uv run python scripts/trace_runs.py [runs/review-on.jsonl]

Reads the run file and gold (suite files and the eight packs); prints one block per finished case, so it
can be re-run while the eval is still going. Dev tool: it only reads run files and gold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proofgraph.review.packs import load_gold  # noqa: E402

GOLD = Path("/Users/jhanviarora/proofgraph/data/gold")
PACKS = Path("/Users/jhanviarora/proofgraph/data/handoff-2026-10-31/packs")


def gold_path(case: str) -> Path:
    return GOLD / f"{case}.json" if case.startswith("TC") else next(PACKS.glob(f"*/{case}-*"))


def show(case: str, review: dict) -> None:
    gold = load_gold(gold_path(case))
    print(f"\n=== {case}  claim: {gold.claim[:110]}")
    print(f"gold: {[(p.id, p.status) for p in gold.parts]}   answer: {review['status']}")
    for part in review["parts"]:
        info = (review.get("graph") or {}).get("parts", {}).get(part["id"], {})
        mark = "" if any(part["status"] == g.status for g in gold.parts) else "  <-- differs from gold"
        print(f"- {part['id']} {part['status']}{mark}: {part['text'][:90]}")
        print(f"    why: {(part.get('reason') or '')[:200]}")
        if info:
            print(f"    scenario {info['scenario']}, tier {info['tier']}, walk/read agreement {info['agreement']}")
            print(f"    deciding {info['deciding'][:5]}  walk-only {len(info['walk_only'])}  read-only {len(info['read_only'])}")
            print(f"    second reads {info['second_reads']}  rejected {info['rejected']}  paths {len(info['paths'])}")
    stats = (review.get("graph") or {}).get("stats", {})
    if stats:
        print(f"    graph: {stats.get('rules')} rules, {stats.get('entities')} entities over {stats.get('pages')} pages")
    for card in review["cards"][:3]:
        print(f"    card {card['relation']:11} p{card['page']} {card['quote'][:100]!r}")


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "runs/review-on.jsonl")
    for line in path.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            show(row["case"], row["review"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
