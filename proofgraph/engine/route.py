"""Route facts and links to the Day 1 checks. No proposer and no model client."""

from proofgraph.engine.calc import check_compute
from proofgraph.engine.combine import combine
from proofgraph.engine.ground import apply_conflicts, ground
from proofgraph.schema import Case, ClaimProgram, FactCheck, Link, LinkResult, Verdict


def run_program(case: Case, program: ClaimProgram) -> Verdict:
    """Ground, check, and combine a hand-written program. Rounds stay 0."""
    checks = apply_conflicts(program.facts, [ground(fact, case) for fact in program.facts])
    by_id = {check.fact_id: check for check in checks}
    results = [check(link, by_id, program, case) for link in program.links]
    return combine(program, checks, results, case.claim, case_id=case.id)


def check(
    link: Link,
    facts: dict[str, FactCheck],
    program: ClaimProgram,
    case: Case,
) -> LinkResult:
    """Dispatch one link. Wording and missing evidence block without a model call."""
    strength = _strength(link)
    try:
        input_checks = [facts[fact_id] for fact_id in link.inputs]
    except KeyError:
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength=strength,
            detail="EVAL_ERROR",
        )
    if any(item.status == "conflict" for item in input_checks):
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength=strength,
            detail="CONFLICT",
        )
    if any(item.status != "grounded" for item in input_checks):
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength=strength,
            detail="UNGROUNDED_QUOTE",
        )
    if link.kind in {"compute", "temporal"} or (link.kind == "rule" and link.expr):
        by_fact = {fact.id: fact for fact in program.facts}
        try:
            used = [by_fact[fact_id] for fact_id in link.inputs]
        except KeyError:
            return LinkResult(
                link_id=link.id,
                status="blocked",
                strength=strength,
                detail="EVAL_ERROR",
            )
        outcome = check_compute(link.expr, used, case.claim)
        return LinkResult(
            link_id=link.id,
            status=outcome.status,
            strength=strength,
            detail=outcome.detail,
        )
    if link.kind == "wording":
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength="CHECKED",
            detail="CHECKER_UNAVAILABLE",
        )
    return LinkResult(
        link_id=link.id,
        status="blocked",
        strength=strength,
        detail="EVAL_ERROR",
    )


def _strength(link: Link) -> str:
    if link.kind == "wording":
        return "CHECKED"
    if link.kind == "rule" and link.rule_source == "assumed":
        return "ASSUMED"
    return "COMPUTED"
