"""Scorer v0 (R-12): compare review runs to gold and print the numbers the project reports.

Run input: `runs/review-<tag>-<date>.jsonl`, one JSON object per line:
    {"case": "<gold case id>", "review": <Review JSON from proofgraph/review/models.py>}
Each file is one run and gets its own report section. Output goes to `results/report.md` and stdout.
No run files means a non-zero exit with a message, never an empty report.

Gold comes from `--gold` paths (a gold-1 JSON file, a pack directory, or a directory of either);
default `tests/fixtures/gold`. Gold stays out of the product: only this script reads it.

How a case is scored
- A card matches a gold relation when part, relation, page agree and at least half of the gold
  quote's words appear in the card quote. Precision is by card relation, recall by gold relation.
  Gold `not_enough` relations have no card relation, so they are counted and listed, not scored.
- Part status is exact match. A gold part with `conflict: true` passes only when the run part is
  `contradicted` with `conflict: true`.
- Box metrics cover gold relations that have boxes. Hit@0.5: every gold box has a run box with
  IoU >= 0.5. Centre-in-box: every gold box holds the centre of some run box. Both are split by the
  page kind of the matched card; no matched card means kind `unscored` (a miss). Pin rate: the
  matched card is `pinned`, over the same gold relations.
- A gold case with no run line, or a run with no cards, scores zero on everything it owns.
- Every proportion carries its k/n and a Wilson 95% interval. Rows: ALL, per pool, per split,
  per source dataset. Pools are never averaged together.
"""

import argparse
import glob
import json
import math
import re
import sys
from pathlib import Path

from proofgraph.review.models import Card, Review
from proofgraph.review.packs import Gold, GoldRelation, load_gold

Tally = dict[str, tuple[int, int]]
Z = 1.96
WIDE_BELOW = 20
RELATIONS = ("supports", "contradicts", "weakens", "set_aside")
PAGE_KINDS = ("text_layer", "image_only", "image", "unscored")


def wilson(k: int, n: int) -> tuple[float, float] | None:
    """Wilson 95% score interval for k successes in n trials; None when n is 0."""
    if n == 0:
        return None
    p = k / n
    denom = 1 + Z * Z / n
    centre = (p + Z * Z / (2 * n)) / denom
    half = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _floor_pct(x: float) -> float:
    return math.floor(x * 1000 + 1e-9) / 10


def _ceil_pct(x: float) -> float:
    return math.ceil(x * 1000 - 1e-9) / 10


def fmt_proportion(k: int, n: int) -> str:
    """`66.6% (2/3) 95% CI [20.7%, 93.9%]`; point estimate and lower bound round down, upper up."""
    interval = wilson(k, n)
    if interval is None:
        return f"n/a ({k}/{n})"
    lo, hi = interval
    text = f"{_floor_pct(k / n):.1f}% ({k}/{n}) 95% CI [{_floor_pct(lo):.1f}%, {_ceil_pct(hi):.1f}%]"
    return text + (f" wide: n<{WIDE_BELOW}" if n < WIDE_BELOW else "")


def _words(text: str) -> set[str]:
    return set(re.findall(r"\w+", text.lower()))


def word_overlap(gold_quote: str, card_quote: str) -> float:
    """Share of the gold quote's distinct words that appear in the card quote."""
    gold = _words(gold_quote)
    return len(gold & _words(card_quote)) / len(gold) if gold else 0.0


def _matches(card: Card, rel: GoldRelation) -> bool:
    return (card.part == rel.part and card.relation == rel.relation and card.page == rel.page
            and word_overlap(rel.quote_pdf, card.quote) >= 0.5)


def _iou(a: list[int], b: list[int]) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    inter = max(0, w) * max(0, h)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def _centre_in(run_box: list[int], gold_box: list[int]) -> bool:
    cx, cy = (run_box[0] + run_box[2]) / 2, (run_box[1] + run_box[3]) / 2
    return gold_box[0] <= cx <= gold_box[2] and gold_box[1] <= cy <= gold_box[3]


def _add(t: Tally, key: str, hit: bool, n: int = 1) -> None:
    k0, n0 = t.get(key, (0, 0))
    t[key] = (k0 + (n if hit else 0), n0 + n)


def _page_kind(review: Review, card: Card) -> str:
    for doc in review.docs:
        if doc.id == card.doc:
            for page in doc.pages:
                if page.n == card.page:
                    return page.kind
    return "unscored"


def score_case(review: Review | None, gold: Gold) -> Tally:
    """Pure function from (run, gold) to counts of (hits, trials) per metric. None means no run."""
    t: Tally = {}
    cards = review.cards if review else []
    _add(t, "case_has_run", review is not None)

    for card in cards:
        _add(t, f"precision:{card.relation}", any(_matches(card, r) for r in gold.relations if r.part == card.part))

    run_parts = {p.id: p for p in review.parts} if review else {}
    for part in gold.parts:
        got = run_parts.get(part.id)
        if part.conflict:
            ok = got is not None and got.status == "contradicted" and got.conflict
            _add(t, "conflict_pass", ok)
        else:
            ok = got is not None and got.status == part.status
        _add(t, "part_status", ok)

    for rel in gold.relations:
        if rel.relation == "not_enough":
            _add(t, "excluded:not_enough", True)
            continue
        hits = [c for c in cards if _matches(c, rel)]
        _add(t, f"recall:{rel.relation}", bool(hits))
        if not rel.boxes:
            continue
        kind = _page_kind(review, hits[0]) if hits else "unscored"
        run_boxes = [b for c in hits for b in c.boxes]
        _add(t, "pin_rate", any(c.box_status == "pinned" for c in hits))
        _add(t, f"hit50:{kind}", all(any(_iou(rb, gb) >= 0.5 for rb in run_boxes) for gb in rel.boxes))
        _add(t, f"centre:{kind}", all(any(_centre_in(rb, gb) for rb in run_boxes) for gb in rel.boxes))
    return t


def _merge(into: Tally, other: Tally) -> None:
    for key, (k, n) in other.items():
        k0, n0 = into.get(key, (0, 0))
        into[key] = (k0 + k, n0 + n)


def build_rows(runs: dict[str, Review], golds: list[Gold]) -> dict[str, Tally]:
    """ALL plus one row per pool, split and source dataset. Every gold case is scored."""
    rows: dict[str, Tally] = {}
    for gold in golds:
        tally = score_case(runs.get(gold.case), gold)
        for label in ("ALL", f"pool={gold.pool}", f"split={gold.split}", f"dataset={gold.source_dataset}"):
            _merge(rows.setdefault(label, {}), tally)
    return rows


def render(rows: dict[str, Tally], *, missing: list[str], extra: list[str], title: str) -> str:
    out = [f"# {title}", ""]
    out.append(f"Gold cases with no run: {', '.join(sorted(missing)) if missing else 'none'} (each counted as a miss)")
    out.append(f"Run cases with no gold: {', '.join(sorted(extra)) if extra else 'none'} (not scored)")
    for label, t in rows.items():
        out += ["", f"## {label}", ""]
        names = [("case_has_run", "cases with a run")]
        names += [(f"precision:{r}", f"precision, {r}") for r in RELATIONS]
        names += [(f"recall:{r}", f"recall, {r}") for r in RELATIONS]
        names += [("part_status", "part status accuracy"), ("conflict_pass", "conflict pass rule"),
                  ("pin_rate", "pin rate")]
        kinds = sorted({k.split(":")[1] for k in t if k.startswith(("hit50:", "centre:"))})
        names += [(f"hit50:{k}", f"box Hit@0.5, {k} pages") for k in kinds]
        names += [(f"centre:{k}", f"centre-in-box, {k} pages") for k in kinds]
        for key, name in names:
            out.append(f"- {name}: {fmt_proportion(*t.get(key, (0, 0)))}")
        skipped = t.get("excluded:not_enough", (0, 0))[1]
        if skipped:
            out.append(f"- gold not_enough relations not scored (no card relation): {skipped}")
    return "\n".join(out) + "\n"


def load_runs(path: Path) -> dict[str, Review]:
    runs: dict[str, Review] = {}
    for number, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row["case"] in runs:
            raise ValueError(f"{path}:{number}: duplicate case {row['case']!r}")
        runs[row["case"]] = Review.model_validate(row["review"])
    return runs


def load_golds(paths: list[Path]) -> list[Gold]:
    golds: list[Gold] = []
    for path in paths:
        if path.is_file() or (path / "pack.json").exists():
            golds.append(load_gold(path))
        elif path.is_dir():
            golds += load_golds(sorted(path.iterdir()))
        # anything else (README, stray files) is not gold
    return golds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs-glob", default="runs/review-*.jsonl")
    ap.add_argument("--gold", action="append", type=Path, help="gold file or directory; repeatable")
    ap.add_argument("--out", type=Path, default=Path("results/report.md"))
    args = ap.parse_args(argv)

    files = sorted(glob.glob(args.runs_glob))
    if not files:
        print(f"report_review: no run files match {args.runs_glob}", file=sys.stderr)
        return 2
    golds = load_golds([p for p in (args.gold or [Path("tests/fixtures/gold")]) if p.exists()])
    if not golds:
        print("report_review: no gold cases found; pass --gold", file=sys.stderr)
        return 2
    ids = {g.case for g in golds}

    sections = []
    for name in files:
        runs = load_runs(Path(name))
        rows = build_rows(runs, golds)
        sections.append(render(rows, missing=sorted(ids - set(runs)), extra=sorted(set(runs) - ids),
                               title=f"Review run {Path(name).name}"))
    text = "\n".join(sections)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
