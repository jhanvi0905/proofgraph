"""Numbers: raw amount strings -> integer minor units. A rule table, never a model.

No floats, no arithmetic beyond scaling, no FX. A string the rules do not
cover returns ParseFailure. It is never guessed at, so "US$10,000,0O0" (the
letter O) fails loudly instead of being repaired.
"""

from __future__ import annotations

import re

from proofgraph.schema import Amount, Currency, ParseFailure

_CURRENCY = [  # (pattern, currency); first match wins
    (re.compile(r"^\s*(?:US\$|USD\s*|\$)"), Currency.USD),
]
_NIL_RE = re.compile(r"^(nil|none|zero)$", re.I)
_NUM_RE = re.compile(r"^(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?\s*(m|mm|million|k|thousand|b|billion)?$", re.I)
_SCALE = {"m": 6, "mm": 6, "million": 6, "k": 3, "thousand": 3, "b": 9, "billion": 9}


def parse_amount(raw: str) -> Amount | ParseFailure:
    s = raw.strip()
    currency = None
    for pat, cur in _CURRENCY:
        m = pat.match(s)
        if m:
            currency, s = cur, s[m.end():].strip()
            break
    if currency is None:
        return ParseFailure(raw=raw, reason="missing_unit")
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
