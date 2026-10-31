"""Blind card check. No network. C17 adjudication, independence and fail-safe."""

import json
import threading
import time
from typing import Any, Mapping

import pytest

from proofgraph.clients.checker import CheckerClient, CheckerError
from proofgraph.config import DEFAULT_CHECKER_MODEL, load_settings
from proofgraph.review.check import check_card, check_cards
from proofgraph.review.models import Card, Part
from proofgraph.review.status import part_status

QUOTE = "cancellation is communicated before 18:00 local time on the day prior."
PART = "Tallgrass is owed a 250 dollar truck-ordered-not-used fee"


def make_card(cid="c1", relation="supports", quote=QUOTE, part="P1", check="not_run") -> Card:
    return Card(
        id=cid, part=part, relation=relation, quote=quote, doc="d1", page=1,
        box_status="pinned", why="w", check=check,
    )


def make_part(pid="P1", text=PART) -> Part:
    return Part(id=pid, text=text, span=(0, len(text)), status="supported")


# C17 (roadmap-sprint.md): supports agrees on entails, contradicts on contradicts,
# weakens is consistent on anything but entails. Chosen for weakens: contradicts and
# not_mentioned agree, entails disagrees. A set_aside card is never checked.
TABLE = [
    ("supports", "entails", "agrees"),
    ("supports", "contradicts", "disagrees"),
    ("supports", "not_mentioned", "disagrees"),
    ("contradicts", "contradicts", "agrees"),
    ("contradicts", "entails", "disagrees"),
    ("contradicts", "not_mentioned", "disagrees"),
    ("weakens", "entails", "disagrees"),
    ("weakens", "contradicts", "agrees"),
    ("weakens", "not_mentioned", "agrees"),
]


@pytest.mark.parametrize(("relation", "answer", "expected"), TABLE)
def test_relation_by_answer_table(relation, answer, expected):
    seen = []

    def checker(quote, statement):
        seen.append((quote, statement))
        return answer

    assert check_card(QUOTE, PART, relation=relation, checker=checker) == expected
    assert seen == [(QUOTE, PART)]


def test_checker_error_and_timeout_are_unavailable():
    def boom(quote, statement):
        raise CheckerError("down")

    def slow(quote, statement):
        raise TimeoutError()

    assert check_card(QUOTE, PART, relation="supports", checker=boom) == "unavailable"
    assert check_card(QUOTE, PART, relation="supports", checker=slow) == "unavailable"


def test_unknown_answer_is_unavailable_not_a_pass():
    assert check_card(QUOTE, PART, relation="supports", checker=lambda q, s: "maybe") == "unavailable"


def test_card_without_quote_is_not_run_and_checker_not_called():
    def checker(quote, statement):
        raise AssertionError("must not be called")

    assert check_card("", PART, relation="supports", checker=checker) == "not_run"
    assert check_card("   ", PART, relation="supports", checker=checker) == "not_run"


def test_transport_receives_only_the_two_strings(tmp_path, monkeypatch):
    class Fake:
        def __init__(self):
            self.bodies = []

        def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
            self.bodies.append(json.loads(json.dumps(body)))
            return {
                "id": "x", "object": "chat.completion", "model": DEFAULT_CHECKER_MODEL,
                "choices": [{"index": 0, "finish_reason": "stop",
                             "message": {"role": "assistant", "content": '{"answer":"entails"}'}}],
            }

    fake = Fake()
    settings = load_settings({"BASETEN_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)})
    client = CheckerClient(settings, transport=fake)
    monkeypatch.setattr("proofgraph.clients.checker.CheckerClient", lambda *a, **k: client)
    card = Card(
        id="card-zz9", part="P1", relation="weakens", weakener_type="exception",
        quote=QUOTE, doc="secret-doc-name.pdf", page=7, box_status="pinned",
        why="proposer-reasoning-xyz", check="not_run",
    )
    other = make_card("card-other", "supports", "OTHER-CARD-QUOTE")
    out = check_cards([card, other], [make_part()])
    assert out[0].check == "disagrees"  # weakens vs entails
    assert len(fake.bodies) == 2
    bodies = {json.dumps(b) for b in fake.bodies}
    first = next(b for b in fake.bodies if QUOTE in json.dumps(b))
    sent = json.dumps(first)
    for leak in ("weakens", "exception", "proposer-reasoning-xyz", "secret-doc-name",
                 "card-zz9", "card-other", "OTHER-CARD-QUOTE", "pinned"):
        assert leak not in sent
    assert QUOTE in sent and PART in sent
    assert len(first["messages"]) == 1
    assert len(bodies) == 2


def test_disagreement_keeps_card_and_status_unchanged():
    cards = [make_card("a", "contradicts"), make_card("b", "supports")]
    before = part_status(cards, receipt_complete=True)
    out = check_cards(cards, [make_part()], checker=lambda q, s: "not_mentioned")
    assert [c.check for c in out] == ["disagrees", "disagrees"]
    assert [c.id for c in out] == ["a", "b"]
    assert [c.relation for c in out] == ["contradicts", "supports"]
    assert part_status(out, receipt_complete=True) == before


def test_unavailable_leaves_status_unchanged():
    def boom(q, s):
        raise CheckerError("down")

    cards = [make_card("a", "weakens"), make_card("b", "supports")]
    before = part_status(cards, receipt_complete=True)
    out = check_cards(cards, [make_part()], checker=boom)
    assert [c.check for c in out] == ["unavailable", "unavailable"]
    assert part_status(out, receipt_complete=True) == before


def test_every_card_checked_except_set_aside():
    calls = []

    def checker(q, s):
        calls.append(q)
        return "entails"

    cards = [make_card("a", "supports", "qa"), make_card("b", "set_aside", "qb"),
             make_card("c", "weakens", "qc")]
    out = check_cards(cards, [make_part()], checker=checker)
    assert sorted(calls) == ["qa", "qc"]
    assert [c.check for c in out] == ["agrees", "not_run", "disagrees"]


def test_one_failure_does_not_stop_others_and_order_is_input_order():
    def checker(q, s):
        if q == "q1":
            raise CheckerError("boom")
        time.sleep(0.05 if q == "q0" else 0)  # finish out of order
        return "entails"

    cards = [make_card(f"c{i}", "supports", f"q{i}") for i in range(6)]
    out = check_cards(cards, [make_part()], checker=checker)
    assert [c.id for c in out] == [f"c{i}" for i in range(6)]
    assert [c.check for c in out] == [
        "agrees", "unavailable", "agrees", "agrees", "agrees", "agrees"]


def test_pool_is_capped_at_four_workers():
    lock = threading.Lock()
    state = {"now": 0, "peak": 0}

    def checker(q, s):
        with lock:
            state["now"] += 1
            state["peak"] = max(state["peak"], state["now"])
        time.sleep(0.03)
        with lock:
            state["now"] -= 1
        return "entails"

    cards = [make_card(f"c{i}", "supports", f"q{i}") for i in range(12)]
    check_cards(cards, [make_part()], checker=checker)
    assert 1 < state["peak"] <= 4


def test_unknown_part_is_unavailable():
    out = check_cards([make_card(part="PX")], [make_part()], checker=lambda q, s: "entails")
    assert out[0].check == "unavailable"


def test_input_cards_are_not_mutated():
    cards = [make_card()]
    check_cards(cards, [make_part()], checker=lambda q, s: "entails")
    assert cards[0].check == "not_run"
