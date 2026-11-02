"""Candidate units: a bounded, deterministic list of page passages that share a term with the claim part.

Pure, stdlib only: no model, no index, no embeddings, no ranking. It reuses the absence sweep's own term
logic (``absence._term_tokens`` and ``absence._tokenise``: stemming, number keys, spelled-out numbers,
hyphen-break joins), so a unit is a candidate exactly when the sweep would report a hit inside it.

A page is cut into units. A unit is one of:
  * ``list``     a list item or numbered clause ("a.", "(i)", "7.", "5.2 Title") with its wrapped lines;
  * ``row``      one line that looks like a table row (a separator, or mostly numeric tokens);
  * ``sentence`` one sentence of ordinary prose (abbreviations such as "Sec." and "e.g." do not end one;
                 a section number such as "5.2" never does).
Unit text is an exact substring of the page text. A row's header line is kept in ``context``, not in ``text``.

Coverage: before the cap, every unit that holds a sweep hit is a candidate. Over the cap, the first unit for
each (term, document) pair is kept first, then the rest fill in document order; ``truncated`` says so.
Cue words ("except", "unless", "subject to", "not", "only", "notwithstanding", "provided that") are recorded
on a candidate; since a candidate already shares a term, a cue never adds a unit by itself.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from proofgraph.review.absence import _term_tokens, _tokenise

CANDIDATE_RULE_VERSION = "candidates-1"
DEFAULT_CAP = 40
CONTEXT_MAX = 120

_ABBREVIATIONS = frozenset("""
mr mrs ms dr prof sr jr st sec secs no nos art arts fig figs ex e.g i.e eg ie inc ltd co corp llc vs v
cf approx est dept para paras pp p vol ch cl ss sched ref jan feb mar apr jun jul aug sep sept oct nov dec
""".split())
_CUE = re.compile(r"\b(except|unless|subject to|not|only|notwithstanding|provided that)\b", re.IGNORECASE)
_LIST_MARKER = re.compile(
    r"^\s*(?:\((?:[a-zA-Z]|[ivxlcdm]+|\d{1,3})\)|[a-z]\.|\d{1,3}[.)]|\d{1,3}(?:\.\d{1,3})+\.?)\s+\S")
_SEPARATOR = re.compile(r"\||\t| {2,}")
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s+(?=[\"'(\[]?[A-Z0-9])")


class PageLike(Protocol):
    doc: str
    page: int
    text: str | None


@dataclass(frozen=True)
class Candidate:
    id: str
    doc: str
    page: int
    text: str  # exact substring of the page text
    offset: int  # character offset of ``text`` in the page text
    kind: str  # "sentence", "list" or "row"
    terms: tuple[str, ...]  # claim terms found in the unit, first-appearance order
    cues: tuple[str, ...] = ()
    context: str = ""  # a table row's header line; empty otherwise


@dataclass(frozen=True)
class CandidateSet:
    rule_version: str
    candidates: tuple[Candidate, ...]
    total_matched: int
    kept: int
    truncated: bool
    cap: int


@dataclass(frozen=True)
class _Unit:
    start: int
    end: int
    kind: str
    context: str = ""


# ----------------------------------------------------------------------------- splitting

def _is_row(line: str) -> bool:
    tokens = line.split()
    if len(tokens) < 2:
        return False
    if _SEPARATOR.search(line.strip()):
        return True
    digits = sum(any(c.isdigit() for c in t) for t in tokens)
    return len(tokens) >= 3 and digits * 2 >= len(tokens)


def _sentences(text: str, base: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for m in _SENTENCE_END.finditer(text):
        stop = m.start() + 1
        while stop < m.end() and text[stop] in "\"')]":
            stop += 1
        if text[m.start()] == ".":
            word = re.search(r"(\S+)$", text[: m.start() + 1])
            w = word.group(1).lower().strip("\"'([") if word else ""
            if w.rstrip(".") in _ABBREVIATIONS or w in _ABBREVIATIONS or re.fullmatch(r"[a-z]\.", w):
                continue
        spans.append((base + start, base + stop))
        start = m.end()
    spans.append((base + start, base + len(text)))
    return spans


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _units(text: str) -> list[_Unit]:
    units: list[_Unit] = []
    block: tuple[int, int, str] | None = None  # start, end, kind
    header = ""  # the non-row text line just before a run of rows
    pos = 0

    def close() -> None:
        nonlocal block
        if block is None:
            return
        s, e, kind = block
        block = None
        s, e = _trim(text, s, e)
        if s >= e:
            return
        if kind == "list":
            units.append(_Unit(s, e, "list"))
        else:
            for a, b in _sentences(text[s:e], s):
                a, b = _trim(text, a, b)
                if a < b:
                    units.append(_Unit(a, b, "sentence"))

    for line in text.split("\n"):
        s, e = pos, pos + len(line)
        pos = e + 1
        if not line.strip():
            close()
            header = ""
        elif _is_row(line):
            close()
            a, b = _trim(text, s, e)
            units.append(_Unit(a, b, "row", header[:CONTEXT_MAX]))
        elif _LIST_MARKER.match(line):
            close()
            block = (s, e, "list")
            header = line.strip()
        elif block is not None:
            block = (block[0], e, block[2])
            header = line.strip()
        else:
            block = (s, e, "para")
            header = line.strip()
    close()
    return units


# ----------------------------------------------------------------------------- build

def build_candidates(part_text: str, pages: Sequence[PageLike], cap: int = DEFAULT_CAP) -> CandidateSet:
    wanted = {k: t for t, keys in _term_tokens(part_text) for k in keys}
    doc_order: dict[str, int] = {}
    for p in pages:
        doc_order.setdefault(p.doc, len(doc_order))

    found: list[tuple[tuple[int, int, int], str, int, _Unit, tuple[str, ...]]] = []
    seen: set[tuple[str, int, int]] = set()
    for p in pages:
        if not p.text or not wanted:
            continue
        toks, extras, _ = _tokenise(p.text)
        units = _units(p.text)
        starts = [u.start for u in units]
        by_unit: dict[int, list[str]] = {}
        for t in sorted(toks + extras, key=lambda t: (t.start, t.lo, t.hi, t.keys)):
            key = next((k for k in t.keys if k in wanted), None)
            if key is None:
                continue
            i = _unit_index(starts, units, t.start)
            if i is not None:
                by_unit.setdefault(i, []).append(wanted[key])
        for i, terms in by_unit.items():
            u = units[i]
            ident = (p.doc, p.page, u.start)
            if ident in seen:
                continue
            seen.add(ident)
            found.append(((doc_order[p.doc], p.page, u.start), p.doc, p.page, u, tuple(dict.fromkeys(terms))))
    found.sort(key=lambda f: f[0])

    chosen = _apply_cap(found, cap)
    page_text = {(p.doc, p.page): p.text for p in pages if p.text}
    out = []
    for n, (_, doc, page, u, terms) in enumerate((found[i] for i in chosen), start=1):
        text = page_text[(doc, page)][u.start:u.end]
        cues = tuple(dict.fromkeys(m.group().lower() for m in _CUE.finditer(text)))
        out.append(Candidate(f"k{n}", doc, page, text, u.start, u.kind, terms, cues, u.context))
    return CandidateSet(CANDIDATE_RULE_VERSION, tuple(out), len(found), len(out), len(out) < len(found), cap)


def _unit_index(starts: list[int], units: list[_Unit], offset: int) -> int | None:
    lo, hi = 0, len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= offset:
            lo = mid + 1
        else:
            hi = mid
    i = lo - 1
    return i if i >= 0 and offset < units[i].end else None


def _apply_cap(found: list[Any], cap: int) -> list[int]:
    if len(found) <= cap:
        return list(range(len(found)))
    keep: list[int] = []
    covered: set[tuple[str, str]] = set()
    for i, (_, doc, _page, _u, terms) in enumerate(found):
        if len(keep) >= cap:
            break
        pairs = {(t, doc) for t in terms}
        if pairs - covered:
            keep.append(i)
            covered |= pairs
    chosen = set(keep)
    for i in range(len(found)):
        if len(chosen) >= cap:
            break
        chosen.add(i)
    return sorted(chosen)
