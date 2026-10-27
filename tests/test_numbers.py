"""Number parsing and text normalisation."""

from decimal import Decimal

from proofgraph.engine.numbers import (
    exceeds_half_percent,
    find_numbers,
    iter_literals,
    normalise_text,
    parse_number,
)


def test_parentheses_are_negative():
    assert parse_number("( 2,483 )") == Decimal("-2483")


def test_currency_and_commas():
    assert parse_number("$183,479") == Decimal("183479")


def test_percent_is_a_fraction():
    assert parse_number("12.5%") == Decimal("0.125")


def test_em_dash_is_zero():
    assert parse_number("\u2014") == Decimal(0)


def test_words_are_not_numbers():
    assert parse_number("about") is None
    assert parse_number("10:00") is None


def test_find_numbers_keeps_tokens_separate():
    assert find_numbers("Detention: $75.00/hour after 2 hours free time") == [
        Decimal("75.00"),
        Decimal("2"),
    ]


def test_clock_times_are_not_split_into_numbers():
    assert find_numbers("Arrived: 10:00") == []


def test_large_dollar_literal_place():
    found = iter_literals("Revenue was $183,479,000.")
    assert len(found) == 1
    assert found[0].value == Decimal("183479000")
    assert found[0].unit == Decimal("1000")
    assert found[0].hedged is False


def test_percent_literal_place():
    found = iter_literals("The margin was 18.2%.")
    assert found[0].value == Decimal("0.182")
    assert found[0].unit == Decimal("0.001")


def test_hedge_word_is_attached_to_the_next_literal():
    assert iter_literals("about 18.2")[0].hedged is True
    assert iter_literals("18.2")[0].hedged is False


def test_years_are_skipped_only_without_money_or_percent():
    claim = "In 2024 revenue was $10 and the change was 3%."
    skipped = [item.value for item in iter_literals(claim, skip_years=True)]
    assert Decimal("2024") not in skipped
    assert Decimal("10") in skipped
    assert Decimal("0.03") in skipped


def test_fact_identifiers_are_not_literals():
    values = [item.value for item in iter_literals("(f3*1000) == 183479000")]
    assert values == [Decimal("1000"), Decimal("183479000")]


def test_normalise_strips_invisible_space_and_unifies_quotes():
    raw = "He said \u201c75\u200b\u201d"
    assert normalise_text(raw) == 'He said "75"'
    assert normalise_text("a   b") == "a b"


def test_half_percent_boundary():
    assert exceeds_half_percent(Decimal("995"), Decimal("1000")) is False
    assert exceeds_half_percent(Decimal("100"), Decimal("110")) is True
    assert exceeds_half_percent(Decimal("0"), Decimal("0")) is False
