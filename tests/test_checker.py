"""One verifier, two locator kinds. The PDF check uses the PDF parser, never our column rebuild."""

from __future__ import annotations

from pathlib import Path

import pytest

from proofgraph.checker import CitationHashMismatch, open_source, verify_citation
from proofgraph.ingest import ingest
from proofgraph.schema import Citation, SourceManifest

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LABELS = {s.source_id: s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources}
HO, GIL = LABELS["iso_ho0003_0491"], LABELS["gillette_ex10e"]


def _pdf_cite(page: int, text: str, sha: str = HO.sha256_of_file) -> Citation:
    return Citation.model_validate({"source_file": HO.file, "sha256_of_file": sha,
                                    "locator": {"kind": "page_quote", "page": page}, "text": text})


def _raw_cite(start: int, text: str, sha: str = GIL.sha256_of_file) -> Citation:
    return Citation.model_validate({"source_file": GIL.file, "sha256_of_file": sha,
                                    "locator": {"kind": "raw_offsets", "start": start, "end": start + len(text)}, "text": text})


@pytest.fixture(scope="module")
def pdf():
    if not (RAW / HO.file).exists():
        pytest.skip("ISO file absent")
    return open_source(RAW / HO.file)


@pytest.fixture(scope="module")
def txt():
    if not (RAW / GIL.file).exists():
        pytest.skip("gillette file absent")
    return open_source(RAW / GIL.file)


def test_page_quote_found_once_holds(pdf):
    assert verify_citation(_pdf_cite(1, '"Bodily injury" means bodily harm, sickness or'), pdf) is None
    assert verify_citation(_pdf_cite(1, "Vacant land, other than farm land, owned by or"), pdf) is None  # right column


def test_page_quote_that_repeats_on_the_page_is_broken(pdf):
    assert "2 times" in verify_citation(_pdf_cite(1, "HO 00 03 04 91"), pdf)


def test_page_quote_across_a_line_break_is_broken(pdf):
    assert "0 times" in verify_citation(_pdf_cite(1, '"Bodily injury" means bodily harm, sickness or disease'), pdf)


def test_page_quote_on_the_wrong_page_is_broken(pdf):
    assert "0 times" in verify_citation(_pdf_cite(2, '"Bodily injury" means bodily harm, sickness or'), pdf)


def test_page_quote_must_be_one_line():
    with pytest.raises(ValueError):
        _pdf_cite(1, "two\nlines")


def test_page_quote_checks_the_instrument_page_range(pdf):
    inst = ingest(HO, RAW).instruments[0]
    narrowed = inst.model_copy(update={"first_page": 2, "last_page": 18})
    assert verify_citation(_pdf_cite(1, '"Bodily injury" means bodily harm, sickness or'), pdf, within=inst) is None
    assert "outside" in verify_citation(_pdf_cite(1, '"Bodily injury" means bodily harm, sickness or'), pdf, within=narrowed)


def test_raw_offsets_exact_and_broken(txt):
    assert verify_citation(_raw_cite(68460, "NIL/NIL/1,000,000"), txt) is None
    assert "broken" in verify_citation(_raw_cite(68460, "NIL/NIL/1,000,001"), txt)


def test_locator_kind_must_match_the_source(pdf):
    c = Citation.model_validate({"source_file": HO.file, "sha256_of_file": HO.sha256_of_file,
                                 "locator": {"kind": "raw_offsets", "start": 0, "end": 4}, "text": "%PDF"})
    assert "no raw text layer" in verify_citation(c, pdf)


def test_hash_mismatch_is_fatal_for_both_kinds(pdf, txt):
    with pytest.raises(CitationHashMismatch):
        verify_citation(_pdf_cite(1, "x", sha="0" * 64), pdf)
    with pytest.raises(CitationHashMismatch):
        verify_citation(_raw_cite(0, "x", sha="0" * 64), txt)
