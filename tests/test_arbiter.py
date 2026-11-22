"""Arbiter on the retention slot: three assertions in, documents_disagree out, every pair recorded."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from proofgraph.arbiter import arbitrate
from proofgraph.assertions import assert_one
from proofgraph.ingest import ingest
from proofgraph.schema import ComparisonReason, MappingFile, RuleName, SourceManifest, Verdict
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


@pytest.fixture(scope="module")
def assertions():
    if not (RAW / LABEL.file).exists():
        pytest.skip("gillette file absent")
    res = ingest(LABEL, RAW)
    raw = (RAW / LABEL.file).read_bytes().decode("ascii")
    m = MappingFile.model_validate_json((ROOT / "data" / "mappings.json").read_text())
    insts = {i.doc_id: i for i in res.instruments}
    return tuple(assert_one(inp, m, insts[inp.instrument_doc_id], res.source, raw, memory_trace()) for inp in m.assertions)


def test_retention_slot_is_documents_disagree(assertions):
    v = arbitrate(SLOT, assertions)
    assert v.verdict is Verdict.DOCUMENTS_DISAGREE and v.governing_assertion is None
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
    assert (ic.compared, ic.reason, ic.raw_values_differ) == (False, ComparisonReason.CURRENCY_NOT_STATED, False)


def test_scope_is_what_stops_reliance_winning(assertions):
    """Counterfactual: if Reliance were issued under FD960228, rule 2 would fire and Reliance would govern."""
    moved = tuple(a.model_copy(update={"instrument": a.instrument.model_copy(update={"policy_numbers": ("FD960228",)})})
                  if a.assertion_id == "reliance_corp_reimbursement_retention" else a for a in assertions)
    v = arbitrate(SLOT, moved)
    assert v.governing_assertion == "reliance_corp_reimbursement_retention"
    assert [r.name for r in v.rules if r.fired] == [RuleName.LATER_EFFECTIVE_DATE]
