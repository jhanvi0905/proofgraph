"""Propose candidate number, date, and time facts from source text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from proofgraph.schema import Fact

_MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
    "Sept",
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
_MONTH = "|".join(_MONTH_NAMES)
_MONTH_INDEX = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sept": 9,
    "sep": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}
_MDY = re.compile(
    rf"(?<!\w)(?P<month>{_MONTH})\.?\s+"
    rf"(?:(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\b,?\s+)?"
    rf"(?P<year>\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_DMY = re.compile(
    rf"(?<!\w)(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\b\s+"
    rf"(?P<month>{_MONTH})\.?\s+"
    rf"(?P<year>\d{{4}})(?!\d)",
    re.IGNORECASE,
)
_ISO = re.compile(
    r"(?<!\d)(?P<year>\d{4})-(?P<month>\d{2})(?:-(?P<day>\d{2}))?(?!\d)"
)
_TIME = re.compile(
    r"(?<![\w:])(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?(?![\w:])"
)
_BODY = re.compile(
    r"(?<![\w.])"
    r"(?P<neg>\()?\s*"
    r"(?P<dollar>\$)?\s*"
    r"(?P<digits>\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.(?P<decimal>\d+))?"
    r"(?:\s*(?P<pct>%))?"
    r"(?(neg)\s*\))"
)
_LEFT = re.compile(
    r"\(\s*in\s+(?:millions?|thousands?|billions?)\s*\)\s*$",
    re.IGNORECASE,
)
_RIGHT = re.compile(
    r"\s+(?:"
    r"(?:in\s+(?:the\s+)?)?(?:millions?|billions?|thousands?)\b(?:\s+dollars?\b)?"
    r"|percent\b"
    r"|dollars?\b"
    r"|\(\s*in\s+(?:millions?|thousands?|billions?)\s*\)"
    r")",
    re.IGNORECASE,
)
_MILLION = re.compile(r"\bmillions?\b", re.IGNORECASE)
_BILLION = re.compile(r"\bbillions?\b", re.IGNORECASE)
_THOUSAND = re.compile(r"\bthousands?\b", re.IGNORECASE)
_PERCENT_WORD = re.compile(r"\bpercent\b", re.IGNORECASE)
_DOLLAR_WORD = re.compile(r"\bdollars?\b", re.IGNORECASE)

KindName = Literal["number", "date", "time"]


@dataclass(frozen=True)
class _Hit:
    start: int
    end: int
    quote: str
    value: int | float | str
    scale: str | None
    kind: KindName


def propose_spans(text: str, source_id: str = "s") -> list[Fact]:
    """Return facts the text states. No verdict, link, or expression.

    Scale is read only from that span. A span with no scale stays null.
    """
    hits = _keep(_date_hits(text) + _time_hits(text) + _number_hits(text))
    facts: list[Fact] = []
    for index, hit in enumerate(hits, start=1):
        facts.append(
            Fact(
                id=f"f{index}",
                label=hit.kind,
                source_id=source_id,
                quote=hit.quote,
                value=hit.value,
                scale=hit.scale,  # type: ignore[arg-type]
                kind=hit.kind,
            )
        )
    return facts


def _date_hits(text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    for pattern, named in ((_DMY, True), (_MDY, True), (_ISO, False)):
        for match in pattern.finditer(text):
            value = _date_value(
                match.group("year"),
                match.group("month"),
                match.group("day"),
                month_is_name=named,
            )
            if value is None:
                continue
            hits.append(
                _Hit(
                    match.start(),
                    match.end(),
                    text[match.start() : match.end()],
                    value,
                    None,
                    "date",
                )
            )
    return hits


def _date_value(
    year: str,
    month: str,
    day: str | None,
    *,
    month_is_name: bool,
) -> str | None:
    if month_is_name:
        month_number = _MONTH_INDEX.get(month.lower().rstrip("."))
        if month_number is None:
            return None
    else:
        month_number = int(month)
    year_number = int(year)
    if day is None:
        if not 1 <= month_number <= 12:
            return None
        return f"{year_number:04d}-{month_number:02d}"
    try:
        parsed = date(year_number, month_number, int(day))
    except ValueError:
        return None
    return f"{parsed.year:04d}-{parsed.month:02d}-{parsed.day:02d}"


def _time_hits(text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    for match in _TIME.finditer(text):
        hour = int(match.group("h"))
        minute = int(match.group("m"))
        second = match.group("s")
        if hour > 23 or minute > 59:
            continue
        if second is not None and int(second) > 59:
            continue
        quote = match.group(0)
        hits.append(_Hit(match.start(), match.end(), quote, quote, None, "time"))
    return hits


def _number_hits(text: str) -> list[_Hit]:
    hits: list[_Hit] = []
    for match in _BODY.finditer(text):
        if _clock_fragment(text, match):
            continue
        start, end = match.span()
        start = _extend_left(text, start)
        end = _extend_right(text, end)
        negative = match.group("neg") is not None
        if not negative:
            wrapped = _outer_parentheses(text, start, end)
            if wrapped is not None:
                start, end = wrapped
                negative = True
        quote = text[start:end]
        hits.append(
            _Hit(
                start,
                end,
                quote,
                _number_value(match.group("digits"), match.group("decimal"), negative),
                _scale(quote),
                "number",
            )
        )
    return hits


def _clock_fragment(text: str, match: re.Match[str]) -> bool:
    start = match.start("digits")
    end = match.end("decimal") if match.group("decimal") is not None else match.end("digits")
    before = text[start - 1] if start else ""
    after = text[end] if end < len(text) else ""
    return before == ":" or after == ":"


def _extend_left(text: str, start: int) -> int:
    match = _LEFT.search(text[:start])
    if match is None or match.end() != start:
        return start
    return match.start()


def _extend_right(text: str, end: int) -> int:
    match = _RIGHT.match(text, end)
    if match is None:
        return end
    return match.end()


def _outer_parentheses(text: str, start: int, end: int) -> tuple[int, int] | None:
    left = start - 1
    while left >= 0 and text[left] in " \t":
        left -= 1
    right = end
    while right < len(text) and text[right] in " \t":
        right += 1
    if left >= 0 and text[left] == "(" and right < len(text) and text[right] == ")":
        return left, right + 1
    return None


def _number_value(digits: str, decimal: str | None, negative: bool) -> int | float:
    raw = digits.replace(",", "")
    number = Decimal(f"{raw}.{decimal}" if decimal is not None else raw)
    if negative:
        number = -number
    if number == number.to_integral_value():
        return int(number)
    return float(number)


def _scale(quote: str) -> str | None:
    """Scale stated inside this span. Absent stays null."""
    if _MILLION.search(quote):
        return "millions"
    if _BILLION.search(quote):
        return "billions"
    if _THOUSAND.search(quote):
        return "thousands"
    if "%" in quote or _PERCENT_WORD.search(quote):
        return "percent"
    if "$" in quote or _DOLLAR_WORD.search(quote):
        return "units"
    return None


def _keep(hits: list[_Hit]) -> list[_Hit]:
    ordered = sorted(hits, key=lambda hit: (hit.start, hit.start - hit.end))
    kept: list[_Hit] = []
    for hit in ordered:
        if any(hit.start < earlier.end and earlier.start < hit.end for earlier in kept):
            continue
        kept.append(hit)
    kept.sort(key=lambda hit: hit.start)
    return kept
