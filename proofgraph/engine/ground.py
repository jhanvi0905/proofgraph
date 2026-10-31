"""Fact grounding and numeric conflicts.

A fact reaches one of four methods by its source and its shape:

- text source: ``quote``, the quote and the value are in the text.
- pdf source with a page and a box: ``text_in_box``, a 2%, 3%, then 4% margin
  around the box must contain the value.
- image source, kind ``time``: ``blind_reread``, the crop alone goes to the
  blind checker and the reading must be the same time of day.
- image source, kind ``count``: ``count_agreement``, SAM's count of the noun
  (``Fact.entity``) must equal the stated count.

Every method fails closed: any miss or error is ``ungrounded`` with a reason.
"""

from __future__ import annotations

import io
import re
from decimal import Decimal
from pathlib import Path

from proofgraph.clients.checker import blind_reread, clocks_agree
from proofgraph.clients.sam import sam_count
from proofgraph.engine.numbers import exceeds_half_percent, find_numbers, normalise_text, numeric_value
from proofgraph.pdf import MarginMiss, read_page_words, select_margin
from proofgraph.schema import Case, Fact, FactCheck, Source
from proofgraph.spend import SpendCapReached, SpendLedgerError

# Pad around a drawn box before the crop goes to the blind re-read.
_CROP_PAD = 0.02
_NUMBER_TOKEN = re.compile(r"\$?\d[\d,]*(?:\.\d+)?%?")


def ground(fact: Fact, case: Case) -> FactCheck:
    """Ground a fact by the method its source and shape call for."""
    source = next((item for item in case.sources if item.id == fact.source_id), None)
    if source is not None and source.kind == "image":
        if fact.kind == "time":
            return _blind_reread(fact, source)
        if fact.kind == "count":
            return _count_agreement(fact, source)
        return _ungrounded(fact, "no grounding method for this image fact")
    if source is not None and source.kind == "pdf" and fact.box is not None and fact.page is not None:
        return _text_in_box(fact, source)
    if source is None or not source.text or not fact.quote:
        return _ungrounded(fact, "quote not in source")
    if normalise_text(fact.quote) not in normalise_text(source.text):
        return _ungrounded(fact, "quote not in source")
    if not _value_in_quote(fact.value, fact.quote):
        return _ungrounded(fact, "value not in quote")
    return FactCheck(
        fact_id=fact.id,
        status="grounded",
        method="quote",
        detail="quote match",
    )


def apply_conflicts(facts: list[Fact], checks: list[FactCheck]) -> list[FactCheck]:
    """Mark both grounded facts when the conflict key matches and values diverge."""
    by_id = {check.fact_id: check for check in checks}
    groups: dict[tuple[str, str, str], list[Fact]] = {}
    for fact in facts:
        check = by_id.get(fact.id)
        key = _conflict_key(fact)
        if check is None or check.status != "grounded" or key is None:
            continue
        if numeric_value(fact.value) is None:
            continue
        groups.setdefault(key, []).append(fact)
    conflicted: set[str] = set()
    for group in groups.values():
        for index, first in enumerate(group):
            first_value = numeric_value(first.value)
            for second in group[index + 1 :]:
                second_value = numeric_value(second.value)
                if first_value is None or second_value is None:
                    continue
                if exceeds_half_percent(first_value, second_value):
                    conflicted.add(first.id)
                    conflicted.add(second.id)
    updated: list[FactCheck] = []
    for check in checks:
        if check.fact_id in conflicted:
            updated.append(
                check.model_copy(
                    update={
                        "status": "conflict",
                        "detail": "values differ by more than 0.5%",
                    }
                )
            )
        else:
            updated.append(check)
    return updated


def _ungrounded(fact: Fact, detail: str, method: str = "quote") -> FactCheck:
    return FactCheck(fact_id=fact.id, status="ungrounded", method=method, detail=detail)  # type: ignore[arg-type]


def _text_in_box(fact: Fact, source: Source) -> FactCheck:
    method = "text_in_box"
    if not source.path or fact.page is None or fact.box is None:
        return _ungrounded(fact, "pdf has no path, page, or box", method)
    try:
        words = read_page_words(Path(source.path), page=fact.page)
        match = select_margin(words, fact.box, _needle(fact))
    except MarginMiss:
        return _ungrounded(fact, "value not in the box at 2%, 3%, or 4%", method)
    except (ValueError, OSError) as exc:
        return _ungrounded(fact, f"pdf box unreadable: {exc}", method)
    if not _value_in_quote(fact.value, match.text):
        return _ungrounded(fact, "value not in the box", method)
    return FactCheck(
        fact_id=fact.id,
        status="grounded",
        method="text_in_box",
        detail=f"value in box at {match.margin:.0%} margin",
    )


def _needle(fact: Fact) -> str:
    """The text the box must contain: the quote's token for a number, else the value."""
    number = numeric_value(fact.value)
    if number is not None and fact.quote:
        for token in _NUMBER_TOKEN.findall(fact.quote):
            if numeric_value(token) == number:
                return token
    return str(fact.value) if fact.value is not None else ""


def _blind_reread(fact: Fact, source: Source) -> FactCheck:
    method = "blind_reread"
    if not _valid_box(fact.box):
        return _ungrounded(fact, "no box to crop", method)
    try:
        crop = _png(source, fact.box, _CROP_PAD)
        reading = blind_reread(crop)
    except (SpendCapReached, SpendLedgerError):
        raise  # a spend stop is not a grounding miss
    except Exception as exc:  # fail closed: any other error leaves the fact ungrounded
        return _ungrounded(fact, f"blind re-read failed: {_why(exc)}", method)
    if not isinstance(fact.value, str) or not clocks_agree(reading, fact.value):
        return _ungrounded(fact, f"blind re-read {reading!r} is not {fact.value!r}", method)
    return FactCheck(
        fact_id=fact.id,
        status="grounded",
        method="blind_reread",
        detail=f"blind re-read {reading!r} is the same time",
    )


def _count_agreement(fact: Fact, source: Source) -> FactCheck:
    method = "count_agreement"
    stated = numeric_value(fact.value)
    noun = (fact.entity or "").strip()
    if stated is None or stated != stated.to_integral_value() or stated < 0:
        return _ungrounded(fact, "stated count is not a whole number", method)
    if not noun:
        return _ungrounded(fact, "no noun to count", method)
    try:
        still = _png(source, fact.box if _valid_box(fact.box) else None, 0.0)
        counted = sam_count(still, noun)
    except (SpendCapReached, SpendLedgerError):
        raise  # a spend stop is not a grounding miss
    except Exception as exc:  # fail closed: any other error leaves the fact ungrounded
        return _ungrounded(fact, f"SAM count failed: {_why(exc)}", method)
    if Decimal(counted) != stated:
        return _ungrounded(fact, f"SAM counted {counted} {noun}, stated {stated}", method)
    return FactCheck(
        fact_id=fact.id,
        status="grounded",
        method="count_agreement",
        detail=f"SAM counted {counted} {noun}",
    )


def _valid_box(box: list[int] | None) -> bool:
    return box is not None and len(box) == 4 and box[0] < box[2] and box[1] < box[3]


def _png(source: Source, box: list[int] | None, pad: float) -> bytes:
    """PNG bytes of the image, or of the 0-1000 box padded by ``pad`` of the page."""
    if not source.path:
        raise ValueError("image has no path")
    from PIL import Image  # transitive via streamlit; not a declared dependency

    with Image.open(source.path) as image:
        image = image.convert("RGB")
        if box is not None:
            grid = 1000
            left, top, right, bottom = (
                min(max(value + sign * pad * grid, 0), grid)
                for value, sign in zip(box, (-1, -1, 1, 1))
            )
            image = image.crop(
                (
                    round(left * image.width / grid),
                    round(top * image.height / grid),
                    round(right * image.width / grid),
                    round(bottom * image.height / grid),
                )
            )
        out = io.BytesIO()
        image.save(out, format="PNG")
        return out.getvalue()


def _why(exc: Exception) -> str:
    code = getattr(exc, "reason_code", None)
    return str(code) if code else type(exc).__name__


def _value_in_quote(value: object, quote: str) -> bool:
    if isinstance(value, str) and numeric_value(value) is None:
        return normalise_text(value) in normalise_text(quote)
    number = numeric_value(value)
    if number is None:
        return False
    return any(number == found for found in find_numbers(quote))


def _conflict_key(fact: Fact) -> tuple[str, str, str] | None:
    if not fact.label.strip():
        return None
    if fact.entity is None or not fact.entity.strip():
        return None
    if fact.period is None or not fact.period.strip():
        return None
    return (fact.label.strip(), fact.entity.strip(), fact.period.strip())
