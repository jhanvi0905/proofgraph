"""Iteration 2 E: score a page's text layer, retry spacing, send hopeless pages to transcription."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from proofgraph.review.ingest import ingest
from proofgraph.review.text_quality import (
    CID_MAX_SHARE,
    LONG_MAX_SHARE,
    LONG_WORD,
    is_poor,
    long_share,
    cid_share,
    pick_better,
)

GOOD = "Net income was 58.4 million for the year ended December".split()
CID = ["C(cid:82)(cid:81)fide(cid:81)(cid:87)ial"] + GOOD[:10]
GLUED = ["Netincomewas$58.4millionforthefiscalyearended"] + GOOD[:5]


def test_shares_on_synthetic_tokens() -> None:
    assert cid_share(GOOD) == 0
    assert cid_share(["(cid:1)", "a", "b", "c"]) == 0.25
    assert long_share(["x" * (LONG_WORD + 1), "a"]) == 0.5
    assert long_share(["x" * LONG_WORD]) == 0  # exactly 25 is fine
    assert cid_share([]) == long_share([]) == 0


def test_is_poor_uses_fixed_thresholds() -> None:
    assert not is_poor(GOOD)
    assert is_poor(CID)
    assert is_poor(GLUED)
    # at the limit is not over it
    ok = ["(cid:1)"] + ["w"] * 49  # exactly 2%
    assert cid_share(ok) == pytest.approx(CID_MAX_SHARE) and not is_poor(ok)
    assert LONG_MAX_SHARE == 0.05


def test_pick_better_keeps_default_on_tie_and_prefers_lower_score() -> None:
    assert pick_better(GOOD, GOOD + ["x"]) == GOOD
    assert pick_better(GLUED, GOOD) == GOOD
    assert pick_better(GOOD, GLUED) == GOOD


def _pdf(path: Path, ops: str) -> None:
    """A one-page PDF with Helvetica and the given content-stream operators; no PDF library needed."""
    stream = f"BT /F1 10 Tf {ops} ET".encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Font /BaseFont /Courier >>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    path.write_bytes(out)


def _glued_pdf(path: Path) -> None:
    """Courier words (6pt a letter) 1.5pt apart: inside pdfplumber's default x_tolerance of 3, outside 1."""
    words = "Net income was $58.4 million for the fiscal year ended December thirty first".split()
    ops = [f"1 0 0 1 {50 + 42 * i} 720 Tm ({w}) Tj" for i, w in enumerate("Annual report of the company results".split())]
    x = 50.0
    for word in words:
        ops.append(f"1 0 0 1 {x:.2f} 700 Tm ({word}) Tj")
        x += 6 * len(word) + 1.5
    _pdf(path, " ".join(ops))


def test_flag_off_leaves_default_words(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    p = tmp_path / "g.pdf"
    _glued_pdf(p)
    [doc] = ingest([p])
    glued = [w.text for w in doc.pages[0].words]
    assert is_poor(glued)
    assert doc.pages[0].kind == "text"


def test_flag_on_retries_spacing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = tmp_path / "g.pdf"
    _glued_pdf(p)
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    off = [w.text for w in ingest([p])[0].pages[0].words]
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    [doc] = ingest([p])
    page = doc.pages[0]
    on = [w.text for w in page.words]
    assert page.kind == "text"
    assert not is_poor(on)
    assert long_share(on) < long_share(off)


def test_flag_on_cid_page_goes_to_transcription(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _pdf(tmp_path / "c.pdf", "50 700 Td (C\\(cid:82\\)\\(cid:81\\)fide (cid:1) (cid:2) agreement between the parties) Tj")
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    assert ingest([tmp_path / "c.pdf"])[0].pages[0].kind in {"text", "image_only"}
    off_kind = ingest([tmp_path / "c.pdf"])[0].pages[0].kind
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    assert ingest([tmp_path / "c.pdf"])[0].pages[0].kind == "image_only"
    assert off_kind  # flag-off kind unchanged by the new rule
