"""Assertions: one citation plus its routes -> one typed assertion on one slot (D1, D2).

Code reads the value from inside the citation; no model is involved. A
cell_position route splits a composite cell. Otherwise the first amount written
in the citation is taken. Currency and basis come only from inside the same
citation. When it does not write them they are None, never filled in.

Every citation (the assertion's, each route's, each justifying one) goes
through checker.verify_citation, the only verifier. A hash mismatch raises; a
broken citation makes the assertion invalid, and it never enters comparison.
The value and basis phrase are excerpts of the verified citation's own text,
so they are never located again.
"""

from __future__ import annotations

from proofgraph.checker import CitationHashMismatch, Source, verify_citation  # noqa: F401  (re-exported)
from proofgraph.numbers import find_amount, find_basis, parse_amount
from proofgraph.schema import (
    Assertion,
    AssertionInput,
    Citation,
    Excerpt,
    Instrument,
    InstrumentRef,
    InvalidAssertion,
    MappingFile,
    MappingMethod,
    MappingRecord,
    ParseFailure,
    RawOffsets,
    RouteRef,
    RouteStrength,
    TraceRecord,
)
from proofgraph.trace import Trace


def assert_one(
    inp: AssertionInput,
    mappings: MappingFile,
    instrument: Instrument,
    src: Source,
    trace: Trace,
) -> Assertion | InvalidAssertion:
    result = _assert(inp, mappings, instrument, src)
    chunk = _containing_span(instrument, inp.citation)
    trace.write(TraceRecord(
        stage="assert", packet_id=None, atom_id=inp.assertion_id, span_ids=(chunk,) if chunk else (),
        model=None, prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
        verdict=None, rejects=(result.reason,) if isinstance(result, InvalidAssertion) else (), repairs=0,
        detail=result.to_json(),
    ))
    return result


def _assert(inp: AssertionInput, mappings: MappingFile, instrument: Instrument, src: Source) -> Assertion | InvalidAssertion:
    def bad(reason: str) -> InvalidAssertion:
        return InvalidAssertion(mapping_id=inp.assertion_id, reason=reason)

    if inp.instrument_doc_id != instrument.doc_id:
        return bad(f"input names {inp.instrument_doc_id}, got {instrument.doc_id}")
    routes: list[MappingRecord] = []
    for rid in inp.route_ids:
        rec = next((r for r in mappings.records if r.mapping_id == rid), None)
        if rec is None:
            return bad(f"route {rid} not in mappings")
        if rec.instrument_doc_id != instrument.doc_id:
            return bad(f"route {rid} belongs to {rec.instrument_doc_id}")
        routes.append(rec)
    # the assertion's citation and each route's own citation must lie in the asserting instrument;
    # justifying citations may come from any document in the packet
    for c in (inp.citation, *(r.cited for r in routes)):
        broken = verify_citation(c, src, within=instrument)
        if broken:
            return bad(broken)
    for c in (j for r in routes for j in r.justified_by):
        broken = verify_citation(c, src)
        if broken:
            return bad(broken)

    policy_routes = [r for r in routes if "." not in r.produces]
    measure_routes = [r for r in routes if "." in r.produces]
    if len(policy_routes) != 1 or len(measure_routes) != 1:
        return bad("need exactly one route to the policy part and one to part.measure")
    measure = measure_routes[0]

    cit = inp.citation
    if measure.method is MappingMethod.CELL_POSITION:
        if measure.cited != cit or measure.position is None:
            return bad("cell_position route must cite the assertion's own cell")
        parts = cit.text.split("/")
        if measure.position > len(parts):
            return bad(f"cell has {len(parts)} parts, position {measure.position}")
        rel = sum(len(p) + 1 for p in parts[: measure.position - 1])
        span = (rel, rel + len(parts[measure.position - 1]))
    else:
        span = find_amount(cit.text)
        if span is None:
            return bad("no amount written in the citation")
    value = _excerpt(cit, *span)
    amount = parse_amount(value.text)
    if isinstance(amount, ParseFailure):
        return bad(f"value {value.text!r}: {amount.reason}")
    b = find_basis(cit.text)
    basis, basis_phrase = (b[0], _excerpt(cit, b[1], b[2])) if b else (None, None)

    return Assertion(
        assertion_id=inp.assertion_id,
        slot=f"{policy_routes[0].produces}.{measure.produces}",
        instrument=InstrumentRef(
            doc_id=instrument.doc_id, version=instrument.version, instrument_type=instrument.instrument_type,
            policy_numbers=instrument.policy_numbers, effective_date=instrument.effective_date,
        ),
        citation=cit,
        value=value,
        amount=amount,
        basis=basis,
        basis_phrase=basis_phrase,
        routes=tuple(RouteRef(mapping_id=r.mapping_id, method=r.method, strength=r.strength) for r in routes),
        weakest=_weakest(routes),
    )


_ORDER = [RouteStrength.READ, RouteStrength.DERIVED, RouteStrength.JUDGMENT]


def _weakest(routes: list[MappingRecord]) -> RouteStrength:
    return max((r.strength for r in routes), key=_ORDER.index)


def _excerpt(c: Citation, start: int, end: int) -> Excerpt:
    return Excerpt(start=start, end=end, text=c.text[start:end])


def _containing_span(instrument: Instrument, c: Citation) -> str | None:
    """The ingest chunk holding a raw-offset citation, for the trace. None for page quotes."""
    if not isinstance(c.locator, RawOffsets) or instrument.file_start is None:
        return None
    shift = instrument.file_start - instrument.source_start
    for sp in instrument.spans:
        if shift + sp.start <= c.locator.start and c.locator.end <= shift + sp.end:
            return sp.span_id
    return None
