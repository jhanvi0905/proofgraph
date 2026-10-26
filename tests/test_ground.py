"""Quote match and the conflict rule."""

from proofgraph.engine.ground import apply_conflicts, ground
from proofgraph.schema import Case, Fact, FactCheck, Source


def _ground(text: str, quote: str | None, value: object, kind: str = "number"):
    case = Case(
        id="c",
        dataset="freight",
        mode="passage",
        claim="claim",
        sources=[Source(id="s", kind="text", text=text)],
    )
    fact = Fact(
        id="f",
        label="n",
        source_id="s",
        quote=quote,
        value=value,  # type: ignore[arg-type]
        kind=kind,  # type: ignore[arg-type]
    )
    return ground(fact, case)


def _fact(fid: str, value: int, *, entity: str | None, period: str | None, label: str = "revenue"):
    return Fact(
        id=fid,
        label=label,
        source_id="s",
        quote=str(value),
        value=value,
        kind="number",
        entity=entity,
        period=period,
    )


def _checks(*ids: str, status: str = "grounded") -> list[FactCheck]:
    return [
        FactCheck(fact_id=fid, status=status, method="quote", detail="quote match")  # type: ignore[arg-type]
        for fid in ids
    ]


def test_exact_quote_grounds():
    result = _ground("Detention: $75.00/hour after 2 hours free time", "Detention: $75.00/hour after 2 hours free time", 75)
    assert result.status == "grounded"
    assert result.method == "quote"


def test_collapsed_whitespace_still_matches():
    result = _ground("Detention:   $75.00", "Detention: $75.00", 75)
    assert result.status == "grounded"


def test_zero_width_space_is_ignored():
    result = _ground("Deten\u200btion: $75.00", "Detention: $75.00", 75)
    assert result.status == "grounded"


def test_curly_quotes_match_straight_quotes():
    result = _ground("He said \u201chello\u201d", 'He said "hello"', "hello", kind="text")
    assert result.status == "grounded"


def test_dashes_are_normalised():
    result = _ground("pages 10\u201312", "pages 10-12", "10-12", kind="text")
    assert result.status == "grounded"


def test_value_must_appear_in_the_quote():
    result = _ground("Detention: $75.00", "Detention:", 75)
    assert result.status == "ungrounded"
    assert result.detail == "value not in quote"


def test_missing_quote_is_ungrounded():
    result = _ground("Detention: $75.00", "not in the source", 75)
    assert result.status == "ungrounded"


def test_parentheses_negative_value_grounds():
    result = _ground("Cost ( 2,483 )", "( 2,483 )", -2483)
    assert result.status == "grounded"


def test_currency_commas_ground():
    result = _ground("Paid $183,479 today", "$183,479", 183479)
    assert result.status == "grounded"


def test_percent_value_grounds():
    result = _ground("Rate 12.5% flat", "12.5%", 0.125)
    assert result.status == "grounded"


def test_em_dash_grounds_as_zero():
    result = _ground("Operating loss \u2014", "\u2014", 0)
    assert result.status == "grounded"


def test_positive_value_does_not_match_parentheses():
    result = _ground("Cost ( 2,483 )", "( 2,483 )", 2483)
    assert result.status == "ungrounded"


def test_time_string_matches_by_text():
    result = _ground("Arrived: 10:00 Departed: 14:12", "Arrived: 10:00", "10:00", kind="time")
    assert result.status == "grounded"


def test_quote_match_is_case_sensitive():
    result = _ground("Detention: $75.00", "detention: $75.00", 75)
    assert result.status == "ungrounded"


def test_missing_source_is_ungrounded():
    case = Case(
        id="c",
        dataset="freight",
        mode="passage",
        claim="claim",
        sources=[],
    )
    fact = Fact(id="f", label="n", source_id="missing", quote="x", value=1, kind="number")
    assert ground(fact, case).status == "ungrounded"


def test_conflict_when_label_entity_and_period_match():
    facts = [
        _fact("f1", 100, entity="Acme", period="FY2024"),
        _fact("f2", 110, entity="Acme", period="FY2024"),
    ]
    checks = apply_conflicts(facts, _checks("f1", "f2"))
    assert {item.fact_id: item.status for item in checks} == {
        "f1": "conflict",
        "f2": "conflict",
    }


def test_no_conflict_when_entity_differs():
    facts = [
        _fact("f1", 100, entity="Acme", period="FY2024"),
        _fact("f2", 200, entity="Other", period="FY2024"),
    ]
    checks = apply_conflicts(facts, _checks("f1", "f2"))
    assert {item.status for item in checks} == {"grounded"}


def test_no_conflict_when_entity_is_missing():
    facts = [
        _fact("f1", 100, entity=None, period="FY2024"),
        _fact("f2", 110, entity=None, period="FY2024"),
    ]
    blank = [
        _fact("f1", 100, entity="", period="FY2024"),
        _fact("f2", 110, entity="", period="FY2024"),
    ]
    assert {item.status for item in apply_conflicts(facts, _checks("f1", "f2"))} == {"grounded"}
    assert {item.status for item in apply_conflicts(blank, _checks("f1", "f2"))} == {"grounded"}


def test_no_conflict_when_period_is_missing():
    facts = [
        _fact("f1", 100, entity="Acme", period=None),
        _fact("f2", 110, entity="Acme", period=""),
    ]
    checks = apply_conflicts(facts, _checks("f1", "f2"))
    assert {item.status for item in checks} == {"grounded"}


def test_exactly_half_a_percent_does_not_conflict():
    facts = [
        _fact("f1", 995, entity="Acme", period="FY2024"),
        _fact("f2", 1000, entity="Acme", period="FY2024"),
    ]
    checks = apply_conflicts(facts, _checks("f1", "f2"))
    assert {item.status for item in checks} == {"grounded"}


def test_ungrounded_fact_is_not_pulled_into_a_conflict():
    facts = [
        _fact("f1", 100, entity="Acme", period="FY2024"),
        _fact("f2", 110, entity="Acme", period="FY2024"),
    ]
    checks = _checks("f1") + _checks("f2", status="ungrounded")
    result = apply_conflicts(facts, checks)
    assert {item.fact_id: item.status for item in result} == {
        "f1": "grounded",
        "f2": "ungrounded",
    }
