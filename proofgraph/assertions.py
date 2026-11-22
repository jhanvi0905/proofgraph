"""Assertions: one cited cell -> one typed assertion on one slot (D1, D2).

Only the composite-cell route exists so far: Item VII's Primary-row retention.
Code splits the cell; the model is not involved. Every citation is checked
against the raw file at load:
- hash mismatch raises CitationHashMismatch (fatal: the file is not the file);
- text mismatch makes the assertion invalid, and it never enters comparison.
Fields the citation cannot source (currency, basis) are None. They are never filled in.
"""

from __future__ import annotations

from proofgraph.numbers import parse_amount
from proofgraph.schema import (
    Assertion,
    Citation,
    Instrument,
    InstrumentRef,
    InvalidAssertion,
    MappingMethod,
    MappingRecord,
    ParseFailure,
    SourceText,
    TraceRecord,
)
from proofgraph.trace import Trace


class CitationHashMismatch(RuntimeError):
    pass


def assert_cell(
    cell: MappingRecord,
    policy: MappingRecord,
    instrument: Instrument,
    source: SourceText,
    raw_file_text: str,
    trace: Trace,
) -> Assertion | InvalidAssertion:
    result = _assert_cell(cell, policy, instrument, source, raw_file_text)
    chunk = _containing_span(instrument, source, cell.cited)
    trace.write(TraceRecord(
        stage="assert", packet_id=None,
        atom_id=None, span_ids=(chunk,) if chunk else (), model=None, prompt_hash=None,
        input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False, verdict=None,
        rejects=(result.reason,) if isinstance(result, InvalidAssertion) else (), repairs=0,
        detail=result.to_json(),
    ))
    return result


def _assert_cell(cell, policy, instrument, source, raw) -> Assertion | InvalidAssertion:
    if cell.method is not MappingMethod.CELL_POSITION or cell.position is None:
        return InvalidAssertion(mapping_id=cell.mapping_id, reason="cell record is not a cell_position route")
    if policy.method is not MappingMethod.POLICY_NUMBER:
        return InvalidAssertion(mapping_id=policy.mapping_id, reason="policy record is not a policy_number route")
    for rec in (cell, policy):
        if rec.instrument_doc_id != instrument.doc_id:
            return InvalidAssertion(mapping_id=rec.mapping_id, reason=f"record belongs to {rec.instrument_doc_id}, not {instrument.doc_id}")
        for c in (rec.cited, *rec.justified_by):
            broken = _check_citation(c, source, raw)
            if broken:
                return InvalidAssertion(mapping_id=rec.mapping_id, reason=broken)
        if not _inside(rec.cited, instrument, source):
            return InvalidAssertion(mapping_id=rec.mapping_id, reason="cited text lies outside the asserting instrument")

    parts = cell.cited.text.split("/")
    if cell.position > len(parts):
        return InvalidAssertion(mapping_id=cell.mapping_id, reason=f"cell has {len(parts)} parts, position {cell.position}")
    part_start = cell.cited.start + sum(len(p) + 1 for p in parts[: cell.position - 1])
    part = parts[cell.position - 1]
    value = Citation(
        source_file=cell.cited.source_file, sha256_of_file=cell.cited.sha256_of_file, layer=cell.cited.layer,
        start=part_start, end=part_start + len(part), text=part,
    )
    if raw[value.start:value.end] != value.text:  # derived citation must still be exact
        return InvalidAssertion(mapping_id=cell.mapping_id, reason="derived value citation does not match the file")
    amount = parse_amount(part)
    if isinstance(amount, ParseFailure):
        return InvalidAssertion(mapping_id=cell.mapping_id, reason=f"value {part!r}: {amount.reason}")

    return Assertion(
        assertion_id=f"{instrument.doc_id}:{value.start}-{value.end}",
        slot=f"{policy.produces}.{cell.produces}",
        instrument=InstrumentRef(
            doc_id=instrument.doc_id, version=instrument.version, instrument_type=instrument.instrument_type,
            policy_numbers=instrument.policy_numbers, effective_date=instrument.effective_date,
        ),
        value=value,
        amount=amount,
        basis=None,  # Item VII has no basis column
        basis_phrase=None,
        mapping_ids=(policy.mapping_id, cell.mapping_id),
    )


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
