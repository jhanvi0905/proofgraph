"""Coverage, verdict, label, and reason lines."""

from proofgraph.engine.numbers import iter_literals, numeric_value
from proofgraph.schema import ClaimProgram, FactCheck, Link, LinkResult, Verdict

_CODES = {
    "UNGROUNDED_QUOTE",
    "VALUE_NOT_IN_BOX",
    "REREAD_MISMATCH",
    "COUNT_MISMATCH",
    "CONFLICT",
    "UNIT_MISMATCH",
    "SCALE_AMBIGUOUS",
    "UNCOVERED_NUMBER",
    "UNVERIFIABLE_PART",
    "NOT_MENTIONED",
    "CLAUSE_CONFLICT",
    "EVAL_ERROR",
    "EXTRACTION_FAILED",
    "CHECKER_UNAVAILABLE",
}
_RANK = {"ASSUMED": 0, "CHECKED": 1, "COMPUTED": 2}
_FETCH = {
    "CONFLICT": (
        "Need one agreed figure; grounded values for the same label, entity, "
        "and period differ by more than 0.5%."
    ),
    "SCALE_AMBIGUOUS": "Need the stated scale (units, thousands, or millions).",
    "UNCOVERED_NUMBER": "Need a check that covers every number in the claim.",
    "UNGROUNDED_QUOTE": "Need a source quote that contains this fact.",
    "UNVERIFIABLE_PART": "Need evidence for the part of the claim that could not be mapped.",
    "EVAL_ERROR": "Need a checkable expression.",
    "CHECKER_UNAVAILABLE": "Need the blind checker before this wording link can be decided.",
    "NOT_MENTIONED": "Need text that mentions this statement.",
    "CLAUSE_CONFLICT": "Need a reading that resolves the contradicting clauses.",
}


def combine(
    program: ClaimProgram,
    facts: list[FactCheck],
    links: list[LinkResult],
    claim: str,
    case_id: str = "",
) -> Verdict:
    """Combine grounded checks into one verdict. This slice never calls revise."""
    fact_by_id = {item.fact_id: item for item in facts}
    result_by_id = {item.link_id: item for item in links}
    required = [link for link in program.links if link.id in set(program.required)]
    codes: list[str] = []
    reasons: list[str] = []
    fetch: list[str] = []

    def add_code(code: str) -> None:
        if code in codes:
            return
        codes.append(code)
        line = _FETCH.get(code)
        if line and line not in fetch:
            fetch.append(line)

    def result_of(link: Link) -> LinkResult:
        return result_by_id[link.id]

    if any(_has_status(link, fact_by_id, "conflict") for link in required):
        add_code("CONFLICT")
        reasons.append(
            "Grounded figures that share a label, entity, and period differ by more than 0.5%."
        )
        return _verdict(
            case_id, "UNRESOLVED", None, reasons, codes, fetch, facts, links
        )

    if _uncovered(program, facts, claim):
        add_code("UNCOVERED_NUMBER")
    if program.unverifiable_parts:
        add_code("UNVERIFIABLE_PART")
        reasons.extend(program.unverifiable_parts)

    failed = [
        link
        for link in required
        if result_of(link).status == "fail" and _all_status(link, fact_by_id, "grounded")
    ]
    if failed:
        for link in failed:
            detail = result_of(link).detail
            if detail and detail not in _CODES and detail not in reasons:
                reasons.append(detail)
        for link in required:
            detail = result_of(link).detail
            if result_of(link).status == "blocked" and detail in _CODES:
                add_code(detail)
        label = _weakest([result_of(link).strength for link in failed])
        return _verdict(
            case_id,
            "CONTRADICTED",
            label,
            reasons,
            codes,
            fetch,
            facts,
            links,
        )

    if (
        all(result_of(link).status == "pass" for link in required)
        and "UNCOVERED_NUMBER" not in codes
        and "UNVERIFIABLE_PART" not in codes
    ):
        label = _weakest([result_of(link).strength for link in required])
        return _verdict(case_id, "SUPPORTED", label, [], [], [], facts, links)

    for link in required:
        detail = result_of(link).detail
        if detail in _CODES:
            add_code(detail)
        elif result_of(link).status == "not_mentioned":
            add_code("NOT_MENTIONED")
    if not reasons:
        reasons.append("The claim could not be settled from the grounded evidence.")
    return _verdict(case_id, "UNRESOLVED", None, reasons, codes, fetch, facts, links)


def _has_status(link: Link, fact_by_id: dict[str, FactCheck], status: str) -> bool:
    return any(fact_by_id[fact_id].status == status for fact_id in link.inputs)


def _all_status(link: Link, fact_by_id: dict[str, FactCheck], status: str) -> bool:
    return all(fact_by_id[fact_id].status == status for fact_id in link.inputs)


def _uncovered(program: ClaimProgram, checks: list[FactCheck], claim: str) -> list[object]:
    grounded_ids = {item.fact_id for item in checks if item.status == "grounded"}
    grounded_values = [
        number
        for fact in program.facts
        if fact.id in grounded_ids and (number := numeric_value(fact.value)) is not None
    ]
    tested = []
    for link in program.links:
        tested.extend(item.value for item in iter_literals(link.claim_span))
        if link.expr:
            tested.extend(item.value for item in iter_literals(link.expr))
    missing = []
    for item in iter_literals(claim, skip_years=True):
        if any(item.value == value for value in grounded_values):
            continue
        if any(item.value == value for value in tested):
            continue
        missing.append(item.value)
    return missing


def _weakest(strengths: list[str]) -> str | None:
    if not strengths:
        return None
    return min(strengths, key=lambda name: _RANK[name])


def _verdict(
    case_id: str,
    verdict: str,
    label: str | None,
    reasons: list[str],
    codes: list[str],
    fetch: list[str],
    facts: list[FactCheck],
    links: list[LinkResult],
) -> Verdict:
    return Verdict(
        case_id=case_id,
        verdict=verdict,  # type: ignore[arg-type]
        label=label,  # type: ignore[arg-type]
        reasons=list(reasons),
        reason_codes=list(codes),
        fetch=list(fetch),
        rounds=0,
        fact_checks=list(facts),
        link_results=list(links),
        flags=[],
    )
