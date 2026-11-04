"""Evidence stages for every wrong case of a flag-on run (M4 error split). No model call, no spend.

  uv run python scripts/error_split.py [--run review-on-2] [--cache CACHE_DIR]

For each case the run got wrong, counts the gold relations that support, contradict or weaken, and how many of them
were carried by an extracted statement, reached (by the walk, the full read, a card or the decision), shown as a card,
and decisive. Cases whose gold has no evidence quotes show zeros: their cause is read from the traces in
`results/run2-analysis.md`. Dev tool: it reads run files, the graph cache and gold; product code never does.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import health  # noqa: E402
from report_review import load_runs, score_system, word_overlap  # noqa: E402

from proofgraph.review.packs import load_gold  # noqa: E402

HALF = health.HALF


def stages(review: dict, gold, graphs) -> tuple[int, int, int, int, int]:
    g = health.find_graph(review, graphs)
    info = review["graph"]["parts"].values()
    ends = {p[-1] for i in info for p in i["paths"]} | {x for i in info for x in i["read_only"]}
    deciding = {x for i in info for x in i["deciding"]}
    carded = {c["quote"] for c in review["cards"]}
    rules = [(n, d) for n, d in g.nodes(data=True) if d.get("kind") == "rule"]
    n = extracted = reached = card = decisive = 0
    for rel in gold.relations:
        if rel.relation not in ("supports", "contradicts", "weakens"):
            continue
        n += 1
        node, data = max(rules, key=lambda nd: word_overlap(rel.quote, nd[1]["quote"]))
        if word_overlap(rel.quote, data["quote"]) < HALF:
            continue
        extracted += 1
        reached += node in ends or node in deciding or data["quote"] in carded
        card += data["quote"] in carded
        decisive += node in deciding
    return n, extracted, reached, card, decisive


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", default="review-on-2")
    ap.add_argument("--cache", type=Path, default=ROOT / "cache")
    a = ap.parse_args()
    graphs = health.index_graphs(a.cache)
    reviews = health.load_run(a.run)
    golds = {c: load_gold(health.gold_path(c, Path("."), False)) for c in reviews}
    score = score_system(load_runs(ROOT / "runs" / f"{a.run}.jsonl"), list(golds.values()))
    print("| Case | Gold | Answer | Gold relations | Extracted | Reached | Card | Decisive |\n|---|---|---|---|---|---|---|---|")
    for case, review in reviews.items():
        if case in score.correct:
            continue
        n, *rest = stages(review, golds[case], graphs)
        gold = ",".join(p.status for p in golds[case].parts)
        answer = ",".join(p["status"] for p in review["parts"])
        print(f"| {case} | {gold} | {answer} | {n} | " + " | ".join(map(str, rest)) + " |")
    print(f"\n{len(score.correct)} correct, {len(reviews) - len(score.correct)} wrong of {len(reviews)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
