"""Checkable evidence packets. Compute rows run offline. No network."""

import json
from pathlib import Path

from proofgraph.engine.route import run_program
from proofgraph.schema import Case, ClaimProgram

PACKETS = Path(__file__).resolve().parents[1] / "examples" / "packets"


def test_packet_directory_has_the_real_filing_and_the_bills():
    names = sorted(path.name for path in PACKETS.glob("*.json"))
    assert names == [
        "detention-correct.json",
        "detention-overcharge.json",
        "governing-law-not-mentioned.json",
        "late-fee-overcharge.json",
        "numeric-test-0.json",
        "numeric-val-0.json",
    ]


def test_compute_packets_match_the_recomputed_verdict():
    ran = 0
    for path in sorted(PACKETS.glob("*.json")):
        payload = json.loads(path.read_text())
        program = payload.get("program")
        if program is None:
            continue
        verdict = run_program(
            Case.model_validate(payload["case"]),
            ClaimProgram.model_validate(program),
        )
        expected = payload["expected"]
        assert verdict.verdict == expected["verdict"], path.name
        assert verdict.label == expected["label"], path.name
        ran += 1
    assert ran == 3
