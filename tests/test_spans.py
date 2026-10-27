"""Deterministic span proposals. No model and no calculator."""

import ast
from pathlib import Path

from proofgraph.engine.spans import propose_spans
from proofgraph.schema import Fact

_SPANS = Path(__file__).resolve().parents[1] / "proofgraph" / "engine" / "spans.py"


def test_dollar_span_is_exact_units():
    facts = propose_spans("$40,622,540")
    assert len(facts) == 1
    assert facts[0].quote == "$40,622,540"
    assert facts[0].value == 40622540
    assert facts[0].scale == "units"
    assert facts[0].kind == "number"


def test_currency_word_is_units_unless_a_magnitude_is_stated():
    dollars = propose_spans("75 dollars")
    assert dollars[0].quote == "75 dollars"
    assert dollars[0].value == 75
    assert dollars[0].scale == "units"
    assert dollars[0].kind == "number"

    assert propose_spans("$75")[0].scale == "units"
    assert propose_spans("1 dollar")[0].scale == "units"
    assert propose_spans("75 million dollars")[0].scale == "millions"
    assert propose_spans("$2 million")[0].scale == "millions"
    assert propose_spans("$2 billion")[0].scale == "billions"
    assert propose_spans("4 thousand dollars")[0].scale == "thousands"


def test_magnitude_words_and_parentheticals():
    cases = [
        ("3 million", "3 million", "millions"),
        ("3 millions", "3 millions", "millions"),
        ("(in millions) 3", "(in millions) 3", "millions"),
        ("3 (in millions)", "3 (in millions)", "millions"),
        ("3 thousand", "3 thousand", "thousands"),
        ("3 thousands", "3 thousands", "thousands"),
        ("(in thousands) 3", "(in thousands) 3", "thousands"),
        ("3 billion", "3 billion", "billions"),
        ("3 billions", "3 billions", "billions"),
        ("(in billions) 3", "(in billions) 3", "billions"),
    ]
    for text, quote, scale in cases:
        facts = propose_spans(text)
        assert len(facts) == 1, text
        assert facts[0].quote == quote
        assert facts[0].value == 3
        assert facts[0].scale == scale
        assert facts[0].kind == "number"


def test_percent_sign_and_word():
    signed = propose_spans("12.5%")
    assert signed[0].quote == "12.5%"
    assert signed[0].value == 12.5
    assert signed[0].scale == "percent"
    assert signed[0].kind == "number"

    word = propose_spans("12.5 percent")
    assert word[0].quote == "12.5 percent"
    assert word[0].value == 12.5
    assert word[0].scale == "percent"


def test_unstated_scale_stays_null():
    facts = propose_spans("Revenue was 183,479.")
    assert facts[0].quote == "183,479"
    assert facts[0].value == 183479
    assert facts[0].scale is None
    assert facts[0].kind == "number"


def test_scale_is_not_filled_in_to_make_arithmetic_pass():
    facts = propose_spans("183,479")
    assert facts[0].value == 183479
    assert facts[0].scale is None
    distant = propose_spans("183,479 and the word million appears later")
    assert distant[0].quote == "183,479"
    assert distant[0].scale is None
    separated = propose_spans("(in millions) revenue 183")
    assert separated[0].quote == "183"
    assert separated[0].scale is None


def test_month_and_year_does_not_invent_a_day():
    facts = propose_spans("Filed November 2024.")
    assert len(facts) == 1
    assert facts[0].kind == "date"
    assert facts[0].quote == "November 2024"
    assert facts[0].value == "2024-11"
    assert facts[0].scale is None


def test_stated_day_is_kept():
    facts = propose_spans("November 3, 2024")
    assert len(facts) == 1
    assert facts[0].kind == "date"
    assert facts[0].quote == "November 3, 2024"
    assert facts[0].value == "2024-11-03"


def test_clock_time_is_not_a_number():
    facts = propose_spans("Arrived: 10:00")
    assert len(facts) == 1
    assert facts[0].kind == "time"
    assert facts[0].quote == "10:00"
    assert facts[0].value == "10:00"
    assert facts[0].scale is None


def test_parentheses_are_negative_and_commas_group():
    spaced = propose_spans("Loss ( 2,483 ) today")
    assert spaced[0].quote == "( 2,483 )"
    assert spaced[0].value == -2483
    assert spaced[0].kind == "number"
    assert spaced[0].scale is None

    assert propose_spans("40,622,540")[0].value == 40622540
    assert propose_spans("(40,622)")[0].value == -40622
    signed = propose_spans("($40,622)")
    assert signed[0].quote == "($40,622)"
    assert signed[0].value == -40622
    assert signed[0].scale == "units"


def test_spans_are_facts_in_reading_order():
    facts = propose_spans(
        "On November 2024 at 10:00 the fund paid $40,622,540.",
        source_id="p87",
    )
    assert [fact.kind for fact in facts] == ["date", "time", "number"]
    assert [fact.id for fact in facts] == ["f1", "f2", "f3"]
    assert facts[0].quote == "November 2024"
    assert facts[0].value == "2024-11"
    assert facts[1].quote == "10:00"
    assert facts[1].value == "10:00"
    assert facts[2].quote == "$40,622,540"
    assert facts[2].value == 40622540
    assert facts[2].scale == "units"
    assert all(isinstance(fact, Fact) and fact.source_id == "p87" for fact in facts)


def test_text_without_a_span_is_empty():
    assert propose_spans("No figures here.") == []


def test_proposer_does_not_import_a_model_or_the_calculator():
    tree = ast.parse(_SPANS.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    for name in modules:
        assert "muse" not in name
        assert "openai" not in name
        assert "calc" not in name
        assert name != "proofgraph.propose"
