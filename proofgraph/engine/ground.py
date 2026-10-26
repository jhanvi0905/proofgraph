"""Quote grounding and numeric conflicts."""

from __future__ import annotations

from proofgraph.engine.numbers import exceeds_half_percent, find_numbers, normalise_text, numeric_value
from proofgraph.schema import Case, Fact, FactCheck


def ground(fact: Fact, case: Case) -> FactCheck:
    """Ground a plain-text fact when its quote and value both match the source."""
    source = next((item for item in case.sources if item.id == fact.source_id), None)
    if source is None or not source.text or not fact.quote:
        return _ungrounded(fact, "quote not in source")
    if normalise_text(fact.quote) not in normalise_text(source.text):
        return _ungrounded(fact, "quote not in source")
    if not _value_in_quote(fact.value, fact.quote):
        return _ungrounded(fact, "value not in quote")
    return FactCheck(
        fact_id=fact.id,
        status="grounded",
        method="quote",
        detail="quote match",
    )


def apply_conflicts(facts: list[Fact], checks: list[FactCheck]) -> list[FactCheck]:
    """Mark both grounded facts when the conflict key matches and values diverge."""
    by_id = {check.fact_id: check for check in checks}
    groups: dict[tuple[str, str, str], list[Fact]] = {}
    for fact in facts:
        check = by_id.get(fact.id)
        key = _conflict_key(fact)
        if check is None or check.status != "grounded" or key is None:
            continue
        if numeric_value(fact.value) is None:
            continue
        groups.setdefault(key, []).append(fact)
    conflicted: set[str] = set()
    for group in groups.values():
        for index, first in enumerate(group):
            first_value = numeric_value(first.value)
            for second in group[index + 1 :]:
                second_value = numeric_value(second.value)
                if first_value is None or second_value is None:
                    continue
                if exceeds_half_percent(first_value, second_value):
                    conflicted.add(first.id)
                    conflicted.add(second.id)
    updated: list[FactCheck] = []
    for check in checks:
        if check.fact_id in conflicted:
            updated.append(
                check.model_copy(
                    update={
                        "status": "conflict",
                        "detail": "values differ by more than 0.5%",
                    }
                )
            )
        else:
            updated.append(check)
    return updated


def _ungrounded(fact: Fact, detail: str) -> FactCheck:
    return FactCheck(fact_id=fact.id, status="ungrounded", method="quote", detail=detail)


def _value_in_quote(value: object, quote: str) -> bool:
    if isinstance(value, str) and numeric_value(value) is None:
        return normalise_text(value) in normalise_text(quote)
    number = numeric_value(value)
    if number is None:
        return False
    return any(number == found for found in find_numbers(quote))


def _conflict_key(fact: Fact) -> tuple[str, str, str] | None:
    if not fact.label.strip():
        return None
    if fact.entity is None or not fact.entity.strip():
        return None
    if fact.period is None or not fact.period.strip():
        return None
    return (fact.label.strip(), fact.entity.strip(), fact.period.strip())
