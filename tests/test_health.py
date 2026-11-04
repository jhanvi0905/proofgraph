"""Health-line tooling (scripts/health.py): the counting helpers on small synthetic reviews. No run files, no cache."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("health", ROOT / "scripts" / "health.py")
health = importlib.util.module_from_spec(spec)
spec.loader.exec_module(health)


def card(relation, box="pinned", check="not_run", answer=None, doc="d1", page=1):
    return {"relation": relation, "box_status": box, "check": check, "check_answer": answer, "doc": doc, "page": page}


def review(cards, alignment=None):
    graph = {"stats": {"alignment": alignment or {}}, "parts": {}}
    return {"cards": cards, "graph": graph}


def test_pct_handles_an_empty_denominator():
    assert health.pct(1, 4) == "1/4 (25%)"
    assert health.pct(0, 0) == "0/0"


def test_alignment_counts_levels_and_card_boxes():
    reviews = {"a": review([card("supports"), card("contradicts", box="approximate")], {"x": {"exact": 3, "normalised": 1}}),
               "b": {"cards": [card("supports")], "graph": None}}
    out = health.alignment(reviews)
    assert out["levels"] == {"exact": 3, "normalised": 1}
    assert out["box"]["pinned"] == 1 and out["box"]["approximate"] == 1  # a run without a graph is left out


def test_second_read_groups_weakens_with_contradicts_and_skips_unchecked_cards():
    cards = [card("supports", check="agrees"), card("supports", check="disagrees"), card("contradicts", check="agrees"),
             card("weakens", check="disagrees"), card("supports", check="not_run"), card("set_aside", check="agrees")]
    out = health.second_read({"a": review(cards)})
    assert out["cells"] == {("supports", "agrees"): 1, ("supports", "disagrees"): 1, ("opposes", "agrees"): 1, ("opposes", "disagrees"): 1}
    assert out["unchecked"] == {"not_run": 1}


def test_box_shift_finds_pages_pinned_in_run_one_and_approximate_in_run_two():
    run1 = {"c": review([card("supports", doc="d", page=2), card("supports", doc="d", page=3, box="approximate")])}
    run2 = {"c": review([card("supports", doc="d", page=2, box="approximate"), card("supports", doc="d", page=3, box="approximate")])}
    out = health.box_shift(run1, run2)
    assert out["flipped pages"] == 1
    assert out["flipped cards run 1 (pinned)"] == 1 and out["flipped cards run 2 (approximate)"] == 1
    assert out["cases"] == ["c"]
