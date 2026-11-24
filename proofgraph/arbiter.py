"""Arbiter: the assertions on one question -> one verdict, plus the rule that decided it. No model here.

A pure function. Inputs are data only. No I/O, no logging, no model client;
test_arbiter checks the imports. Citations on amends routes are verified by the
caller (the one verifier needs the file); the arbiter reads only what they record.

Order (DECISIONS.md D3, D7, D9):
  0. Missing-document check (D9), structural, from the mapping. For each document
     asserting on the question that records what it amends: if the amended
     instrument belongs to the question's policy set and is not in the packet,
     unresolved, governing_instrument_absent, naming both. If it belongs to another
     policy, the check skips it and records it as excluded, with the reason.
Both precedence rules are scoped to instruments issued under the slot's policy, the
slot's first segment (D3):
  1. endorsement_over_base: an in-scope endorsement beats an in-scope base
     form or cover note on the same slot.
  2. later_effective_date: among in-scope asserters, the later instrument
     effective date wins. This compares instrument dates, never coverage periods.
A rule's winner is `resolved_by_rule` only when some pair was compared and its
numerals differ (D9). Over equal values the rule still names the governing
document, with reason no_conflict.
Then, when no rule picked a governing assertion (D7):
  - some pair's numerals differ (compared or not, D6): unresolved, documents_disagree;
  - else some pair's numerals agree but currency or basis blocked the comparison:
    unresolved, amounts_not_comparable (D9; was uncompared_agreement);
  - else the asserters agree, or there is one: its value governs, no_conflict.
    A pair with no numeral (NIL) could never have been compared, so it does not block;
  - no assertions on the slot: not_found, no_addressing_span.
Last, amount claims (D9): the governing value against the claim's declared value.
Equal: supported. Different: contradicted. Not comparable: unresolved,
amounts_not_comparable, naming the mismatch between the claim and the governing value.

Wording claims (D9) go to arbitrate_wording: the same check 0 and rules 1-2, over
documents, and the governing clause is quoted verbatim. Nothing is compared.
"""

from __future__ import annotations

from itertools import combinations

from proofgraph.numbers import compare, compare_claim, numeral
from proofgraph.schema import (
    AmendsCheck, Assertion, Claim, Clause, ComparisonReason, DocumentMapping, InstrumentRef, InstrumentType,
    NotFoundReason, QuotedClause, RouteRef, RouteStrength, RuleEvaluation, RuleName, Side, SlotVerdict,
    SupportedReason, UnresolvedReason, ValueComparison, Verdict,
)

Asserter = tuple[str, InstrumentRef]  # (assertion or clause id, the instrument it comes from)


def arbitrate(claim: Claim, assertions: tuple[Assertion, ...], documents: tuple[str, ...],
              mappings: tuple[DocumentMapping, ...] = (), policies: tuple[str, ...] | None = None) -> SlotVerdict:
    """`documents`: every doc_id in the packet. `mappings`: their document mappings (amends routes, verified).
    `policies`: the question's policy set; None means the slot's first segment."""
    if claim.kind != "amount" or claim.slot is None:
        raise ValueError(f"{claim.claim_id}: arbitrate takes amount claims; wording claims go to arbitrate_wording")
    slot = claim.slot
    policy = slot.split(".", 1)[0]
    policies = policies or (policy,)
    on_slot = tuple(a for a in assertions if a.slot == slot)
    in_scope = tuple(a for a in on_slot if policy in a.instrument.policy_numbers)
    pairs = tuple(compare(a, b) for a, b in combinations(on_slot, 2))
    unresolved = sum(1 for p in pairs if not p.compared)
    checks = _amends_checks(tuple(dict.fromkeys(a.instrument.doc_id for a in on_slot)), documents, mappings, policies)

    base = dict(slot=slot, assertions=tuple(a.assertion_id for a in on_slot),
                in_scope=tuple(a.assertion_id for a in in_scope), pairs=pairs, unresolved_pairs=unresolved,
                weakest_routes=tuple(_weakest_route(a) for a in on_slot), claim_kind="amount",
                claim_value=claim.value, policies=policies, amends_checks=checks)

    if not on_slot:
        return SlotVerdict(**base, verdict=Verdict.NOT_FOUND, rules=(), governing_assertion=None, supported_reason=None,
                           governing_doc_id=None, governing_rule=None, unresolved_reason=None,
                           not_found_reason=NotFoundReason.NO_ADDRESSING_SPAN)

    r0 = _absent_rule(checks)
    if r0.fired:
        return SlotVerdict(**base, verdict=Verdict.UNRESOLVED, rules=(r0,), governing_assertion=None,
                           supported_reason=None, governing_doc_id=None, governing_rule=None,
                           unresolved_reason=UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT, not_found_reason=None,
                           unresolved_detail=r0.reason)

    rules, fired = _precedence(tuple((a.assertion_id, a.instrument) for a in in_scope))
    rules = [r0, *rules]
    governing = fired.governing_assertion if fired else None

    conflicting = [p for p in pairs if p.value is ValueComparison.DIFFERENT]
    untested = [p for p in pairs if not p.compared and p.value is ValueComparison.EQUAL
                and p.reason is not ComparisonReason.NO_NUMERAL]
    if governing is not None:
        # A rule picked a winner. It decided something only if two amounts were compared and differ.
        had_conflict = any(p.compared and p.value is ValueComparison.DIFFERENT for p in pairs)
        reason = SupportedReason.RESOLVED_BY_RULE if had_conflict else SupportedReason.NO_CONFLICT
    elif conflicting:
        detail = "; ".join(f"{p.a} vs {p.b}: {'compared, ' + p.detail if p.compared else 'not compared, ' + p.reason.value + ' (' + p.detail + ')'}"
                           for p in conflicting)
        rules.append(RuleEvaluation(name=RuleName.UNRESOLVED_CONFLICT, fired=True, reason=detail, governing_assertion=None))
        return SlotVerdict(**base, verdict=Verdict.UNRESOLVED, rules=tuple(rules), governing_assertion=None,
                           supported_reason=None, governing_doc_id=None, governing_rule=None,
                           unresolved_reason=UnresolvedReason.DOCUMENTS_DISAGREE, not_found_reason=None,
                           unresolved_detail=detail)
    elif untested:
        detail = "; ".join(f"{p.a} vs {p.b}: numerals agree, not compared, {p.reason.value} ({p.detail})" for p in untested)
        rules.append(RuleEvaluation(name=RuleName.UNTESTED_AGREEMENT, fired=True, reason=detail, governing_assertion=None))
        return SlotVerdict(**base, verdict=Verdict.UNRESOLVED, rules=tuple(rules), governing_assertion=None,
                           supported_reason=None, governing_doc_id=None, governing_rule=None,
                           unresolved_reason=UnresolvedReason.AMOUNTS_NOT_COMPARABLE, not_found_reason=None,
                           unresolved_detail=detail)
    else:
        reason = SupportedReason.NO_CONFLICT
        # one asserter, or all agree: the value governs; one with a numeral, if any has one
        governing = next((a.assertion_id for a in on_slot if numeral(a.value.text) is not None), on_slot[0].assertion_id)
        if len({a.instrument.doc_id for a in on_slot}) > 1:
            governing = None  # several documents agree: none of them is named as governing
    compared_with = governing or next((a.assertion_id for a in on_slot if numeral(a.value.text) is not None),
                                      on_slot[0].assertion_id)
    against = next(a for a in on_slot if a.assertion_id == compared_with)
    cc = compare_claim(claim.value, against)
    common = dict(governing_assertion=governing, governing_reason=reason, governing_value=against.value.text,
                  governing_doc_id=next((a.instrument.doc_id for a in on_slot if a.assertion_id == governing), None),
                  governing_rule=fired.name if fired else None, claim_comparison=cc, not_found_reason=None)
    if not cc.compared:
        detail = f"claim {claim.value!r} vs {against.instrument.doc_id} {against.value.text!r}: {cc.reason.value} ({cc.detail})"
        rules.append(RuleEvaluation(name=RuleName.CLAIM_NOT_COMPARABLE, fired=True, reason=detail, governing_assertion=None))
        return SlotVerdict(**base, **common, verdict=Verdict.UNRESOLVED, rules=tuple(rules), supported_reason=None,
                           unresolved_reason=UnresolvedReason.AMOUNTS_NOT_COMPARABLE, unresolved_detail=detail)
    verdict = Verdict.SUPPORTED if cc.value is ValueComparison.EQUAL else Verdict.CONTRADICTED
    return SlotVerdict(**base, **common, verdict=verdict, rules=tuple(rules),
                       supported_reason=reason if verdict is Verdict.SUPPORTED else None, unresolved_reason=None)


def arbitrate_wording(claim: Claim, clauses: tuple[Clause, ...], documents: tuple[str, ...],
                      mappings: tuple[DocumentMapping, ...] = (), policies: tuple[str, ...] | None = None) -> SlotVerdict:
    """Wording claims: no amount verdict. The governing clause is quoted verbatim, marked not checked.

    The precedence rules run over documents (one representative per document). Attack-pass
    clauses are surfaced as clashes, judgment routes with their quotes, never as a verdict.
    """
    if claim.kind != "wording" or claim.slot is None:
        raise ValueError(f"{claim.claim_id}: arbitrate_wording takes wording claims")
    slot = claim.slot
    policy = slot.split(".", 1)[0]
    policies = policies or (policy,)
    docs = tuple(dict.fromkeys(c.instrument.doc_id for c in clauses))
    per_doc = {d: next(c for c in clauses if c.instrument.doc_id == d) for d in docs}
    in_scope = tuple(c for c in per_doc.values() if policy in c.instrument.policy_numbers)
    checks = _amends_checks(docs, documents, mappings, policies)
    quoted_all = tuple(_quote(c) for c in clauses)
    clashes = tuple(_quote(c) for c in clauses if c.side is Side.ATTACK)
    base = dict(slot=slot, assertions=tuple(c.clause_id for c in clauses), in_scope=tuple(c.clause_id for c in in_scope),
                pairs=(), unresolved_pairs=0, weakest_routes=tuple(c.identification for c in clauses),
                claim_kind="wording", claim_value=None, policies=policies, amends_checks=checks,
                clauses=quoted_all, clashes=clashes, supported_reason=None, not_found_reason=None)
    if not clauses:
        return SlotVerdict(**{**base, "not_found_reason": NotFoundReason.NO_ADDRESSING_SPAN}, verdict=Verdict.NOT_FOUND,
                           rules=(), governing_assertion=None, governing_doc_id=None, governing_rule=None,
                           unresolved_reason=None)
    r0 = _absent_rule(checks)
    if r0.fired:
        return SlotVerdict(**base, verdict=Verdict.UNRESOLVED, rules=(r0,), governing_assertion=None,
                           governing_doc_id=None, governing_rule=None,
                           unresolved_reason=UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT, unresolved_detail=r0.reason)
    rules, fired = _precedence(tuple((c.clause_id, c.instrument) for c in in_scope))
    rules = [r0, *rules]
    gov_doc = None
    if fired:
        gov_doc = next(c.instrument.doc_id for c in clauses if c.clause_id == fired.governing_assertion)
    elif len(docs) == 1:
        gov_doc = docs[0]
    if gov_doc is None:
        return SlotVerdict(**base, verdict=Verdict.QUOTED, rules=tuple(rules), governing_assertion=None,
                           governing_doc_id=None, governing_rule=None, unresolved_reason=None,
                           unresolved_detail=f"no rule picks one governing clause among {len(docs)} documents; every clause is quoted")
    mine = [c for c in clauses if c.instrument.doc_id == gov_doc]
    gov = next((c for c in mine if c.side is Side.SUPPORT), mine[0])
    return SlotVerdict(**base, verdict=Verdict.QUOTED, rules=tuple(rules), governing_assertion=gov.clause_id,
                       governing_doc_id=gov_doc, governing_rule=fired.name if fired else None,
                       governing_reason=SupportedReason.NO_CONFLICT, unresolved_reason=None, quoted=_quote(gov))


def _quote(c: Clause) -> QuotedClause:
    strength = RouteStrength.JUDGMENT if c.side is Side.ATTACK else c.identification.strength
    return QuotedClause(clause_id=c.clause_id, doc_id=c.instrument.doc_id, page=c.page, text=c.citation.text,
                        reading=c.reading, side=c.side, strength=strength)


def _amends_checks(asserting: tuple[str, ...], documents: tuple[str, ...], mappings: tuple[DocumentMapping, ...],
                   policies: tuple[str, ...]) -> tuple[AmendsCheck, ...]:
    out = []
    by = {m.doc_id: m for m in mappings}
    for d in asserting:
        m = by.get(d)
        if m is None or m.amends is None:
            continue
        am = m.amends
        common = dict(doc_id=d, amends=am.instrument, amends_doc_id=am.instrument_doc_id, amends_policy=am.policy,
                      strength=am.strength)
        if am.policy not in policies:
            out.append(AmendsCheck(**common, outcome="excluded",
                                   reason=f"{d} amends {am.instrument}, outside this question's policies {', '.join(policies)}"))
        elif am.instrument_doc_id is not None and am.instrument_doc_id in documents:
            out.append(AmendsCheck(**common, outcome="present",
                                   reason=f"{d} amends {am.instrument} ({am.instrument_doc_id}), which is in the packet"))
        else:
            out.append(AmendsCheck(**common, outcome="absent",
                                   reason=f"{d} amends {am.instrument} (policy {am.policy}), which is not in the packet"))
    return tuple(out)


def _absent_rule(checks: tuple[AmendsCheck, ...]) -> RuleEvaluation:
    absent = [c for c in checks if c.outcome == "absent"]
    if absent:
        return RuleEvaluation(name=RuleName.AMENDED_INSTRUMENT_ABSENT, fired=True,
                              reason="; ".join(c.reason for c in absent), governing_assertion=None)
    seen = "; ".join(c.reason for c in checks) or "no asserting document records what it amends"
    return RuleEvaluation(name=RuleName.AMENDED_INSTRUMENT_ABSENT, fired=False, reason=seen, governing_assertion=None)


def _precedence(in_scope: tuple[Asserter, ...]) -> tuple[list[RuleEvaluation], RuleEvaluation | None]:
    r1 = _endorsement_over_base(in_scope)
    r2 = _later_effective_date(in_scope) if not r1.fired else RuleEvaluation(
        name=RuleName.LATER_EFFECTIVE_DATE, fired=False, reason="not evaluated: rule 1 fired", governing_assertion=None)
    return [r1, r2], next((r for r in (r1, r2) if r.fired), None)


def _weakest_route(a: Assertion) -> RouteRef:
    return next(r for r in a.routes if r.strength is a.weakest)


def _endorsement_over_base(in_scope: tuple[Asserter, ...]) -> RuleEvaluation:
    endorsements = [a for a in in_scope if a[1].instrument_type is InstrumentType.ENDORSEMENT]
    bases = [a for a in in_scope if a[1].instrument_type is not InstrumentType.ENDORSEMENT]
    if not endorsements or not bases:
        return RuleEvaluation(
            name=RuleName.ENDORSEMENT_OVER_BASE, fired=False,
            reason=f"needs an endorsement and a base form both in scope; in scope: {[a[0] for a in in_scope] or 'none'}",
            governing_assertion=None)
    if len(endorsements) > 1:
        return RuleEvaluation(name=RuleName.ENDORSEMENT_OVER_BASE, fired=False,
                              reason="more than one in-scope endorsement; rule 2 orders them", governing_assertion=None)
    return RuleEvaluation(name=RuleName.ENDORSEMENT_OVER_BASE, fired=True,
                          reason=f"{endorsements[0][0]} endorses the base", governing_assertion=endorsements[0][0])


def _later_effective_date(in_scope: tuple[Asserter, ...]) -> RuleEvaluation:
    dated = [a for a in in_scope if a[1].effective_date is not None]
    if len(dated) < 2:
        return RuleEvaluation(
            name=RuleName.LATER_EFFECTIVE_DATE, fired=False,
            reason=f"needs two dated in-scope asserters; in scope: {[a[0] for a in in_scope] or 'none'}",
            governing_assertion=None)
    latest = max(a[1].effective_date for a in dated)
    top = [a for a in dated if a[1].effective_date == latest]
    if len(top) > 1:
        return RuleEvaluation(name=RuleName.LATER_EFFECTIVE_DATE, fired=False,
                              reason=f"tie on {latest}", governing_assertion=None)
    return RuleEvaluation(name=RuleName.LATER_EFFECTIVE_DATE, fired=True,
                          reason=f"{top[0][0]} is latest ({latest})", governing_assertion=top[0][0])
