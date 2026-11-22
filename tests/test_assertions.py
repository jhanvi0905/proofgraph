"""Citation -> assertion. Hash mismatch is fatal; a broken citation makes the assertion invalid."""

from __future__ import annotations

from pathlib import Path

import pytest

from proofgraph.assertions import CitationHashMismatch, assert_cell
from proofgraph.ingest import ingest
from proofgraph.schema import Assertion, InvalidAssertion, MappingFile, SourceManifest
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LABEL = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
             if s.source_id == "gillette_ex10e")
RECS = {r.mapping_id: r for r in MappingFile.model_validate_json((ROOT / "data" / "mappings.json").read_text()).records}

pytestmark = pytest.mark.skipif(not (RAW / LABEL.file).exists(), reason="gillette file absent")


@pytest.fixture(scope="module")
def env():
    res = ingest(LABEL, RAW)
    raw = (RAW / LABEL.file).read_bytes().decode("ascii")
    insts = {i.doc_id: i for i in res.instruments}
    return res.source, raw, insts


def _run(env, cell=None, policy=None, doc="coda_end13"):
    source, raw, insts = env
    return assert_cell(cell or RECS["item7_primary_retention_position3"], policy or RECS["item7_primary_policy_number"],
                       insts[doc], source, raw, memory_trace())


def test_line_1325_yields_one_assertion_with_unstated_currency_and_basis(env):
    a = _run(env)
    assert isinstance(a, Assertion)
    assert a.slot == "FD960228.corp_reimbursement.retention"
    assert a.value.text == "1,000,000" and env[1][a.value.start:a.value.end] == "1,000,000"
    assert a.amount.minor_units == 100_000_000 and a.amount.currency is None
    assert a.basis is None and a.basis_phrase is None


def test_asserted_by_resolves_to_the_instrument_record(env):
    a = _run(env)
    assert a.instrument.doc_id == "coda_end13"
    assert a.instrument.policy_numbers == ("GS-212C",)
    assert str(a.instrument.effective_date) == "1996-06-01"


def test_broken_citation_is_invalid_not_a_warning(env):
    cell = RECS["item7_primary_retention_position3"]
    bad = cell.model_copy(update={"cited": cell.cited.model_copy(update={"text": "NIL/NIL/1,000,001"})})
    r = _run(env, cell=bad)
    assert isinstance(r, InvalidAssertion) and "broken citation" in r.reason


def test_hash_mismatch_is_fatal(env):
    cell = RECS["item7_primary_retention_position3"]
    bad = cell.model_copy(update={"cited": cell.cited.model_copy(update={"sha256_of_file": "0" * 64})})
    with pytest.raises(CitationHashMismatch):
        _run(env, cell=bad)


def test_citation_outside_the_asserting_instrument_is_invalid(env):
    r = _run(env, doc="reliance_binder")
    assert isinstance(r, InvalidAssertion)
