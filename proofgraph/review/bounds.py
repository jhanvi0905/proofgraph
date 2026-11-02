"""Deterministic quote hygiene: widen a quote to its sentence, clause or list item, and reject
fragments that cannot carry a claim. Pure code: no model, no network.

``expand_quote`` finds the quote in the page text with the same letters-and-digits matching
snap uses, then extends left and right to the nearest real sentence end (. ! ? ;) or to the
next list item. A dot that follows an abbreviation, a section number or a list enumerator is
not a sentence end. An item that opens a list also takes the line before it when that line
ends in a colon (the lead-in). Anything it cannot place exactly, or that would pass ``cap``
characters, comes back unchanged.

Behind PROOFGRAPH_QUOTE_BOUNDS=1; see ``enabled``.
"""

from __future__ import annotations

import os
import re
import unicodedata

CAP = 400
MIN_WORDS = 6

_ENUM = re.compile(
    r"[ \t]*(?:\(?[A-Za-z]\)|\(?\d{1,2}\)|\(?[ivxlc]{1,5}\)|[A-Za-z]\.(?=\s)|\d{1,2}\.(?=\s)"
    r"|[ivxlc]{1,5}\.(?=\s)|[•\-*]\s)\s*"
)
_ABBREV = {
    "sec", "no", "nos", "art", "para", "fig", "vs", "inc", "ltd", "co", "corp", "mr", "mrs", "ms",
    "dr", "st", "approx", "cl", "ch", "eg", "ie", "e.g", "i.e", "u.s", "cf", "al", "p", "pp", "ex",
}
_REF_WORDS = {"section", "sec", "article", "art", "clause", "paragraph", "para", "no", "nos", "item", "page"}
_CLOSERS = "\"')]”’"
_MONTHS = (
    "jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec|january|february|march|april|june|july|"
    "august|september|october|november|december"
)
_DATEISH = re.compile(rf"(?:\d+|{_MONTHS}|st|nd|rd|th|[\W_])+", re.I)
_LABEL = re.compile(
    r"(?:issued|dated?|effective|revised|version|page|ref(?:erence)?|no|number|filed|signed)\b[^:\n]{0,20}:\s*",
    re.I,
)


def enabled() -> bool:
    return os.environ.get("PROOFGRAPH_QUOTE_BOUNDS") == "1"


def _fold(text: str) -> list[tuple[str, int]]:
    """Letters and digits only (NFKC, casefolded), each with its index in ``text``."""
    out: list[tuple[str, int]] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch).casefold():
            if c.isalnum():
                out.append((c, i))
    return out


def _locate(quote: str, page_text: str) -> tuple[int, int] | None:
    target = "".join(c for c, _ in _fold(quote))
    if not target:
        return None
    folded = _fold(page_text)
    page = "".join(c for c, _ in folded)
    at = page.find(target)
    if at == -1:
        return None
    return folded[at][1], folded[at + len(target) - 1][1] + 1


def _is_terminator(text: str, p: int) -> bool:
    ch = text[p]
    if ch not in ".!?;":
        return False
    q = p + 1
    while q < len(text) and text[q] in _CLOSERS:
        q += 1
    if q < len(text) and not text[q].isspace():
        return False  # 5.2, $75.00, e.g.
    if ch == ";":
        return True
    nxt = q
    while nxt < len(text) and text[nxt].isspace():
        nxt += 1
    if ch == "." and nxt < len(text) and text[nxt].islower():
        return False
    line_start = text.rfind("\n", 0, p) + 1
    token = re.search(r"[^\s(]*$", text[line_start:p]).group(0)  # type: ignore[union-attr]
    if ch != ".":
        return True
    low = token.lower().strip(".")
    if low in _ABBREV or (len(token) == 1 and token.isalpha()):
        return False
    if text[line_start:p].strip() == token and len(token) <= 3:
        return False  # a list enumerator at the start of its line
    if re.fullmatch(r"[\d.]+", token):
        before = text[line_start:p][: -len(token)].split()
        return not (before and before[-1].lower().strip(".:") in _REF_WORDS)
    return True


def _item_starts(text: str) -> list[int]:
    """Index of the start of every line that opens a list item."""
    starts, at = [], 0
    for line in text.split("\n"):
        if _ENUM.match(line):
            starts.append(at)
        at += len(line) + 1
    return starts


def _left(text: str, start: int, items: list[int], cap: int) -> int:
    bound = 0
    for p in range(start - 1, max(-1, start - cap - 1), -1):
        if _is_terminator(text, p):
            bound = p + 1
            break
    else:
        bound = text.rfind("\n", 0, start) + 1  # no sentence end in reach: the line
    item = max((s for s in items if s <= start), default=0)
    if item >= bound and item in items:
        bound = item
        prev_end = text.rfind("\n", 0, bound - 1) if bound else -1
        prev = text[prev_end + 1 : bound].strip() if bound else ""
        if prev.endswith(":"):
            bound = prev_end + 1  # the lead-in line
    while bound < start and text[bound].isspace():
        bound += 1
    return bound


def _right(text: str, end: int, items: list[int], cap: int) -> int:
    limit = min(len(text), end + cap + 1)
    for p in range(end - 1, limit):
        if _is_terminator(text, p):
            return p + 1
        if p + 1 in items:
            return p
    nl = text.find("\n", end)
    return len(text) if nl == -1 else nl  # no sentence end in reach: the line


def _squash(text: str) -> str:
    return " ".join(text.split())


def expand_quote(quote: str, page_text: str, cap: int = CAP) -> str:
    """The sentence, clause or list item around ``quote``; ``quote`` itself if it cannot be placed
    exactly or the result would pass ``cap`` characters."""
    found = _locate(quote, page_text)
    if found is None:
        return quote
    items = _item_starts(page_text)
    start = _left(page_text, found[0], items, cap)
    end = _right(page_text, found[1], items, cap)
    wide = _squash(page_text[start:end])
    return wide if 0 < len(wide) <= cap else quote


def reject_quote(quote: str) -> bool:
    """True for a quote that cannot carry a claim: empty, too short, or a bare heading, date or label."""
    text = quote.strip()
    if not text or len(text.split()) < MIN_WORDS:
        return True
    if text.endswith(":"):
        return True
    if _DATEISH.fullmatch(text):
        return True
    label = _LABEL.match(text)
    if label and _DATEISH.fullmatch(text[label.end():]):
        return True
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and all(c.isupper() for c in letters) and len(text.split()) <= 12
