"""Claim plus evidence packet through propose and the engine. No network.

Mapping under test (also documented in proofgraph/pipeline.py):
claim.id -> Case.id, claim.statement -> Case.claim,
claimant_role and domain stay on ClaimRun, items[].id/text -> Source,
title/source/url/locator stay off the source text. Blank text is dropped.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.pipeline import ClaimInput, EvidencePacket, run_claim, run_payload, to_case
from proofgraph.schema import ClaimProgram, Source

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path(__file__).parent / "fixtures" / "synthetic_pm_packet.json"
_ANSWER_KEYS = frozenset({"expected_pattern", "answer", "gold_evidence", "expected"})
_TOKEN = "ANSWERKEY-DO-NOT-READ"


class _AnswerKeyTrap(dict):
    """Raises if the run reads an eval answer key."""

    def __getitem__(self, key: str) -> Any:
        if key in _ANSWER_KEYS:
            raise AssertionError(f"read answer key {key}")
        return dict.__getitem__(self, key)

    def __contains__(self, key: object) -> bool:
        if key in _ANSWER_KEYS:
            raise AssertionError(f"read answer key {key}")
        return dict.__contains__(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        if key in _ANSWER_KEYS:
            raise AssertionError(f"read answer key {key}")
        return dict.get(self, key, default)


class _FakeTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("transport called too many times")
        return self._responses.pop(0)

    @property
    def calls(self) -> int:
        return len(self.bodies)


def _load() -> dict[str, Any]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["synthetic"] is True
    assert "SYNTHETIC" in payload["label"]
    assert payload["expected_pattern"] == "SUPPORTED"
    assert _TOKEN in payload["gold_evidence"]
    return payload


def test_claim_packet_runs_offline_and_ignores_the_answer_key(tmp_path):
    raw = _load()
    result = run_payload(_AnswerKeyTrap(raw))

    assert result.claim_id == "synthetic-pm-wizard"
    assert result.claimant_role == "product manager"
    assert result.domain == "product discovery"
    assert result.packet_id == "synthetic-packet-wizard"
    assert result.packet_title == "Synthetic wizard packet"
    assert result.proposer == "offline_program"
    assert result.verdict.verdict == "CONTRADICTED"
    assert result.verdict.verdict != raw["expected_pattern"]
    assert result.verdict.label == "COMPUTED"
    assert result.verdict.rounds == 0
    assert result.verdict.fact_checks
    assert result.verdict.link_results
    assert {check.method for check in result.verdict.fact_checks} == {"quote"}
    assert "digraph" in result.graph
    assert _TOKEN not in result.model_dump_json()

    packet = EvidencePacket.model_validate(raw["evidence_packet"])
    item_ids = [item.id for item in packet.items]
    assert [item.item_id for item in result.items] == item_ids
    by_id = {item.item_id: item for item in result.items}
    assert by_id["pilot-cost"].status == "supports"
    assert by_id["saving-slip"].status == "contradicts"
    assert by_id["kitchen-rumor"].status == "unresolved"
    assert "UNGROUNDED_QUOTE" in by_id["kitchen-rumor"].reason
    assert by_id["sticky-note"].status == "dropped"
    assert by_id["sticky-note"].reason == "no proposed fact cites this item"
    assert by_id["blank-scan"].status == "dropped"
    assert by_id["blank-scan"].reason == "empty text"
    for item in result.items:
        assert item.reason.strip()

    known = set(item_ids)
    assert result.relations
    for relation in result.relations:
        assert relation.item_ids
        assert set(relation.item_ids) <= known
    related = {relation.link_id: relation.item_ids for relation in result.relations}
    assert related["l_cost"] == ["pilot-cost"]
    assert related["l_saving"] == ["saving-slip"]
    assert related["l_rumor"] == ["kitchen-rumor"]

    claim = ClaimInput.model_validate(raw["claim"])
    case = to_case(claim, packet)
    assert case.id == claim.id
    assert case.claim == claim.statement
    assert case.dataset == "findver"
    assert case.mode == "passage"
    assert case.answer is None
    assert case.gold_evidence == []
    assert "product manager" not in case.claim
    assert "product discovery" not in case.claim
    assert [(source.id, source.kind, source.text) for source in case.sources] == [
        ("pilot-cost", "text", packet.items[0].text),
        ("saving-slip", "text", packet.items[1].text),
        ("kitchen-rumor", "text", packet.items[2].text),
        ("sticky-note", "text", packet.items[3].text),
    ]
    assert all(isinstance(source, Source) for source in case.sources)

    program = ClaimProgram.model_validate(raw["offline_program"])
    other = run_claim(
        claim.model_copy(update={"domain": "freight logistics", "claimant_role": "dispatcher"}),
        packet,
        program=program,
    )
    assert other.verdict == result.verdict
    assert other.relations == result.relations
    assert other.domain == "freight logistics"
    assert other.claimant_role == "dispatcher"

    transport = _FakeTransport([{"output_text": json.dumps(raw["offline_program"])}])
    client = MuseClient(
        load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)}),
        transport=transport,
    )
    proposed = run_claim(claim, packet, client=client)
    assert transport.calls == 1
    assert proposed.verdict == result.verdict
    assert proposed.proposer == "client"
    prompt = json.dumps(transport.bodies[0])
    assert claim.statement in prompt
    assert "SYNTHETIC pilot log: the pilot cost $40,000." in prompt
    assert "Source id: blank-scan" not in prompt
    assert "synthetic://pilot-cost" not in prompt
    assert "Synthetic pilot cost note" not in prompt
    assert _TOKEN not in prompt
    assert "expected_pattern" not in prompt
    assert "gold_evidence" not in prompt


def test_cli_prints_the_claim_run_without_api_keys():
    env = os.environ.copy()
    env.pop("MODEL_API_KEY", None)
    env.pop("BASETEN_API_KEY", None)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "proofgraph", "tests/fixtures/synthetic_pm_packet.json"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    printed = json.loads(completed.stdout)
    assert printed["verdict"]["verdict"] == "CONTRADICTED"
    assert printed["proposer"] == "offline_program"
    assert _TOKEN not in completed.stdout
    assert "expected_pattern" not in completed.stdout
