"""Proposer: what is this uploaded document? The model quotes; code verifies every quote.

Called once per readable file, before any run, on the text of the first pages. The model returns quotes for the
printed form number, edition, title, the kind of document (one of InstrumentType), what it amends, and a policy
number if one is printed. It decides nothing: a proposal is a row a person confirms or corrects before anything runs.

Code checks each quote against the PDF with the same parser the citation verifier uses: the quote must be one line
and occur at least once on its stated page (a form number repeats in headers and footers, so "at least once").
Which occurrence is recorded (page, occurrence, count). A quote that is not found is rejected. A failed check gets
one repair retry that carries the errors, like passes.py; whatever is still not found after that is dropped and listed.

A file with no verified form number and no verified title is returned unplaced, with what it would need.
The route anchor (the one line the frozen mapping cites) must occur exactly once on its page, because that is what
verify_citation demands; if every verified quote repeats, the file is unplaced for that reason.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict

from proofgraph.checker import Source, open_source
from proofgraph.ingest import pdf_text_layer
from proofgraph.model import ModelReply, complete_json
from proofgraph.schema import InstrumentType, TraceRecord
from proofgraph.trace import Trace

Complete = Callable[..., ModelReply]
FIRST_PAGES = 3
FIELDS = ("form_number", "edition", "title", "kind", "amends", "policy_number")

SYSTEM = (
    "You read the first pages of one insurance document and quote what is printed on it: its form number, edition "
    "date, title, what kind of document it is, the form it amends if it says so, and a policy number if one is "
    "printed. You only quote. You do not decide which policy the document belongs to. Return JSON only, matching the schema."
)
TEMPLATE = """File name: {name}

Text of the first pages (each page starts with its number):
{pages}

For each item below, give `quote`: the characters printed on the document, copied exactly from ONE line, and
`page`: the page that line is on. If the item is not printed in these pages, give an empty quote and page 0.
- form_number: the printed form number (for example a code like "XX 00 00 00 00"); it often repeats in a header or footer.
- edition: the printed edition or revision date.
- title: the document's printed title or heading.
- kind: which kind of document this is, one of {kinds}, plus a quote of the line that shows it (for example a
  line saying it is an endorsement, a declarations page, a binder). Use an empty quote and "" if you cannot tell.
- amends: the line, if one is printed, naming the form or instrument this document amends or is attached to.
- policy_number: a printed policy number, if there is one.
Do not infer anything that is not printed."""

REPAIR = """{prompt}

Your previous answer failed validation:
{errors}
Return a corrected answer."""


class Quote(BaseModel):
    """A quote the model gave and code found on the page."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    field: str
    text: str
    page: int
    occurrence: int  # 1-based; reading order (top, then left) among the occurrences on the page
    count: int  # how many times the line occurs on the page


class Row(BaseModel):
    """One uploaded file as the proposer left it. A person confirms or corrects this before anything runs."""

    model_config = ConfigDict(extra="forbid")
    file: str
    stored: str  # the stored file's name
    sha256: str
    pages: int
    status: str  # proposed | unplaceable | typed
    kind: str = ""
    form_number: str = ""
    edition: str = ""
    title: str = ""
    amends: str = ""
    policy: str = ""  # proposed from a verified printed policy number, else blank
    how: str = "judgment"  # read when the form number and a policy number are printed and verified; judgment otherwise
    quotes: tuple[Quote, ...] = ()
    anchor: Quote | None = None  # the line the frozen mapping cites: verified, and exactly once on its page
    rejected: tuple[str, ...] = ()
    reason: str = ""  # why a file is unplaceable, and what it would need


def wire_schema() -> dict:
    quote = {"type": "object", "properties": {"quote": {"type": "string"}, "page": {"type": "integer"}},
             "required": ["quote", "page"], "additionalProperties": False}
    kind = {"type": "object", "properties": {"kind": {"type": "string", "enum": [t.value for t in InstrumentType] + [""]},
                                             "quote": {"type": "string"}, "page": {"type": "integer"}},
            "required": ["kind", "quote", "page"], "additionalProperties": False}
    props = {f: (kind if f == "kind" else quote) for f in FIELDS}
    return {"type": "object", "properties": props, "required": list(FIELDS), "additionalProperties": False}


def _norm(s: str) -> str:
    return " ".join(s.split())


def check_quote(field: str, quote: str, page: int, src: Source, pages: int) -> tuple[Quote | None, str | None]:
    """(verified quote, None) or (None, why not). Empty quote means "not printed": neither."""
    q = quote.strip()
    if not q:
        return None, None
    if "\n" in q:
        return None, f"{field}: quote {q[:60]!r} runs over more than one line; quote one line"
    q = _norm(q)
    if not 1 <= page <= min(pages, FIRST_PAGES):
        return None, f"{field}: page {page} is not one of the pages given (1-{min(pages, FIRST_PAGES)})"
    hits = src.page_find(page, q)
    if not hits:
        return None, f"{field}: quote {q!r} does not occur exactly on page {page}"
    first = sorted(hits, key=lambda h: (round(h[1]), h[0]))[0]
    return Quote(field=field, text=q, page=page, occurrence=sorted(hits, key=lambda h: (round(h[1]), h[0])).index(first) + 1,
                 count=len(hits)), None


def verify_line(path: Path, page: int, text: str) -> tuple[Quote | None, str | None]:
    """The same check for a line a person typed (the mapping-form fallback)."""
    n, _, _ = pdf_text_layer(path, 0)
    return check_quote("typed", text, page, open_source(path), n) if 1 <= page <= FIRST_PAGES else (
        None, f"page {page} is not within the first {FIRST_PAGES} pages")


def propose(path: Path, name: str, stored: str, sha256: str, trace: Trace, complete: Complete = complete_json) -> Row:
    pages, texts, _ = pdf_text_layer(path, FIRST_PAGES)
    src = open_source(path)
    prompt = TEMPLATE.format(name=name, kinds=", ".join(t.value for t in InstrumentType),
                             pages="\n\n".join(f"[page {i}]\n{t}" for i, t in enumerate(texts, 1)))
    schema = wire_schema()
    errors: list[str] = []
    verified: dict[str, Quote] = {}
    kind = ""
    for attempt in range(2):
        text = prompt if attempt == 0 else REPAIR.format(prompt=prompt, errors="\n".join(f"- {e}" for e in errors))
        reply = complete(text, schema, system=SYSTEM, template=TEMPLATE, effort="low")
        wire = json.loads(reply.text)
        verified, errors, kind = {}, [], ""
        for f in FIELDS:
            item = wire.get(f) or {}
            q, why = check_quote(f, item.get("quote", ""), int(item.get("page", 0) or 0), src, pages)
            if why:
                errors.append(why)
            elif q:
                verified[f] = q
        claimed_kind = (wire.get("kind") or {}).get("kind", "")
        if claimed_kind and "kind" in verified:
            kind = claimed_kind
        elif claimed_kind:
            errors.append(f"kind: {claimed_kind!r} came without a quote that is on the page")
        trace.write(TraceRecord(
            stage="propose", packet_id=None, atom_id=name, span_ids=(), model=reply.model, prompt_hash=reply.prompt_hash,
            input_tokens=reply.input_tokens, output_tokens=reply.output_tokens, latency_ms=reply.latency_ms,
            cache_hit=reply.cache_hit, verdict=None, rejects=tuple(errors), repairs=attempt,
            detail=f"verified={sorted(verified)}"))
        if not errors:
            break

    def text_of(f: str) -> str:
        return verified[f].text if f in verified else ""

    base = dict(file=name, stored=stored, sha256=sha256, pages=pages, kind=kind, form_number=text_of("form_number"),
                edition=text_of("edition"), title=text_of("title"), amends=text_of("amends"), policy=text_of("policy_number"),
                quotes=tuple(verified[f] for f in FIELDS if f in verified), rejected=tuple(errors))
    base["how"] = "read" if "form_number" in verified and "policy_number" in verified else "judgment"
    if "form_number" not in verified and "title" not in verified:
        return Row(status="unplaceable", reason=_needs(name, "no printed form number or title could be verified on the first pages"), **base)
    anchor = next((verified[f] for f in ("form_number", "title", "amends", "edition", "policy_number", "kind")
                   if f in verified and verified[f].count == 1), None)
    if anchor is None:
        return Row(status="unplaceable", reason=_needs(name, "every line it quotes repeats on its page, so no one line can anchor the mapping"), **base)
    return Row(status="proposed", anchor=anchor, **base)


def _needs(name: str, why: str) -> str:
    return (f"{name} could not be placed: {why}. To place it, say what kind of document it is, which policy it describes, "
            f"how you know, and give one line printed on it (a form number, title or heading) that occurs once on its page.")


def edition_date(edition: str):
    """MM YY (as ISO forms print it, "04 91") to the first of that month; anything else is None. Never guessed."""
    import datetime as dt

    m = re.fullmatch(r"\D*?(\d{2})\s*[/ -]?\s*(\d{2})\D*", edition)
    if not m or not 1 <= int(m.group(1)) <= 12:
        return None
    yy = int(m.group(2))
    return dt.date(1900 + yy if yy >= 50 else 2000 + yy, int(m.group(1)), 1)
