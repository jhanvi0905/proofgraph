"""D11: a typed claim, a confirmed grouping, then the unchanged decision tree.

Three steps, each a plain function:

- `read_claim`: code reads the typed claim (kind, amount as written and as read, basis, any
  policy number from the packet). No model.
- `gather_typed`: the existing reads run under a run-local key; every quote is verified as
  before. Returns candidate lines per document, and the documents where nothing was found.
- `decide_typed`: a person's confirmation (every line confirmed or dropped with a reason) becomes
  the question; the confirmed lines are re-keyed to it and `arbitrate` / `arbitrate_wording` run.

D13 item 2: a line whose verified quote states several amounts, with no valid pointer, lists the amounts code
found in that quote; the person may pick one at confirmation. Code never matches the claim's words to a figure;
with no pick the line stays value_ambiguous.

The arbiter, comparators, assertions, checker, passes and atomize are not touched (freeze).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from proofgraph.arbiter import arbitrate, arbitrate_wording
from proofgraph.assertions import VALUE_AMBIGUOUS, assert_from_evidence
from proofgraph.numbers import BASIS_PHRASE, CLAIM_CURRENCY_TOKEN, find_amounts, find_basis, parse_amount
from proofgraph.pipeline import PacketRun, gather
from proofgraph.schema import (DOLLARS_COUNTRY_NOT_PRINTED, MINOR_UNITS, Amount, Assertion, Basis, Claim, DocumentMappingFile,
                               Excerpt, MappingMethod, ParseFailure, PageQuote, RouteRef, RouteStrength)
from proofgraph.trace import Trace

_SCALE = r"(?:m|mm|million|k|thousand|b|billion)\b"
# An amount needs a currency marker, digit grouping, or a scale word, so "item 5" is not one.
_AMOUNT_RE = re.compile(
    rf"(?P<cur>{CLAIM_CURRENCY_TOKEN})\s?(?P<n>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<s1>{_SCALE}))?"
    rf"|(?P<n2>\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?)(?:\s?(?P<s2>{_SCALE}))?"
    rf"|(?P<n3>\d+(?:\.\d+)?)\s?(?P<s3>million|thousand|billion)\b",
    re.I,
)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_RE = re.compile(
    rf"\b\d{{1,2}}/\d{{1,2}}/\d{{2,4}}\b|\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b{_MONTHS}\s+\d{{1,2}},?\s+\d{{4}}\b|\b\d{{1,2}}\s+{_MONTHS}\s+\d{{4}}\b",
    re.I,
)

Refusal = Literal["empty_claim", "more_than_one_value", "dates_not_supported", "value_unparseable",
                  "no_candidate_line", "no_line_confirmed", "confirmation_incomplete", "policy_not_in_packet",
                  "value_ambiguous", "unknown_currency", "currency_not_known", "figure_not_read"]

REFUSAL_TEXT = {
    "empty_claim": "Type a claim to check.",
    "more_than_one_value": "The claim states more than one amount. Check one amount at a time.",
    "dates_not_supported": "Claims about dates can't be checked yet: there is no date comparator.",
    "value_unparseable": "The amount in the claim couldn't be read as a number.",
    "no_candidate_line": "None of the documents for this policy had a line about the claim.",
    "no_line_confirmed": "No line was confirmed as being about the claim, so there is nothing to compare.",
    "confirmation_incomplete": "Every line must be confirmed or set aside with a reason before the check runs.",
    "policy_not_in_packet": "That policy is not one the documents were assigned to.",
    "unknown_currency": ("The claim's currency, {token}, is not in the currency table (ISO 4217 codes and the printed signs "
                         "listed with them), so it can't be compared."),
    "currency_not_known": "That currency is not an ISO 4217 code in the currency table.",
    "value_ambiguous": ("Unresolved: a line you confirmed states more than one amount, and the reads did not say which one "
                        "is the claim's, so nothing was compared. Pick the figure the claim means, or set that line aside "
                        "if it is not about the claim."),
    "figure_not_read": "The figure picked in a line could not be read as an amount, so nothing was compared.",
}


@dataclass(frozen=True)
class ReadClaim:
    text: str
    kind: Literal["amount", "wording"] | None
    written: str | None  # the amount exactly as typed, e.g. "$1M"
    value: str | None  # the amount as read, for the comparator, e.g. "$1,000,000"
    currency: str | None
    basis: Basis | None
    policy_matches: tuple[str, ...]  # packet policy numbers found in the text; shown, never applied
    refusal: Refusal | None = None
    token: str | None = None  # unknown_currency: the token as written


def refusal_text(refusal: Refusal, token: str | None = None) -> str:
    return REFUSAL_TEXT[refusal].replace("{token}", token or "")


def _render(a: Amount, marker: str) -> str:
    whole, cents = divmod(a.minor_units, 100)
    s = f"{whole:,}" + (f".{cents:02d}" if a.decimals else "")
    return f"{marker}{s}"


def read_claim(text: str, packet_policies: tuple[str, ...]) -> ReadClaim:
    """What code reads from a typed claim. No model, nothing filled in."""
    t = " ".join(text.split())
    matches = tuple(p for p in packet_policies if re.search(rf"(?<![\w-]){re.escape(p)}(?![\w-])", t))
    if not t:
        return ReadClaim(t, None, None, None, None, None, matches, "empty_claim")
    amounts = [m for m in _AMOUNT_RE.finditer(t)]
    basis = find_basis(t)
    if len({m.group(0).strip().lower() for m in amounts}) > 1:
        return ReadClaim(t, "amount", None, None, None, None, matches, "more_than_one_value")
    if amounts:
        m = amounts[0]
        cur = (m.group("cur") or "").strip()
        num = m.group("n") or m.group("n2") or m.group("n3")
        scale = m.group("s1") or m.group("s2") or m.group("s3") or ""
        parsed = parse_amount(f"{cur}{' ' if len(cur) == 3 and cur.isalpha() else ''}{num}{' ' + scale if scale else ''}")
        if isinstance(parsed, ParseFailure):
            if parsed.reason.startswith("unknown_currency"):
                return ReadClaim(t, "amount", m.group(0), None, None, None, matches, "unknown_currency", token=cur)
            return ReadClaim(t, "amount", m.group(0), None, None, None, matches, "value_unparseable")
        # the currency mark as written: a code is followed by a space ("USD 1,000"), a sign is not ("$1,000")
        marker = f"{cur} " if len(cur) == 3 and cur.isalpha() else cur
        value = _render(parsed, marker)
        if basis:
            value += " " + BASIS_PHRASE.get(basis[0], t[basis[1]:basis[2]])
        return ReadClaim(t, "amount", m.group(0).strip(), value, parsed.currency.value if parsed.currency else None,
                         basis[0] if basis else None, matches)
    if _DATE_RE.search(t):
        return ReadClaim(t, None, None, None, None, None, matches, "dates_not_supported")
    return ReadClaim(t, "wording", None, None, None, None, matches)


@dataclass(frozen=True)
class Candidate:
    """One verified line the reads returned, for a person to confirm or set aside."""

    line_id: str
    doc_id: str
    side: str
    page: int | None
    start: int | None
    end: int | None
    quote: str
    value: str | None
    no_value: str | None = None  # D12 item 1: why no value was read (value_ambiguous), shown to the person
    # D13 item 2: the amounts code found in the verified quote, in order, when it states several and no pointer is valid
    figures: tuple[str, ...] = ()


@dataclass
class Gathered:
    read: ReadClaim
    policy: str
    temp_slot: str
    doc_ids: list[str]
    run: PacketRun
    checked: tuple
    candidates: list[Candidate] = field(default_factory=list)
    nothing_found: list[str] = field(default_factory=list)  # admitted documents with no candidate line


def _slug(text: str, words: int = 6) -> str:
    toks = re.findall(r"[a-z0-9]+", text.lower())
    return "_".join(toks[:words]) or "claim"


def _loc(citation) -> tuple[int | None, int | None, int | None]:
    loc = citation.locator
    return (loc.page, None, None) if isinstance(loc, PageQuote) else (None, loc.start, loc.end)


def gather_typed(read: ReadClaim, policy: str, packet_id: str, doc_ids: list[str], mappings: DocumentMappingFile,
                 data: Path, trace: Trace) -> Gathered:
    """The reads, under a run-local key: policy plus a slug of the claim text (D11, fix 2)."""
    digest = hashlib.sha256(read.text.encode()).hexdigest()[:8]
    temp_slot = f"{policy}.typed_{_slug(re.sub(_AMOUNT_RE, ' ', read.text))}_{digest}"
    claim = Claim(claim_id=f"typed-{digest}", text=read.text, slot=temp_slot, kind=read.kind, value=read.value)
    run, checked = gather(packet_id, claim, doc_ids, mappings, data, trace)
    g = Gathered(read=read, policy=policy, temp_slot=temp_slot, doc_ids=doc_ids, run=run, checked=checked)
    items = run.clauses if read.kind == "wording" else run.assertions
    for it in items:
        lid = it.clause_id if read.kind == "wording" else it.assertion_id
        page, start, end = _loc(it.citation)
        value = None if read.kind == "wording" else it.value.text
        g.candidates.append(Candidate(lid, it.instrument.doc_id, it.side.value if hasattr(it, "side") else
                                      ("attack" if lid.startswith("attack:") else "support"),
                                      page, start, end, " ".join(it.citation.text.split()), value))
    if read.kind == "amount":  # D12 item 1: a line whose value is ambiguous is shown, never silently dropped
        evidence = {f"{e.side.value}:{e.doc_id}:{e.span_id[:8]}": e for e in run.evidence}
        for inv in run.invalid:
            ev = evidence.get(inv.mapping_id)
            if ev is None or not inv.reason.startswith(VALUE_AMBIGUOUS):
                continue
            page, start, end = _loc(ev.citation)
            amounts = find_amounts(ev.citation.text)
            figures = tuple(ev.citation.text[a:b] for a, b in amounts) if len(amounts) > 1 else ()
            g.candidates.append(Candidate(inv.mapping_id, ev.doc_id, ev.side.value, page, start, end,
                                          " ".join(ev.citation.text.split()), None, inv.reason, figures))
    found = {c.doc_id for c in g.candidates}
    g.nothing_found = [d for d, _ in run.documents if d not in found]
    return g


@dataclass
class Decided:
    run: PacketRun
    record: dict
    refusal: Refusal | None = None


def decide_typed(g: Gathered, confirmed: set[str], dropped: dict[str, str], *, confirmed_by: str,
                 policy_source: str, basis_set: Basis | None = None, grouping_mode: str = "person",
                 mapping_row: str | None = None, currency_set: str | None = None,
                 figures_set: dict[str, int] | None = None) -> Decided:
    """A person's grouping becomes the question; the unchanged decision tree runs on it.

    D12 item 5: a claim written with "$" (dollars, the country not printed) may have its currency set here
    by the person, as its basis may (D11). Only the claim's: a document's printed currency is never filled in.

    D13 item 2: `figures_set` maps a value_ambiguous line to the index of the figure the person picked among the
    amounts code found in its verified quote. Only lines that list figures take a pick; any other pick is ignored.
    """
    ids = {c.line_id for c in g.candidates}
    dollars = g.read.currency == DOLLARS_COUNTRY_NOT_PRINTED
    if currency_set is not None and not dollars:
        currency_set = None  # the claim names its currency; nothing to set
    if currency_set is not None and currency_set not in MINOR_UNITS:
        return Decided(g.run, {"claim_as_typed": g.read.text}, "currency_not_known")
    record = {
        "grouping_mode": grouping_mode, "mapping_row": mapping_row, "confirmed_by": confirmed_by,
        "policy": g.policy, "policy_source": policy_source,
        "claim_as_typed": g.read.text, "amount_as_written": g.read.written, "amount_as_read": g.read.value,
        "basis_source": "claimant" if g.read.basis else ("set_at_confirmation" if basis_set else "not_stated"),
        "currency_source": ("not_stated" if g.read.currency is None else "set_at_confirmation" if dollars and currency_set
                            else "dollars_country_not_printed" if dollars else "claimant"),
        "currency_set": currency_set if dollars else None,
        "value_source": "verified_quote", "value_set": [],
        "dropped": [{"line_id": k, "reason": v, "text": next(c.quote for c in g.candidates if c.line_id == k),
                     "doc_id": next(c.doc_id for c in g.candidates if c.line_id == k)} for k, v in dropped.items() if k in ids],
        "nothing_found": list(g.nothing_found),
    }
    if not g.candidates:
        return Decided(g.run, record, "no_candidate_line")
    if (confirmed | set(dropped)) != ids or confirmed & set(dropped) or any(not dropped[k].strip() for k in dropped):
        return Decided(g.run, record, "confirmation_incomplete")
    if not confirmed:
        return Decided(g.run, record, "no_line_confirmed")

    chosen = [c for c in g.candidates if c.line_id in confirmed]
    picks = {c.line_id: (figures_set or {})[c.line_id] for c in chosen if c.no_value and c.figures
             and isinstance((figures_set or {}).get(c.line_id), int) and 0 <= (figures_set or {})[c.line_id] < len(c.figures)}
    if any(c.no_value and c.line_id not in picks for c in chosen):
        record["value_ambiguous"] = [{"line_id": c.line_id, "doc_id": c.doc_id, "text": c.quote, "reason": c.no_value}
                                     for c in chosen if c.no_value and c.line_id not in picks]
        return Decided(g.run, record, "value_ambiguous")
    # The label comes from the printed wording: prefer a line from a document issued under the policy itself,
    # then the shortest. Amounts are stripped from the key.
    items = {x.clause_id if g.read.kind == "wording" else x.assertion_id: x
             for x in (g.run.clauses if g.read.kind == "wording" else g.run.assertions)}
    picked: list[Assertion] = []
    if picks:
        evidence = {f"{e.side.value}:{e.doc_id}:{e.span_id[:8]}": e for e in g.run.evidence}
        for c in chosen:
            if c.line_id not in picks:
                continue
            a = _picked_assertion(evidence.get(c.line_id), g.run.instruments.get(c.doc_id), picks[c.line_id], g.temp_slot)
            if a is None:
                record["figure_not_read"] = {"line_id": c.line_id, "text": c.quote, "figure": c.figures[picks[c.line_id]]}
                return Decided(g.run, record, "figure_not_read")
            picked.append(a)
            items[c.line_id] = a
            record["value_set"].append({"line_id": c.line_id, "doc_id": c.doc_id, "line": c.quote,
                                        "figure": a.value.text, "index": picks[c.line_id], "figures": list(c.figures)})
        record["value_source"] = "set_at_confirmation"
    own = [c for c in chosen if g.policy in items[c.line_id].instrument.policy_numbers]
    label = min((c.quote for c in (own or chosen)), key=len)
    final = f"{g.policy}.{_slug(re.sub(_AMOUNT_RE, ' ', label))}"
    record["question"] = final
    record["label_from"] = label
    value = g.read.value
    if g.read.kind == "amount" and basis_set and not g.read.basis:
        value = f"{value} {BASIS_PHRASE[basis_set]}"
    if g.read.kind == "amount" and dollars and currency_set and value.startswith("$"):
        value = f"{currency_set} {value[1:]}"
    record["claim_value_compared"] = value
    claim = Claim(claim_id=g.run.claim.claim_id, text=g.read.text, slot=final, kind=g.read.kind, value=value)

    run = g.run
    run.claim = claim
    if g.read.kind == "wording":
        run.clauses = [c for c in run.clauses if c.clause_id in confirmed]
        run.verdict = arbitrate_wording(claim, tuple(run.clauses), tuple(g.doc_ids), g.checked, (g.policy,))
    else:
        run.assertions = [a.model_copy(update={"slot": final}) for a in [*run.assertions, *picked] if a.assertion_id in confirmed]
        run.invalid = [x for x in run.invalid if x.mapping_id not in picks]
        run.verdict = arbitrate(claim, tuple(run.assertions), tuple(g.doc_ids), g.checked, (g.policy,))
    return Decided(run, record)


def _picked_assertion(ev, instrument, index: int, slot: str) -> Assertion | None:
    """D13 item 2: the assertion for a figure a person picked in a verified quote, or None if it cannot be read.

    The figure is the index-th amount code found in the quote, so it lies inside the verified text by
    construction; it goes through the same assertion step as a pointer would, and its reading route is
    recorded as set at confirmation, a judgment.
    """
    if ev is None or instrument is None:
        return None
    amounts = find_amounts(ev.citation.text)
    if not 0 <= index < len(amounts) or len(amounts) < 2:
        return None
    s, e = amounts[index]
    pointed = ev.model_copy(update={"value": Excerpt(start=s, end=e, text=ev.citation.text[s:e])})
    a = assert_from_evidence(pointed, instrument, slot, Trace(None))
    if not isinstance(a, Assertion):
        return None
    reading = RouteRef(mapping_id=f"set_at_confirmation:{ev.span_id}", method=MappingMethod.JUDGMENT, strength=RouteStrength.JUDGMENT)
    return a.model_copy(update={"routes": (a.routes[0], reading), "weakest": RouteStrength.JUDGMENT})
