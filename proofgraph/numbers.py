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
    """The only place that decides whether two asserted quantities are comparable (D9, superseding D6's rule).

    Comparable when the currencies match, or neither side states one, AND both state the
    same basis, or neither states one (the question already fixes the quantity). One side
    stating a currency or basis and the other not is a named mismatch, saying which side
    lacked it; so are two different currencies or two different bases. No equivalence
    between bases is assumed, and no currency is converted.
    """
    return _compare(a.assertion_id, a.value.text, a.amount.currency, a.basis,
                    b.assertion_id, b.value.text, b.amount.currency, b.basis)


def compare_claim(claim_value: str, b: Assertion) -> Comparison:
    """The claim's declared value against one assertion, by the same rule as compare(). a is "claim".

    The claim's amount, currency and basis are read from its value as the author wrote it (the
    first amount written in it, and the basis phrase anywhere in it), never filled in.
    """
    text = claim_amount_text(claim_value)
    parsed = parse_amount(text)
    found = find_basis(claim_value)
    currency = None if isinstance(parsed, ParseFailure) else parsed.currency
    return _compare("claim", text, currency, found[0] if found else None,
                    b.assertion_id, b.value.text, b.amount.currency, b.basis)


def claim_amount_text(claim_value: str) -> str:
    """The amount inside a declared claim value ("USD 1,000,000 each claim" -> "USD 1,000,000")."""
    span = find_amount(claim_value)
    return claim_value[span[0]:span[1]] if span else claim_value.strip()


def _compare(ia: str, ta: str, ca: Currency | None, ba: Basis | None,
             ib: str, tb: str, cb: Currency | None, bb: Basis | None) -> Comparison:
    value = compare_values(ta, tb)

    def out(compared: bool, reason: ComparisonReason, detail: str) -> Comparison:
        return Comparison(a=ia, b=ib, compared=compared, reason=reason, detail=detail, value=value)

    if value is ValueComparison.NOT_COMPARABLE:
        return out(False, ComparisonReason.NO_NUMERAL, f"{ta!r} vs {tb!r}")
    if (ca is None) != (cb is None):
        missing = ia if ca is None else ib
        return out(False, ComparisonReason.CURRENCY_NOT_STATED, f"not stated by {missing}")
    if ca is not cb:
        return out(False, ComparisonReason.CURRENCY_MISMATCH, f"{ca.value} vs {cb.value}")
    if (ba is None) != (bb is None):
        missing = ia if ba is None else ib
        return out(False, ComparisonReason.BASIS_NOT_STATED, f"not stated by {missing}")
    if ba is not bb:
        return out(False, ComparisonReason.BASIS_MISMATCH, f"{ba.value} vs {bb.value}")
    return out(True, ComparisonReason.DIFFERENT if value is ValueComparison.DIFFERENT else ComparisonReason.EQUAL,
               f"{ta!r} vs {tb!r}")
