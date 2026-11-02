"""Date inference and ordering for candidate passages. Pure, stdlib only, deterministic.

A passage's date is the first full date in its own text (after removing phrases that cite another
document, such as "letter dated <date>"); else its document's header date; else the earliest date on the
document's first page; else undated. Numeric d/m/y dates are ambiguous and are never read.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from proofgraph.review.candidates import Candidate

_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
_MONTH = "|".join(sorted([*_MONTHS, *(m[:3] for m in _MONTHS), "sept"], key=len, reverse=True))
_DATE = (rf"(?:(?P<m1>{_MONTH})\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y1>\d{{4}})"
         rf"|(?P<d2>\d{{1,2}})(?:st|nd|rd|th)?\s+(?P<m2>{_MONTH})\.?,?\s+(?P<y2>\d{{4}})"
         r"|(?P<y3>\d{4})-(?P<n3>\d{2})-(?P<d3>\d{2}))")
_DATE_RE = re.compile(rf"\b{_DATE}\b", re.IGNORECASE)
_DOC_NOUN = "letter|notice|email|memo|memorandum|agreement|order|amendment|announcement"
_REF_RE = re.compile(rf"\b(?P<phrase>(?:{_DOC_NOUN})\b[^\n]{{0,40}}?\bdated\s+(?P<date>{_DATE}))",
                     re.IGNORECASE)
_HEADER_RE = re.compile(rf"\b(?:adopted|dated|effective|date)\s*:\s*{_DATE}", re.IGNORECASE)
HEADER_SPAN = 600


@dataclass(frozen=True)
class Dated:
    date: str | None  # ISO yyyy-mm-dd
    source: str  # "in passage", "document header", "first page" or "undated"


@dataclass(frozen=True)
class Ref:
    phrase: str
    date: str
    cited_in: str
    status: str  # "supplied" or "not supplied"


def _iso(m: re.Match[str]) -> str | None:
    g = m.groupdict()
    if g["y1"]:
        y, mo, d = g["y1"], _MONTHS[_full(g["m1"])], g["d1"]
    elif g["y2"]:
        y, mo, d = g["y2"], _MONTHS[_full(g["m2"])], g["d2"]
    else:
        y, mo, d = g["y3"], g["n3"], g["d3"]
    try:
        return date(int(y), int(mo), int(d)).isoformat()
    except ValueError:
        return None


def _full(month: str) -> str:
    low = month.lower()
    return next(m for m in _MONTHS if m.startswith(low[:3]))


def _first_date(text: str) -> str | None:
    return next((d for m in _DATE_RE.finditer(text) if (d := _iso(m))), None)


def _earliest_date(text: str) -> str | None:
    return min((d for m in _DATE_RE.finditer(text) if (d := _iso(m))), default=None)


def _header_date(text: str) -> str | None:
    m = _HEADER_RE.search(text[:HEADER_SPAN])
    return _iso(m) if m else None


def infer_dates(cands: Iterable[Candidate], page_text: Mapping[tuple[str, int], str]) -> dict[str, Dated]:
    out: dict[str, Dated] = {}
    for c in cands:
        first_page = page_text.get((c.doc, 1), "")
        for iso, source in (
            (_first_date(_REF_RE.sub(" ", c.text)), "in passage"),
            (_header_date(first_page), "document header"),
            (_earliest_date(first_page), "first page"),
        ):
            if iso:
                out[c.id] = Dated(iso, source)
                break
        else:
            out[c.id] = Dated(None, "undated")
    return out


def order(items: Sequence[tuple[Candidate, Dated]]) -> list[tuple[Candidate, Dated]]:
    """Sort by (date, document order, page, offset); undated last. Document order is first appearance."""
    rank: dict[str, int] = {}
    for c, _ in items:
        rank.setdefault(c.doc, len(rank))
    return sorted(items, key=lambda it: (it[1].date is None, it[1].date or "", rank[it[0].doc],
                                         it[0].page, it[0].offset))


def referenced_documents(quotes: Iterable[tuple[str, str]], headers: Mapping[str, str | None]) -> list[Ref]:
    """Documents cited by phrase and date in ``(cited_in, quote)`` pairs; flag those no header date matches."""
    have = {d for d in headers.values() if d}
    refs = []
    for cited_in, quote in quotes:
        for m in _REF_RE.finditer(quote):
            iso = _first_date(m.group("date"))
            if iso:
                refs.append(Ref(m.group("phrase"), iso, cited_in, "supplied" if iso in have else "not supplied"))
    return refs
