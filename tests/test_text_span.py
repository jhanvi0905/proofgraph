"""Local text-in-box mapping. No network and no Files API."""

import ast
import inspect
import zlib
from pathlib import Path

import pytest

from proofgraph.pdf import (
    TEXT_BOX_MARGINS,
    MarginMiss,
    SpanNotFound,
    UnsupportedPdf,
    bind_file_id,
    map_text_span,
    read_page_words,
    select_margin,
)

FIXTURE = Path(__file__).parent / "fixtures" / "text_span_rate.pdf"
ROOT = Path(__file__).resolve().parents[1]
RATE = (
    b"BT\n"
    b"/F1 12 Tf\n"
    b"1 0 0 1 72 700 Tm\n"
    b"(Detention: $75.00/hour after 2 hours free time) Tj\n"
    b"1 0 0 1 72 640 Tm\n"
    b"(Linehaul: $1,840.00) Tj\n"
    b"ET\n"
)
DETENTION = "Detention: $75.00/hour after 2 hours free time"


def _pdf_pages(streams: list[bytes], *, basefont: str = "Courier", flate: bool = False) -> bytes:
    """Minimal Courier PDF. Page numbers follow the /Kids order."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /" + basefont.encode("ascii") + b" >>",
    ]
    kids: list[str] = []
    for stream in streams:
        page_id = len(objects) + 1
        content_id = page_id + 1
        kids.append(f"{page_id} 0 R")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {content_id} 0 R /Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        payload = zlib.compress(stream) if flate else stream
        header = b"<< "
        if flate:
            header += b"/Filter /FlateDecode "
        header += b"/Length %d >>\nstream\n" % len(payload)
        objects.append(header + payload + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode())
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_fixture_is_the_local_rate_page():
    assert FIXTURE.is_file()
    raw = FIXTURE.read_bytes()
    assert raw == _pdf_pages([RATE])
    assert b"/BaseFont /Courier" in raw
    assert b"Detention: $75.00/hour after 2 hours free time" in raw


def test_full_line_maps_to_the_courier_grid():
    span = map_text_span(FIXTURE, DETENTION, page=1)
    assert span.page == 1
    assert span.box == (118, 107, 659, 119)
    assert span.margin == 0.02
    assert span.expanded_box == (98, 87, 679, 139)
    assert span.file_id is None
    assert span.words[0] == "Detention:"
    assert "Linehaul:" not in span.words
    assert "$75.00" in span.text


def test_inner_span_is_narrower_than_the_line():
    full = map_text_span(FIXTURE, DETENTION, page=1)
    money = map_text_span(FIXTURE, "$75.00", page=1, value="$75.00")
    end = map_text_span(FIXTURE, "time", page=1)
    assert money.box == (247, 107, 318, 119)
    assert end.box == (612, 107, 659, 119)
    assert money.box[0] > full.box[0]
    assert money.box[2] < full.box[2]
    assert money.margin == 0.02
    assert money.file_id is None


def test_bytes_and_path_agree():
    from_path = map_text_span(FIXTURE, "Detention:", page=1)
    from_bytes = map_text_span(FIXTURE.read_bytes(), "Detention:", page=1)
    assert from_bytes.box == from_path.box == (118, 107, 235, 119)


def test_margin_ladder_keeps_the_smallest_hit():
    """A box 2.1% of the page below the centres misses at 2% and hits at 3%.

    That is the 28 Oct rate-sheet observation: 3% stays on the detention line,
    and a box 3.5% below needs 4%, which also reaches linehaul.
    """
    words = read_page_words(FIXTURE, page=1)
    centres = [
        (word.top + word.bottom) / 2 / word.page_height * 1000
        for word in words
        if word.text.startswith("Detention")
    ]
    cy = centres[0]
    tight = select_margin(words, (0, round(cy + 21), 1000, round(cy + 40)), "$75.00")
    assert TEXT_BOX_MARGINS == (0.02, 0.03, 0.04)
    assert tight.margin == 0.03
    assert "Detention:" in tight.words
    assert "Linehaul:" not in tight.words

    wider = select_margin(words, (0, round(cy + 35), 1000, round(cy + 40)), "$75.00")
    assert wider.margin == 0.04
    assert "Detention:" in wider.words
    assert "Linehaul:" in wider.words


def test_margin_stops_at_four_percent():
    with pytest.raises(MarginMiss):
        map_text_span(FIXTURE, DETENTION, value="Linehaul")


def test_missing_quote_raises():
    with pytest.raises(SpanNotFound):
        map_text_span(FIXTURE, "not on the page", page=1)


def test_bind_file_id_is_local():
    span = map_text_span(FIXTURE, DETENTION, page=1)
    bound = bind_file_id(span, "  file_rate_01  ")
    assert span.file_id is None
    assert bound.file_id == "file_rate_01"
    assert bound.box == span.box
    assert bound.margin == span.margin
    assert bound.page == span.page
    assert bound.expanded_box == span.expanded_box
    with pytest.raises(ValueError):
        bind_file_id(span, "  ")
    with pytest.raises(TypeError):
        map_text_span(FIXTURE, DETENTION, page=1, file_id="file_rate_01")  # type: ignore[call-arg]


def test_mapping_module_does_not_call_the_network():
    source = (ROOT / "proofgraph" / "pdf.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    assert modules == ["__future__", "re", "zlib", "collections.abc", "dataclasses", "pathlib", "proofgraph.engine.numbers"]
    for name in modules:
        assert "muse" not in name
        assert "propose" not in name
        assert "clients" not in name
        assert not name.startswith(("socket", "http", "urllib", "httpx", "openai"))
    calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]
    assert "create" not in calls
    assert "bind_file_id" in source
    assert list(inspect.signature(map_text_span).parameters) == ["source", "quote", "page", "value"]
    assert list(inspect.signature(bind_file_id).parameters) == ["span", "file_id"]


def test_second_page_is_not_the_first():
    raw = _pdf_pages(
        [
            b"BT\n/F1 12 Tf\n1 0 0 1 72 700 Tm\n(Alpha line) Tj\nET\n",
            b"BT\n/F1 12 Tf\n1 0 0 1 72 700 Tm\n(Beta line) Tj\nET\n",
        ]
    )
    assert read_page_words(raw, page=2)[0].text == "Beta"
    span = map_text_span(raw, "Beta line", page=2)
    assert span.page == 2
    assert span.file_id is None
    with pytest.raises(SpanNotFound):
        map_text_span(raw, "Alpha line", page=2)


def test_flate_courier_matches_the_plain_stream():
    plain = read_page_words(_pdf_pages([RATE]), page=1)
    packed = read_page_words(_pdf_pages([RATE], flate=True), page=1)
    assert packed == plain


def test_non_courier_and_rotation_are_refused():
    with pytest.raises(UnsupportedPdf):
        read_page_words(_pdf_pages([RATE], basefont="Helvetica"), page=1)
    rotated = _pdf_pages([b"BT\n/F1 12 Tf\n0 1 -1 0 72 700 Tm\n(Hi) Tj\nET\n"])
    with pytest.raises(UnsupportedPdf):
        read_page_words(rotated, page=1)
    loose = _pdf_pages([b"(Hi) Tj\n"])
    with pytest.raises(UnsupportedPdf):
        read_page_words(loose, page=1)
