"""Slots are the author's canonical keys: every key resolves to itself; anything else raises before a trace line."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofgraph.claims import UnknownSlot, load_claims, resolve
from proofgraph.schema import SlotRegistry

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = SlotRegistry.model_validate_json((ROOT / "data" / "slots.json").read_text())


def test_every_registry_key_round_trips():
    for e in REGISTRY.slots:
        assert resolve(e.key, REGISTRY) == e.key


@pytest.mark.parametrize("candidate", [
    "FD960228.corporate_reimbursement.retention",  # the drift atomize produced
    "fd960228.corp_reimbursement.retention",  # case
    "FD960228.corp_reimbursement.retention ",  # whitespace
])
def test_near_misses_raise_no_alias_no_fuzzy_match(candidate):
    with pytest.raises(UnknownSlot) as exc:
        resolve(candidate, REGISTRY)
    assert exc.value.known == sorted(e.key for e in REGISTRY.slots)


def test_claim_with_unknown_slot_raises_and_writes_no_trace(tmp_path, monkeypatch):
    claims = tmp_path / "claims.json"
    claims.write_text(json.dumps({"note": "t", "claims": [
        {"claim_id": "x", "text": "t", "slot": "FD960228.corporate_reimbursement.retention"}]}))
    trace = tmp_path / "trace.jsonl"
    from proofgraph import cli

    monkeypatch.setattr(cli, "DATA", tmp_path)
    (tmp_path / "slots.json").write_text((ROOT / "data" / "slots.json").read_text())
    (tmp_path / "predicates.json").write_text((ROOT / "data" / "predicates.json").read_text())
    with pytest.raises(UnknownSlot):
        cli.main(["atomize", "x", "--trace", str(trace)])
    assert not trace.exists()


def test_the_shipped_claims_all_resolve():
    load_claims(ROOT / "data" / "claims.json", ROOT / "data" / "slots.json")
