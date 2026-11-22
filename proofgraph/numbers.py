"""Numbers: raw amount strings -> integer minor units. A rule table, never a model.

No floats, no arithmetic beyond scaling, no FX. A string the rules do not
cover returns ParseFailure. It is never guessed at, so "US$10,000,0O0" (the
letter O) fails loudly instead of being repaired. A missing currency is not a
failure: it is returned as currency=None ("not stated", D1).
"""

from __future__ import annotations

import re

from proofgraph.schema import Amount, Assertion, Basis, Comparison, ComparisonReason, Currency, ParseFailure, ValueComparison

_CURRENCY = [  # (pattern, currency); first match wins
    (re.compile(r"^\s*(?:US\$|USD\s*|\$)"), Currency.USD),
]
_NIL_RE = re.compile(r"^(nil|none|zero)$", re.I)
_NUM_RE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(m|mm|million|k|thousand|b|billion)?$", re.I)
_SCALE = {"m": 6, "mm": 6, "million": 6, "k": 3, "thousand": 3, "b": 9, "billion": 9}


_CURRENCY_TOKEN_RE = re.compile(r"US\$|USD|\$")


def numeral(text: str) -> int | None:
    """The amount written in `text` as integer minor units, with currency tokens dropped.

    Returns None when there is no numeral: NIL, words, or anything the rule table
    does not cover. The same rules apply to every document.
    """
    m = _NUM_RE.match(_CURRENCY_TOKEN_RE.sub("", text).strip())
    if m is None:
        return None
    whole, frac, scale = m.group(1).replace(",", ""), m.group(2) or "", (m.group(3) or "").lower()
    exp = _SCALE.get(scale, 0)
    if exp and len(frac) > exp:
        return None
    return int(whole + frac) * 10 ** (exp + 2 - len(frac))  # integer arithmetic only


def compare_values(a: str, b: str) -> ValueComparison:
    """Equal or different on numerals alone; not_comparable if either side has none."""
    na, nb = numeral(a), numeral(b)
    if na is None or nb is None:
        return ValueComparison.NOT_COMPARABLE
    return ValueComparison.EQUAL if na == nb else ValueComparison.DIFFERENT


def parse_amount(raw: str) -> Amount | ParseFailure:
    s = raw.strip()
    currency = None
    for pat, cur in _CURRENCY:
        m = pat.match(s)
        if m:
            currency, s = cur, s[m.end():].strip()
            break
    if _NIL_RE.match(s):
        return Amount(minor_units=0, decimals=0, currency=currency)
    m = _NUM_RE.match(s)
    if m is None:
        return ParseFailure(raw=raw, reason="unparseable")
    whole, frac, scale = m.group(1).replace(",", ""), m.group(2) or "", (m.group(3) or "").lower()
    exp = _SCALE.get(scale, 0)
    if exp and len(frac) > exp:
        return ParseFailure(raw=raw, reason="fraction_finer_than_scale")
    # integer arithmetic only: whole.frac * 10^exp * 100
    digits = int(whole + frac)
    minor = digits * 10 ** (exp + 2 - len(frac))
    return Amount(minor_units=minor, decimals=0 if exp else len(frac), currency=currency)


_AMOUNT_IN_TEXT_RE = re.compile(r"(?:US\$|USD\s*|\$)?\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|(?:US\$|USD\s*|\$)\d+(?:\.\d{1,2})?")
_BASIS_LEXICON = [  # (pattern, basis); matched inside one citation only
    (re.compile(r"\beach\s+claim\b", re.I), Basis.EACH_CLAIM),
    (re.compile(r"\bany\s+one\s+claim\b", re.I), Basis.ANY_ONE_CLAIM),
    (re.compile(r"\beach\s+loss\b", re.I), Basis.EACH_LOSS),
    (re.compile(r"\beach\s+occurrence\b", re.I), Basis.EACH_OCCURRENCE),
    (re.compile(r"\bper\s+person\b", re.I), Basis.PER_PERSON),
    (re.compile(r"\bin\s+the\s+aggregate\b", re.I), Basis.AGGREGATE),
]


def find_amount(text: str) -> tuple[int, int] | None:
    """Offsets of the first amount written in `text` (with its currency marker), or None."""
    m = _AMOUNT_IN_TEXT_RE.search(text)
    return (m.start(), m.end()) if m else None


def find_basis(text: str) -> tuple[Basis, int, int] | None:
    """The basis phrase written in `text`, or None if it states none. Never inferred."""
    hits = [(m.start(), b, m.end()) for pat, b in _BASIS_LEXICON for m in [pat.search(text)] if m]
    if not hits:
        return None
    start, basis, end = min(hits)
    return basis, start, end


def compare(a: Assertion, b: Assertion) -> Comparison:
    """The only place that decides whether two asserted quantities are comparable.

    Comparable only when both state a currency, the currencies match, both state
    a basis, and the bases match. Otherwise compared=False with the reason. No
    equivalence between bases is assumed, and no currency is converted.
    """
    ca, cb = a.amount.currency, b.amount.currency
    ba, bb = a.basis, b.basis
    value = compare_values(a.value.text, b.value.text)

    def out(compared: bool, reason: ComparisonReason, detail: str) -> Comparison:
        return Comparison(a=a.assertion_id, b=b.assertion_id, compared=compared, reason=reason,
                          detail=detail, value=value)

    if value is ValueComparison.NOT_COMPARABLE:
        return out(False, ComparisonReason.NO_NUMERAL, f"{a.value.text!r} vs {b.value.text!r}")
    if ca is None or cb is None:
        missing = [x.assertion_id for x, c in ((a, ca), (b, cb)) if c is None]
        return out(False, ComparisonReason.CURRENCY_NOT_STATED, f"not stated by {', '.join(missing)}")
    if ca is not cb:
        return out(False, ComparisonReason.CURRENCY_MISMATCH, f"{ca.value} vs {cb.value}")
    if ba is None or bb is None:
        missing = [x.assertion_id for x, v in ((a, ba), (b, bb)) if v is None]
        return out(False, ComparisonReason.BASIS_NOT_STATED, f"not stated by {', '.join(missing)}")
    if ba is not bb:
        return out(False, ComparisonReason.BASIS_MISMATCH, f"{ba.value} vs {bb.value}")
    return out(True, ComparisonReason.DIFFERENT if value is ValueComparison.DIFFERENT else ComparisonReason.EQUAL,
               f"{a.value.text!r} vs {b.value.text!r}")
