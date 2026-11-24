"""Arbiter on the retention slot: three assertions in, unresolved (documents_disagree) out, every pair recorded.

D9: the arbiter now takes the claim (its declared value), the packet's documents and their mappings.
Tests whose expected verdict moved under D9 say so where they assert it."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from proofgraph.arbiter import arbitrate
from proofgraph.assertions import assert_one
from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.schema import (
    Assertion, Claim, ComparisonReason, DocumentMappingFile, MappingFile, RuleName, SourceManifest, UnresolvedReason,
    ValueComparison, Verdict,
)
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SLOT = "FD960228.corp_reimbursement.retention"
LABEL = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
             if s.source_id == "gillette_ex10e")
CLAIM = Claim(claim_id="retention", text="t", slot=SLOT, kind="amount", value="USD 1,000,000")
DOCS = tuple(i.doc_id for i in LABEL.instruments)
MAPS = DocumentMappingFile.model_validate_json((ROOT / "data" / "document_mappings.json").read_text()).documents


def arb(assertions, value="USD 1,000,000", policies=None, maps=MAPS):
    claim = CLAIM.model_copy(update={"value": value})
    return arbitrate(claim, assertions, DOCS, maps, policies)


def test_arbiter_imports_no_model_and_does_no_io():
    tree = ast.parse((ROOT / "proofgraph" / "arbiter.py").read_text())
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not mods & {"proofgraph.model", "anthropic", "proofgraph.trace", "logging", "pathlib", "os"}
    assert "open(" not in (ROOT / "proofgraph" / "arbiter.py").read_text()


def _assertions_with_broken(mapping_id: str | None):
    res = ingest(LABEL, RAW)
    src = open_source(RAW / LABEL.file)
    m = MappingFile.model_validate_json((ROOT / "data" / "mappings.json").read_text())
    if mapping_id:
        recs = tuple(r.model_copy(update={"cited": r.cited.model_copy(update={"text": "X" * len(r.cited.text)})})
                     if r.mapping_id == mapping_id else r for r in m.records)
        m = m.model_copy(update={"records": recs})
    insts = {i.doc_id: i for i in res.instruments}
    out = (assert_one(inp, m, insts[inp.instrument_doc_id], src, memory_trace()) for inp in m.assertions)
    return tuple(a for a in out if isinstance(a, Assertion))


@pytest.fixture(scope="module")
def assertions():
    if not (RAW / LABEL.file).exists():
        pytest.skip("gillette file absent")
    res = ingest(LABEL, RAW)
    src = open_source(RAW / LABEL.file)
    m = MappingFile.model_validate_json((ROOT / "data" / "mappings.json").read_text())
    insts = {i.doc_id: i for i in res.instruments}
    return tuple(assert_one(inp, m, insts[inp.instrument_doc_id], src, memory_trace()) for inp in m.assertions)


def test_retention_slot_is_unresolved_documents_disagree(assertions):
    v = arb(assertions)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.DOCUMENTS_DISAGREE)
    assert v.governing_assertion is None
    assert v.in_scope == ("cover_note_ib_retention",)
    fired = [r.name for r in v.rules if r.fired]
    assert fired == [RuleName.UNRESOLVED_CONFLICT]
    assert v.unresolved_detail and v.claim_comparison is None  # no value governs, so the claim is not compared


def test_endorsement_13_is_excluded_from_the_missing_document_check_with_its_reason(assertions):
    """D9: Endorsement 13 amends GS-212C, not FD960228. The check skips it and says so; it is never dropped."""
    v = arb(assertions)
    (c,) = v.amends_checks
    assert (c.doc_id, c.outcome, c.amends) == ("coda_end13", "excluded", "GS-212C")
    assert c.reason == "coda_end13 amends GS-212C, outside this question's policies FD960228"
    assert v.unresolved_reason is UnresolvedReason.DOCUMENTS_DISAGREE  # Gillette stays unresolved


def test_missing_document_check_counterfactual_a_question_spanning_gs212c(assertions):
    """Put GS-212C in the question's policy set: Endorsement 13 now amends an instrument of the question,
    the base GS-212C wording is not in the packet, and the verdict moves to governing_instrument_absent.
    Without the check (no amends routes) the same packet stays documents_disagree."""
    v = arb(assertions, policies=("FD960228", "GS-212C"))
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT)
    assert "coda_end13" in v.unresolved_detail and "GS-212C" in v.unresolved_detail
    assert [r.name for r in v.rules if r.fired] == [RuleName.AMENDED_INSTRUMENT_ABSENT]
    off = arb(assertions, policies=("FD960228", "GS-212C"), maps=())
    assert off.unresolved_reason is UnresolvedReason.DOCUMENTS_DISAGREE


def test_every_pair_is_recorded_with_its_reason(assertions):
    v = arb(assertions)
    by = {frozenset((p.a, p.b)): p for p in v.pairs}
    assert len(by) == 3 and v.unresolved_pairs == 3
    cr = by[frozenset(("cover_note_ib_retention", "reliance_corp_reimbursement_retention"))]
    # D12 item 5: Reliance prints "$" (dollars, country not printed) and the cover note "USD", so the pair stops at
    # the currency before the bases (each_claim vs each_loss, the reason recorded until D12). Still not compared.
    assert (cr.compared, cr.reason, cr.detail) == (False, ComparisonReason.CURRENCY_COUNTRY_NOT_PRINTED, "'$' vs USD")
    ic = by[frozenset(("item7_primary_retention", "cover_note_ib_retention"))]
    assert (ic.compared, ic.reason, ic.value) == (False, ComparisonReason.CURRENCY_NOT_STATED, ValueComparison.EQUAL)


def test_later_effective_date_flips_the_verdict_when_reliance_is_in_scope(assertions):
    """Rule 2's scope is what keeps Reliance out, not its date. Put Reliance under FD960228 and
    later_effective_date fires (12/31/96 over 6/1/96), Reliance governs, and the verdict flips.
    A rule never shown to flip a verdict is decoration; this is rule 2's."""
    moved = tuple(a.model_copy(update={"instrument": a.instrument.model_copy(update={"policy_numbers": ("FD960228",)})})
                  if a.assertion_id == "reliance_corp_reimbursement_retention" else a for a in assertions)
    # D9: the governing value is now compared with the claim's. A claim of $500,000 each loss matches it.
    v = arb(moved, value="$500,000 each loss")
    assert v.verdict is Verdict.SUPPORTED and arb(assertions).verdict is Verdict.UNRESOLVED
    assert v.governing_assertion == "reliance_corp_reimbursement_retention"
    assert v.governing_rule is RuleName.LATER_EFFECTIVE_DATE and v.governing_doc_id == "reliance_binder"
    assert [r.name for r in v.rules if r.fired] == [RuleName.LATER_EFFECTIVE_DATE]
    # D9: no pair the rule ordered was compared and differed (the bases mismatch, Item VII states no
    # currency), so it was not shown to settle a disagreement: no_conflict, with the rule still named.
    assert v.supported_reason.value == "no_conflict" and v.governing_reason.value == "no_conflict"
    # The author's claim (USD 1,000,000, no basis) against Reliance's $500,000 each loss: not comparable, named.
    w = arb(moved)
    assert (w.verdict, w.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.AMOUNTS_NOT_COMPARABLE)
    # D12 item 5: the claim's "USD" against Reliance's "$" is named first (until D12: basis_not_stated, "not stated by claim").
    assert w.claim_comparison.reason is ComparisonReason.CURRENCY_COUNTRY_NOT_PRINTED and w.claim_comparison.detail == "'$' vs USD"
    assert w.governing_doc_id == "reliance_binder" and "claim 'USD 1,000,000' vs reliance_binder '$500,000'" in w.unresolved_detail


def test_unresolved_conflict_survives_without_the_cover_note_judgment_route(assertions):
    """Break the cover note's I.B route: its assertion is invalid and leaves. Item VII vs Reliance
    still differ in value and cannot be compared, so the headline holds without the weakest cover-note link."""
    left = _assertions_with_broken("cover_ib_corp_reimbursement")
    assert {a.assertion_id for a in left} == {"item7_primary_retention", "reliance_corp_reimbursement_retention"}
    v = arb(left)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.DOCUMENTS_DISAGREE)
    assert [r.name for r in v.rules if r.fired] == [RuleName.UNRESOLVED_CONFLICT]


def test_without_reliance_the_slot_is_unresolved_not_supported(assertions):
    """Break Reliance's route to FD960228: only Item VII and the cover note remain.

    Their numerals agree (1,000,000), but Item VII states no currency, so the pair was
    never compared. Up to commit be47202 this returned `supported`. Decision D7 changed it
    on purpose, not to make a test pass: a reader seeing `supported` would infer an
    agreement the arbiter never tested. So the verdict is unresolved with reason
    uncompared_agreement. Nothing disagrees, so it is not documents_disagree, and it is a
    relabel within the four verdicts, not a fifth.
    The headline (documents_disagree) still rests on this judgment route: without it,
    no document says $500,000."""
    left = _assertions_with_broken("reliance_primary_carrier_to_fd960228")
    assert {a.assertion_id for a in left} == {"item7_primary_retention", "cover_note_ib_retention"}
    v = arb(left)
    # D9 renamed uncompared_agreement to amounts_not_comparable; the case is the same.
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.AMOUNTS_NOT_COMPARABLE)
    assert [r.name for r in v.rules if r.fired] == [RuleName.UNTESTED_AGREEMENT]


def test_one_assertion_with_nothing_disputing_it_is_supported(assertions):
    """The ordinary case D7 protects: one document states a value, no pairs, supported.

    D9: the sole asserter now governs (governing_doc_id is named, with no rule), and its value is
    compared with the claim's. The cover note says "USD 1,000,000 each Claim"; a claim that states
    the same basis is supported. The author's claim states none, so it is not comparable, named."""
    cover = tuple(a for a in assertions if a.assertion_id == "cover_note_ib_retention")
    v = arb(cover, value="USD 1,000,000 each claim")
    assert v.verdict is Verdict.SUPPORTED and v.pairs == ()
    assert v.supported_reason.value == "no_conflict" and v.governing_rule is None
    assert v.governing_doc_id == "london_fd960228" and v.claim_comparison.compared
    w = arb(cover)
    assert (w.verdict, w.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.AMOUNTS_NOT_COMPARABLE)
    assert [r.name for r in w.rules if r.fired] == [RuleName.CLAIM_NOT_COMPARABLE]


def test_no_assertions_is_not_found():
    v = arb(())
    assert v.verdict is Verdict.NOT_FOUND and v.not_found_reason.value == "no_addressing_span"



def test_a_rule_that_only_orders_agreeing_values_is_not_a_decision(assertions):
    """Two in-scope asserters with the same value and different dates: rule 2 picks the later one,
    but there was nothing to resolve, so the reason stays no_conflict."""
    import datetime as dt

    cover = next(a for a in assertions if a.assertion_id == "cover_note_ib_retention")
    later = cover.model_copy(update={
        "assertion_id": "cover_note_restated",
        "instrument": cover.instrument.model_copy(update={"doc_id": "restated", "effective_date": dt.date(1996, 12, 1)}),
    })
    v = arb((cover, later), value="USD 1,000,000 each claim")
    assert v.verdict is Verdict.SUPPORTED and v.governing_rule is RuleName.LATER_EFFECTIVE_DATE
    assert v.supported_reason.value == "no_conflict"
    assert v.pairs[0].compared and v.pairs[0].value is ValueComparison.EQUAL
