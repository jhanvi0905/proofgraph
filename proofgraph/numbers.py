"""Numbers: raw amount strings -> integer minor units. A rule table, never a model.

No floats, no arithmetic beyond scaling, no FX. A string the rules do not
cover returns ParseFailure. It is never guessed at, so "US$10,000,0O0" (the
letter O) fails loudly instead of being repaired. A missing currency is not a
failure: it is returned as currency=None ("not stated", D1).
"""

from __future__ import annotations

import re

from proofgraph.schema import (
    BASIS_TABLE, CURRENCY_TABLE, DOLLARS_COUNTRY_NOT_PRINTED, MINOR_UNITS, Amount, Assertion, Basis, Comparison,
    ComparisonReason, Currency, ParseFailure, ValueComparison,
)

# ---- D12 item 5: currencies and basis phrases are data (data/currencies.json, data/basis_phrases.json)
_CODES = frozenset(MINOR_UNITS)
_SYMBOLS = {r["symbol"]: Currency(r["currency"] or DOLLARS_COUNTRY_NOT_PRINTED) for r in CURRENCY_TABLE["symbols"]}
_SIGNS = "$€£¥₹₩₽₺₪₫₱₦₴₸¢"  # printed currency signs; one outside the symbol table is an unknown currency
_SYM_ALT = "|".join(re.escape(x) for x in sorted(_SYMBOLS, key=len, reverse=True))
# A printed currency mark: a table symbol, letters before a dollar sign ("NT$"), or any other currency sign.
_MARK = rf"(?:{_SYM_ALT}|[A-Z]{{1,3}}\$|[{re.escape(_SIGNS)}])"
# In a value or a claim, a leading three-letter token is in currency position, known or not.
_LEAD_TOKEN_RE = re.compile(rf"^\s*(?P<tok>{_MARK}|[A-Z]{{3}}(?=\s*\d))\s*")
# A typed claim's currency position (D11 read_claim): a printed mark or any three capital letters before the number.
CLAIM_CURRENCY_TOKEN = rf"(?-i:{_MARK}|[A-Z]{{3}}(?=\s?\d))"  # case-sensitive inside a case-insensitive pattern
# In running text only table codes count as a currency, so all-caps prose ("AND 1,000") is not read as one.
_PROSE_CUR = rf"(?:{_MARK}|(?:{'|'.join(sorted(_CODES))})(?=\s?\d))"

_NIL_RE = re.compile(r"^(nil|none|zero)$", re.I)
_NUM_RE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(m|mm|million|k|thousand|b|billion)?$", re.I)
_SCALE = {"m": 6, "mm": 6, "million": 6, "k": 3, "thousand": 3, "b": 9, "billion": 9}


def currency_of(token: str) -> Currency | None:
    """The currency a printed token names: a symbol from the table, or an ISO 4217 code. None if unknown."""
    tok = token.strip()
    if tok in _SYMBOLS:
        return _SYMBOLS[tok]
    return Currency(tok) if tok in _CODES else None


def _strip_token(text: str) -> str:
    return _LEAD_TOKEN_RE.sub("", text, count=1)


def numeral(text: str) -> int | None:
    """The amount written in `text` as integer minor units, with currency tokens dropped.

    Returns None when there is no numeral: NIL, words, or anything the rule table
    does not cover. The same rules apply to every document.
    """
    m = _NUM_RE.match(_strip_token(text).strip())
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
    m = _LEAD_TOKEN_RE.match(s)
    if m:
        currency = currency_of(m.group("tok"))
        if currency is None:
            return ParseFailure(raw=raw, reason=f"unknown_currency: {m.group('tok')}")
        s = s[m.end():].strip()
    if _NIL_RE.match(s):
        return Amount(minor_units=0, decimals=0, currency=currency)
    m = _NUM_RE.match(s)
    if m is None:
        return ParseFailure(raw=raw, reason="unparseable")
    whole, frac, scale = m.group(1).replace(",", ""), m.group(2) or "", (m.group(3) or "").lower()
    exp = _SCALE.get(scale, 0)
    if exp and len(frac) > exp:
        return ParseFailure(raw=raw, reason="fraction_finer_than_scale")
    places = MINOR_UNITS.get(currency.value, 2) if currency is not None else 2
    if not exp and len(frac) > places:
        return ParseFailure(raw=raw, reason=f"more decimals than {currency.value} has ({places})")
    # integer arithmetic only: whole.frac * 10^exp * 100
    digits = int(whole + frac)
    minor = digits * 10 ** (exp + 2 - len(frac))
    return Amount(minor_units=minor, decimals=0 if exp else len(frac), currency=currency)


_AMOUNT_IN_TEXT_RE = re.compile(rf"(?:{_PROSE_CUR}\s*)?\d{{1,3}}(?:,\d{{3}})+(?:\.\d{{1,2}})?|{_PROSE_CUR}\s*\d+(?:\.\d{{1,2}})?")
_BASIS_LEXICON = [  # (pattern, basis) from data/basis_phrases.json; matched inside one citation only
    (re.compile(r"\b" + r"\s+".join(re.escape(w) for w in row["phrase"].split()) + r"\b", re.I), Basis(row["basis"]))
    for row in BASIS_TABLE["rows"]
]
BASIS_PHRASE = {}  # each basis's phrase as the table writes it (the first row naming it)
for _row in BASIS_TABLE["rows"]:
    BASIS_PHRASE.setdefault(Basis(_row["basis"]), _row["phrase"])


_SCALE_WORD = r"(?i:m|mm|million|k|thousand|b|billion)"
_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
# D12 item 1: every amount written in a verified quote. An amount needs a currency mark, digit grouping, or a
# scale word, so a list number ("8."), a day count ("60 days") or a form date ("07/20") is not one.
_AMOUNTS_RE = re.compile(
    rf"{_PROSE_CUR}\s?{_NUMBER}(?:\s?{_SCALE_WORD}\b)?"
    rf"|(?<![\w.,])\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?(?:\s?{_SCALE_WORD}\b)?"
    rf"|(?<![\w.,])\d+(?:\.\d+)?\s?(?i:million|thousand|billion)\b",
)


def find_amounts(text: str) -> list[tuple[int, int]]:
    """Offsets of every amount written in `text` (with its currency marker and scale word), in order."""
    return [(m.start(), m.end()) for m in _AMOUNTS_RE.finditer(text)]


def find_amount(text: str) -> tuple[int, int] | None:
    """Offsets of the first amount written in `text` (with its currency marker), or None."""
    m = _AMOUNT_IN_TEXT_RE.search(text)
    return (m.start(), m.end()) if m else None


def find_basis(text: str) -> tuple[Basis, int, int] | None:
    """The basis phrase written in `text`, or None if it states none. Never inferred. The earliest phrase wins,
    the longest at one position."""
    hits = [(m.start(), -(m.end() - m.start()), b, m.end()) for pat, b in _BASIS_LEXICON for m in [pat.search(text)] if m]
    if not hits:
        return None
    start, _, basis, end = min(hits, key=lambda h: (h[0], h[1]))
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
        dollars = Currency(DOLLARS_COUNTRY_NOT_PRINTED)
        if dollars in (ca, cb):  # D12: "$" names no country; a person sets the claim's currency at confirmation
            return out(False, ComparisonReason.CURRENCY_COUNTRY_NOT_PRINTED, f"'$' vs {(cb if ca is dollars else ca).value}")
        return out(False, ComparisonReason.CURRENCY_MISMATCH, f"{ca.value} vs {cb.value}")
    if (ba is None) != (bb is None):
        missing = ia if ba is None else ib
        return out(False, ComparisonReason.BASIS_NOT_STATED, f"not stated by {missing}")
    if ba is not bb:
        return out(False, ComparisonReason.BASIS_MISMATCH, f"{ba.value} vs {bb.value}")
    return out(True, ComparisonReason.DIFFERENT if value is ValueComparison.DIFFERENT else ComparisonReason.EQUAL,
               f"{ta!r} vs {tb!r}")
