"""Analyse a flag-on run: how each graph was formed, and where gold evidence fell out of the pipeline.

  uv run python scripts/analyze_run.py runs/review-on-2.jsonl [--gold-clean] [--out results/run2-analysis.md]

Per case: graph size and quality (rules by tier and alignment level, entities, edges by kind, same-as links,
unclear edges, rejections), what the walk and the full read each reached, and, for every gold relation, the funnel
extracted -> walked -> carded -> decisive. A gold relation counts as "in" a stage when some statement there shares at
least half of its words with the gold quote (the scorer's rule). Dev tool: it reads run files, the graph cache and
gold; product code never does.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from report_review import word_overlap  # noqa: E402

from proofgraph.review.packs import load_gold  # noqa: E402

GOLD = Path("/Users/jhanviarora/proofgraph/data/gold")
GOLD_CLEAN = ROOT / "data" / "gold-clean"
PACKS = Path("/Users/jhanviarora/proofgraph/data/handoff-2026-10-31/packs")
HALF = 0.5


def gold_path(case: str, clean: bool) -> Path:
    if clean:
        return GOLD_CLEAN / f"{case}.json"
    return GOLD / f"{case}.json" if case.startswith("TC") else next(PACKS.glob(f"*/{case}-*"))


def find_graph(stats: dict, deciding: list[str]) -> dict | None:
    for f in glob.glob(str(ROOT / "cache" / "graphs" / "*.json")):
        d = json.load(open(f))
        rules = {n["id"] for n in d["nodes"] if n.get("kind") == "rule"}
        ents = sum(n.get("kind") == "entity" for n in d["nodes"])
        if len(rules) == stats["rules"] and ents == stats["entities"] and rules >= set(deciding):
            return d
    return None


def analyse(case: str, review: dict, clean: bool) -> dict:
    gold = load_gold(gold_path(case, clean))
    graph = review["graph"]
    infos = graph["parts"]
    deciding = [i for p in infos.values() for i in p.get("deciding", [])]
    d = find_graph(graph["stats"], deciding)
    out = {"case": case, "gold": [p.status for p in gold.parts], "answer": [p["status"] for p in review["parts"]],
           "overall": review["status"], "stats": graph["stats"], "graph_found": d is not None,
           "scenarios": sorted({p["scenario"] for p in infos.values()}),
           "tiers": sorted({p["tier"] for p in infos.values()}),
           "agreement": [p["agreement"] for p in infos.values()],
           "walk_only": sum(len(p["walk_only"]) for p in infos.values()),
           "read_only": sum(len(p["read_only"]) for p in infos.values()),
           "rejected": dict(sum((Counter(p["rejected"]) for p in infos.values()), Counter())),
           "no_link": [k for k, p in infos.items() if not p["linked"]],
           "no_deciding": [k for k, p in infos.items() if not p["deciding"]]}
    if d is None:
        return out
    nodes = {n["id"]: n for n in d["nodes"]}
    rules = [n for n in d["nodes"] if n.get("kind") == "rule"]
    out["rules_by_tier"] = dict(Counter(n["tier"] for n in rules))
    out["rules_by_level"] = dict(Counter(n["level"] for n in rules))
    out["rules_by_stype"] = dict(Counter(n.get("stype", "rule") for n in rules))
    out["edges"] = dict(Counter(f"{e['kind']}/{e['tier']}" for e in d["edges"]))
    out["same_as"] = dict(Counter(f"{l['kind']}:{l['rule']}" for l in d["graph"].get("same_as", [])))
    out["graph_rejected"] = d["graph"].get("rejected", {})
    walked = {p[-1] for i in infos.values() for p in i["paths"]}
    carded = {c["quote"] for c in review["cards"]}
    funnel = []
    for r in gold.relations:
        hit = max(rules, key=lambda n: word_overlap(r.quote, n["quote"]), default=None)
        ok = hit is not None and word_overlap(r.quote, hit["quote"]) >= HALF
        funnel.append({"relation": r.relation, "page": r.page, "quote": r.quote[:80], "extracted": ok,
                       "tier": hit["tier"] if ok else None, "walked": ok and hit["id"] in walked,
                       "carded": ok and hit["quote"] in carded, "decisive": ok and hit["id"] in deciding})
    out["funnel"] = funnel
    return out


def render(rows: list[dict], title: str) -> str:
    lines = [f"# {title}", "", f"{len(rows)} cases with a graph.", ""]
    f = [x for r in rows for x in r.get("funnel", [])]
    if f:
        n = len(f)
        lines += ["## Where gold evidence fell out of the pipeline", "",
                  "| Stage | Gold relations | Share |", "|---|---|---|"]
        for label, key in (("extracted as a statement", "extracted"), ("reached by the walk", "walked"),
                           ("shown as a card", "carded"), ("decisive", "decisive")):
            k = sum(1 for x in f if x[key])
            lines.append(f"| {label} | {k}/{n} | {k / n:.0%} |")
        lines.append("")
    lines += ["## Per case", "",
              "| Case | Gold | Answer | Scen. | Tier | Rules (tier) | Ents | Walk-only / read-only | No link | No deciding |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {','.join(r['gold'])} | {','.join(r['answer'])} | {','.join(r['scenarios'])} | "
                     f"{','.join(r['tiers'])} | {r['stats']['rules']} {r.get('rules_by_tier', '')} | {r['stats']['entities']} | "
                     f"{r['walk_only']} / {r['read_only']} | {','.join(r['no_link']) or '-'} | {','.join(r['no_deciding']) or '-'} |")
    lines += ["", "## Gold evidence per case (extracted > walked > card > decisive)", ""]
    for r in rows:
        for x in r.get("funnel", []):
            marks = " > ".join(f"{k}{'+' if x[k] else '-'}" for k in ("extracted", "walked", "carded", "decisive"))
            lines.append(f"- {r['case']} {x['relation']} p{x['page']}: {marks} | {x['quote']!r}")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("runs", type=Path)
    ap.add_argument("--gold-clean", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--title", default="Run analysis")
    a = ap.parse_args()
    seen, rows = {}, []
    for line in a.runs.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            seen[r["case"]] = r["review"]
    for case, review in seen.items():
        if review.get("graph"):
            rows.append(analyse(case, review, a.gold_clean))
    text = render(rows, a.title)
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(text)
    json.dump(rows, open(ROOT / "runs" / "analysis-rows.json", "w"), indent=1, default=str)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
