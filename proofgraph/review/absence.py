"""Absence receipt: an audit run AFTER the model, never fed back into it (rule B8).

It records which pages were read, which could not be, and what a plain lexical sweep
of the part's own terms finds on the read pages. A hit never changes a status by
itself: it only makes ``complete`` false, so ``part_status`` says ``cannot_tell``
and the UI can show why. Pure, deterministic, stdlib only: no index, no embeddings,
no top-k, no model, no network.

The failure that matters is a FALSE ``complete: true`` (it becomes a false ``not_found``).
Every rule below therefore errs toward MORE hits, MORE unread pages and LESS citing.

Normalisation, one rule at a time (see ``_fold``, ``_stem``, ``_number_keys``):
  1. casefold, Unicode compatibility decomposition, accents and invisible format
     characters dropped (ligature "ffi" -> "ffi", "e-acute" -> "e", zero-width space -> nothing),
     apostrophes dropped, every dash becomes a hyphen;
  2. a hyphen followed by a line break also yields an extra joined word ("dep-\\nosit" -> "deposit");
     any other hyphen is just a space ("well-known" -> "well known");
  3. English endings: a few irregular verbs/plurals, then ies/ied -> y, "-es" after s/x/z/ch/sh,
     plain "-s", "-ing", "-ed", a final "e" dropped, a doubled final consonant undoubled, final y -> i;
  4. numbers: commas dropped, "2:30" = "2.30", an hour 13..23 also keys as hour-12, a k/m/b/bn suffix
     or a following thousand/million/billion word scales the value (the unscaled value stays a key too),
     and spelled-out numbers ("two hundred fifty") become digits.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from proofgraph.review.models import Card, Receipt

MIN_WORD_LEN = 3
CONTEXT_CHARS = 40

# A page is READ only with real words: at least this many alphabetic words of >= 3 letters,
# and letters are at least this share of its non-space characters. Pure numeric tables may
# fall below the share; they are then "unread" (a human looks), which is the safe direction.
MIN_READABLE_WORDS = 3
MIN_ALPHA_SHARE = 0.4

# Only a card in one of these boxes can cite a hit (same rule as status._RED_BOXES).
CITING_BOXES = frozenset({"pinned", "located"})

_NUM = r"\d[\d,]*(?:[.:]\d+)?(?:(?:bn|[kmb])(?![^\W_]))?"
_TOKEN = re.compile(rf"({_NUM})|([^\W\d_][^\W_]*)")
_HYPHEN_BREAK = re.compile(r"-[^\S\n]*\n\s*")
_STOPWORDS = frozenset("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had
has have having he her here hers him his how i if in into is it its me more most my no nor not of
off on once only or other our out over own same she should so some such than that the their them
then there these they this those through to too under until up very was we were what when where
which while who whom why will with would you your
""".split())

_IRREGULAR = {
    "paid": "pay", "said": "say", "sold": "sell", "bought": "buy", "made": "make", "gave": "give",
    "took": "take", "held": "hold", "sent": "send", "left": "leave", "wrote": "write",
    "men": "man", "women": "woman", "children": "child",
}
_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate(
    "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALES = {"thousand": 10**3, "million": 10**6, "billion": 10**9}
_SUFFIX = {"k": 10**3, "m": 10**6, "b": 10**9, "bn": 10**9}


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
    offset: int  # character offset in the original page text
    context: str
    cited: bool  # covered by the quote of a pinned/located card on this page


@dataclass(frozen=True)
class AbsenceReceipt:
    pages_read: tuple[tuple[str, int], ...]
    unread: tuple[tuple[str, int], ...]
    terms: tuple[str, ...]
    hits: dict[str, tuple[SweepHit, ...]]
    uncited_hits: tuple[SweepHit, ...]
    complete: bool
    reason: str | None


@dataclass(frozen=True)
class _Tok:
    keys: tuple[str, ...]  # match keys; two tokens match when they share one
    raw: str  # folded surface form (numbers: canonical value)
    is_word: bool
    start: int  # offset in the ORIGINAL text
    lo: int = 0  # token index span this token covers
    hi: int = 0


# ----------------------------------------------------------------------------- normalisation

def _fold(text: str) -> tuple[str, list[int]]:
    """Folded text plus, for each folded character, its offset in the original."""
    out: list[str] = []
    origin: list[int] = []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch.casefold()):
            cat = unicodedata.category(c)
            if cat in ("Mn", "Cf") or c in "'\u2019\u02bc":
                continue
            out.append("-" if cat == "Pd" else c)
            origin.append(i)
    return "".join(out), origin


def _stem(word: str) -> str:
    w = _IRREGULAR.get(word, word)
    if len(w) > 4 and w.endswith(("ies", "ied")):
        w = w[:-3] + "y"
    elif len(w) > 4 and w.endswith(("ses", "xes", "zes", "ches", "shes")):
        w = w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        w = w[:-1]
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("eed"):
        w = w[:-1]  # "agreed" -> "agree", so the final-e rule below treats it like "agree"
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    if len(w) >= 3 and w.endswith("e"):
        w = w[:-1]
    if len(w) >= 3 and w[-1] == w[-2] and w[-1] not in "aeiou":
        w = w[:-1]
    if len(w) >= 3 and w.endswith("y"):
        w = w[:-1] + "i"
    return w


def _plain(d: Decimal) -> str:
    return format(d.normalize(), "f")


def _number_keys(raw: str) -> tuple[str, ...]:
    """Match keys for a numeric token such as '1,250.00', '2:30', '1.2m'."""
    m = re.fullmatch(r"([\d,]+(?:[.:]\d+)?)(bn|[kmb])?", raw)
    if not m:
        return (raw,)
    body, suffix = m.group(1), m.group(2)
    try:
        value = Decimal(body.replace(",", "").replace(":", "."))
    except InvalidOperation:
        return (raw,)
    keys = [_plain(value)]
    if suffix:
        keys.insert(0, _plain(value * _SUFFIX[suffix]))
    hm = re.fullmatch(r"(\d{1,2})[.:](\d\d)", body)
    if hm and 13 <= int(hm.group(1)) <= 23 and int(hm.group(2)) < 60:
        keys.append(_plain(Decimal(f"{int(hm.group(1)) - 12}.{hm.group(2)}")))
    return tuple(dict.fromkeys(keys))


def _spoken_step(total: int, cur: int, word: str) -> tuple[int, int] | None:
    """Advance a spelled-out number by one word, or None if the word cannot continue it."""
    if word in _ONES:
        v = _ONES[word]
        if cur % 100 == 0 or (v < 10 and cur % 100 >= 20 and cur % 10 == 0):
            return total, cur + v
        return None
    if word in _TENS:
        return (total, cur + _TENS[word]) if cur % 100 == 0 else None
    if word == "hundred":
        return (total, max(cur, 1) * 100) if cur < 100 else None
    if word in _SCALES:
        return total + max(cur, 1) * _SCALES[word], 0
    return None


def _tokenise(text: str) -> tuple[list[_Tok], list[_Tok], str]:
    """Main tokens, extra hyphen-break joined tokens, and the folded text."""
    folded, origin = _fold(text)
    raws: list[tuple[str, bool, int, int]] = []  # (text, is_word, folded start, folded end)
    for m in _TOKEN.finditer(folded):
        raws.append((m.group(), m.group(2) is not None, m.start(), m.end()))

    toks: list[_Tok] = []
    i = 0
    while i < len(raws):
        txt, is_word, s, e = raws[i]
        if is_word and (txt in _ONES or txt in _TENS or txt in _SCALES or txt == "hundred"):
            total, cur = 0, 0
            j = i
            step = _spoken_step(total, cur, txt)
            while step is not None:
                total, cur = step
                j += 1
                nxt = j
                if (nxt + 1 < len(raws) and raws[nxt][0] == "and" and raws[nxt + 1][1]
                        and (cur > 0 or total > 0) and cur % 100 == 0
                        and _spoken_step(total, cur, raws[nxt + 1][0]) is not None):
                    nxt += 1
                step = _spoken_step(total, cur, raws[nxt][0]) if nxt < len(raws) and raws[nxt][1] else None
                if step is not None:
                    j = nxt
            value = _plain(Decimal(total + cur))
            toks.append(_Tok((value,), value, False, origin[s], len(toks), len(toks)))
            i = j
            continue
        if is_word:
            toks.append(_Tok((_stem(txt),), txt, True, origin[s], len(toks), len(toks)))
        else:
            keys = _number_keys(txt)
            if i + 1 < len(raws) and raws[i + 1][0] in _SCALES and raws[i + 1][1]:
                d = Decimal(keys[-1] if "." in keys[-1] or keys[-1].isdigit() else keys[0])
                keys = (_plain(d * _SCALES[raws[i + 1][0]]), *keys)
                i += 1
            toks.append(_Tok(keys, keys[0], False, origin[s], len(toks), len(toks)))
        i += 1

    # Extra joined tokens for "dep-\nosit": the main tokens stay, the joined word is added.
    extras: list[_Tok] = []
    word_pos = [(k, t) for k, t in enumerate(toks) if t.is_word]
    spans = [(r[2], r[3]) for r in raws if r[1]]
    for (k1, t1), (k2, t2), (s1, e1), (s2, e2) in zip(word_pos, word_pos[1:], spans, spans[1:]):
        if k2 == k1 + 1 and _HYPHEN_BREAK.fullmatch(folded[e1:s2]):
            joined = t1.raw + t2.raw
            extras.append(_Tok((_stem(joined),), joined, True, t1.start, k1, k2))
    return toks, extras, folded


def _is_readable(folded: str, toks: Sequence[_Tok]) -> bool:
    words = sum(1 for t in toks if t.is_word and t.raw.isalpha() and len(t.raw) >= MIN_WORD_LEN)
    chars = [c for c in folded if not c.isspace()]
    if words < MIN_READABLE_WORDS or not chars:
        return False
    return sum(c.isalpha() for c in chars) / len(chars) >= MIN_ALPHA_SHARE


def _term_tokens(part_text: str) -> list[tuple[str, tuple[str, ...]]]:
    """(term, match keys) for the part's numbers and content words, first-appearance order."""
    toks, _, _ = _tokenise(part_text)
    seen: set[str] = set()
    out: list[tuple[str, tuple[str, ...]]] = []
    for t in toks:
        if t.is_word and (len(t.raw) < MIN_WORD_LEN or t.raw in _STOPWORDS):
            continue
        if seen.intersection(t.keys):
            continue
        seen.update(t.keys)
        out.append((t.raw, t.keys))
    return out


def sweep_terms(part_text: str) -> tuple[str, ...]:
    """Numbers and content words of the part, first-appearance order, deduplicated."""
    return tuple(term for term, _ in _term_tokens(part_text))


# ----------------------------------------------------------------------------- citing

def _matches(page_tok: _Tok, quote_tok: _Tok) -> bool:
    return bool(set(page_tok.keys) & set(quote_tok.keys))


def _covered(toks: Sequence[_Tok], cards: Sequence[Card]) -> set[int]:
    """Token indices covered by each card's OWN occurrence of its quote (first unused one)."""
    covered: set[int] = set()
    used: set[int] = set()
    quoted = [(c, _tokenise(c.quote)[0]) for c in cards]
    quoted.sort(key=lambda cq: (tuple(t.keys for t in cq[1]), cq[0].id))
    for _, q in quoted:
        n = len(q)
        if not n:
            continue
        starts = [i for i in range(len(toks) - n + 1)
                  if all(_matches(toks[i + k], q[k]) for k in range(n))]
        if not starts:
            continue
        pick = next((i for i in starts if i not in used), starts[0])
        used.add(pick)
        covered.update(range(pick, pick + n))
    return covered


# ----------------------------------------------------------------------------- receipt

def build_receipt(part_text: str, pages: Sequence[AbsencePage], cards: Iterable[Card]) -> AbsenceReceipt:
    cards = list(cards)
    term_keys = _term_tokens(part_text)
    terms = tuple(t for t, _ in term_keys)
    wanted = {k: t for t, keys in term_keys for k in keys}

    scanned: list[tuple[AbsencePage, list[_Tok], list[_Tok]]] = []
    read: dict[tuple[str, int], None] = {}
    unread: dict[tuple[str, int], None] = {}
    for p in pages:
        key = (p.doc, p.page)
        toks, extras, folded = _tokenise(p.text) if p.text else ([], [], "")
        if p.text and _is_readable(folded, toks):
            read[key] = None
            scanned.append((p, toks, extras))
        else:
            unread[key] = None
    for key in unread:  # a page that is unreadable in any copy stays unread
        read.pop(key, None)

    hits: dict[str, list[SweepHit]] = {t: [] for t in terms}
    uncited: list[SweepHit] = []
    for p, toks, extras in scanned:
        citing = [c for c in cards if (c.doc, c.page) == (p.doc, p.page)
                  and c.relation != "set_aside" and c.box_status in CITING_BOXES]
        covered = _covered(toks, citing)
        for t in sorted(toks + extras, key=lambda t: (t.start, t.lo, t.hi, t.keys)):
            key = next((k for k in t.keys if k in wanted), None)
            if key is None:
                continue
            lo, hi = max(0, t.start - CONTEXT_CHARS), t.start + CONTEXT_CHARS
            context = " ".join(p.text[lo:hi].split())
            cited = all(i in covered for i in range(t.lo, t.hi + 1))
            hit = SweepHit(wanted[key], p.doc, p.page, t.start, context, cited)
            hits[wanted[key]].append(hit)
            if not cited:
                uncited.append(hit)

    uncited.sort(key=lambda h: (h.doc, h.page, h.offset, h.term))
    unpinned = [c for c in cards if c.relation != "set_aside" and c.box_status not in CITING_BOXES]
    reasons: list[str] = []
    if not terms:
        reasons.append("no searchable terms in the claim part, so absence cannot be shown")
    if not read:
        reasons.append("no page was read")
    if unread:
        reasons.append(f"{len(unread)} page(s) unread")
    if unpinned:
        reasons.append(f"{len(unpinned)} card(s) could not be pinned to the page text: "
                       "the model saw something we could not locate")
    if uncited:
        reasons.append(f"{len(uncited)} uncited sweep hit(s) on read pages")
    return AbsenceReceipt(
        pages_read=tuple(read), unread=tuple(unread), terms=terms,
        hits={t: tuple(h) for t, h in hits.items() if h},
        uncited_hits=tuple(uncited), complete=not reasons, reason="; ".join(reasons) or None,
    )


def to_model_receipt(receipt: AbsenceReceipt) -> Receipt:
    """The saved-review ``models.Receipt``. Page tuples are already unique, so counts do not double.

    ``unread`` loses the document (the model type holds page numbers only); ``uncited_hits``
    becomes one readable line per hit.
    """
    return Receipt(
        pages_read=len(set(receipt.pages_read)),
        unread=[page for _, page in dict.fromkeys(receipt.unread)],
        terms=list(receipt.terms),
        uncited_hits=[f"{h.doc} p{h.page} @{h.offset} {h.term}: {h.context}" for h in receipt.uncited_hits],
    )
