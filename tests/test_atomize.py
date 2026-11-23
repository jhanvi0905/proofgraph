"""Atomise with a fake model: validation, repair, and refusal to force a fit.

Negatives matter more than positives. The ~20 hand-labelled claims come with
the packets; these pin the mechanics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from proofgraph.atomize import atomize, validate_atom_fields
from proofgraph.model import ModelReply
from proofgraph.schema import AtomErrorCode, Claim, ProposedAtom, load_predicate_set
from proofgraph.trace import memory_trace

PREDICATES = load_predicate_set(Path(__file__).resolve().parent.parent / "data" / "predicates.json")
CLAIM = Claim(claim_id="c1", text="The primary corporate reimbursement retention under FD960228 is USD 1,000,000.",
              slot="FD960228.corp_reimbursement.retention", kind="amount", value="USD 1,000,000")  # D9: declared


def _atom(**over) -> dict:
    base = dict(predicate="states", kind=None, negated=False, subject="primary D&O layer corporate reimbursement retention",
                quantity_raw="USD 1,000,000", value=None,
                period=None, territory=None, basis=None, conditions=None)
    base.update(over)
    return base


def _fake(*replies: dict):
    calls = []

    def complete(prompt, schema, *, system, template, effort="low"):
        calls.append(prompt)
        return ModelReply(json.dumps(replies[len(calls) - 1]), "fake-model", "ph", 10, 5, 1, False)

    complete.calls = calls
    return complete


def _errs(claim_slot="FD960228.corp_reimbursement.retention", **over):
    errs, _ = validate_atom_fields(ProposedAtom.model_validate_json(json.dumps(_atom(**over))), PREDICATES, claim_slot)
    return {e.code for e in errs}


def test_retention_claim_atomises_to_one_states_atom():
    trace = memory_trace()
    res = atomize(CLAIM, PREDICATES, trace, _fake({"atoms": [_atom()], "no_fit_reason": None}))
    assert res.errors == () and res.repairs == 0 and len(res.atoms) == 1
    a = res.atoms[0]
    assert a.predicate == "states" and a.slot == "FD960228.corp_reimbursement.retention"
    assert a.quantity.minor_units == 100_000_000 and a.quantity.currency.value == "USD"
    assert len(trace.records) == 1 and trace.records[0].stage == "atomize"


# ---- negatives: each must fail validation


def test_unresolved_reference_fails():
    assert AtomErrorCode.UNRESOLVED_REF in _errs(subject="the policy")


def test_missing_unit_fails():
    assert AtomErrorCode.MISSING_UNIT in _errs(quantity_raw="1,000,000")


def test_conjunction_in_value_fails():
    assert AtomErrorCode.CONJUNCTION_IN_VALUE in _errs(quantity_raw="USD 1,000,000 and USD 500,000")


def test_letter_o_in_amount_is_not_repaired():
    assert AtomErrorCode.UNPARSEABLE_QUANTITY in _errs(quantity_raw="US$10,000,0O0")


def test_states_needs_a_slot_from_the_claim_file():
    assert AtomErrorCode.MISSING_SLOT in _errs(claim_slot=None)


def test_the_model_cannot_name_a_slot():
    """The wire schema has no slot field, and a reply that adds one is rejected outright."""
    from proofgraph.atomize import _wire_schema

    assert "slot" not in _wire_schema(PREDICATES)["properties"]["atoms"]["items"]["properties"]
    with pytest.raises(ValidationError):
        ProposedAtom.model_validate_json(json.dumps(_atom(slot="FD960228.corporate_reimbursement.retention")))


def test_atom_takes_the_slot_from_the_claim():
    res = atomize(CLAIM, PREDICATES, memory_trace(), _fake({"atoms": [_atom()], "no_fit_reason": None}))
    assert res.atoms[0].slot == CLAIM.slot


def test_kind_rules():
    assert AtomErrorCode.BAD_KIND in _errs(kind="follow_form")  # states takes no kind
    assert AtomErrorCode.BAD_KIND in _errs(predicate="subject_to", kind=None, quantity_raw=None, value="x")


def test_unknown_predicate_fails():
    assert AtomErrorCode.UNKNOWN_PREDICATE in _errs(predicate="equals")


def test_proposed_atom_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProposedAtom.model_validate_json(json.dumps(_atom(confidence=0.9)))


# ---- repair: one retry, then fail


def test_one_repair_then_success():
    fake = _fake({"atoms": [_atom(quantity_raw="1,000,000")], "no_fit_reason": None},
                 {"atoms": [_atom()], "no_fit_reason": None})
    res = atomize(CLAIM, PREDICATES, memory_trace(), fake)
    assert res.repairs == 1 and res.rejects == 1 and len(res.atoms) == 1
    assert "missing_unit" in fake.calls[1]


def test_two_failures_return_errors_not_atoms():
    bad = {"atoms": [_atom(subject="it")], "no_fit_reason": None}
    fake = _fake(bad, bad)
    res = atomize(CLAIM, PREDICATES, memory_trace(), fake)
    assert res.atoms == () and res.repairs == 1 and len(fake.calls) == 2
    assert {e.code for e in res.errors} == {AtomErrorCode.UNRESOLVED_REF}


def test_no_fit_is_an_outcome_not_a_repair():
    fake = _fake({"atoms": [], "no_fit_reason": "a claim about premium financing"})
    res = atomize(CLAIM, PREDICATES, memory_trace(), fake)
    assert res.atoms == () and res.repairs == 0 and len(fake.calls) == 1
    assert res.errors[0].code is AtomErrorCode.NO_PREDICATE_FITS
