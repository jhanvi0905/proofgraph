"""Verdict rules."""

from proofgraph.engine.combine import combine
from proofgraph.engine.route import run_program
from proofgraph.schema import (
    Case,
    ClaimProgram,
    Fact,
    FactCheck,
    Link,
    LinkResult,
    Source,
)


def _program(facts: list[Fact], links: list[Link], required: list[str], parts: list[str] | None = None):
    return ClaimProgram(
        facts=facts,
        links=links,
        required=required,
        unverifiable_parts=[] if parts is None else parts,
    )


def _grounded(fid: str) -> FactCheck:
    return FactCheck(fact_id=fid, status="grounded", method="quote", detail="quote match")


def test_conflict_required_input_is_unresolved_without_a_round():
    case = Case(
        id="conflict-1",
        dataset="traps",
        mode="passage",
        claim="Revenue was $100.",
        sources=[
            Source(id="a", kind="text", text="Revenue 100"),
            Source(id="b", kind="text", text="Revenue 110"),
        ],
    )
    program = _program(
        [
            Fact(
                id="f1",
                label="revenue",
                source_id="a",
                quote="Revenue 100",
                value=100,
                kind="number",
                entity="Acme",
                period="FY2024",
            ),
            Fact(
                id="f2",
                label="revenue",
                source_id="b",
                quote="Revenue 110",
                value=110,
                kind="number",
                entity="Acme",
                period="FY2024",
            ),
        ],
        [
            Link(
                id="l1",
                kind="compute",
                inputs=["f1", "f2"],
                statement="The two revenue figures agree",
                expr="f1 == f2",
                claim_span="$100",
            )
        ],
        ["l1"],
    )
    verdict = run_program(case, program)
    assert verdict.verdict == "UNRESOLVED"
    assert verdict.reason_codes == ["CONFLICT"]
    assert verdict.rounds == 0
    assert verdict.flags == []
    assert "checker=fallback" not in verdict.reason_codes
    assert {item.fact_id: item.status for item in verdict.fact_checks} == {
        "f1": "conflict",
        "f2": "conflict",
    }


def test_different_entity_does_not_become_conflict():
    case = Case(
        id="no-conflict",
        dataset="traps",
        mode="passage",
        claim="Revenue was $100.",
        sources=[
            Source(id="a", kind="text", text="Revenue 100"),
            Source(id="b", kind="text", text="Revenue 200"),
        ],
    )
    program = _program(
        [
            Fact(
                id="f1",
                label="revenue",
                source_id="a",
                quote="Revenue 100",
                value=100,
                kind="number",
                entity="Acme",
                period="FY2024",
            ),
            Fact(
                id="f2",
                label="revenue",
                source_id="b",
                quote="Revenue 200",
                value=200,
                kind="number",
                entity="Other",
                period="FY2024",
            ),
        ],
        [
            Link(
                id="l1",
                kind="compute",
                inputs=["f1", "f2"],
                statement="The two revenue figures agree",
                expr="f1 == f2",
                claim_span="$100",
            )
        ],
        ["l1"],
    )
    verdict = run_program(case, program)
    assert verdict.verdict == "CONTRADICTED"
    assert "CONFLICT" not in verdict.reason_codes
    assert {item.status for item in verdict.fact_checks} == {"grounded"}


def test_supported_when_required_links_pass():
    program = _program(
        [
            Fact(id="f1", label="a", source_id="s", value=4, kind="number", scale="units", quote="4"),
            Fact(id="f2", label="b", source_id="s", value=6, kind="number", scale="units", quote="6"),
        ],
        [
            Link(
                id="l1",
                kind="compute",
                inputs=["f1", "f2"],
                statement="sum",
                expr="f1 + f2 == 10.00",
                claim_span="$10.00",
            )
        ],
        ["l1"],
    )
    verdict = combine(
        program,
        [_grounded("f1"), _grounded("f2")],
        [LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="expression holds")],
        "The total is $10.00.",
        case_id="ok",
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert verdict.rounds == 0


def test_label_is_the_weakest_deciding_link():
    program = _program(
        [Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10")],
        [
            Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 10.00", claim_span="$10.00"),
            Link(
                id="l2",
                kind="rule",
                inputs=["f1"],
                statement="assumed rule",
                rule_source="assumed",
                claim_span="rule",
            ),
        ],
        ["l1", "l2"],
    )
    verdict = combine(
        program,
        [_grounded("f1")],
        [
            LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="ok"),
            LinkResult(link_id="l2", status="pass", strength="ASSUMED", detail="shown"),
        ],
        "The total is $10.00.",
        case_id="weak",
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "ASSUMED"


def test_blocked_link_outside_the_verdict_does_not_lower_the_label():
    program = _program(
        [Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10")],
        [
            Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 10.00", claim_span="$10.00"),
            Link(id="l2", kind="compute", inputs=["f1"], statement="other", expr="f1 == 10.00", claim_span="$10.00"),
        ],
        ["l1"],
    )
    verdict = combine(
        program,
        [_grounded("f1")],
        [
            LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="ok"),
            LinkResult(link_id="l2", status="blocked", strength="ASSUMED", detail="SCALE_AMBIGUOUS"),
        ],
        "The total is $10.00.",
        case_id="label",
    )
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"


def test_uncovered_number_is_unresolved():
    program = _program(
        [Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10")],
        [Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 10.00", claim_span="$10.00")],
        ["l1"],
    )
    verdict = combine(
        program,
        [_grounded("f1")],
        [LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="ok")],
        "The total is $10.00 and the fee is $3.00.",
        case_id="cover",
    )
    assert verdict.verdict == "UNRESOLVED"
    assert "UNCOVERED_NUMBER" in verdict.reason_codes


def test_integer_years_are_not_uncovered():
    program = _program(
        [Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10")],
        [Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 10.00", claim_span="$10.00")],
        ["l1"],
    )
    verdict = combine(
        program,
        [_grounded("f1")],
        [LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="ok")],
        "In 2024 the total is $10.00.",
        case_id="year",
    )
    assert verdict.verdict == "SUPPORTED"
    assert "UNCOVERED_NUMBER" not in verdict.reason_codes


def test_unverifiable_part_blocks_support():
    program = _program(
        [Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10")],
        [Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 10.00", claim_span="$10.00")],
        ["l1"],
        ["the signature"],
    )
    verdict = combine(
        program,
        [_grounded("f1")],
        [LinkResult(link_id="l1", status="pass", strength="COMPUTED", detail="ok")],
        "The total is $10.00.",
        case_id="part",
    )
    assert verdict.verdict == "UNRESOLVED"
    assert "UNVERIFIABLE_PART" in verdict.reason_codes
    assert verdict.rounds == 0


def test_grounded_failure_still_contradicts_when_another_link_is_blocked():
    program = _program(
        [
            Fact(id="f1", label="a", source_id="s", value=10, kind="number", quote="10"),
            Fact(id="f2", label="b", source_id="s", value=3, kind="number", quote="3"),
        ],
        [
            Link(id="l1", kind="compute", inputs=["f1"], statement="math", expr="f1 == 9", claim_span="$10"),
            Link(id="l2", kind="compute", inputs=["f2"], statement="other", expr="f2 == 3", claim_span="$3"),
        ],
        ["l1", "l2"],
    )
    verdict = combine(
        program,
        [
            _grounded("f1"),
            FactCheck(fact_id="f2", status="ungrounded", method="quote", detail="quote not in source"),
        ],
        [
            LinkResult(link_id="l1", status="fail", strength="COMPUTED", detail="expression does not hold"),
            LinkResult(link_id="l2", status="blocked", strength="COMPUTED", detail="UNGROUNDED_QUOTE"),
        ],
        "Pay $10 and $3.",
        case_id="partial",
    )
    assert verdict.verdict == "CONTRADICTED"
    assert verdict.label == "COMPUTED"
    assert "UNGROUNDED_QUOTE" in verdict.reason_codes
    assert verdict.reasons == ["expression does not hold"]
