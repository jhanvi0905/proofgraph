"""Zero-cost replay: what old shape() vs new shape() keep from cached relate_set responses.

Reads the response cache READ ONLY. No model call, no network, no spend.
For each cached relate_set response it prints the cards the old shape (sorted by doc, page) would keep
and the cards the new shape (model order inside a relation) would keep, and flags a quote the cached
blind checker agreed with (entails for supports, contradicts for contradicts) that one drops and the
other keeps. The checker join is by exact (quote, part) from the cached checker requests.

Usage: uv run python scripts/replay_shape.py [cache_dir]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from pydantic import ValidationError

from proofgraph.review.relate import _WORST_FIRST, RelateItem, _norm, shape

DEFAULT_CACHE = Path("/Users/jhanviarora/proofgraph/cache")
_PART = re.compile(r"CLAIM PART:\n(.*?)\n\nPACKET", re.S)
_CHECK = re.compile(r"Passage: (.*)\nStatement: (.*)$", re.S)


def old_shape(items, injection_quote=None, cap=3, per_relation=2):
    """The previous rule: each relation sorted by (doc, page) before the slots are filled."""
    inj = _norm(injection_quote) if injection_quote else ""
    kept = [i for i in items if not (inj and inj in _norm(i.quote))]
    real = [i for i in kept if i.relation != "set_aside" and _norm(i.quote)]
    if not real:
        return [i for i in kept if i.relation == "set_aside"][:1]
    real.sort(key=lambda i: (_WORST_FIRST[i.relation], i.doc, i.page))
    unique, seen = [], set()
    for i in real:
        key = (i.doc, i.page, _norm(i.quote))
        if key not in seen:
            seen.add(key)
            unique.append(i)
    norms = [_norm(i.quote) for i in unique]
    cands = [i for n, i in enumerate(unique) if not any(m != norms[n] and norms[n] in m for m in norms)]
    by = {r: [] for r in _WORST_FIRST}
    for i in cands:
        by[i.relation].append(i)
    chosen = []
    for slot in range(per_relation):
        for r in _WORST_FIRST:
            if len(chosen) < cap and len(by[r]) > slot:
                chosen.append(by[r][slot])
    return sorted(chosen, key=cands.index)


def _text(response: dict) -> str:
    for out in response.get("output", []):
        for part in out.get("content") or []:
            if part.get("type") == "output_text":
                return part.get("text", "")
    return ""


def _items(raw: str):
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None, None
    items = []
    for d in data.get("items", []) if isinstance(data, dict) else []:
        try:
            items.append(RelateItem.model_validate({k: d.get(k) for k in RelateItem.model_fields}))
        except (ValidationError, AttributeError):
            pass
    return items, data.get("injection_quote")


def _checks(cache: Path) -> dict[tuple[str, str], str]:
    out = {}
    for f in cache.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            if not d["endpoint"].startswith("POST /v1/chat"):
                continue
            m = _CHECK.search(d["request"]["messages"][0]["content"])
            label = json.loads(d["response"]["choices"][0]["message"]["content"])["answer"]
        except (OSError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            continue
        if m:
            out[(m.group(1), m.group(2))] = label
    return out


def _agreed(item, part, checks) -> bool:
    label = checks.get((item.quote, part))
    return (item.relation, label) in {("supports", "entails"), ("contradicts", "contradicts")}


def _fmt(i) -> str:
    return f"{i.relation[:5]:5} {i.doc[:8]} p{i.page} {i.quote[:80]!r}"


def main(cache: Path) -> int:
    checks = _checks(cache)
    flagged = total = 0
    for f in sorted(cache.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            sent = json.dumps(d["request"]["text"]["format"].get("name")) + d["request"]["input"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            continue
        if '"RelateSet"' not in sent.split("CLAIM PART")[0][:80] and not sent.startswith('"RelateSet"'):
            continue
        raw = _text(d["response"])
        items, inj = _items(raw)
        m = _PART.search(d["request"]["input"])
        part = m.group(1) if m else ""
        total += 1
        print(f"\n{f.name[:10]} part={part[:60]!r} raw={len(raw)}B")
        if items is None:
            print("  unparseable response (skipped)")
            continue
        old, new = old_shape(items, inj), shape(items, inj)
        print(f"  model listed {len(items)}")
        for tag, got in (("old", old), ("new", new)):
            for i in got:
                print(f"  {tag} {_fmt(i)}")
        for a, b, name in ((old, new, "dropped by new"), (new, old, "dropped by old")):
            for i in a:
                if i not in b and _agreed(i, part, checks):
                    flagged += 1
                    print(f"  FLAG checker-agreed quote {name}: {i.quote[:80]!r}")
    print(f"\n{total} relate_set responses, {len(checks)} cached checker answers, {flagged} flags")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CACHE))
