"""Citation -> assertion. Hash mismatch is fatal; a broken citation makes the assertion invalid."""

from __future__ import annotations

from pathlib import Path

import pytest

from proofgraph.assertions import CitationHashMismatch, assert_one
from proofgraph.ingest import ingest
from proofgraph.schema import Assertion, InvalidAssertion, MappingFile, SourceManifest
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LABEL = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
             if s.source_id == "gillette_ex10e")
MAPPINGS = MappingFile.model_validate_json((ROOT / "data" / "mappings.json").read_text())
INPUTS = {a.assertion_id: a for a in MAPPINGS.assertions}

pytestmark = pytest.mark.skipif(not (RAW / LABEL.file).exists(), reason="gillette file absent")


@pytest.fixture(scope="module")
def env():
    res = ingest(LABEL, RAW)
    raw = (RAW / LABEL.file).read_bytes().decode("ascii")
    insts = {i.doc_id: i for i in res.instruments}
    return res.source, raw, insts


def _run(env, inp=None, doc=None, mappings=MAPPINGS):
    source, raw, insts = env
    inp = inp or INPUTS["item7_primary_retention"]
    return assert_one(inp, mappings, insts[doc or inp.instrument_doc_id], source, raw, memory_trace())


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


def _with_cited(mapping_id, **update):
    recs = tuple(r.model_copy(update={"cited": r.cited.model_copy(update=update)}) if r.mapping_id == mapping_id else r
                 for r in MAPPINGS.records)
    return MAPPINGS.model_copy(update={"records": recs})


def test_broken_route_citation_is_invalid_not_a_warning(env):
    r = _run(env, mappings=_with_cited("item7_primary_policy_number", text="757/FD960229"))
    assert isinstance(r, InvalidAssertion) and "broken citation" in r.reason


def test_hash_mismatch_is_fatal(env):
    with pytest.raises(CitationHashMismatch):
        _run(env, mappings=_with_cited("item7_primary_policy_number", sha256_of_file="0" * 64))


def test_citation_outside_the_asserting_instrument_is_invalid(env):
    inp = INPUTS["item7_primary_retention"].model_copy(update={"instrument_doc_id": "reliance_binder"})
    r = _run(env, inp=inp)
    assert isinstance(r, InvalidAssertion)


def test_three_asserters_one_slot_each_with_its_own_routes(env):
    got = {i: _run(env, inp=INPUTS[i]) for i in INPUTS}
    assert all(isinstance(a, Assertion) for a in got.values())
    assert {a.slot for a in got.values()} == {"FD960228.corp_reimbursement.retention"}
    assert {a.instrument.doc_id for a in got.values()} == {"coda_end13", "london_fd960228", "reliance_binder"}
    cover, rel, item7 = got["cover_note_ib_retention"], got["reliance_corp_reimbursement_retention"], got["item7_primary_retention"]
    assert (cover.amount.minor_units, cover.amount.currency.value, cover.basis.value) == (100_000_000, "USD", "each_claim")
    assert (rel.amount.minor_units, rel.amount.currency.value, rel.basis.value) == (50_000_000, "USD", "each_loss")
    assert item7.amount.currency is None and item7.basis is None
    # no two asserters share a route
    routes = [{r.mapping_id for r in a.routes} for a in got.values()]
    assert not (routes[0] & routes[1] or routes[0] & routes[2] or routes[1] & routes[2])


def test_route_strength_is_on_each_assertion(env):
    got = {i: _run(env, inp=INPUTS[i]) for i in INPUTS}
    assert {i: a.weakest.value for i, a in got.items()} == {
        "item7_primary_retention": "derived",
        "cover_note_ib_retention": "judgment",
        "reliance_corp_reimbursement_retention": "judgment",
    }
    judged = {r.mapping_id for a in got.values() for r in a.routes if r.strength.value == "judgment"}
    assert judged == {"cover_ib_corp_reimbursement", "reliance_primary_carrier_to_fd960228"}


def test_judgment_route_must_write_out_its_reasoning():
    from pydantic import ValidationError
    rec = next(r for r in MAPPINGS.records if r.mapping_id == "cover_ib_corp_reimbursement")
    with pytest.raises(ValidationError):
        type(rec).model_validate({**rec.model_dump(mode="json"), "reasoning": None})
