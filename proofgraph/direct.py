"""System A, Direct Muse: the baseline. One call, the same evidence, no ProofGraph.

The prompt is prompts/direct.md word for word. The case goes through
``for_engine`` and its text is fenced as in ``propose``. The call goes through
``MuseClient``, so the retries and the spend cap apply. This module never
raises into a caller: a failed call is an ``unavailable`` answer. It does not
touch the engine or any Verdict.

    uv run python -m proofgraph.direct PACKET.json --record

makes one live call and writes PACKET.direct.json, the recording shown at the
scoreboard. That file says it is a recording, not a live answer.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from proofgraph.adapters.base import for_engine
from proofgraph.clients.muse import MuseClient, MuseError
from proofgraph.propose import _evidence
from proofgraph.schema import Case

_PROMPT = Path(__file__).resolve().parent.parent / "prompts" / "direct.md"
_LABELS = ("entailed", "refuted")
SYSTEM_NAME = "A · Direct Muse"


class DirectReply(BaseModel):
    """What Muse is asked to return: the label and the step-by-step evidence."""

    answer: str
    reasoning: str


class DirectAnswer(BaseModel):
    label: Literal["entailed", "refuted", "unavailable"]
    text: str
    raw: dict[str, Any]


def direct_answer(case: Case, client: MuseClient) -> DirectAnswer:
    """Ask Muse to answer ``entailed`` or ``refuted``. Never raises."""

    try:
        visible = for_engine(case)
        instructions = _PROMPT.read_text(encoding="utf-8").strip()
        evidence, file_ids = _evidence(visible, client)
        reply = client.structured(
            f"{instructions}\n\n{evidence}", DirectReply, file_ids=file_ids
        )
    except MuseError as exc:
        code = getattr(exc, "reason_code", type(exc).__name__)
        return DirectAnswer(label="unavailable", text=f"{code}: {exc}", raw={})
    except OSError as exc:
        return DirectAnswer(label="unavailable", text=f"UPLOAD_FAILED: {exc}", raw={})
    label = reply.answer.strip().lower()
    if label in _LABELS:
        return DirectAnswer(label=label, text=reply.reasoning, raw=reply.model_dump())
    # Strict parse: anything else keeps the model's words and counts as no answer.
    return DirectAnswer(
        label="unavailable",
        text=f"UNPARSEABLE_LABEL: {reply.answer}",
        raw=reply.model_dump(),
    )


def main(argv: list[str] | None = None, *, client: MuseClient | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    record = "--record" in args
    paths = [arg for arg in args if arg != "--record"]
    if len(paths) != 1:
        print("usage: python -m proofgraph.direct PACKET.json [--record]", file=sys.stderr)
        return 2
    packet = Path(paths[0])
    try:
        case = Case.model_validate(json.loads(packet.read_text(encoding="utf-8"))["case"])
    except (OSError, ValueError, KeyError, TypeError, ValidationError) as exc:
        print(f"could not read packet: {exc}", file=sys.stderr)
        return 2
    muse = client if client is not None else MuseClient()
    result = direct_answer(case, muse)
    print(result.label)
    print(result.text)
    if not record:
        return 0
    if result.label == "unavailable":
        print("not recorded: no usable answer", file=sys.stderr)
        return 1
    out = packet.with_name(packet.name.removesuffix(".json") + ".direct.json")
    out.write_text(
        json.dumps(
            {
                "kind": "recording",
                "note": "Recorded answer from one earlier call to Direct Muse. "
                "This is a recording, not a live answer.",
                "system": SYSTEM_NAME,
                "case_id": case.id,
                "model": muse.settings.muse_model,
                "recorded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "label": result.label,
                "text": result.text,
                "raw": result.raw,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"recorded {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
