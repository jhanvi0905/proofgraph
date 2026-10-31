"""Parse numbers and normalise source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff"), None)
_QUOTES_AND_DASHES = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
    }
)
_HEDGE = re.compile(r"\b(?:about|approximately|nearly|around)\b", re.IGNORECASE)
_LITERAL = re.compile(
    r"(?<![\w.])"
    r"(?P<neg>\()?\s*"
    r"(?P<dollar>\$)?\s*"
    r"(?P<digits>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<decimal>\d+))?"
    r"\s*(?P<percent>%)?"
    r"(?(neg)\s*\))"
)
_TOKEN = re.compile(
    r"\(\s*\$?\s*[\d,]+(?:\.\d+)?\s*\)"
    r"|\$?\d[\d,]*(?:\.\d+)?%?"
    r"|(?<![\w])\u2014(?![\w])"
)


def normalise_text(text: str) -> str:
    """Strip invisible characters, collapse whitespace, and unify quotes and dashes."""
    cleaned = text.translate(_INVISIBLE).translate(_QUOTES_AND_DASHES)
    cleaned = cleaned.replace("\u00a0", " ")
    return re.sub(r"\s+", " ", cleaned).strip()


def parse_number(text: str) -> Decimal | None:
    """Parse one numeric token. Parentheses are negative. A bare em dash is zero."""
    raw = text.strip()
    if raw == "\u2014":
        return Decimal(0)
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative = True
        raw = raw[1:-1].strip()
    raw = raw.replace("$", "").replace(",", "").replace(" ", "")
    percent = False
    if raw.endswith("%"):
        percent = True
        raw = raw[:-1]
    if not re.fullmatch(r"\d+(?:\.\d+)?", raw or ""):
        return None
    number = Decimal(raw)
    if percent:
        number = number / Decimal(100)
    if negative:
        number = -number
    return number


def find_numbers(text: str) -> list[Decimal]:
    """Return every numeric token in text. Clock times are not numbers."""
    visible = text.translate(_INVISIBLE).replace("\u00a0", " ")
    found: list[Decimal] = []
    for match in _TOKEN.finditer(visible):
        start, end = match.span()
        if end < len(visible) and visible[end] == ":":
            continue
        if start > 0 and visible[start - 1] == ":":
            continue
        number = parse_number(match.group(0))
        if number is not None:
            found.append(number)
    return found


def exceeds_half_percent(left: Decimal, right: Decimal) -> bool:
    """True when the values differ by more than 0.5% of the larger magnitude."""
    difference = abs(left - right)
    base = max(abs(left), abs(right))
    if base == 0:
        return False
    return difference / base > Decimal("0.005")


@dataclass(frozen=True)
class Literal:
    value: Decimal
    unit: Decimal
    hedged: bool
    percent: bool = False


def _display_unit(digits: str, decimal: str | None) -> Decimal:
    if decimal is not None:
        return Decimal(10) ** -len(decimal)
    if not digits.strip("0"):
        return Decimal(1)
    trailing = len(digits) - len(digits.rstrip("0"))
    return Decimal(10) ** trailing


def iter_literals(text: str, *, skip_years: bool = False) -> list[Literal]:
    """Numeric literals with the place value used for rounding tolerance."""
    literals: list[Literal] = []
    for match in _LITERAL.finditer(text):
        digits = match.group("digits").replace(",", "")
        decimal = match.group("decimal")
        percent = match.group("percent") is not None
        display = Decimal(f"{digits}.{decimal}" if decimal else digits)
        if match.group("neg"):
            display = -display
        if (
            skip_years
            and not percent
            and match.group("dollar") is None
            and decimal is None
            and display == display.to_integral_value()
            and Decimal(1900) <= display <= Decimal(2100)
        ):
            continue
        unit = _display_unit(digits, decimal)
        value = display / Decimal(100) if percent else display
        if percent:
            unit = unit / Decimal(100)
        window = text[max(0, match.start() - 48) : match.start()]
        literals.append(
            Literal(
                value=value,
                unit=unit,
                hedged=bool(_HEDGE.search(window)),
                percent=percent,
            )
        )
    return literals


def numeric_value(value: object) -> Decimal | None:
    """Coerce a fact value to Decimal when it is numeric."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return parse_number(value.strip())
    return None
