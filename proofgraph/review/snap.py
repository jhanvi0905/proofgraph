"""Snap a quote the model returned onto the words of a text-layer page.

``snap(quote, page_words)`` finds the quote among the page words and returns one
rectangle per printed line on the 0 to 1000 grid. Pure and deterministic: no model,
no network. No match means ``unpinned`` and no box; a box is never guessed.

Matching works on the letters and digits only, so case, punctuation, pipes in table
quotes, spacing, ligatures (NFKC) and hyphen line breaks do not matter. Some PDFs fuse
many printed words into one extracted "word", so a match may begin or end inside a word;
the rectangle then covers every whole word the match touches. If no exact match exists,
a window of whole words is accepted when its difflib ratio is at least ``FUZZY_RATIO``.
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from pydantic import TypeAdapter, ValidationError

from proofgraph.review.ingest import Word
from proofgraph.review.models import GRID, Box, BoxStatus

FUZZY_RATIO = 0.9
MIN_FUZZY_CHARS = 20  # shorter quotes must match exactly; a near match on a few letters means little
_LENGTH_SLACK = (0.8, 1.25)  # windows outside this length band cannot reach FUZZY_RATIO
PAD = 3  # grid units added around each line so the drawn box clears the glyphs
_SAME_LINE_OVERLAP = 0.5  # share of the shorter word height that must overlap vertically

_BOX = TypeAdapter(Box)


@dataclass(frozen=True)
class Snap:
    status: BoxStatus  # "pinned" or "unpinned"
    boxes: list[list[int]] = field(default_factory=list)


_UNPINNED = Snap("unpinned")


def _normalise(text: str) -> str:
    """Lower-case letters and digits only, after unicode compatibility folding."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


def snap(quote: str, page_words: Sequence[Word]) -> Snap:
    target = _normalise(quote)
    if not target:
        return _UNPINNED

    kept: list[Word] = []
    pieces: list[str] = []
    for word in page_words:
        piece = _normalise(word.text)
        if piece:
            kept.append(word)
            pieces.append(piece)
    if not kept:
        return _UNPINNED

    offsets = [0]  # offsets[i] is where word i starts in the page string
    for piece in pieces:
        offsets.append(offsets[-1] + len(piece))
    page = "".join(pieces)

    found = _exact(target, page) or _fuzzy(target, page, offsets)
    if found is None:
        return _UNPINNED
    first = bisect_right(offsets, found[0]) - 1
    last = bisect_right(offsets, found[1] - 1) - 1
    boxes = _line_boxes(_word_boxes(kept, offsets, first, last, found))
    return Snap("pinned", boxes) if boxes else _UNPINNED


def _exact(target: str, page: str) -> tuple[int, int] | None:
    """First occurrence, as a character range of the page string."""
    at = page.find(target)
    return None if at == -1 else (at, at + len(target))


def _word_boxes(
    kept: list[Word], offsets: list[int], first: int, last: int, found: tuple[int, int]
) -> list[list[int]]:
    """Boxes of the words the match touches. A match that begins or ends inside a fused
    word trims that word's box by the share of its letters outside the match."""
    boxes = [list(w.box) for w in kept[first : last + 1]]
    lead = found[0] - offsets[first]
    tail = offsets[last + 1] - found[1]
    first_box, last_box = list(boxes[0]), list(boxes[-1])
    first_width, last_width = first_box[2] - first_box[0], last_box[2] - last_box[0]
    first_letters = offsets[first + 1] - offsets[first]
    last_letters = offsets[last + 1] - offsets[last]
    left = first_box[0] + round(first_width * lead / first_letters)
    right = last_box[2] - round(last_width * tail / last_letters)
    if first == last:
        if left < right:  # both ends inside one word
            boxes[0][0], boxes[0][2] = left, right
        return boxes
    if left < first_box[2]:
        boxes[0][0] = left
    if right > last_box[0]:
        boxes[-1][2] = right
    return boxes


def _fuzzy(target: str, page: str, offsets: list[int]) -> tuple[int, int] | None:
    """Best whole-word window at or above FUZZY_RATIO, as a character range."""
    if len(target) < MIN_FUZZY_CHARS:
        return None
    low, high = (round(len(target) * f) for f in _LENGTH_SLACK)
    matcher = SequenceMatcher(None, autojunk=False)
    matcher.set_seq2(target)
    best, best_ratio = None, FUZZY_RATIO
    n_words = len(offsets) - 1
    for first in range(n_words):
        for last in range(first, n_words):
            size = offsets[last + 1] - offsets[first]
            if size > high:
                break
            if size < low:
                continue
            matcher.set_seq1(page[offsets[first] : offsets[last + 1]])
            if matcher.real_quick_ratio() < best_ratio or matcher.quick_ratio() < best_ratio:
                continue
            ratio = matcher.ratio()
            if ratio > best_ratio or (best is None and ratio >= FUZZY_RATIO):
                best, best_ratio = (offsets[first], offsets[last + 1]), ratio
    return best


def _line_boxes(boxes: list[list[int]]) -> list[list[int]]:
    """One rectangle per printed line, in reading order. Empty if any rectangle is invalid."""
    lines: list[list[int]] = []
    for x0, y0, x1, y1 in boxes:
        if lines and _same_line(lines[-1], (y0, y1)):
            line = lines[-1]
            line[0], line[1] = min(line[0], x0), min(line[1], y0)
            line[2], line[3] = max(line[2], x1), max(line[3], y1)
        else:
            lines.append([x0, y0, x1, y1])
    padded = [
        [max(0, x0 - PAD), max(0, y0 - PAD), min(GRID, x1 + PAD), min(GRID, y1 + PAD)]
        for x0, y0, x1, y1 in lines
    ]
    try:
        return [_BOX.validate_python(box) for box in padded]
    except ValidationError:
        return []


def _same_line(line: list[int], span: tuple[int, int]) -> bool:
    top, bottom = span
    overlap = min(line[3], bottom) - max(line[1], top)
    shorter = min(line[3] - line[1], bottom - top)
    return shorter > 0 and overlap >= _SAME_LINE_OVERLAP * shorter
