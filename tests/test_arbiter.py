"""Arbiter on the retention slot: three assertions in, unresolved (documents_disagree) out, every pair recorded."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from proofgraph.arbiter import arbitrate
from proofgraph.assertions import assert_one
from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.schema import (
    Assertion, ComparisonReason, MappingFile, RuleName, SourceManifest, UnresolvedReason, ValueComparison, Verdict,
)
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SLOT = "FD960228.corp_reimbursement.retention"
LABEL = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
             if s.source_id == "gillette_ex10e")


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
    v = arbitrate(SLOT, assertions)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.DOCUMENTS_DISAGREE)
    assert v.governing_assertion is None
    assert v.in_scope == ("cover_note_ib_retention",)
    fired = [r.name for r in v.rules if r.fired]
    assert fired == [RuleName.UNRESOLVED_CONFLICT]


def test_every_pair_is_recorded_with_its_reason(assertions):
    v = arbitrate(SLOT, assertions)
    by = {frozenset((p.a, p.b)): p for p in v.pairs}
    assert len(by) == 3 and v.unresolved_pairs == 3
    cr = by[frozenset(("cover_note_ib_retention", "reliance_corp_reimbursement_retention"))]
    assert (cr.compared, cr.reason, cr.detail) == (False, ComparisonReason.BASIS_MISMATCH, "each_claim vs each_loss")
    ic = by[frozenset(("item7_primary_retention", "cover_note_ib_retention"))]
    assert (ic.compared, ic.reason, ic.value) == (False, ComparisonReason.CURRENCY_NOT_STATED, ValueComparison.EQUAL)


def test_later_effective_date_flips_the_verdict_when_reliance_is_in_scope(assertions):
    """Rule 2's scope is what keeps Reliance out, not its date. Put Reliance under FD960228 and
    later_effective_date fires (12/31/96 over 6/1/96), Reliance governs, and the verdict flips.
    A rule never shown to flip a verdict is decoration; this is rule 2's."""
    moved = tuple(a.model_copy(update={"instrument": a.instrument.model_copy(update={"policy_numbers": ("FD960228",)})})
                  if a.assertion_id == "reliance_corp_reimbursement_retention" else a for a in assertions)
    v = arbitrate(SLOT, moved)
    assert v.verdict is Verdict.SUPPORTED and arbitrate(SLOT, assertions).verdict is Verdict.UNRESOLVED
    assert v.governing_assertion == "reliance_corp_reimbursement_retention"
    assert [r.name for r in v.rules if r.fired] == [RuleName.LATER_EFFECTIVE_DATE]


def test_unresolved_conflict_survives_without_the_cover_note_judgment_route(assertions):
    """Break the cover note's I.B route: its assertion is invalid and leaves. Item VII vs Reliance
    still differ in value and cannot be compared, so the headline holds without the weakest cover-note link."""
    left = _assertions_with_broken("cover_ib_corp_reimbursement")
    assert {a.assertion_id for a in left} == {"item7_primary_retention", "reliance_corp_reimbursement_retention"}
    v = arbitrate(SLOT, left)
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
    v = arbitrate(SLOT, left)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.UNCOMPARED_AGREEMENT)
    assert [r.name for r in v.rules if r.fired] == [RuleName.UNTESTED_AGREEMENT]


def test_one_assertion_with_nothing_disputing_it_is_supported(assertions):
    """The ordinary case D7 protects: one document states a value, no pairs, supported."""
    cover = tuple(a for a in assertions if a.assertion_id == "cover_note_ib_retention")
    v = arbitrate(SLOT, cover)
    assert v.verdict is Verdict.SUPPORTED and v.pairs == ()


def test_no_assertions_is_not_found():
    v = arbitrate(SLOT, ())
    assert v.verdict is Verdict.NOT_FOUND and v.not_found_reason.value == "no_addressing_span"
