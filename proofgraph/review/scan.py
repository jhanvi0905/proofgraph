"""Scan path: evidence from pages that have no text layer.

``transcribe`` sends the page image to Muse Spark and gets back lines with boxes.
``page_text`` turns those lines into the text the relation call reads. ``locate``
fuzzy-matches a relation quote to the transcribed lines and returns their boxes.

Model boxes are estimates (probe P1: they sit about a line low and the offset varies
by page). So a match is ``approximate``, never ``pinned``, and no match is ``unpinned``
with no box. The request holds the prompt and the image only: no gold or pack text.
"""

from __future__ import annotations

import hashlib
import tempfile
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel, Field

from proofgraph.clients.muse import MuseClient
from proofgraph.review.models import GRID, BoxStatus
from proofgraph.review.relate import PageText

MATCH_RATIO = 0.85
MIN_FUZZY_CHARS = 20  # a shorter quote must match exactly; a near match on a few letters means little
MAX_RUN = 3  # a quote may span up to this many consecutive lines

_PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "transcribe.md"


class Line(BaseModel):
    text: str
    box: list[float] = Field(min_length=4, max_length=4)


class Transcription(BaseModel):
    lines: list[Line]


@dataclass(frozen=True)
class ScanBox:
    status: BoxStatus  # "approximate" or "unpinned", never "pinned"
    boxes: list[list[int]] = field(default_factory=list)


def transcribe(png: bytes, muse: MuseClient) -> Transcription:
    prompt = _PROMPT.read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError("prompts/transcribe.md is empty")
    name = hashlib.sha256(png).hexdigest()[:12] + ".png"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(png)
        file_id = muse.upload_user_data(path)
    return muse.structured(prompt, Transcription, file_ids=[file_id])


def page_text(doc: str, page: int, transcription: Transcription) -> PageText:
    return PageText(doc, page, "\n".join(line.text for line in transcription.lines))


def locate(quote: str, transcription: Transcription) -> ScanBox:
    target = _normalise(quote)
    lines = [(_normalise(l.text), _clean_box(l.box)) for l in transcription.lines]
    if not target:
        return _NONE
    best_score, best_boxes = 0.0, None
    for size in range(1, MAX_RUN + 1):
        for i in range(len(lines) - size + 1):
            run = lines[i : i + size]
            score = _score(target, "".join(t for t, _ in run))
            if score > best_score:  # strict: a tie keeps the shorter run
                best_score, best_boxes = score, [b for _, b in run]
    if best_boxes is None or best_score < MATCH_RATIO:
        return _NONE
    boxes = [b for b in best_boxes if b is not None]
    return ScanBox("approximate", boxes) if boxes else _NONE


_NONE = ScanBox("unpinned")


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


def _score(quote: str, text: str) -> float:
    if not text:
        return 0.0
    if quote in text:
        return 1.0
    if len(quote) < MIN_FUZZY_CHARS:
        return 0.0
    n = len(quote)
    best = 0.0
    for size in sorted({max(1, round(n * f)) for f in (0.9, 1.0, 1.1)}):
        for start in range(max(1, len(text) - size + 1)):
            window = text[start : start + size]
            best = max(best, SequenceMatcher(None, quote, window).ratio())
    return best


def _clean_box(raw: list[float]) -> list[int] | None:
    x0, y0, x1, y1 = (max(0, min(GRID, round(v))) for v in raw)
    return [x0, y0, x1, y1] if x0 < x1 and y0 < y1 else None
