"""Ingest invariants. Raw files are not in git; these tests skip when absent."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from proofgraph.ingest import ingest
from proofgraph.schema import IngestResult, SourceManifest, span_id_for

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
MANIFEST = SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text(encoding="utf-8"))
LABELS = {s.source_id: s for s in MANIFEST.sources}


@pytest.fixture(scope="module", params=sorted(LABELS))
def result(request) -> IngestResult:
    label = LABELS[request.param]
    if not (RAW / label.file).exists():
        pytest.skip(f"{label.file} not in data/raw")
    return ingest(label, RAW)


def _page_of(offset: int, page_starts: tuple[int, ...]) -> int:
    return max(i for i, ps in enumerate(page_starts, 1) if offset >= ps)


def test_every_span_is_its_source_slice(result: IngestResult):
    text = result.source.text
    for inst in result.instruments:
        for sp in inst.spans:
            assert text[sp.start:sp.end] == sp.text, sp.span_id


def test_spans_stay_inside_their_instrument_and_page(result: IngestResult):
    ps = result.source.page_starts
    for inst in result.instruments:
        for sp in inst.spans:
            assert inst.source_start <= sp.start < sp.end <= inst.source_end
            assert _page_of(sp.start, ps) == sp.page == _page_of(sp.end - 1, ps)


def test_span_ids_unique_and_recomputable(result: IngestResult):
    ids = [sp.span_id for inst in result.instruments for sp in inst.spans]
    assert len(ids) == len(set(ids))
    for inst in result.instruments:
        for sp in inst.spans:
            assert sp.span_id == span_id_for(sp.doc_id, sp.version, sp.text, sp.start, sp.end)


def test_instruments_tile_the_source(result: IngestResult):
    insts = sorted(result.instruments, key=lambda i: i.source_start)
    assert insts[0].source_start == 0
    assert insts[-1].source_end == len(result.source.text)
    for a, b in zip(insts, insts[1:]):
        assert a.source_end == b.source_start


# ---------------------------------------------------------------- EDGAR


def test_edgar_source_is_raw_bytes():
    label = LABELS["gillette_ex10e"]
    path = RAW / label.file
    if not path.exists():
        pytest.skip("gillette file absent")
    res = ingest(label, RAW)
    raw = path.read_text(encoding="ascii")
    assert raw.count(res.source.text) == 1
    assert len(res.source.page_starts) == 18
    end13 = next(i for i in res.instruments if i.doc_id == "coda_end13")
    schedule = next(sp for sp in end13.spans if "ERMA" in sp.text)
    assert "752034765-96" in schedule.text and "NIL/NIL/1,000,000" in schedule.text


# ---------------------------------------------------------------- PDF


def test_pdf_conserves_every_character():
    """Reading-order rebuild must neither drop nor duplicate a character.

    Characters, not words: word boundaries shift when a font changes mid-token
    (bold "10." + regular "$1000").
    """
    import pdfplumber

    label = LABELS["iso_ho0003_0491"]
    path = RAW / label.file
    if not path.exists():
        pytest.skip("ISO file absent")
    res = ingest(label, RAW)
    with pdfplumber.open(path) as pdf:
        expected = Counter(c["text"] for p in pdf.pages for c in p.chars if not c["text"].isspace())
    assert Counter(ch for ch in res.source.text if not ch.isspace()) == expected


def test_pdf_reading_order_and_headings():
    label = LABELS["iso_ho0003_0491"]
    if not (RAW / label.file).exists():
        pytest.skip("ISO file absent")
    res = ingest(label, RAW)
    text = res.source.text
    lines = text.split("\n")
    # page 1: right column follows the left column, not interleaved with it
    assert text.index('4. "Insured location" means') < text.index("c. Any premises used by you")
    assert "named c. Any premises" not in text
    # a centred heading that straddles the gutter stays one line
    assert "SECTION I – PERILS INSURED AGAINST" in lines
    paths = {sp.section_path[1] for sp in res.instruments[0].spans if len(sp.section_path) > 1}
    for heading in [
        "SECTION I – PROPERTY COVERAGES",
        "SECTION I – PERILS INSURED AGAINST",
        "SECTION I – EXCLUSIONS",
        "SECTION I – CONDITIONS",
        "SECTION II – LIABILITY COVERAGES",
        "SECTION II – EXCLUSIONS",
        "SECTION II – ADDITIONAL COVERAGES",
        "SECTION II – CONDITIONS",
        "SECTIONS I AND II – CONDITIONS",
    ]:
        assert heading in paths, heading
    # a regular-weight cross-reference is not a heading
    assert "SECTION I – CONDITION 2.d." not in paths
    terms = {d.term for d in res.instruments[0].definitions}
    assert {"bodily injury", "business", "insured", "insured location", "occurrence"} <= terms
