"""Coverage, verdict, label, and reason lines."""

import re

from proofgraph.engine.numbers import iter_literals, numeric_value, parse_number
from proofgraph.schema import ClaimProgram, Fact, FactCheck, Link, LinkResult, Verdict

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
_MONTH_YEAR = re.compile(
    r"^(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+((?:19|20)\d{2})$",
    re.IGNORECASE,
)
_DOLLAR = re.compile(r"\$\s*\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$\s*\d+(?:\.\d+)?")


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
    waived_ids = {
        link.id
        for link in required
        if _covered_wording(link, program, fact_by_id, result_by_id)
    }
    deciding = [link for link in required if link.id not in waived_ids]
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
        for link in deciding:
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
        deciding
        and all(result_of(link).status == "pass" for link in deciding)
        and "UNCOVERED_NUMBER" not in codes
        and "UNVERIFIABLE_PART" not in codes
    ):
        label = _weakest([result_of(link).strength for link in deciding])
        if waived_ids:
            support = [_aggregate_sentence(program, deciding, claim)]
        else:
            support = []
            for link in deciding:
                detail = result_of(link).detail
                if detail and detail not in _CODES and detail not in support:
                    support.append(detail)
        return _verdict(case_id, "SUPPORTED", label, support, [], [], facts, links)

    for link in deciding:
        detail = result_of(link).detail
        if detail in _CODES:
            add_code(detail)
        elif result_of(link).status == "not_mentioned":
            add_code("NOT_MENTIONED")
    if not reasons:
        reasons.append("The claim could not be settled from the grounded evidence.")
    return _verdict(case_id, "UNRESOLVED", None, reasons, codes, fetch, facts, links)


def _covered_wording(
    link: Link,
    program: ClaimProgram,
    fact_by_id: dict[str, FactCheck],
    result_by_id: dict[str, LinkResult],
) -> bool:
    """A month-year wording span already inside a passing compute quote.

    The checker never runs. The span does not block when both the month and
    the year sit in a grounded quote that a passing compute link reads.
    """

    if link.kind != "wording":
        return False
    result = result_by_id.get(link.id)
    if result is None or result.status != "blocked" or result.detail != "CHECKER_UNAVAILABLE":
        return False
    parsed = _MONTH_YEAR.fullmatch(link.claim_span.strip())
    if parsed is None:
        return False
    month, year = parsed.group(1), parsed.group(2)
    facts = {fact.id: fact for fact in program.facts}
    for other in program.links:
        if other.kind != "compute":
            continue
        other_result = result_by_id.get(other.id)
        if other_result is None or other_result.status != "pass":
            continue
        for fact_id in other.inputs:
            check = fact_by_id.get(fact_id)
            fact = facts.get(fact_id)
            if check is None or fact is None or check.status != "grounded":
                continue
            if _month_year_in_quote(month, year, fact.quote or ""):
                return True
    return False


def _month_year_in_quote(month: str, year: str, quote: str) -> bool:
    collapsed = re.sub(r"\s+", " ", quote)
    return (
        re.search(
            rf"\b{re.escape(month)}\b(?: \d{{1,2}},)? {re.escape(year)}\b",
            collapsed,
            re.IGNORECASE,
        )
        is not None
    )


def _aggregate_sentence(program: ClaimProgram, deciding: list[Link], claim: str) -> str:
    """Name the compute inputs and the claim total, without pasting a passage."""

    facts = {fact.id: fact for fact in program.facts}
    parts: list[str] = []
    for link in deciding:
        if link.kind != "compute":
            continue
        for fact_id in link.inputs:
            fact = facts.get(fact_id)
            if fact is None:
                continue
            part = _name_aggregate(fact)
            if part and part not in parts:
                parts.append(part)
    total = _stated_total(deciding, claim)
    if not parts or total is None:
        return "The grounded amounts support the claim."
    named = _join_names(parts)
    verb = "totals" if len(parts) == 1 else "total"
    sentence = f"{named} {verb} the claimed {total}."
    return sentence[:1].upper() + sentence[1:]


def _name_aggregate(fact: Fact) -> str:
    label = fact.label.strip()
    amount = _matching_dollar(fact)
    if label and amount:
        return f"the {label} of {amount}"
    return label or amount or ""


def _matching_dollar(fact: Fact) -> str | None:
    number = numeric_value(fact.value)
    if number is None or not fact.quote:
        return None
    for match in _DOLLAR.finditer(fact.quote):
        token = re.sub(r"\s+", "", match.group(0))
        if parse_number(token) == number:
            return token
    return None


def _stated_total(deciding: list[Link], claim: str) -> str | None:
    for link in deciding:
        if link.kind != "compute":
            continue
        match = _DOLLAR.search(link.claim_span)
        if match is not None:
            return re.sub(r"\s+", "", match.group(0))
    matches = list(_DOLLAR.finditer(claim))
    if not matches:
        return None
    return re.sub(r"\s+", "", matches[-1].group(0))


def _join_names(parts: list[str]) -> str:
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + ", and " + parts[-1]


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
