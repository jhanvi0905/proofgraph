"""Health lines (M6) for the flag-on runs, from the recorded runs and the graph cache. No model call, no spend.

  uv run python scripts/health.py [--cache CACHE_DIR] [--gold-clean DIR] [--out results/health.md]

Per run: how well statement quotes aligned to the page and how many cards are pinned; what was rejected; the
2x2 agreement of the first read against the blind second reader; walk-versus-read agreement (alone and against
the gold part status); and, for every gold relation, how many hops the walk needs to reach the statement that
carries it. Dev tool: it reads run files, the graph cache and gold; product code never does.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from report_review import word_overlap  # noqa: E402

from proofgraph.review import graph as graph_io  # noqa: E402
from proofgraph.review.packs import load_gold  # noqa: E402
from proofgraph.review.query import _view, paths  # noqa: E402

GOLD = Path("/Users/jhanviarora/proofgraph/data/gold")
PACKS = Path("/Users/jhanviarora/proofgraph/data/handoff-2026-10-31/packs")
HALF = 0.5  # the scorer's rule: a statement carries a gold quote when it shares at least half of its words
RUNS = [("Suite run 1", "review-on", False), ("Suite run 2", "review-on-2", False), ("Clean check", "clean-on", True)]
LEVELS = ("exact", "normalised", "fuzzy", "unmatched")
CARD_FIRST_READ = {"supports": "supports", "contradicts": "opposes", "weakens": "opposes"}


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({k / n:.0%})" if n else "0/0"


def load_run(name: str) -> dict[str, dict]:
    out = {}
    for line in (ROOT / "runs" / f"{name}.jsonl").read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["case"]] = r["review"]
    return out


def gold_path(case: str, clean_dir: Path, clean: bool) -> Path:
    if clean:
        return clean_dir / f"{case}.json"
    return GOLD / f"{case}.json" if case.startswith("TC") else next(PACKS.glob(f"*/{case}-*"))


def index_graphs(cache: Path) -> list[tuple[str, nx.MultiDiGraph]]:
    out = []
    for f in sorted((cache / "graphs").glob("*.json")):
        g = graph_io.load(f.stem, cache)
        if g is not None:
            out.append((f.stem, g))
    return out


def find_graph(review: dict, graphs: list[tuple[str, nx.MultiDiGraph]]) -> nx.MultiDiGraph | None:
    info = review["graph"]
    deciding = {i for p in info["parts"].values() for i in p.get("deciding", [])}
    for _, g in graphs:
        rules = {n for n, d in g.nodes(data=True) if d.get("kind") == "rule"}
        ents = sum(d.get("kind") == "entity" for _, d in g.nodes(data=True))
        if (len(rules) == info["stats"]["rules"] and ents == info["stats"]["entities"]
                and set(g.graph["docs"]) == set(info["docs"]) and rules >= deciding):
            return g
    return None


def alignment(reviews: dict[str, dict]) -> dict:
    lv, box, tier = Counter(), Counter(), Counter()
    for rv in reviews.values():
        if not rv.get("graph"):
            continue
        for d in rv["graph"]["stats"]["alignment"].values():
            lv.update(d)
        box.update(c["box_status"] for c in rv["cards"])
    return {"levels": lv, "box": box, "tier": tier}


def rejections(reviews: dict[str, dict], graphs) -> dict:
    parts, built, found = Counter(), Counter(), 0
    for rv in reviews.values():
        if not rv.get("graph"):
            continue
        for p in rv["graph"]["parts"].values():
            parts.update({k: v for k, v in p["rejected"].items() if v})
        g = find_graph(rv, graphs) if graphs else None
        if g is not None:
            found += 1
            built.update(g.graph.get("rejected", {}))
    return {"parts": parts, "built": built, "graphs_found": found}


def second_read(reviews: dict[str, dict]) -> dict:
    """First read = the comparator's label of a statement (the card relation); second = the blind reader's check."""
    cells, answers, state = Counter(), Counter(), Counter()
    for rv in reviews.values():
        if not rv.get("graph"):
            continue
        for c in rv["cards"]:
            if c["relation"] not in CARD_FIRST_READ:
                continue
            if c["check"] in ("agrees", "disagrees"):
                cells[(CARD_FIRST_READ[c["relation"]], c["check"])] += 1
                answers[(c["relation"], c["check"], c["check_answer"])] += 1
            else:
                state[c["check"]] += 1
    return {"cells": cells, "answers": answers, "unchecked": state}


def agreement(reviews: dict[str, dict], clean: bool, clean_dir: Path) -> tuple[Counter, Counter]:
    flags, vs_gold = Counter(), Counter()
    for case, rv in reviews.items():
        if not rv.get("graph"):
            continue
        gold = {p.id.lower(): p.status for p in load_gold(gold_path(case, clean_dir, clean)).parts}
        answer = {p["id"].lower(): p["status"] for p in rv["parts"]}
        for pid, info in rv["graph"]["parts"].items():
            pid = pid.lower()
            flags[info["agreement"]] += 1
            if pid in gold and pid in answer:
                vs_gold[(info["agreement"], answer[pid] == gold[pid])] += 1
    return flags, vs_gold


def reachability(reviews: dict[str, dict], graphs, clean: bool, clean_dir: Path) -> Counter:
    """For each gold relation (supports, contradicts, weakens): the fewest hops at which the walk reaches the
    statement that carries it, with every entity linked by any part of the claim as a source."""
    out: Counter = Counter()
    for case, rv in reviews.items():
        if not rv.get("graph"):
            continue
        g = find_graph(rv, graphs)
        if g is None:
            out["graph not in cache"] += 1
            continue
        sources = sorted({e for p in rv["graph"]["parts"].values() for e in p["linked"] if e in g})
        rules = [(n, d) for n, d in g.nodes(data=True) if d.get("kind") == "rule"]
        h, _ = _view(g)
        walks = {k: {p.end for p in paths(g, sources, max_hops=k).paths} for k in (1, 2, 3)}
        dist = {}
        for s in sources:
            if s in h:
                dist.update({n: min(d, dist.get(n, 99)) for n, d in nx.single_source_shortest_path_length(h, s).items()})
        for r in load_gold(gold_path(case, clean_dir, clean)).relations:
            if r.relation not in ("supports", "contradicts", "weakens"):
                continue
            out["gold relations"] += 1
            hit = max(rules, key=lambda nd: word_overlap(r.quote, nd[1]["quote"]), default=None)
            if hit is None or word_overlap(r.quote, hit[1]["quote"]) < HALF:
                out["no statement carries it"] += 1
                continue
            sid = hit[0]
            if not sources:
                out["no linked entity"] += 1
                continue
            for k in (1, 2, 3):
                if sid in walks[k]:
                    out[f"walk reaches at {k} hop" + ("s" if k > 1 else "")] += 1
                    break
            else:
                out["connected beyond the walk" if sid in dist else "not connected"] += 1
    return out


def box_shift(run1: dict[str, dict], run2: dict[str, dict]) -> dict:
    """Why the pinned share fell: cards on pages that were pinned in run 1 and approximate in run 2, against the rest."""
    page: dict = {}
    for tag, rv in (("a", run1), ("b", run2)):
        for case, r in rv.items():
            for c in r["cards"]:
                page.setdefault((case, c["doc"], c["page"]), {"a": Counter(), "b": Counter()})[tag][c["box_status"]] += 1
    flipped = [k for k, v in page.items() if v["a"]["pinned"] and v["b"]["approximate"] and not v["b"]["pinned"]]
    out = {"flipped pages": len(flipped), "flipped cards run 1 (pinned)": 0, "flipped cards run 2 (approximate)": 0}
    for k in flipped:
        out["flipped cards run 1 (pinned)"] += page[k]["a"]["pinned"]
        out["flipped cards run 2 (approximate)"] += page[k]["b"]["approximate"]
    out["cases"] = sorted({k[0] for k in flipped})
    return out


def render(data: dict, shift: dict) -> str:
    names = [n for n, _, _ in RUNS]
    L = ["# Health lines (M6)", "",
         "Free analysis of the recorded runs, from `scripts/health.py` (`uv run python scripts/health.py`); no model call. "
         "Runs: suite run 1 (`runs/review-on.jsonl`), suite run 2 after error analysis (`runs/review-on-2.jsonl`), "
         "clean check (`runs/clean-on.jsonl`). Gold is read by the script only. Counts are over the cards and parts the "
         "runs recorded; nothing here is a new measurement of correctness.", "", "## 1. Quote alignment", "",
         "Each statement's quote is aligned to the page text. Pinned means a card's quote was snapped to the word boxes of "
         "a text page (what the review page calls a valid quote); a transcribed scan can only be approximate.", "",
         "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for lv in LEVELS:
        row = [pct(d["align"]["levels"][lv], sum(d["align"]["levels"].values())) for d in data.values()]
        L.append(f"| statements {lv} | " + " | ".join(row) + " |")
    for st in ("pinned", "approximate", "unpinned"):
        row = [pct(d["align"]["box"][st], sum(d["align"]["box"].values())) for d in data.values()]
        L.append(f"| cards {st} | " + " | ".join(row) + " |")
    L += ["", "## 2. Rejected statements", "",
          "Nothing is dropped silently. `unmatched` statements (above) are kept as unclear and never decide. "
          "Rejections recorded per part by the link, compare and full-read steps, and by graph construction "
          "(read from the graph cache, so only graphs found there are counted):", "",
          "| | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for c, label in (("parts", "per part"), ("built", "graph build")):
        for k in sorted({k for d in data.values() for k in d["rej"][c]}):
            L.append(f"| {label}: {k} | " + " | ".join(str(d["rej"][c][k]) for d in data.values()) + " |")
    L.append("| graphs found in cache | " + " | ".join(str(d["rej"]["graphs_found"]) for d in data.values()) + " |")
    L += ["", "## 3. First read against the blind second reader", "",
          "Rows are the first read of a statement (the comparator's label as shown on its card: supports, or opposes = "
          "contradicts or weakens). Columns are whether the second reader, who sees the statement without the first read's "
          "label, agrees. Only statements that were second-read are counted.", ""]
    for name, d in data.items():
        c = d["second"]["cells"]
        L += [f"**{name}**", "", "| First read | Second reader agrees | Second reader disagrees | Agreement |", "|---|---|---|---|"]
        for row in ("supports", "opposes"):
            a, b = c[(row, "agrees")], c[(row, "disagrees")]
            L.append(f"| {row} | {a} | {b} | {pct(a, a + b)} |")
        tot_a = c[("supports", "agrees")] + c[("opposes", "agrees")]
        tot_b = c[("supports", "disagrees")] + c[("opposes", "disagrees")]
        L.append(f"| all | {tot_a} | {tot_b} | {pct(tot_a, tot_a + tot_b)} |")
        un = d["second"]["unchecked"]
        L += ["", f"Not second-read on a card: {sum(un.values())} ({', '.join(f'{k} {v}' for k, v in sorted(un.items())) or 'none'}).", ""]
    L += ["## 4. Walk against the full read", "",
          "The typed walk and an independent full read each pick the statements that bear on a part; the flag compares "
          "the relevant sets. The second table splits the parts by whether the final part status matched the gold part status "
          "(parts are matched by id; a part with no gold counterpart is left out).", "",
          "| Flag | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for fl in ("agree", "partial", "disagree", "both_empty"):
        L.append(f"| {fl} | " + " | ".join(str(d["agree"][0][fl]) for d in data.values()) + " |")
    L += ["", "Parts answered as gold, by flag:", "", "| Flag | " + " | ".join(names) + " |", "|---|" + "---|" * len(names)]
    for fl in ("agree", "partial", "disagree", "both_empty"):
        cells = []
        for d in data.values():
            ok, bad = d["agree"][1][(fl, True)], d["agree"][1][(fl, False)]
            cells.append(pct(ok, ok + bad))
        L.append(f"| {fl} | " + " | ".join(cells) + " |")
    L += ["", "## 5. Reachability at the hops each gold path needs", "",
          "The clean check has no gold relations (its gold is a label only), so it is not shown. For every suite gold relation that supports, contradicts or weakens: the walk is run from every entity any part of the "
          "claim linked, at 1, 2 and 3 hops (3 is what ships; the walk rules, hub brake and unclear edges apply; this is the "
          "walk before ranking and truncation), and the statement is the one sharing at least half of the gold quote's words. Parts are not matched to gold parts, so a "
          "relation counts as reached when the walk for any part reaches it.", "",
          "| | Suite run 2 |", "|---|---|"]
    rows = ["gold relations", "no statement carries it", "no linked entity", "walk reaches at 1 hop", "walk reaches at 2 hops",
            "walk reaches at 3 hops", "connected beyond the walk", "not connected", "graph not in cache"]
    for k in rows:
        L.append(f"| {k} | {data['Suite run 2']['reach'][k]} |")
    L += ["", "## 6. Why the pinned share fell (91% to 79%)", "",
          "Cards on pages that were pinned in run 1 and are approximate in run 2 (same case, document and page):", "",
          "| | |", "|---|---|"]
    for k, v in shift.items():
        L.append(f"| {k} | {', '.join(v) if isinstance(v, list) else v} |")
    L += ["", "Reading the numbers: run 1 had 203 pinned of 222 cards; run 2 has 147 of 186. Counting the flipped cards as "
          "pinned would give 157 of 186 (84%), so about 5 of the 12 points are this one effect and the rest is a change in "
          "which cards are shown (fewer cards on text pages, more on pages that were always scans). The flipped pages are "
          "the ones the text-quality check (Iteration 2 E) sends to transcription, whose boxes can only be approximate "
          "(`proofgraph/review/scan.py`). Scoring the PDF text layers locally with `proofgraph.review.text_quality`: the "
          "TC38, TC45 and TC46 agreement has 3% to 11% of tokens as `(cid:` codes on pages 1 to 5 (limit 2%), and the "
          "fin-08 earnings release and fact sheet have 6% to 9% (the 10-K/A is repaired by the tighter retry, so it stays on "
          "the text path). This is the check working as designed: the text becomes readable and the box becomes approximate."]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache", type=Path, default=ROOT / "cache")
    ap.add_argument("--gold-clean", type=Path, default=ROOT / "data" / "gold-clean")
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "health.md")
    a = ap.parse_args()
    graphs = index_graphs(a.cache)
    data = {}
    for name, run, clean in RUNS:
        rv = load_run(run)
        suite2 = name == "Suite run 2"
        data[name] = {"align": alignment(rv), "rej": rejections(rv, graphs), "second": second_read(rv),
                      "agree": agreement(rv, clean, a.gold_clean),
                      "reach": reachability(rv, graphs, clean, a.gold_clean) if suite2 else Counter()}
    text = render(data, box_shift(load_run("review-on"), load_run("review-on-2")))
    a.out.write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
