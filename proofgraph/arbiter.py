"""Arbiter: the assertions on one slot -> one verdict, plus the rule that decided it. No model here.

A pure function. Inputs are data only. No I/O, no logging, no model client;
test_arbiter checks the imports.

Rule order (first rule that fires wins). Both rules are scoped to instruments
issued under the slot's policy, the slot's first segment (DECISIONS.md D3):
  1. endorsement_over_base: an in-scope endorsement beats an in-scope base
     form or cover note on the same slot.
  2. later_effective_date: among in-scope asserters, the later instrument
     effective date wins. This compares instrument dates, never coverage periods.
Then, when no rule picked a governing assertion (D7):
  - some pair's numerals differ (compared or not, D6): unresolved, documents_disagree;
  - else some pair's numerals agree but currency or basis blocked the comparison:
    unresolved, uncompared_agreement. A reader would otherwise draw an
    agreement the arbiter never tested;
  - else supported. That includes one assertion with no pairs: one document
    states a value and nothing disputes it. A pair with no numeral (NIL) could
    never have been compared, so it does not block supported;
  - no assertions on the slot: not_found, no_addressing_span.
"""

from __future__ import annotations

from itertools import combinations

from proofgraph.numbers import compare
from proofgraph.schema import (
    Assertion, ComparisonReason, InstrumentType, NotFoundReason, RouteRef, RuleEvaluation, RuleName, SlotVerdict,
    UnresolvedReason, ValueComparison, Verdict,
)


def arbitrate(slot: str, assertions: tuple[Assertion, ...]) -> SlotVerdict:
    on_slot = tuple(a for a in assertions if a.slot == slot)
    policy = slot.split(".", 1)[0]
    in_scope = tuple(a for a in on_slot if policy in a.instrument.policy_numbers)
    pairs = tuple(compare(a, b) for a, b in combinations(on_slot, 2))

    r1 = _endorsement_over_base(in_scope)
    r2 = _later_effective_date(in_scope) if not r1.fired else RuleEvaluation(
        name=RuleName.LATER_EFFECTIVE_DATE, fired=False, reason="not evaluated: rule 1 fired", governing_assertion=None)
    rules = [r1, r2]
    governing = next((r.governing_assertion for r in rules if r.fired), None)

    conflicting = [p for p in pairs if p.value is ValueComparison.DIFFERENT]
    untested = [p for p in pairs if not p.compared and p.value is ValueComparison.EQUAL
                and p.reason is not ComparisonReason.NO_NUMERAL]
    unresolved = sum(1 for p in pairs if not p.compared)
    unresolved_reason = None
    not_found_reason = None
    if not on_slot:
        verdict, not_found_reason = Verdict.NOT_FOUND, NotFoundReason.NO_ADDRESSING_SPAN
    elif governing is not None:
        verdict = Verdict.SUPPORTED  # slot-level: the governing value stands; claim comparison comes later
    elif conflicting:
        rules.append(RuleEvaluation(
            name=RuleName.UNRESOLVED_CONFLICT, fired=True,
            reason="; ".join(f"{p.a} vs {p.b}: {'compared, ' + p.detail if p.compared else 'not compared, ' + p.reason.value + ' (' + p.detail + ')'}"
                             for p in conflicting),
            governing_assertion=None))
        verdict, unresolved_reason = Verdict.UNRESOLVED, UnresolvedReason.DOCUMENTS_DISAGREE
    elif untested:
        rules.append(RuleEvaluation(
            name=RuleName.UNTESTED_AGREEMENT, fired=True,
            reason="; ".join(f"{p.a} vs {p.b}: numerals agree, not compared, {p.reason.value} ({p.detail})" for p in untested),
            governing_assertion=None))
        verdict, unresolved_reason = Verdict.UNRESOLVED, UnresolvedReason.UNCOMPARED_AGREEMENT
    else:
        verdict = Verdict.SUPPORTED

    return SlotVerdict(
        slot=slot, verdict=verdict,
        assertions=tuple(a.assertion_id for a in on_slot),
        in_scope=tuple(a.assertion_id for a in in_scope),
        pairs=pairs, rules=tuple(rules), governing_assertion=governing,
        unresolved_reason=unresolved_reason, not_found_reason=not_found_reason, unresolved_pairs=unresolved,
        weakest_routes=tuple(_weakest_route(a) for a in on_slot),
    )


def _weakest_route(a: Assertion) -> RouteRef:
    return next(r for r in a.routes if r.strength is a.weakest)


def _endorsement_over_base(in_scope: tuple[Assertion, ...]) -> RuleEvaluation:
    endorsements = [a for a in in_scope if a.instrument.instrument_type is InstrumentType.ENDORSEMENT]
    bases = [a for a in in_scope if a.instrument.instrument_type is not InstrumentType.ENDORSEMENT]
    if not endorsements or not bases:
        return RuleEvaluation(
            name=RuleName.ENDORSEMENT_OVER_BASE, fired=False,
            reason=f"needs an endorsement and a base form both in scope; in scope: {[a.assertion_id for a in in_scope] or 'none'}",
            governing_assertion=None)
    if len(endorsements) > 1:
        return RuleEvaluation(name=RuleName.ENDORSEMENT_OVER_BASE, fired=False,
                              reason="more than one in-scope endorsement; rule 2 orders them", governing_assertion=None)
    return RuleEvaluation(name=RuleName.ENDORSEMENT_OVER_BASE, fired=True,
                          reason=f"{endorsements[0].assertion_id} endorses the base", governing_assertion=endorsements[0].assertion_id)


def _later_effective_date(in_scope: tuple[Assertion, ...]) -> RuleEvaluation:
    dated = [a for a in in_scope if a.instrument.effective_date is not None]
    if len(dated) < 2:
        return RuleEvaluation(
            name=RuleName.LATER_EFFECTIVE_DATE, fired=False,
            reason=f"needs two dated in-scope asserters; in scope: {[a.assertion_id for a in in_scope] or 'none'}",
            governing_assertion=None)
    latest = max(a.instrument.effective_date for a in dated)
    top = [a for a in dated if a.instrument.effective_date == latest]
    if len(top) > 1:
        return RuleEvaluation(name=RuleName.LATER_EFFECTIVE_DATE, fired=False,
                              reason=f"tie on {latest}", governing_assertion=None)
    return RuleEvaluation(name=RuleName.LATER_EFFECTIVE_DATE, fired=True,
                          reason=f"{top[0].assertion_id} is latest ({latest})", governing_assertion=top[0].assertion_id)
