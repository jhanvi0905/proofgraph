"""Draw the walked graph for one part of a flag-on run as a self-contained HTML page (Mermaid).

  uv run python scripts/view_graph.py TC12 [p1] [--runs runs/review-on.jsonl]

Shows the claim part, the entities it was linked to, the typed paths the walk took and the statements at the end.
Statements the decision rested on are drawn in green. Edge labels are the link kind and trust tier.
The graph itself is read from `cache/graphs/`: the file whose entity and rule counts match the run is used.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def find_graph(stats: dict, deciding: list[str]) -> dict:
    for path in sorted((ROOT / "cache" / "graphs").glob("*.json")):
        data = json.loads(path.read_text())
        nodes = data["nodes"]
        rules = [n for n in nodes if n.get("kind") == "rule"]
        entities = [n for n in nodes if n.get("kind") == "entity"]
        if len(rules) == stats["rules"] and len(entities) == stats["entities"] and {n["id"] for n in rules} >= set(deciding):
            return data
    raise SystemExit("no cached graph matches this run (rebuilt with other code?)")


def clean(text: str, n: int = 70) -> str:
    return " ".join(str(text).split())[:n].replace('&', 'and').replace('<', '').replace('>', '').replace('"', "'").replace('#', '')


def build(case: str, part: str, row: dict, full: bool = False) -> str:
    review = row["review"]
    info = review["graph"]["parts"][part]
    data = find_graph(review["graph"]["stats"], info["deciding"])
    nodes = {n["id"]: n for n in data["nodes"]}
    edges: dict[frozenset, set[str]] = {}
    for e in data["edges"]:
        edges.setdefault(frozenset((e["source"], e["target"])), set()).add(f"{e['kind']} ({e['tier']})")

    ids: dict[str, str] = {}

    def nid(key: str) -> str:
        return ids.setdefault(key, f"n{len(ids)}")

    text = next(p["text"] for p in review["parts"] if p["id"] == part)
    lines = [f"flowchart {'LR' if len(info['paths']) > 8 and full else 'TD'}", f'  claim["CLAIM {part}: {clean(text, 90)}"]:::claim']
    drawn: set[str] = set()

    def draw(key: str) -> None:
        if key in drawn:
            return
        drawn.add(key)
        n = nodes.get(key, {})
        if n.get("kind") == "rule":
            cls = "decide" if key in info["deciding"] else "rule"
            label = f"{key[-4:]} {n.get('deontic', '')} {clean(n.get('action', ''), 40)}<br/>{clean(n.get('quote', ''), 70)}<br/>p{n.get('page')}"
            lines.append(f'  {nid(key)}["{label}"]:::{cls}')
        else:
            lines.append(f'  {nid(key)}(["{clean(n.get("name", key), 40)}"]):::ent')

    paths = [p for p in info["paths"] if p[-1] in info["deciding"]] if not full else info["paths"]
    used = {n for p in paths for n in p}
    for entity, how in info["linked"].items():
        if entity in used:
            draw(entity)
            lines.append(f"  claim -- {how} --> {nid(entity)}")
    shown = set()
    for path in paths:
        for a, b in zip(path, path[1:]):
            draw(a), draw(b)
            if (a, b) in shown:
                continue
            shown.add((a, b))
            label = " / ".join(sorted(edges.get(frozenset((a, b)), {"?"})))
            lines.append(f"  {nid(a)} -- {html.escape(label)} --> {nid(b)}")
    lines += [
        "  classDef claim fill:#fde68a,stroke:#92400e,color:#1c1917",
        "  classDef ent fill:#e0f2fe,stroke:#0369a1,color:#0c4a6e",
        "  classDef rule fill:#f5f5f4,stroke:#78716c,color:#1c1917",
        "  classDef decide fill:#bbf7d0,stroke:#15803d,stroke-width:3px,color:#14532d",
    ]
    head = (f"{case} {part}: answer {next(p['status'] for p in review['parts'] if p['id'] == part)}, "
            f"scenario {info['scenario']}, tier {info['tier']}, walk/read {info['agreement']}")
    return f"""<!doctype html><meta charset="utf-8"><title>{html.escape(head)}</title>
<body style="font-family:system-ui;margin:16px"><h3>{html.escape(head)}</h3>
<p>Only paths that end at a deciding statement are drawn (use --full for all). Green = statements the decision rested on. Edge labels: link kind (trust tier).</p>
<pre class="mermaid">{chr(10).join(lines)}</pre>
<script type="module">import m from "https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.esm.min.mjs";
m.initialize({{startOnLoad:true,maxTextSize:200000,flowchart:{{htmlLabels:true}}}});</script></body>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("case")
    ap.add_argument("part", nargs="?", default="p1")
    ap.add_argument("--full", action="store_true", help="draw every walked path, not only those ending at deciding statements")
    ap.add_argument("--runs", type=Path, default=ROOT / "runs/review-on.jsonl")
    args = ap.parse_args()
    rows = [json.loads(line) for line in args.runs.read_text().splitlines() if line.strip()]
    row = next((r for r in rows if r["case"] == args.case), None)
    if row is None:
        raise SystemExit(f"{args.case} is not in {args.runs}")
    out = ROOT / "runs" / "graphs" / f"{args.case}-{args.part}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.case, args.part, row, args.full), encoding="utf-8")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
