"""Candidate pool coverage report. Read-only, offline, no model, no spend.

For each suite case (examples/suite/manifest.json, files under the Dataset folder) and each
``Test Case N/Evidence Packet`` folder (claim.txt and the packet files only), ingest the PDFs (text pages
only), use the whole claim as the part text, and build candidates. For cases that have recorded review
cards (JSON files with ``cards[].quote``), report how many of those quotes sit inside a candidate.

A quote counts as recovered when the first 80 normalised characters of the quote are found inside the
normalised text of some candidate (letters and digits only, case folded), so line breaks and hyphen joins
do not matter. A quote that is not found in any page text at all is "unlocated" and left out of recall.

Usage: uv run python scripts/candidate_coverage.py [--dataset D] [--results DIR ...] [--cap N]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from proofgraph.review.candidates import DEFAULT_CAP, build_candidates  # noqa: E402
from proofgraph.review.ingest import ingest  # noqa: E402
from proofgraph.review.relate import PageText  # noqa: E402
from proofgraph.review.run import _page_text  # noqa: E402

PREFIX = 80


def _norm(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def _pages(paths: list[Path]) -> list[PageText]:
    out: list[PageText] = []
    for doc in ingest(paths):
        if doc.error:
            continue
        for page in doc.pages:
            if page.kind == "text":
                out.append(PageText(doc.doc_id, page.page, _page_text(page.words)))
    return out


def _recorded(dirs: list[Path]) -> dict[str, list[str]]:
    quotes: dict[str, list[str]] = {}
    for d in dirs:
        for f in sorted(d.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            for card in data.get("cards", []):
                if card.get("quote"):
                    quotes.setdefault(data.get("id", f.stem), []).append(card["quote"])
    return quotes


def _case_rows(dataset: Path, only_suite: bool) -> list[tuple[str, str, list[Path]]]:
    manifest = json.loads((ROOT / "examples/suite/manifest.json").read_text(encoding="utf-8"))
    rows = []
    for case in manifest["cases"]:
        paths = [dataset / f["path"] for f in case["files"]]
        if all(p.exists() for p in paths):
            rows.append((case["id"], case["claim"], paths))
    if not only_suite:
        base = dataset / "Test Cases"
        for folder in sorted(base.glob("Test Case *"), key=lambda p: int(p.name.split()[-1])):
            claim, packet = folder / "claim.txt", folder / "Evidence Packet"
            if claim.is_file() and packet.is_dir():
                files = sorted(f for f in packet.iterdir() if f.suffix.lower() == ".pdf")
                rows.append((f"Test Case {folder.name.split()[-1]}", claim.read_text(encoding="utf-8").strip(), files))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", type=Path, default=Path.home() / "Downloads" / "Dataset")
    ap.add_argument("--results", type=Path, nargs="*", default=[])
    ap.add_argument("--cap", type=int, default=DEFAULT_CAP)
    ap.add_argument("--suite-only", action="store_true")
    args = ap.parse_args()

    recorded = _recorded(args.results)
    sizes: list[int] = []
    kinds: Counter[str] = Counter()
    truncated = hit = total = unlocated = 0
    print(f"{'case':<14}{'N':>4}  {'trunc':<5} {'recall':>8}  kinds")
    for cid, claim, paths in _case_rows(args.dataset, args.suite_only):
        pages = _pages(paths)
        result = build_candidates(claim, pages, args.cap)
        norm_cands = [_norm(c.text) for c in result.candidates]
        norm_pages = [_norm(p.text) for p in pages]
        n_hit = n_all = 0
        for quote in recorded.get(cid, []):
            q = _norm(quote)[:PREFIX]
            if not q or not any(q in t for t in norm_pages):
                unlocated += 1
                continue
            n_all += 1
            n_hit += any(q in t for t in norm_cands)
        c_kinds = Counter(c.kind for c in result.candidates)
        sizes.append(len(result.candidates))
        kinds.update(c_kinds)
        truncated += result.truncated
        hit, total = hit + n_hit, total + n_all
        recall = f"{n_hit}/{n_all}" if n_all else "-"
        print(f"{cid:<14}{len(result.candidates):>4}  {'yes' if result.truncated else 'no':<5} {recall:>8}  "
              f"{dict(c_kinds)} matched={result.total_matched}")
    if not sizes:
        print("no cases found")
        return 0
    print(f"\ncases={len(sizes)} median N={statistics.median(sizes)} truncated={truncated}")
    print(f"unit types: {dict(kinds)}")
    pct = f"{hit / total:.1%}" if total else "n/a"
    print(f"overall recall: {hit}/{total} = {pct} (unlocated quotes excluded: {unlocated})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
