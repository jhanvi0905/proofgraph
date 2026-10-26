"""Blind wording check. One quote, one statement, one Muse call.

The prompt is ``prompts/blind_wording.md``. ``MuseClient.structured`` validates
the reply and makes the one JSON repair. A failure raises ``CheckerError``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from proofgraph.clients.muse import ExtractionFailed, MuseClient, MuseError

WordingLabel = Literal["entails", "contradicts", "not_mentioned"]
_PASSAGE = "<<one quote or one clause>>"
_SENTENCE = "<<one plain sentence>>"
_PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "blind_wording.md"


class CheckerError(Exception):
    """The blind checker failed before it could return a label."""

    def __init__(self, message: str, *, reason_code: str = "CHECKER_UNAVAILABLE") -> None:
        super().__init__(message)
        self.reason_code = reason_code


class WordingAnswer(BaseModel):
    answer: WordingLabel


def blind_wording(quote: str, statement: str) -> WordingLabel:
    """Ask Muse whether the quote entails, contradicts, or does not mention the statement."""

    _require_text("quote", quote)
    _require_text("statement", statement)
    client = MuseClient()
    try:
        parsed = client.structured(_render(quote, statement), WordingAnswer)
    except ExtractionFailed as exc:
        raise CheckerError(str(exc), reason_code=exc.reason_code) from exc
    except MuseError as exc:
        raise CheckerError(str(exc)) from exc
    return parsed.answer


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise CheckerError(f"{name} must be a non-empty string")


def _render(quote: str, statement: str) -> str:
    try:
        template = _PROMPT.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CheckerError("could not read prompts/blind_wording.md") from exc
    if template == "":
        raise CheckerError("prompts/blind_wording.md is empty")
    passage_at = template.find(_PASSAGE)
    sentence_at = template.find(_SENTENCE)
    if passage_at < 0 or sentence_at < passage_at or template.count(_PASSAGE) != 1:
        raise CheckerError("prompts/blind_wording.md is missing the passage slot")
    if template.count(_SENTENCE) != 1:
        raise CheckerError("prompts/blind_wording.md is missing the statement slot")
    return (
        template[:passage_at]
        + quote
        + template[passage_at + len(_PASSAGE) : sentence_at]
        + statement
        + template[sentence_at + len(_SENTENCE) :]
    )
