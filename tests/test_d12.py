"""D12: verdict inputs come from verified text and a bounded region.

Each test names the old behaviour it rules out. The PDFs here are written by tests/pdfgen.py at test time,
laid out like the Family C pages (an off-centre gutter, hanging list numbers, parallel wording repeated
across coverages), so nothing third-party is committed.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pdfplumber
import pytest

from proofgraph.checker import open_source, verify_citation
from proofgraph.geometry import column_of, page_layout, page_words
from proofgraph.ingest import _page_lines_layout
from proofgraph.schema import BBox, Citation
from pdfgen import column_lines, write_pdf

# A Chubb-like page: left column at 42.5, right column's list numbers at 292 and its wrapped lines at 306.2,
# so the right column starts left of the page midpoint (306).
ITEM8 = "8. additional fees up to $5,000, as long as you"
ITEM8_2 = "have our written approval in advance, for:"
WAGES = "up to $5,000 per coverage period. You must"
LEFT = "a line printed once, in the left column only"


def _two_column_page():
    left = column_lines(42.5, 60, 30)
    left[6] = (42.5, 138, LEFT)
    right = column_lines(306.2, 60, 8) + [(292.0, 164, ITEM8), (306.2, 177, ITEM8_2)] + column_lines(306.2, 190, 20)
    return left + right


@pytest.fixture(scope="module")
def chubb_like(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("d12")
    # page 2: the same wage sentence printed under two coverages, one per column
    rep = (column_lines(42.5, 60, 10) + [(42.5, 190, WAGES)] + column_lines(42.5, 203, 18)
           + column_lines(306.2, 60, 14) + [(306.2, 242, WAGES)] + column_lines(306.2, 255, 14))
    return write_pdf(d / "chubb_like.pdf", [_two_column_page(), rep])


def _words(path: Path, page: int = 1):
    with pdfplumber.open(path) as pdf:
        p = pdf.pages[page - 1]
        return page_words(p), float(p.width)


def _cite(path: Path, page: int, text: str, region: BBox | None = None, sha: str | None = None) -> Citation:
    src = open_source(path)
    loc = {"kind": "page_quote", "page": page}
    if region is not None:
        loc["region"] = region.model_dump()
    if sha is not None:
        loc["text_sha256"] = sha
    return Citation.model_validate({"source_file": path.name, "sha256_of_file": src.sha256, "locator": loc, "text": text})


# ---------------------------------------------------------------- item 3: columns from page coordinates


def test_gutter_comes_from_coordinates_not_the_page_midpoint(chubb_like):
    words, width = _words(chubb_like)
    layout = page_layout(words, width)
    assert layout.kind == "columns" and len(layout.gutters) == 1
    g = layout.gutters[0]
    assert 270 < g < 292  # the whitespace between the columns, left of the midpoint
    # the old rule (x0 < width/2) put the right column's list number and its wrapped line in different columns
    assert (292.0 < width / 2) != (306.2 < width / 2)
    assert column_of(layout, 292.0, 500.0) == column_of(layout, 306.2, 500.0) == 1


def test_a_block_in_the_right_column_starting_left_of_the_midpoint_verifies(chubb_like):
    """Family C C3, run 2: the checker read this block as crossing columns. Coordinates say one column."""
    src = open_source(chubb_like)
    assert verify_citation(_cite(chubb_like, 1, ITEM8 + "\n" + ITEM8_2), src) is None


def test_lines_from_two_columns_are_still_refused(chubb_like):
    src = open_source(chubb_like)
    assert "more than one column" in verify_citation(_cite(chubb_like, 1, LEFT + "\n" + ITEM8), src)


def test_two_printed_pages_side_by_side_read_as_four_columns(tmp_path):
    xs = [20, 215, 410, 605]
    lines = [ln for x in xs for ln in column_lines(x, 60, 25)]
    path = write_pdf(tmp_path / "two_up.pdf", [lines], width=792, height=612, size=7)
    words, width = _words(path)
    layout = page_layout(words, width)
    assert layout.kind == "columns" and len(layout.gutters) == 3
    with pdfplumber.open(path) as pdf:
        out, _ = _page_lines_layout(pdf.pages[0])
    starts = [b.x0 for _, b, _ in out]
    # each column is read top to bottom before the next: four runs of x positions, left to right
    runs = [starts[0]] + [b for a, b in zip(starts, starts[1:]) if abs(a - b) > 1]
    assert [round(r) for r in runs] == xs


def test_a_table_is_read_row_by_row_not_split_into_columns(tmp_path):
    rows = [(42.6, 200 + 24 * k, f"{chr(65 + k)}. Coverage part {k}") for k in range(9)]
    rows += [(440.2, 200 + 24 * k, f"${k},000") for k in range(9)]
    rows += [(42.6, 150, "COVERAGE PART MAXIMUM COVERAGE PART LIMIT DEDUCTIBLE")]
    path = write_pdf(tmp_path / "table.pdf", [rows])
    words, width = _words(path)
    assert page_layout(words, width).kind == "single"
    with pdfplumber.open(path) as pdf:
        out, layout = _page_lines_layout(pdf.pages[0])
    assert "A. Coverage part 0 $0,000" in [t for t, _, _ in out]  # the label and its amount on one line


def test_the_iso_form_keeps_its_two_columns_and_gutters():
    """No existing reading order moves: every HO 00 03 page is two columns at the gutter used before D12."""
    path = Path(__file__).resolve().parent.parent / "data" / "raw" / "ho_00_03_04_91.pdf"
    if not path.exists():
        pytest.skip("ISO file absent")
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            words = page_words(p)
            layout = page_layout(words, p.width)
            assert layout.kind == "columns" and len(layout.gutters) == 1


def test_each_admitted_passage_records_the_geometry_in_force():
    from proofgraph.ingest import ingest
    from proofgraph.schema import SourceManifest

    root = Path(__file__).resolve().parent.parent
    labels = SourceManifest.model_validate_json((root / "data" / "instruments.json").read_text()).sources
    ho = next(s for s in labels if s.file.endswith(".pdf"))
    if not (root / "data" / "raw" / ho.file).exists():
        pytest.skip("ISO file absent")
    spans = [sp for i in ingest(ho, root / "data" / "raw").instruments for sp in i.spans]
    assert spans and all(sp.layout is not None and sp.layout.kind == "columns" for sp in spans)


# ---------------------------------------------------------------- item 2: identity is the page plus the region


def _region_of(path: Path, page: int, line: str, which: int) -> BBox:
    with pdfplumber.open(path) as pdf:
        hits = pdf.pages[page - 1].search(line, regex=False)
    h = sorted(hits, key=lambda h: h["x0"])[which]
    return BBox(x0=h["x0"] - 5, top=h["top"] - 40, x1=h["x1"] + 5, bottom=h["bottom"] + 40)


def test_a_line_repeated_elsewhere_on_the_page_is_not_ambiguity_inside_the_region(chubb_like):
    """Family C: parallel wording across coverages. Old rule: 2 times on the page, broken."""
    src = open_source(chubb_like)
    assert "2 times on page 2" in verify_citation(_cite(chubb_like, 2, WAGES), src)  # no region: the old rule
    for which in (0, 1):
        region = _region_of(chubb_like, 2, WAGES, which)
        assert verify_citation(_cite(chubb_like, 2, WAGES, region=region), src) is None


def test_a_quote_outside_the_region_is_broken(chubb_like):
    src = open_source(chubb_like)
    far = BBox(x0=40, top=600, x1=280, bottom=700)
    assert "0 times inside the passage's region" in verify_citation(_cite(chubb_like, 2, WAGES, region=far), src)


def test_lines_with_another_line_between_them_are_not_one_quote():
    """Old rule: each line once, top to bottom, same column, so lines 1 and 3 of a block passed as one quote."""
    path = Path(__file__).resolve().parent.parent / "data" / "raw" / "ho_00_03_04_91.pdf"
    if not path.exists():
        pytest.skip("ISO file absent")
    src = open_source(path)
    block = ['1. "Bodily injury" means bodily harm, sickness or', "disease, including required care, loss of services",
             "and death that results."]
    cite = lambda text: Citation.model_validate({"source_file": path.name, "sha256_of_file": src.sha256,
                                                 "locator": {"kind": "page_quote", "page": 1}, "text": text})
    assert verify_citation(cite("\n".join(block)), src) is None
    assert "not consecutive" in verify_citation(cite(block[0] + "\n" + block[2]), src)


def test_a_stale_text_hash_is_refused_never_substituted(chubb_like):
    src = open_source(chubb_like)
    good = hashlib.sha256(ITEM8.encode()).hexdigest()
    assert verify_citation(_cite(chubb_like, 1, ITEM8, sha=good), src) is None
    assert "stale" in verify_citation(_cite(chubb_like, 1, ITEM8, sha="0" * 64), src)


def test_raw_text_citations_keep_file_offsets():
    from proofgraph.schema import RawOffsets

    c = Citation.model_validate({"source_file": "x.txt", "sha256_of_file": "0" * 64,
                                 "locator": {"kind": "raw_offsets", "start": 10, "end": 13}, "text": "abc"})
    assert isinstance(c.locator, RawOffsets) and not hasattr(c.locator, "region")
