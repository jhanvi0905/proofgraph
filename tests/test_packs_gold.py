"""Gold normaliser (gold-1) for both pools, the suite verdict map and the loader boundary."""

import ast
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from proofgraph.review.packs import (
    PACK_SPLIT,
    Gold,
    load_gold,
    map_part_status,
    suite_verdict,
)

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "proofgraph" / "review"

# (pack id, key the pack uses for part statuses, raw status per part, expected split)
PACKS = [
    ("frt-01", "part_status", ["contradicted", "supported"], "held_out"),
    ("frt-03", "part_status", ["supported"], "dev"),
    ("frt-05", "part_status", ["supported_with_qualifier", "contradicted"], "held_out"),
    ("frt-07", "part_status", ["supported", "contradicted"], "dev"),
    ("fin-07", "part_verdicts", ["supported", "supported"], "held_out"),
    ("fin-08", "part_verdicts", ["contradicted", "contradicted"], "dev"),
    ("leg-02", "part_verdicts", ["supported", "supported"], "held_out"),
    ("aipm-05", "part_status", ["contradicted", "contradicted"], "dev"),
]


def _relation(part: str, relation: str = "supports", **over) -> dict:
    return {
        "part": part, "doc": "D1", "file": "a.pdf", "page": 1, "bbox": [100.4, 200.0, 500.6, 220.0],
        "quote": "Fee | $150 | flat", "relation": relation, "weakener_type": None, "note": "n",
    } | over


def _pack_dir(tmp_path: Path, pack_id: str, key: str, statuses: list[str], relations=None) -> Path:
    ids = [f"P{i + 1}" for i in range(len(statuses))]
    texts = [f"statement {i}" for i in range(len(ids))]
    raw = {
        "id": f"{pack_id}-slug", "domain": "x", "claim": "; ".join(texts),
        "parts": [{"id": i, "text": t} for i, t in zip(ids, texts)],
        "documents": [],
        "gold": {
            "overall": statuses[0] or "supported",
            key: dict(zip(ids, statuses)) if statuses[0] is not None else {},
            "relations": relations if relations is not None else [_relation(i) for i in ids],
            "absence": [],
        },
    }
    out = tmp_path / pack_id
    out.mkdir()
    (out / "pack.json").write_text(json.dumps(raw))
    return out


@pytest.mark.parametrize(("pack_id", "key", "statuses", "split"), PACKS)
def test_pack_gold_validates(tmp_path, pack_id, key, statuses, split):
    gold = load_gold(_pack_dir(tmp_path, pack_id, key, statuses))
    assert isinstance(gold, Gold)
    assert (gold.version, gold.pool, gold.case, gold.split) == ("gold-1", "pack", pack_id, split)
    assert [p.status for p in gold.parts] == [map_part_status(s) for s in statuses]
    assert all(p.origin == "curated" for p in gold.parts)
    assert Gold.model_validate(gold.model_dump(mode="json")) == gold


def test_span_is_found_when_verbatim_and_none_when_paraphrased(tmp_path):
    pack = _pack_dir(tmp_path, "frt-07", "part_status", ["supported", "supported"])
    raw = json.loads((pack / "pack.json").read_text())
    raw["parts"][1]["text"] = "a paraphrase of the second statement"
    (pack / "pack.json").write_text(json.dumps(raw))
    assert [p.span for p in load_gold(pack).parts] == [(0, 11), None]


def test_pack_split_covers_exactly_the_eight_packs():
    assert set(PACK_SPLIT) == {p[0] for p in PACKS}


def test_unknown_pack_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="pack"):
        load_gold(_pack_dir(tmp_path, "zzz-99", "part_status", ["supported"]))


@pytest.mark.parametrize(
    ("raw", "mapped"),
    [
        ("supported", "supported"),
        ("supported_with_qualifier", "weakened"),
        ("supported_with_scope_caveat", "weakened"),
        ("supported_headline_weakened", "weakened"),
        ("supported_weakly", "weakened"),
        ("conditional", "weakened"),
        ("contradicted", "contradicted"),
        ("not_found", "not_found"),
        ("conditional_not_met_in_packet", "cannot_tell"),
        ("cannot_tell", "cannot_tell"),
    ],
)
def test_part_status_map(raw, mapped):
    assert map_part_status(raw) == mapped


def test_unmapped_part_status_raises():
    with pytest.raises(ValueError, match="mystery"):
        map_part_status("mystery")


def test_relation_map_quote_pdf_and_boxes(tmp_path):
    rels = [
        _relation("P1", "conditions", weakener_type="condition"),
        _relation("P1", "irrelevant"),
        _relation("P1", "not_enough", weakener_type="absence"),
        _relation("P1", "contradicts", weakener_type="magnitude"),
    ]
    gold = load_gold(_pack_dir(tmp_path, "frt-07", "part_status", ["contradicted"], rels))
    assert [r.relation for r in gold.relations] == ["weakens", "set_aside", "not_enough", "contradicts"]
    assert gold.relations[0].weakener_type == "condition"
    assert gold.relations[2].weakener_type == "absence"
    first = gold.relations[0]
    assert first.quote == "Fee | $150 | flat"
    assert first.quote_pdf == "Fee $150 flat"
    assert first.boxes == [[100, 200, 501, 220]]
    assert (first.box_origin, first.origin) == ("authored", "curated")


def test_missing_part_status_is_derived_and_flagged(tmp_path):
    rels = [_relation("P1", "supports"), _relation("P1", "conditions", weakener_type="condition")]
    pack = _pack_dir(tmp_path, "frt-07", "part_status", [None], rels)
    gold = load_gold(pack)
    assert [(p.status, p.origin) for p in gold.parts] == [("weakened", "derived")]


def test_conflict_needs_contradicted_part_with_both_sides(tmp_path):
    raw = _suite_raw()
    raw["parts"][0]["status"] = "supported"
    with pytest.raises(ValidationError, match="conflict"):
        Gold.model_validate(raw)
    raw = _suite_raw()
    raw["relations"] = [r for r in raw["relations"] if r["relation"] != "supports"]
    with pytest.raises(ValidationError, match="supports"):
        Gold.model_validate(raw)


def _suite_raw() -> dict:
    claim = "The officer was appointed and the appointment took effect."
    rel = {
        "weakener_type": None, "file": "IHP_Bylaws.pdf", "page": 1, "boxes": None,
        "box_origin": "none", "anchor_ref": "anchor 1", "origin": "external",
    }
    return {
        "version": "gold-1", "case": "TC17", "pool": "suite", "source_dataset": "LegalReasonBench",
        "split": "dev", "claim": claim,
        "reference": {"verdict": "conflicting_evidence", "origin": "curated"},
        "parts": [{"id": "P1", "text": claim, "span": [0, len(claim)], "status": "contradicted",
                   "conflict": True, "origin": "curated"}],
        "relations": [
            rel | {"part": "P1", "relation": "supports", "quote": "was appointed", "quote_pdf": "was appointed"},
            rel | {"part": "P1", "relation": "contradicts", "quote": "unless approved",
                   "quote_pdf": "unless approved", "origin": "relabelled"},
        ],
        "unacceptable": ["Treat shipment as delivery"],
    }


def test_sample_suite_gold_file_validates(tmp_path):
    path = tmp_path / "TC17.json"
    path.write_text(json.dumps(_suite_raw()))
    gold = load_gold(path)
    assert (gold.pool, gold.case, gold.parts[0].conflict) == ("suite", "TC17", True)


@pytest.mark.parametrize(
    ("verdict", "missing", "expected"),
    [
        ("supported", False, ("supported", False)),
        ("contradicted", False, ("contradicted", False)),
        ("conflicting_evidence", False, ("contradicted", True)),
        ("insufficient_evidence", False, ("not_found", False)),
        ("insufficient_evidence", True, ("cannot_tell", False)),
    ],
)
def test_suite_verdict_map(verdict, missing, expected):
    assert suite_verdict(verdict, judgment_missing=missing) == expected


def test_unknown_suite_verdict_raises():
    with pytest.raises(ValueError, match="maybe"):
        suite_verdict("maybe")


def _mentions_gold_loader(source: str) -> bool:
    return any(
        (isinstance(n, ast.Name) and n.id == "load_gold")
        or (isinstance(n, ast.Attribute) and n.attr == "load_gold")
        or (isinstance(n, ast.alias) and n.name.split(".")[-1] == "load_gold")
        for n in ast.walk(ast.parse(source))
    )


def test_boundary_check_detects_loader_use():
    assert _mentions_gold_loader("from proofgraph.review.packs import load_gold")
    assert _mentions_gold_loader("import x\nx.packs.load_gold(p)")
    assert not _mentions_gold_loader("from proofgraph.review.packs import load_pack")


def test_review_run_never_imports_gold_loader():
    run = REVIEW / "run.py"
    if run.exists():
        assert not _mentions_gold_loader(run.read_text())
    others = [p for p in REVIEW.glob("*.py") if p.name != "packs.py"]
    assert [p.name for p in others if _mentions_gold_loader(p.read_text())] == []


@pytest.mark.skipif(not os.environ.get("PROOFGRAPH_PACKS_DIR"), reason="local pack data not set")
def test_real_packs_load():
    root = Path(os.environ["PROOFGRAPH_PACKS_DIR"])
    for pack_id in PACK_SPLIT:
        (pack,) = root.glob(f"*/{pack_id}-*")
        assert load_gold(pack).case == pack_id
