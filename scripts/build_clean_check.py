"""Clean check (G2, Iteration 2): 30 ContractNLI contract-and-hypothesis pairs never used before.

  uv run python scripts/build_clean_check.py

Mechanical, no model calls, no authored text. From the published `test.json` it keeps the contracts that
are PDFs and are not in the suite's ContractNLI cases (TC37 to TC46), then takes up to 10 pairs per
published label (Entailment, Contradiction, NotMentioned), one pair per contract, in the order of a
fixed hash of "<document id>:<hypothesis id>". The hypothesis is the claim. Gold is the published label
mapped to the suite statuses (Entailment supported, Contradiction contradicted, NotMentioned not_found);
there are no relations, so "gold evidence quoted" is not scored for this slice.

Writes `runs/clean30.json` (the manifest `scripts/eval_review.py --manifest` reads) and one gold-1 file per
case under `data/gold-clean/` (gitignored).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CNLI = Path("/Users/jhanviarora/Downloads/Dataset/ContractNLI/contract-nli")
SUITE_CASES = Path("/Users/jhanviarora/Downloads/Dataset/Test Cases")
USED = [37, 38, 39, 40, 41, 42, 43, 44, 45, 46]
STATUS = {"Entailment": "supported", "Contradiction": "contradicted", "NotMentioned": "not_found"}
PER_LABEL = 10


def used_contracts() -> set[str]:
    names: set[str] = set()
    for n in USED:
        packet = SUITE_CASES / f"Test Case {n}" / "Evidence Packet"
        names |= {p.name for p in packet.iterdir()} if packet.exists() else set()
    return names | {n.split("_", 1)[1] for n in names if n[:2].isdigit() and "_" in n}


def key(doc_id: int, hypothesis: str) -> str:
    return hashlib.sha256(f"{doc_id}:{hypothesis}".encode()).hexdigest()


def select(test: dict, used: set[str], raw: Path) -> list[dict]:
    taken: set[int] = set()
    out: list[dict] = []
    for label in STATUS:
        pool = sorted(
            ((key(d["id"], h), d, h, a) for d in test["documents"] if d["file_name"].lower().endswith(".pdf")
             and d["file_name"] not in used and (raw / d["file_name"]).exists()
             for h, a in d["annotation_sets"][0]["annotations"].items() if a["choice"] == label),
            key=lambda t: t[0])
        n = 0
        for _, d, h, _a in pool:
            if n == PER_LABEL:
                break
            if d["id"] in taken:
                continue
            taken.add(d["id"])
            n += 1
            out.append({"case": f"cnli-{d['id']}-{h}", "claim": test["labels"][h]["hypothesis"], "files": [str(raw / d["file_name"])],
                        "label": label, "status": STATUS[label], "contract": d["file_name"]})
    return out


def gold(row: dict) -> dict:
    claim = row["claim"]
    return {"version": "gold-1", "case": row["case"], "pool": "suite", "source_dataset": "ContractNLI (clean check)",
            "split": "held_out", "claim": claim, "reference": {"verdict": row["status"], "origin": "external_label"},
            "parts": [{"id": "P1", "text": claim, "span": [0, len(claim)], "status": row["status"], "conflict": False,
                       "origin": "derived"}], "relations": []}


def main() -> int:
    test = json.loads((CNLI / "test.json").read_text())
    rows = select(test, used_contracts(), CNLI / "raw")
    (ROOT / "runs").mkdir(exist_ok=True)
    (ROOT / "runs" / "clean30.json").write_text(json.dumps(rows, indent=1))
    out = ROOT / "data" / "gold-clean"
    out.mkdir(parents=True, exist_ok=True)
    for row in rows:
        (out / f"{row['case']}.json").write_text(json.dumps(gold(row), indent=1))
    counts = {s: sum(r["status"] == s for r in rows) for s in STATUS.values()}
    print(f"{len(rows)} pairs {counts}; manifest runs/clean30.json, gold data/gold-clean/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
