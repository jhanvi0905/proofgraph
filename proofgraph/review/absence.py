"""Absence receipt: an audit run AFTER the model, never fed back into it (rule B8).

It records which pages were read, which could not be, and what a plain lexical sweep
of the part's own terms finds on the read pages. A hit never changes a status by
itself: it only makes ``complete`` false, so ``part_status`` says ``cannot_tell``
and the UI can show why. Pure, deterministic, stdlib only: no index, no embeddings,
no top-k, no model, no network.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from proofgraph.review.models import Card

MIN_WORD_LEN = 3
CONTEXT_CHARS = 40

_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?|[A-Za-z][A-Za-z0-9'-]*")
_STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had
has have having he her here hers him his how i if in into is it its me more most my no nor not of
off on once only or other our out over own same she should so some such than that the their them
then there these they this those through to too under until up very was we were what when where
which while who whom why will with would you your
""".split())


@dataclass(frozen=True)
class AbsencePage:
    """One page as the audit sees it. ``text`` is None when it could not be read."""

    doc: str
    page: int
    text: str | None


@dataclass(frozen=True)
class SweepHit:
    term: str
    doc: str
    page: int
    offset: int  # character offset in the page text
    context: str
    cited: bool  # covered by the quote of a card on this page


@dataclass(frozen=True)
class AbsenceReceipt:
    pages_read: tuple[tuple[str, int], ...]
    unread: tuple[tuple[str, int], ...]
    terms: tuple[str, ...]
    hits: dict[str, tuple[SweepHit, ...]]
    uncited_hits: tuple[SweepHit, ...]
    complete: bool
    reason: str | None


def _norm(token: str) -> str:
    t = token.lower()
    if t[0].isdigit():
        t = t.replace(",", "")
        if "." in t:
            t = t.rstrip("0").rstrip(".")
        return t.lstrip("0") or "0" if t.isdigit() else t
    if len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    return t


def _tokens(text: str) -> list[tuple[str, int]]:
    return [(_norm(m.group()), m.start()) for m in _TOKEN.finditer(text)]


def sweep_terms(part_text: str) -> tuple[str, ...]:
    """Numbers and content words of the part, first-appearance order, deduplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for m in _TOKEN.finditer(part_text):
        raw = m.group().lower()
        if not raw[0].isdigit() and (len(raw) < MIN_WORD_LEN or raw in _STOPWORDS):
            continue
        key = _norm(m.group())
        if key not in seen:
            seen.add(key)
            out.append(raw.replace(",", "") if raw[0].isdigit() else raw)
    return tuple(out)


def _covered(tokens: list[tuple[str, int]], quotes: list[str]) -> set[int]:
    """Token indices inside any card quote found verbatim (after normalising) in the page."""
    words = [t for t, _ in tokens]
    covered: set[int] = set()
    for q in quotes:
        qt = [t for t, _ in _tokens(q)]
        n = len(qt)
        if not n:
            continue
        for i in range(len(words) - n + 1):
            if words[i : i + n] == qt:
                covered.update(range(i, i + n))
    return covered


def build_receipt(part_text: str, pages: Sequence[AbsencePage], cards: Iterable[Card]) -> AbsenceReceipt:
    cards = list(cards)
    terms = sweep_terms(part_text)
    wanted = {_norm(t): t for t in terms}
    read = tuple((p.doc, p.page) for p in pages if p.text and p.text.strip())
    unread = tuple((p.doc, p.page) for p in pages if not (p.text and p.text.strip()))

    hits: dict[str, list[SweepHit]] = {t: [] for t in terms}
    uncited: list[SweepHit] = []
    for p in pages:
        if not (p.text and p.text.strip()):
            continue
        toks = _tokens(p.text)
        covered = _covered(toks, [c.quote for c in cards if (c.doc, c.page) == (p.doc, p.page)])
        for i, (tok, off) in enumerate(toks):
            if tok not in wanted:
                continue
            lo, hi = max(0, off - CONTEXT_CHARS), off + CONTEXT_CHARS
            context = " ".join(p.text[lo:hi].split())
            hit = SweepHit(wanted[tok], p.doc, p.page, off, context, i in covered)
            hits[wanted[tok]].append(hit)
            if not hit.cited:
                uncited.append(hit)

    uncited.sort(key=lambda h: (h.doc, h.page, h.offset, h.term))
    reason = None
    if not terms:
        reason = "no searchable terms in the claim part, so absence cannot be shown"
    elif not read:
        reason = "no page was read"
    elif unread:
        reason = f"{len(unread)} page(s) unread"
    elif uncited:
        reason = f"{len(uncited)} uncited sweep hit(s) on read pages"
    return AbsenceReceipt(
        pages_read=read, unread=unread, terms=terms,
        hits={t: tuple(h) for t, h in hits.items() if h},
        uncited_hits=tuple(uncited), complete=reason is None, reason=reason,
    )
