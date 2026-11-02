"""Tabulate cached blind-checker answers by card relation (second-check experiment).

Read-only. Reads the disk cache (one JSON file per model call) and never writes to it, never calls a
model, never touches the network. See docs/council/2026-11-02-second-check-experiment.md.

How a cached answer is tied to a case and a relation. The checker cache holds only the prompt
(quote, statement) and the raw answer; it does not hold the card relation. The relation lives in the
cached ``Relate`` response for the same part: its ``quote`` is the card quote and its ``relation`` is
the card relation. The part text is in the Relate prompt (``CLAIM PART:``). So a row exists only when
BOTH a Relate response and a checker response are cached for the same (quote, part text). The part
text is then matched to a case by finding it inside a suite claim or a pack claim/part. A case with
no such pair is listed as "no data". Nothing is guessed. Checker entries with no Relate partner
(older engines, other flows) are counted as unmapped and are not tabulated.

Usage: uv run python scripts/tabulate_checks.py [--cache-dir D] [--packs-dir D] [--out FILE.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MAIN = Path("/Users/jhanviarora/proofgraph")
OLD = ("TC17", "TC12", "frt-03", "TC40", "frt-07")
ANSWERS = ("entails", "contradicts", "not_mentioned")
RELATIONS = ("supports", "contradicts", "weakens")
# Same pairing as proofgraph/review/check.py (C17). Duplicated so this script has no import risk.
AGREES = {
    "supports": {"entails"},
    "contradicts": {"contradicts"},
    "weakens": {"contradicts", "not_mentioned"},
}
G6_MIN_CASES, G6_MIN_CARDS = 8, 12
_PROMPT = re.compile(r"Passage: (.*)\nStatement: (.*)$", re.S)
_PACK_ID = re.compile(r"^([a-z]+-\d+)")


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold().rstrip(".,;: ")


def load_entries(cache_dir: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(cache_dir.glob("*.json")):
        try:
            entries.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return entries


def _chat_text(response: dict[str, Any]) -> str | None:
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None


def parse_answer(text: str | None) -> str | None:
    """Raw answer from a cached completion, or None when it is not one of the three labels."""
    if not isinstance(text, str):
        return None
    stripped = text.strip()
    if stripped in ANSWERS:
        return stripped
    try:
        value = json.loads(stripped.strip("`").removeprefix("json").strip())
    except ValueError:
        return None
    answer = value.get("answer") if isinstance(value, dict) else None
    return answer if answer in ANSWERS else None


def checker_index(entries: list[dict[str, Any]]) -> tuple[dict[tuple[str, str], str | None], int]:
    """Map (quote, statement) to the raw answer (None = unusable). Also the entry count."""
    index: dict[tuple[str, str], str | None] = {}
    total = 0
    for entry in entries:
        request = entry.get("request", {})
        schema = request.get("response_format", {}).get("json_schema", {}).get("name")
        if not str(entry.get("endpoint", "")).endswith("chat/completions") or schema != "WordingAnswer":
            continue
        total += 1
        match = _PROMPT.search(request["messages"][0]["content"])
        if match:
            index[(match.group(1), match.group(2))] = parse_answer(_chat_text(entry.get("response", {})))
    return index, total


def relate_rows(entries: list[dict[str, Any]]) -> list[dict[str, str]]:
    """One row per cached Relate response: part text, relation, card quote."""
    rows = []
    for entry in entries:
        request = entry.get("request", {})
        if request.get("text", {}).get("format", {}).get("name") != "Relate":
            continue
        prompt = request.get("input")
        if not isinstance(prompt, str) or "CLAIM PART:\n" not in prompt:
            continue
        part = prompt.split("CLAIM PART:\n", 1)[1].split("\n\nPACKET", 1)[0].strip()
        try:
            output = entry["response"]["output"]
            text = next(c["text"] for m in output if m.get("type") == "message" for c in m["content"])
            found = json.loads(text)
        except (KeyError, StopIteration, TypeError, ValueError):
            continue
        rows.append({"part": part, "relation": str(found.get("relation")), "quote": str(found.get("quote", ""))})
    return rows


def load_cases(manifest: Path, packs_dir: Path | None) -> dict[str, dict[str, Any]]:
    """case id -> {kind, split, texts}. ``texts`` are the claim and part texts used for matching."""
    cases: dict[str, dict[str, Any]] = {}
    for case in json.loads(manifest.read_text(encoding="utf-8"))["cases"]:
        cases[case["id"]] = {"kind": "suite", "split": case.get("split", "?"), "texts": [case["claim"]]}
    from proofgraph.review.packs import PACK_SPLIT

    for short, split in PACK_SPLIT.items():
        cases[short] = {"kind": "pack", "split": split.replace("_", ""), "texts": []}
    extra: dict[str, dict[str, Any]] = {}
    if packs_dir is not None and packs_dir.is_dir():
        for path in sorted(packs_dir.glob("*/*/pack.json")):
            try:
                pack = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            m = _PACK_ID.match(str(pack.get("id", "")))
            if m is None:
                continue
            texts = [pack.get("claim", "")] + [p.get("text", "") for p in pack.get("parts", [])]
            if m.group(1) in cases:
                cases[m.group(1)]["texts"] += [t for t in texts if t]
            else:
                extra.setdefault(m.group(1), {"kind": "pack_out_of_scope", "split": "n/a", "texts": []})
                extra[m.group(1)]["texts"] += [t for t in texts if t]
    cases.update(extra)
    return cases


def match_case(part: str, cases: dict[str, dict[str, Any]]) -> list[str]:
    needle = _norm(part)
    if not needle:
        return []
    return [cid for cid, c in cases.items() if any(needle in _norm(t) for t in c["texts"])]


def pool_of(case_id: str, case: dict[str, Any]) -> str:
    if case["kind"] == "pack_out_of_scope":
        return "OUT_OF_SCOPE"
    return "OLD" if case_id in OLD else "UNSEEN"


def build_report(entries: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    index, checker_total = checker_index(entries)
    rows, seen = [], set()
    ambiguous, no_checker = [], []
    for row in relate_rows(entries):
        ident = (row["part"], row["relation"], row["quote"])
        if ident in seen:
            continue
        seen.add(ident)
        hits = match_case(row["part"], cases)
        if row["relation"] == "set_aside":
            continue  # no card, so no check
        if len(hits) != 1:
            ambiguous.append({**row, "cases": hits})
            continue
        if (row["quote"], row["part"]) not in index:
            no_checker.append({**row, "case": hits[0]})
            continue
        answer = index[(row["quote"], row["part"])]
        badge = (
            "unavailable" if answer is None
            else "agrees" if answer in AGREES.get(row["relation"], set()) else "disagrees"
        )
        cid = hits[0]
        rows.append({"case": cid, "pool": pool_of(cid, cases[cid]), "split": cases[cid]["split"],
                     "part": row["part"], "relation": row["relation"], "answer": answer, "check": badge})
    used_prompts = {(row["quote"], row["part"]) for row in relate_rows(entries)}
    unmapped = sum(1 for key in index if key not in used_prompts)
    return {"rows": rows, "ambiguous": ambiguous, "relate_without_checker": no_checker,
            "checker_entries": checker_total, "checker_entries_unmapped": unmapped,
            "pools": pool_tables(rows), "cases": case_summary(rows, cases), "g6": g6(rows)}


def _table(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    table: dict[str, Counter] = {r: Counter() for r in RELATIONS}
    for row in rows:
        table[row["relation"]][row["answer"] or "unusable"] += 1
    return {rel: dict(c) for rel, c in table.items()}


def pool_tables(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for pool in ("OLD", "UNSEEN"):
        sub = [r for r in rows if r["pool"] == pool]
        disagreed = Counter(r["answer"] for r in sub if r["check"] == "disagrees")
        out[pool] = {
            "cards": len(sub), "cases": len({r["case"] for r in sub}), "table": _table(sub),
            "disagrees": sum(disagreed.values()), "disagrees_by_answer": dict(disagreed),
            "heldout_cards": sum(1 for r in sub if r["split"] == "heldout"),
            "dev_cards": sum(1 for r in sub if r["split"] == "dev"),
        }
    return out


def case_summary(rows: list[dict[str, Any]], cases: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    summary = []
    for cid, case in cases.items():
        sub = [r for r in rows if r["case"] == cid]
        summary.append({"case": cid, "pool": pool_of(cid, case), "split": case["split"], "cards": len(sub),
                        "table": _table(sub) if sub else "no data"})
    return summary


def g6(rows: list[dict[str, Any]]) -> dict[str, Any]:
    sub = [r for r in rows if r["pool"] == "UNSEEN" and r["check"] != "not_run"]
    cases = len({r["case"] for r in sub})
    ok = cases >= G6_MIN_CASES and len(sub) >= G6_MIN_CARDS
    return {"unseen_cases_with_check": cases, "unseen_cards_with_check": len(sub),
            "need": f">= {G6_MIN_CASES} cases and >= {G6_MIN_CARDS} cards",
            "status": "OK" if ok else "INCONCLUSIVE"}


def render(report: dict[str, Any]) -> str:
    lines = []
    for pool, data in report["pools"].items():
        lines.append(f"== {pool}: n={data['cards']} cards in {data['cases']} cases "
                     f"(heldout {data['heldout_cards']}, dev {data['dev_cards']}) ==")
        lines.append(f"{'relation':<12}" + "".join(f"{a:>15}" for a in (*ANSWERS, "unusable")))
        for rel in RELATIONS:
            counts = data["table"][rel]
            lines.append(f"{rel:<12}" + "".join(f"{counts.get(a, 0):>15}" for a in (*ANSWERS, "unusable")))
        lines.append(f"disagrees: {data['disagrees']} by raw answer {data['disagrees_by_answer']}")
        lines.append("")
    lines.append("== per case ==")
    for c in report["cases"]:
        body = "no data" if c["table"] == "no data" else json.dumps(
            {k: v for k, v in c["table"].items() if v}, sort_keys=True)
        if c["pool"] == "OUT_OF_SCOPE" and c["table"] == "no data":
            continue
        lines.append(f"{c['case']:<9}{c['pool']:<13}{c['split']:<9}n={c['cards']}  {body}")
    lines.append("")
    lines.append(f"checker entries: {report['checker_entries']}; with no Relate partner (unmapped, not "
                 f"tabulated): {report['checker_entries_unmapped']}")
    lines.append(f"Relate rows matching no single case: {len(report['ambiguous'])}; "
                 f"Relate rows with no cached check: {len(report['relate_without_checker'])}")
    g = report["g6"]
    lines.append(f"G6: {g['unseen_cases_with_check']} unseen cases, {g['unseen_cards_with_check']} unseen cards "
                 f"with a check (need {g['need']}) -> {g['status']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache-dir", type=Path, default=MAIN / "cache")
    parser.add_argument("--packs-dir", type=Path, default=MAIN / "data/handoff-2026-10-31/packs")
    parser.add_argument("--manifest", type=Path, default=ROOT / "examples/suite/manifest.json")
    parser.add_argument("--out", type=Path, default=None, help="optional JSON output path")
    args = parser.parse_args(argv)
    if not args.cache_dir.is_dir():
        print(f"no cache directory at {args.cache_dir}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT))
    report = build_report(load_entries(args.cache_dir), load_cases(args.manifest, args.packs_dir))
    print(render(report))
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
