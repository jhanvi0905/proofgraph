"""Status rule: cards to part status, parts to overall status."""

import itertools

import pytest

from proofgraph.review.models import Card
from proofgraph.review.status import overall_status, part_status


def card(relation: str, box_status: str = "pinned", cid: str = "c") -> Card:
    return Card(
        id=cid, part="P1", relation=relation, quote="q", doc="d1", page=1,
        box_status=box_status, why="w", check="not_run",
    )


@pytest.mark.parametrize(
    ("cards", "complete", "expected"),
    [
        ([card("contradicts", "unpinned")], True, ("not_found", False)),
        ([card("contradicts", "approximate")], False, ("cannot_tell", False)),
        ([card("contradicts", "approximate"), card("supports")], True, ("supported", False)),
        ([card("contradicts", "unpinned"), card("weakens")], True, ("weakened", False)),
        ([card("contradicts", "pinned")], True, ("contradicted", False)),
        ([card("contradicts", "located")], True, ("contradicted", False)),
        ([card("supports"), card("contradicts", "pinned")], True, ("contradicted", True)),
        ([card("supports", "located"), card("contradicts", "pinned")], True, ("contradicted", False)),
        ([card("supports"), card("contradicts", "located")], True, ("contradicted", False)),
        ([card("weakens"), card("supports")], True, ("weakened", False)),
        ([card("supports")], False, ("supported", False)),
        ([card("set_aside")], True, ("not_found", False)),
        ([card("set_aside")], False, ("cannot_tell", False)),
        ([card("set_aside", "pinned"), card("supports")], True, ("supported", False)),
        ([], True, ("not_found", False)),
        ([], False, ("cannot_tell", False)),
    ],
)
def test_part_status_table(cards, complete, expected):
    assert part_status(cards, receipt_complete=complete) == expected


def test_card_order_does_not_matter():
    cards = [card("supports", cid="a"), card("contradicts", cid="b"), card("weakens", cid="c")]
    results = {part_status(list(p), receipt_complete=True) for p in itertools.permutations(cards)}
    assert results == {("contradicted", True)}


@pytest.mark.parametrize(
    ("parts", "expected"),
    [
        (["supported"], "supported"),
        (["supported", "not_found"], "not_found"),
        (["not_found", "cannot_tell"], "cannot_tell"),
        (["cannot_tell", "weakened", "supported"], "weakened"),
        (["supported", "contradicted", "weakened"], "contradicted"),
        (["weakened", "contradicted"], "contradicted"),
    ],
)
def test_overall_picks_worst_part(parts, expected):
    assert overall_status(parts) == expected
    assert overall_status(list(reversed(parts))) == expected


def test_invalid_input_is_rejected():
    with pytest.raises(ValueError):
        overall_status([])
    for bad in ("Contradicted", "checking", "error", "", None):
        with pytest.raises(ValueError):
            overall_status(["supported", bad])
    bad_card = Card.model_construct(
        id="x", part="P1", relation="agrees", quote="q", doc="d1", page=1,
        box_status="pinned", why="w", check="not_run",
    )
    with pytest.raises(ValueError):
        part_status([bad_card], receipt_complete=True)
    unknown_box = Card.model_construct(
        id="x", part="P1", relation="contradicts", quote="q", doc="d1", page=1,
        box_status="exact", why="w", check="not_run",
    )
    with pytest.raises(ValueError):
        part_status([unknown_box], receipt_complete=True)
    with pytest.raises(ValueError):
        part_status(["supports"], receipt_complete=True)
    with pytest.raises(ValueError):
        part_status([], receipt_complete=None)
