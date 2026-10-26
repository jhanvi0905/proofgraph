"""Schema defaults and fixture validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from proofgraph.schema import Case, ClaimProgram, Fact, Verdict

FIXTURES = Path(__file__).parent / "fixtures"


def test_fact_entity_and_period_default_to_none():
    fact = Fact(id="f", label="rate", source_id="s", kind="number", value=1)
    assert fact.entity is None
    assert fact.period is None


def test_verdict_flags_default_empty_and_independent():
    first = Verdict(case_id="a", verdict="UNRESOLVED")
    second = Verdict(case_id="b", verdict="UNRESOLVED")
    first.flags.append("checker=fallback")
    assert first.reason_codes == []
    assert second.flags == []
    assert first.rounds == 0


def test_checker_fallback_is_not_a_reason_code_field():
    verdict = Verdict(
        case_id="a",
        verdict="UNRESOLVED",
        flags=["checker=fallback"],
    )
    assert verdict.flags == ["checker=fallback"]
    assert "checker=fallback" not in verdict.reason_codes


def test_invalid_fact_kind_is_rejected():
    with pytest.raises(ValidationError):
        Fact(id="f", label="n", source_id="s", kind="money", value=1)


def test_detention_fixture_validates():
    payload = json.loads((FIXTURES / "detention_program.json").read_text())
    case = Case.model_validate(payload["case"])
    program = ClaimProgram.model_validate(payload["program"])
    assert case.id == "detention-001"
    assert program.links[0].expr is not None
    assert "hours_between" in program.links[0].expr


def test_scale_fixture_validates():
    payload = json.loads((FIXTURES / "scale_program.json").read_text())
    stated = ClaimProgram.model_validate(payload["stated"]["program"])
    ambiguous = ClaimProgram.model_validate(payload["ambiguous"]["program"])
    assert stated.facts[0].scale == "thousands"
    assert ambiguous.facts[0].scale is None
    assert stated.links[0].expr == "(f3*1000) == 183479000"
