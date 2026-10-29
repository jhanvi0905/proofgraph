"""Offline demo: run a fixture through the engine.

A fixture is either ``{case, program}`` or a claim plus evidence packet
(``{claim, evidence_packet, offline_program}``). The packet path prints JSON.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import ValidationError

from proofgraph.engine.route import run_program
from proofgraph.pipeline import LiveModelUnwired, run_payload
from proofgraph.schema import Case, ClaimProgram


def main(argv: list[str] | None = None) -> int:
    """Print the verdict, the label, and the reasons for one fixture."""

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m proofgraph FIXTURE.json", file=sys.stderr)
        return 2
    path = Path(args[0])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read fixture: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict):
        print("fixture must contain case and program", file=sys.stderr)
        return 2
    if "claim" in payload and "evidence_packet" in payload:
        return _print_claim_run(payload)
    try:
        case = Case.model_validate(payload["case"])
        program = ClaimProgram.model_validate(payload["program"])
    except KeyError:
        print("fixture must contain case and program", file=sys.stderr)
        return 2
    except ValidationError as exc:
        print(f"fixture does not match the schema: {exc}", file=sys.stderr)
        return 2
    verdict = run_program(case, program)
    print(verdict.verdict)
    if verdict.label is not None:
        print(verdict.label)
    for reason in verdict.reasons:
        print(reason)
    return 0


def _print_claim_run(payload: dict) -> int:
    """Print the claim run as JSON. This path does not call a model API."""

    try:
        result = run_payload(payload)
    except (KeyError, ValidationError, ValueError, LiveModelUnwired) as exc:
        print(f"could not run claim: {exc}", file=sys.stderr)
        return 2
    print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
