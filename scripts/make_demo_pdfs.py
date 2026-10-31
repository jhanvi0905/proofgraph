"""Write the two Courier PDFs for examples/freight/demo-001 from key.json.

The writer is the one in tests/test_text_span.py (`_pdf_pages`); reportlab is
not a dependency. Run it from the repo root:

    uv run python scripts/make_demo_pdfs.py

The invoice count line needs goods_noun and invoice_count in key.json. Until
the human fills them (docs/05, step 4) the invoice is written without it.
"""

from __future__ import annotations

import json
from pathlib import Path

PACKET = Path(__file__).resolve().parent.parent / "examples" / "freight" / "demo-001"

# Lines sit 60 points apart so a 2% to 4% margin on one line never reaches the next.
_TOP = 700
_STEP = 60


def pdf_pages(streams: list[bytes]) -> bytes:
    """Minimal Courier PDF. Same bytes as `_pdf_pages` in tests/test_text_span.py."""
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
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
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
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


def page_stream(lines: list[str]) -> bytes:
    """One Courier 12 page, one line per 60 points from the top."""
    parts = [b"BT\n", b"/F1 12 Tf\n"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        parts.append(f"1 0 0 1 72 {_TOP - index * _STEP} Tm\n".encode())
        parts.append(f"({escaped}) Tj\n".encode("latin-1"))
    parts.append(b"ET\n")
    return b"".join(parts)


def rate_confirmation(key: dict) -> bytes:
    truth = key["truth"]
    return pdf_pages(
        [
            page_stream(
                [
                    f"{key['carrier']} - Rate Confirmation",
                    f"Shipper: {key['shipper']}",
                    f"Detention: ${truth['rate_usd_per_hour']:.2f}/hour after "
                    f"{truth['free_hours']} hours free time",
                ]
            )
        ]
    )


def invoice(key: dict) -> bytes:
    truth = key["truth"]
    lines = [
        f"{key['carrier']} - Invoice",
        f"Bill to: {key['shipper']}",
        f"Detention: ${truth['invoice_detention_usd']:.2f}",
    ]
    if truth["goods_noun"] and truth["invoice_count"] is not None:
        lines.append(f"Delivered: {truth['invoice_count']} {truth['goods_noun']}s")
    return pdf_pages([page_stream(lines)])


def main() -> None:
    key = json.loads((PACKET / "key.json").read_text(encoding="utf-8"))
    (PACKET / "rate_confirmation.pdf").write_bytes(rate_confirmation(key))
    (PACKET / "invoice.pdf").write_bytes(invoice(key))
    truth = key["truth"]
    if not truth["goods_noun"] or truth["invoice_count"] is None:
        print("invoice.pdf has no count line: fill goods_noun and invoice_count, then rerun.")


if __name__ == "__main__":
    main()
