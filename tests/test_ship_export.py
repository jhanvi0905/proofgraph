"""Lead packet through for_engine and run_program. No network.

The shared file is examples/packets/ship-export-this-week.json.
Wrapper role and world stay off Case. dataset on that file is freight.
A filing packet keeps findver. This module does not branch on either.
expected is an eval stamp and is not an input. for_engine clears answer
and gold_evidence before propose and before run_program.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, Mapping

from app.streamlit_app import check_claim
from proofgraph.adapters.base import for_engine
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.engine.route import run_program
from proofgraph.schema import Case, ClaimProgram, Verdict

PACKETS = Path(__file__).resolve().parents[1] / "examples" / "packets"
LEAD = PACKETS / "ship-export-this-week.json"
LATE_FEE = PACKETS / "late-fee-overcharge.json"
_TOKEN = "ANSWERKEY-DO-NOT-READ"
_GAP = "The release note does not mention the export button or this week."


def run_offline(case: Case, program: ClaimProgram) -> Verdict:
    """Clear the answer key, then run the existing engine. No world branch."""

    return run_program(for_engine(case), program)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError("packet must be an object")
    return payload


class _ExpectedTrap(dict):
    """The eval stamp is not an input to the run."""

    def __getitem__(self, key: str) -> Any:
        if key == "expected":
            raise AssertionError("read expected")
        return dict.__getitem__(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        if key == "expected":
            raise AssertionError("read expected")
        return dict.get(self, key, default)


def _case_and_program(path: Path) -> tuple[Case, ClaimProgram]:
    payload = _ExpectedTrap(_load(path))
    case = Case.model_validate(payload["case"])
    program = ClaimProgram.model_validate(payload["program"])
    return case, program


def _poison(case: Case) -> Case:
    return case.model_copy(update={"answer": "SUPPORTED", "gold_evidence": [_TOKEN]})


def _quotes(program: ClaimProgram, link_id: str) -> list[str]:
    facts = {fact.id: fact for fact in program.facts}
    link = next(item for item in program.links if item.id == link_id)
    quotes: list[str] = []
    for fact_id in link.inputs:
        quote = facts[fact_id].quote or ""
        if quote:
            quotes.append(quote)
    return quotes


def _envelope(program: ClaimProgram) -> dict[str, Any]:
    text = program.model_dump_json()
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": "muse-spark-1.3",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }


class _Transport:
    def __init__(self, responses: list[Mapping[str, Any]]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("transport called too many times")
        return dict(self._responses.pop(0))

    @property
    def calls(self) -> int:
        return len(self.bodies)


def test_run_offline_has_no_domain_branch():
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_offline"
    )
    assert not any(isinstance(node, (ast.If, ast.Match)) for node in ast.walk(function))
    dumped = ast.dump(function)
    assert "freight" not in dumped
    assert "findver" not in dumped
    assert "product" not in dumped


def test_ship_export_runs_offline_without_the_eval_stamp(monkeypatch):
    case, program = _case_and_program(LEAD)
    poisoned = _poison(case)
    seen: list[Case] = []
    real = run_program

    def spy(visible: Case, proposed: ClaimProgram) -> Verdict:
        seen.append(visible)
        return real(visible, proposed)

    monkeypatch.setattr(f"{__name__}.run_program", spy)

    verdict = run_offline(poisoned, program)

    assert seen[0].answer is None
    assert seen[0].gold_evidence == []
    assert _TOKEN not in seen[0].model_dump_json()
    assert [source.id for source in seen[0].sources] == [
        "usage_note",
        "support_note",
        "release_note",
    ]
    assert seen[0].id == "ship-export-this-week"
    assert seen[0].dataset == "freight"
    assert "40%" in (seen[0].sources[0].text or "")
    assert "$4,200" in (seen[0].sources[1].text or "")
    assert "export" not in (seen[0].sources[2].text or "").lower()
    assert "this week" not in (seen[0].sources[2].text or "").lower()

    assert verdict.verdict == "CONTRADICTED"
    assert verdict.verdict != "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert _TOKEN not in verdict.model_dump_json()
    assert "gold_evidence" not in verdict.model_dump_json()
    by_link = {item.link_id: item for item in verdict.link_results}
    assert by_link["l_use"].status == "pass"
    assert "40%" in _quotes(program, "l_use")[0]
    assert by_link["l_cost"].status == "fail"
    assert by_link["l_cost"].detail == "expression does not hold"
    assert "$4,200" in _quotes(program, "l_cost")[0]
    assert by_link["l_should"].status == "pass"
    assert by_link["l_should"].strength == "ASSUMED"
    assert "l_should" not in program.required
    assert "UNVERIFIABLE_PART" in verdict.reason_codes
    assert _GAP in verdict.reasons
    assert verdict.verdict in {"SUPPORTED", "CONTRADICTED", "UNRESOLVED"}

    empty = ClaimProgram(facts=[], links=[], required=[], unverifiable_parts=[])
    changed = run_offline(poisoned, empty)
    assert changed.verdict == "UNRESOLVED"
    assert changed.verdict != verdict.verdict


def test_late_fee_uses_the_same_function(monkeypatch):
    case, program = _case_and_program(LATE_FEE)
    poisoned = _poison(case)
    seen: list[Case] = []
    real = run_program

    def spy(visible: Case, proposed: ClaimProgram) -> Verdict:
        seen.append(visible)
        return real(visible, proposed)

    monkeypatch.setattr(f"{__name__}.run_program", spy)

    verdict = run_offline(poisoned, program)

    assert seen[0].answer is None
    assert seen[0].gold_evidence == []
    assert _TOKEN not in seen[0].model_dump_json()
    assert seen[0].dataset == "freight"
    assert seen[0].id == "late-fee-overcharge"
    assert verdict.verdict == "CONTRADICTED"
    assert verdict.verdict != "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert _TOKEN not in verdict.model_dump_json()


def test_propose_then_check_omits_the_answer_key(tmp_path, monkeypatch):
    case, program = _case_and_program(LEAD)
    poisoned = _poison(case)
    seen: list[Case] = []

    def spy(visible: Case, proposed: ClaimProgram) -> Verdict:
        seen.append(visible)
        return run_program(visible, proposed)

    monkeypatch.setattr("app.streamlit_app.run_program", spy)
    transport = _Transport([_envelope(program)])
    client = MuseClient(
        load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)}),
        transport=transport,
    )

    packet = check_claim(poisoned, client=client)

    assert transport.calls == 1
    assert seen[0].answer is None
    assert seen[0].gold_evidence == []
    assert _TOKEN not in seen[0].model_dump_json()
    prompt = json.dumps(transport.bodies[0])
    assert poisoned.claim in prompt
    assert "Export is used by 40% of weekly active accounts." in prompt
    assert "Export support costs $4,200 a month." in prompt
    assert _TOKEN not in prompt
    assert "gold_evidence" not in prompt
    assert "SUPPORTED" not in prompt
    assert "expected" not in prompt
    assert packet.verdict == "CONTRADICTED"
    assert packet.verdict != "SUPPORTED"
    assert packet.label == "COMPUTED"
    assert "UNVERIFIABLE_PART" in packet.reason_codes
    assert _GAP in packet.reasons
    statuses = {row.link_id: row.status for row in packet.link_results}
    assert statuses == {"l_use": "pass", "l_cost": "fail", "l_should": "pass"}
    sources = {row.source_id: row.text for row in packet.sources}
    assert set(sources) == {"usage_note", "support_note", "release_note"}
    assert "40%" in sources["usage_note"]
    assert "$4,200" in sources["support_note"]
    dumped = json.dumps(
        {
            "verdict": packet.verdict,
            "label": packet.label,
            "reasons": packet.reasons,
            "reason_codes": packet.reason_codes,
            "link_results": [row.status for row in packet.link_results],
            "sources": sources,
        }
    )
    assert _TOKEN not in dumped
    assert "gold_evidence" not in dumped
    assert not hasattr(packet, "expected")
