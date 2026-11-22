"""Assertions: one citation plus its routes -> one typed assertion on one slot (D1, D2).

Code reads the value from inside the citation; no model is involved. A
cell_position route splits a composite cell. Otherwise the first amount written
in the citation is taken. Currency and basis come only from inside the same
citation. When it does not write them they are None, never filled in.

Every citation (the assertion's, each route's, each justifying one) is checked
against the raw file at load:
- hash mismatch raises CitationHashMismatch (fatal: the file is not the file);
- text mismatch makes the assertion invalid, and it never enters comparison.
"""

from __future__ import annotations

from proofgraph.numbers import find_amount, find_basis, parse_amount
from proofgraph.schema import (
    Assertion,
    AssertionInput,
    Citation,
    Instrument,
    InstrumentRef,
    InvalidAssertion,
    MappingFile,
    MappingMethod,
    MappingRecord,
    ParseFailure,
    RouteRef,
    RouteStrength,
    SourceText,
    TraceRecord,
)
from proofgraph.trace import Trace


class CitationHashMismatch(RuntimeError):
    pass


def assert_one(
    inp: AssertionInput,
    mappings: MappingFile,
    instrument: Instrument,
    source: SourceText,
    raw_file_text: str,
    trace: Trace,
) -> Assertion | InvalidAssertion:
    result = _assert(inp, mappings, instrument, source, raw_file_text)
    chunk = _containing_span(instrument, source, inp.citation)
    trace.write(TraceRecord(
        stage="assert", packet_id=None, atom_id=inp.assertion_id, span_ids=(chunk,) if chunk else (),
        model=None, prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
        verdict=None, rejects=(result.reason,) if isinstance(result, InvalidAssertion) else (), repairs=0,
        detail=result.to_json(),
    ))
    return result


def _assert(inp, mappings, instrument, source, raw) -> Assertion | InvalidAssertion:
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
    for c in (inp.citation, *(c for r in routes for c in (r.cited, *r.justified_by))):
        broken = _check_citation(c, source, raw)
        if broken:
            return bad(broken)
    for c in (inp.citation, *(r.cited for r in routes)):
        if not _inside(c, instrument, source):
            return bad(f"citation {c.start}-{c.end} lies outside {instrument.doc_id}")

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
    value = _sub(cit, *span)
    amount = parse_amount(value.text)
    if isinstance(amount, ParseFailure):
        return bad(f"value {value.text!r}: {amount.reason}")
    b = find_basis(cit.text)
    basis, basis_phrase = (b[0], _sub(cit, b[1], b[2])) if b else (None, None)

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


def _sub(c: Citation, rel_start: int, rel_end: int) -> Citation:
    """A citation to part of another, with exact offsets; text is sliced, never retyped."""
    return Citation(source_file=c.source_file, sha256_of_file=c.sha256_of_file, layer=c.layer,
                    start=c.start + rel_start, end=c.start + rel_end, text=c.text[rel_start:rel_end])


def _check_citation(c: Citation, source: SourceText, raw: str) -> str | None:
    if c.sha256_of_file != source.sha256_of_file:
        raise CitationHashMismatch(f"citation hashes {c.sha256_of_file[:12]}, file is {source.sha256_of_file[:12]}")
    if c.layer.value != "raw_file" or source.file_offset is None:
        return f"layer {c.layer.value} not supported for {source.source_id}"
    if raw[c.start:c.end] != c.text:
        return f"broken citation at {c.start}-{c.end}: file has {raw[c.start:c.end]!r}"
    return None


def _inside(c: Citation, instrument: Instrument, source: SourceText) -> bool:
    lo = source.file_offset + instrument.source_start
    hi = source.file_offset + instrument.source_end
    return lo <= c.start and c.end <= hi


def _containing_span(instrument: Instrument, source: SourceText, c: Citation) -> str | None:
    if source.file_offset is None:
        return None
    for sp in instrument.spans:
        if source.file_offset + sp.start <= c.start and c.end <= source.file_offset + sp.end:
            return sp.span_id
    return None
