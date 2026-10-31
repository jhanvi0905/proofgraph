"""Review JSON contract: statuses, box grid, quotes, conflict flag, doc note."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from proofgraph.review.models import Doc, Review

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def raw() -> dict:
    return json.loads((FIXTURES / "review_tc40.json").read_text())


def test_tc40_fixture_validates(raw):
    review = Review.model_validate(raw)
    assert review.status == "contradicted"
    assert review.driver_part == "P1"
    assert review.model_dump(mode="json") == raw


def test_tc40_fixture_carries_a_conflict_and_a_doc_note(raw):
    review = Review.model_validate(raw)
    part = review.parts[0]
    relations = {c.relation for c in review.cards if c.part == part.id}
    assert part.conflict is True
    assert part.status == "contradicted"
    assert {"supports", "contradicts"} <= relations
    assert review.docs[0].note


@pytest.mark.parametrize("status", ["Contradicted", "refuted", "", None])
def test_invalid_part_status_rejected(raw, status):
    raw["parts"][0]["status"] = status
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_invalid_review_status_rejected(raw):
    raw["status"] = "refuted"
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


@pytest.mark.parametrize(
    "field,value",
    [
        ("relation", "mentions"),
        ("weakener_type", "vibes"),
        ("box_status", "guessed"),
        ("check", "maybe"),
    ],
)
def test_invalid_card_vocabulary_rejected(raw, field, value):
    raw["cards"][0][field] = value
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


@pytest.mark.parametrize(
    "box",
    [
        [-1, 0, 500, 100],
        [0, 0, 1001, 100],
        [0, 0, 500, 1001],
        [0, 1200, 500, 1300],
    ],
)
def test_box_outside_grid_rejected(raw, box):
    raw["cards"][0]["boxes"] = [box]
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


@pytest.mark.parametrize(
    "box", [[0, 0, 500], [0, 0, 500, 100, 5], [500, 0, 100, 100], [0, 100, 500, 100]]
)
def test_malformed_box_rejected(raw, box):
    raw["cards"][0]["boxes"] = [box]
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_box_on_the_grid_edge_accepted(raw):
    raw["cards"][0]["boxes"] = [[0, 0, 1000, 1000]]
    Review.model_validate(raw)


@pytest.mark.parametrize("quote", ["", None])
def test_card_without_quote_rejected(raw, quote):
    raw["cards"][0]["quote"] = quote
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_card_missing_quote_key_rejected(raw):
    del raw["cards"][0]["quote"]
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_part_conflict_defaults_false(raw):
    del raw["parts"][0]["conflict"]
    raw["parts"][0]["status"] = "supported"
    raw["cards"] = [c for c in raw["cards"] if c["relation"] != "contradicts"]
    raw["parts"][0]["card_ids"] = [c["id"] for c in raw["cards"]]
    raw["status"] = "supported"
    assert Review.model_validate(raw).parts[0].conflict is False


def test_conflict_requires_contradicted_part(raw):
    raw["parts"][0]["status"] = "weakened"
    raw["status"] = "weakened"
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_doc_note_defaults_none():
    doc = Doc(id="d1", name="x.pdf", pages=[])
    assert doc.note is None


def test_card_pointing_at_unknown_part_rejected(raw):
    raw["cards"][0]["part"] = "P9"
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_card_pointing_at_unknown_page_rejected(raw):
    raw["cards"][0]["page"] = 99
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_card_pointing_at_unknown_doc_rejected(raw):
    raw["cards"][0]["doc"] = "d9"
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_part_card_ids_must_exist(raw):
    raw["parts"][0]["card_ids"].append("c99")
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_driver_part_must_exist(raw):
    raw["driver_part"] = "P9"
    with pytest.raises(ValidationError):
        Review.model_validate(raw)


def test_validation_does_not_mutate_input(raw):
    before = copy.deepcopy(raw)
    Review.model_validate(raw)
    assert raw == before
