"""Scorer v0 (R-12): compare review runs to gold and print the numbers the project reports.

Run input: `runs/review-<tag>-<date>.jsonl`, one JSON object per line:
    {"case": "<gold case id>", "review": <Review JSON from proofgraph/review/models.py>}
Each file is one run and gets its own report section. Output goes to `results/report.md` and stdout.
No run files means a non-zero exit with a message, never an empty report.

Gold comes from `--gold` paths (a gold-1 JSON file, a pack directory, or a directory of either);
default `tests/fixtures/gold`. Gold stays out of the product: only this script reads it.

How a case is scored
- Run parts are aligned to gold parts first (ids play no role). Overlap of the run part's claim span
  with the gold span, over the gold span length; each run part goes to the gold part it covers most;
  a gold part is matched when its run parts cover >= 0.5 of it. Gold span None: casefolded,
  whitespace-collapsed text similarity (difflib) >= 0.8. Several run parts on one gold part are
  merged (worst status, cards unioned). Unmatched gold parts are misses in every metric; unmatched
  run parts are listed, not scored. The "alignment" row is the share of gold parts matched.
- A card matches a gold relation when its run part's aligned gold part, relation, page agree and at least half of the gold
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
import difflib
import glob
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from proofgraph.review.models import Card, Part, Review
from proofgraph.review.packs import Gold, GoldPart, GoldRelation, load_gold
from proofgraph.review.status import WORST_FIRST

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


MIN_OVERLAP = 0.5
MIN_TEXT_RATIO = 0.8


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class Match:
    gold: str
    run: tuple[str, ...]
    overlap: float


@dataclass(frozen=True)
class Alignment:
    matches: tuple[Match, ...] = ()
    gold_unmatched: list[str] = field(default_factory=list)
    run_unmatched: list[str] = field(default_factory=list)


def _score(run_part: Part, gold_part: GoldPart) -> tuple[float, int]:
    """(share of the gold part this run part covers, tie-break size); (0, 0) when no overlap."""
    if gold_part.span is not None:
        lo, hi = max(run_part.span[0], gold_part.span[0]), min(run_part.span[1], gold_part.span[1])
        inter = max(0, hi - lo)
        length = gold_part.span[1] - gold_part.span[0]
        return (inter / length, inter) if inter and length else (0.0, 0)
    ratio = difflib.SequenceMatcher(None, _norm(run_part.text), _norm(gold_part.text)).ratio()
    return (ratio, 0) if ratio >= MIN_TEXT_RATIO else (0.0, 0)


def _covered(run_parts: list[Part], gold_part: GoldPart) -> float:
    if gold_part.span is None:
        return max(_score(p, gold_part)[0] for p in run_parts)
    chars = {i for p in run_parts for i in range(*p.span)} & set(range(*gold_part.span))
    return len(chars) / (gold_part.span[1] - gold_part.span[0])


def align(review: Review | None, gold: Gold) -> Alignment:
    """Align run parts to gold parts by claim span (text similarity when the gold span is None).

    Each run part goes to the one gold part it covers most (ties: earlier gold part). A gold part is
    matched when the run parts sent to it cover at least MIN_OVERLAP of it. Ids never matter.
    """
    run_parts = list(review.parts) if review else []
    assigned: dict[str, list[Part]] = {g.id: [] for g in gold.parts}
    for rp in run_parts:
        best = max(((_score(rp, g), -i, g.id) for i, g in enumerate(gold.parts)), default=None)
        if best and best[0][0] > 0:
            assigned[best[2]].append(rp)
    matches, used = [], set()
    for g in gold.parts:
        group = assigned[g.id]
        overlap = _covered(group, g) if group else 0.0
        if overlap >= MIN_OVERLAP:
            matches.append(Match(g.id, tuple(p.id for p in group), overlap))
            used |= {p.id for p in group}
    matched = {m.gold for m in matches}
    return Alignment(tuple(matches), [g.id for g in gold.parts if g.id not in matched],
                     [p.id for p in run_parts if p.id not in used])


def _merge_parts(parts: list[Part]) -> tuple[str, bool]:
    """Status and conflict of several run parts scored as one: the worst status wins."""
    def rank(p: Part) -> int:
        return WORST_FIRST.index(p.status) if p.status in WORST_FIRST else -1  # checking/error: worst

    worst = min(parts, key=rank).status
    return worst, any(p.conflict for p in parts) and worst == "contradicted"


def _matches(card: Card, rel: GoldRelation, aligned: dict[str, str]) -> bool:
    """`aligned` maps run part id to the gold part id it was aligned to; unaligned cards never match."""
    return (aligned.get(card.part) == rel.part and card.relation == rel.relation and card.page == rel.page
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

    alignment = align(review, gold)
    by_id = {p.id: p for p in review.parts} if review else {}
    aligned = {rid: m.gold for m in alignment.matches for rid in m.run}
    _add(t, "alignment", False, 0)
    for part in gold.parts:
        _add(t, "alignment", part.id not in alignment.gold_unmatched)

    # Cards on run parts that aligned to no gold part are listed in the report, not scored.
    for card in cards:
        if card.part in aligned:
            _add(t, f"precision:{card.relation}",
                 any(_matches(card, r, aligned) for r in gold.relations if r.part == aligned[card.part]))

    merged = {m.gold: _merge_parts([by_id[r] for r in m.run]) for m in alignment.matches}
    for part in gold.parts:
        got = merged.get(part.id)
        if part.conflict:
            ok = got is not None and got[0] == "contradicted" and got[1]
            _add(t, "conflict_pass", ok)
        else:
            ok = got is not None and got[0] == part.status
        _add(t, "part_status", ok)

    for rel in gold.relations:
        if rel.relation == "not_enough":
            _add(t, "excluded:not_enough", True)
            continue
        hits = [c for c in cards if _matches(c, rel, aligned)]
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


def alignment_report(runs: dict[str, Review], golds: list[Gold]) -> str:
    """Audit table: per gold case, which run part(s) each gold part was aligned to, and what was left over."""
    lines = ["### Part alignment", "", "| case | gold part | run part(s) | overlap |", "|---|---|---|---|"]
    notes = []
    for gold in sorted(golds, key=lambda g: g.case):
        al = align(runs.get(gold.case), gold)
        by_gold = {m.gold: m for m in al.matches}
        for part in gold.parts:
            m = by_gold.get(part.id)
            run_ids, overlap = (", ".join(m.run), m.overlap) if m else ("unmatched (miss)", 0.0)
            lines.append(f"| {gold.case} | {part.id} | {run_ids} | {overlap:.2f} |")
        if al.run_unmatched:
            notes.append(f"- {gold.case}: run parts not aligned (listed, not scored): {', '.join(al.run_unmatched)}")
    return "\n".join(lines + [""] + notes) + "\n"


def render(rows: dict[str, Tally], *, missing: list[str], extra: list[str], title: str, alignment: str = "") -> str:
    out = [f"# {title}", ""]
    out.append(f"Gold cases with no run: {', '.join(sorted(missing)) if missing else 'none'} (each counted as a miss)")
    out.append(f"Run cases with no gold: {', '.join(sorted(extra)) if extra else 'none'} (not scored)")
    if alignment:
        out += ["", alignment.rstrip("\n")]
    for label, t in rows.items():
        out += ["", f"## {label}", ""]
        names = [("case_has_run", "cases with a run"), ("alignment", "alignment (gold parts matched)")]
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
                               title=f"Review run {Path(name).name}",
                               alignment=alignment_report(runs, golds)))
    text = "\n".join(sections)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
