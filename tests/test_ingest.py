"""R-03: ingest turns uploads into pages with kind, PNG and grid words."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageStat

from proofgraph.review.ingest import ingest

FREIGHT = Path(__file__).parent.parent / "examples" / "freight" / "demo-001"
RATE_CONF = FREIGHT / "rate_confirmation.pdf"


def _mean_brightness(png: bytes) -> float:
    return ImageStat.Stat(Image.open(io.BytesIO(png)).convert("L")).mean[0]


def test_text_pdf_page_one_has_words_on_the_grid() -> None:
    [doc] = ingest([RATE_CONF])
    assert doc.error is None
    page = doc.pages[0]
    assert page.kind == "text"
    assert page.page == 1
    assert len(page.words) > 5
    assert page.png.startswith(b"\x89PNG")
    for word in page.words:
        x0, y0, x1, y1 = word.box
        assert 0 <= x0 < x1 <= 1000
        assert 0 <= y0 < y1 <= 1000


def test_inverted_one_bit_png_comes_out_light(tmp_path: Path) -> None:
    dark = Image.new("1", (200, 300), 0)
    for x in range(20, 180, 8):
        dark.putpixel((x, 150), 1)
    path = tmp_path / "scan.png"
    dark.save(path)
    assert _mean_brightness(path.read_bytes()) < 100

    [doc] = ingest([path])
    assert doc.error is None
    assert doc.pages[0].kind == "image"
    assert _mean_brightness(doc.pages[0].png) > 200


def test_docx_is_refused_per_file(tmp_path: Path) -> None:
    docx = tmp_path / "contract.docx"
    docx.write_bytes(b"PK\x03\x04 not really")
    bad = tmp_path / "other.txt"
    bad.write_text("x")
    docs = ingest([docx, RATE_CONF, bad])
    assert "Save as PDF" in docs[0].error
    assert docs[0].pages == []
    assert docs[1].error is None
    assert docs[2].error


def test_truncated_pdf_returns_an_error(tmp_path: Path) -> None:
    raw = RATE_CONF.read_bytes()
    path = tmp_path / "cut.pdf"
    path.write_bytes(raw[: len(raw) // 3])
    [doc] = ingest([path])
    assert doc.error
    assert doc.pages == []


def test_garbage_and_missing_files_never_raise(tmp_path: Path) -> None:
    junk = tmp_path / "junk.png"
    junk.write_bytes(b"nope")
    docs = ingest([junk, tmp_path / "gone.pdf"])
    assert all(d.error and d.pages == [] for d in docs)


def test_names_are_decoded_and_stripped(tmp_path: Path) -> None:
    path = tmp_path / "  %20My%20Rate%20Conf%2Epdf "
    path.write_bytes(RATE_CONF.read_bytes())
    [doc] = ingest([path])
    assert doc.error is None
    assert doc.name == "My Rate Conf.pdf"
    assert doc.original_name == path.name
    assert len(doc.doc_id) == 12
