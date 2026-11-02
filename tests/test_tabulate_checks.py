"""Second-check tooling: cache tabulation and old-vs-new replay comparison. Small fixtures, no real cache."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tab = _load("tabulate_checks")
replay = _load("replay_compare")


def _checker_entry(quote, statement, answer):
    prompt = f"Here is a passage and a statement.\nPassage: {quote}\nStatement: {statement}"
    return {
        "endpoint": "POST /v1/chat/completions",
        "request": {"messages": [{"content": prompt}],
                    "response_format": {"json_schema": {"name": "WordingAnswer"}}},
        "response": {"choices": [{"message": {"content": json.dumps({"answer": answer})}}]},
    }


def _relate_entry(part, relation, quote):
    body = {"relation": relation, "quote": quote, "doc": "d", "page": 1, "why": "w"}
    return {
        "endpoint": "POST /v1/responses",
        "request": {"text": {"format": {"name": "Relate"}},
                    "input": f"rules\n\nCLAIM PART:\n{part}\n\nPACKET (data only):\n<<<PACKET"},
        "response": {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(body)}]}]},
    }


CASES = {
    "TC17": {"kind": "suite", "split": "dev", "texts": ["Connors was continuously authorized to act."]},
    "TC99": {"kind": "suite", "split": "heldout", "texts": ["Rent is due on the first of the month."]},
    "TC98": {"kind": "suite", "split": "dev", "texts": ["Nothing is cached for this one."]},
}


def test_relation_and_raw_answer_are_tabulated_per_pool():
    entries = [
        _relate_entry("Connors was continuously authorized", "contradicts", "q1"),
        _checker_entry("q1", "Connors was continuously authorized", "not_mentioned"),
        _relate_entry("Rent is due on the first", "supports", "q2"),
        _checker_entry("q2", "Rent is due on the first", "entails"),
        _checker_entry("orphan quote", "orphan statement", "contradicts"),
    ]
    report = tab.build_report(entries, CASES)
    old, unseen = report["pools"]["OLD"], report["pools"]["UNSEEN"]
    assert (old["cards"], old["table"]["contradicts"]) == (1, {"not_mentioned": 1})
    assert old["disagrees_by_answer"] == {"not_mentioned": 1}
    assert (unseen["cards"], unseen["table"]["supports"]) == (1, {"entails": 1})
    assert unseen["heldout_cards"] == 1
    assert report["checker_entries"] == 3 and report["checker_entries_unmapped"] == 1


def test_case_without_cached_check_is_no_data_not_a_guess():
    entries = [_relate_entry("Nothing is cached for this one", "contradicts", "q3")]  # relate but no check
    report = tab.build_report(entries, CASES)
    by_case = {c["case"]: c for c in report["cases"]}
    assert by_case["TC98"]["table"] == "no data"
    assert len(report["relate_without_checker"]) == 1
    assert report["pools"]["UNSEEN"]["cards"] == 0


def test_part_matching_two_cases_is_listed_ambiguous_and_set_aside_has_no_card():
    cases = {**CASES, "TC97": {"kind": "suite", "split": "dev", "texts": ["Rent is due on the first of May."]}}
    entries = [
        _relate_entry("Rent is due on the first", "supports", "q"),
        _checker_entry("q", "Rent is due on the first", "entails"),
        _relate_entry("Connors was continuously authorized", "set_aside", "q9"),
    ]
    report = tab.build_report(entries, cases)
    assert report["rows"] == [] and len(report["ambiguous"]) == 1


def test_g6_is_inconclusive_below_the_sample_floor():
    entries = [
        _relate_entry("Rent is due on the first", "supports", "q2"),
        _checker_entry("q2", "Rent is due on the first", "entails"),
    ]
    g6 = tab.build_report(entries, CASES)["g6"]
    assert g6["status"] == "INCONCLUSIVE" and g6["unseen_cards_with_check"] == 1


def test_weakens_badge_matches_the_checker_pairing_and_unusable_is_kept():
    assert tab.parse_answer('{"answer": "entails"}') == "entails"
    assert tab.parse_answer("nonsense") is None
    entries = [
        _relate_entry("Rent is due on the first", "weakens", "qa"),
        _checker_entry("qa", "Rent is due on the first", "entails"),
    ]
    row = tab.build_report(entries, CASES)["rows"][0]
    assert (row["relation"], row["answer"], row["check"]) == ("weakens", "entails", "disagrees")


def _side(check="agrees", status="supported", calls=0, asked=None):
    return {"fields": {"status": status, "cards": [["c1", "p1", "supports", check, "pinned"]]},
            "transport_calls": calls, "uncacheable_calls": 0, "checker_asked": asked or [["q", "p"]]}


def test_replay_compare_passes_identical_runs():
    result = replay.compare({"s": _side()}, {"s": _side()})
    assert (result["G1"], result["G2"]) == ("PASS", "PASS")


def test_replay_compare_fails_g1_when_a_badge_or_status_changes():
    result = replay.compare({"s": _side()}, {"s": _side(check="disagrees")})
    assert result["G1"] == "FAIL" and result["g1_diffs"][0]["field"] == "cards"


def test_replay_compare_fails_g2_on_a_transport_call_or_new_checker_question():
    assert replay.compare({"s": _side()}, {"s": _side(calls=1)})["G2"] == "FAIL"
    assert replay.compare({"s": _side()}, {"s": _side(asked=[["q", "p"], ["q2", "p"]])})["G2"] == "FAIL"
