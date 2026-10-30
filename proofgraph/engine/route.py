"""Route facts and links to the Day 1 checks. No proposer and no Muse client."""

from proofgraph.clients.checker import CheckerError, blind_wording
from proofgraph.engine.calc import check_compute
from proofgraph.engine.combine import combine
from proofgraph.engine.ground import apply_conflicts, ground
from proofgraph.schema import Case, ClaimProgram, Fact, FactCheck, Link, LinkResult, Verdict


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
    """Dispatch one link. A wording link goes to the blind checker."""
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
    if link.kind == "rule" and _blank(link.expr) and link.rule_source == "assumed":
        shown = link.statement.strip()
        return LinkResult(
            link_id=link.id,
            status="pass",
            strength="ASSUMED",
            detail=shown or "shown",
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
        return _check_wording(link, program)
    return LinkResult(
        link_id=link.id,
        status="blocked",
        strength=strength,
        detail="EVAL_ERROR",
    )


def _check_wording(link: Link, program: ClaimProgram) -> LinkResult:
    """Send one passage and the link statement to the blind checker."""

    quote = _passage(link, program)
    if quote == "":
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength="CHECKED",
            detail="CHECKER_UNAVAILABLE",
        )
    try:
        label = blind_wording(quote, link.statement)
    except CheckerError as exc:
        if exc.status_code == 429:
            raise
        return LinkResult(
            link_id=link.id,
            status="blocked",
            strength="CHECKED",
            detail=exc.reason_code,
        )
    if label == "entails":
        return LinkResult(
            link_id=link.id,
            status="pass",
            strength="CHECKED",
            detail=link.statement,
        )
    if label == "contradicts":
        return LinkResult(
            link_id=link.id,
            status="fail",
            strength="CHECKED",
            detail=link.statement,
        )
    return LinkResult(
        link_id=link.id,
        status="not_mentioned",
        strength="CHECKED",
        detail="NOT_MENTIONED",
    )


def _passage(link: Link, program: ClaimProgram) -> str:
    """The input quotes, once each. Nothing else from the case is included."""

    by_id = {fact.id: fact for fact in program.facts}
    quotes: list[str] = []
    for fact_id in link.inputs:
        fact: Fact | None = by_id.get(fact_id)
        text = fact.quote.strip() if fact is not None and fact.quote else ""
        if text and text not in quotes:
            quotes.append(text)
    return "\n".join(quotes)


def _blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _strength(link: Link) -> str:
    if link.kind == "wording":
        return "CHECKED"
    if link.kind == "rule" and link.rule_source == "assumed":
        return "ASSUMED"
    return "COMPUTED"
