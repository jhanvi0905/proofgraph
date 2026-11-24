"""A tiny PDF writer for geometry tests: Helvetica text placed at given coordinates, nothing else.

pdfplumber reads the characters with the standard font's widths, so a test can lay out columns,
gutters and repeated lines exactly where it wants them, with no PDF library and no committed file.
"""

from __future__ import annotations

from pathlib import Path


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path: Path, pages: list[list[tuple[float, float, str]]], width: float = 612, height: float = 792,
              size: float = 10) -> Path:
    """Each page is a list of (x, top, text): x from the left edge, top from the top edge, in points."""
    objs: list[bytes] = []
    kids = []
    font_id = 3
    page_ids = []
    for i, _ in enumerate(pages):
        page_ids.append(4 + 2 * i)
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{' '.join(f'{p} 0 R' for p in page_ids)}] /Count {len(pages)} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    for i, lines in enumerate(pages):
        ops = []
        for x, top, text in lines:
            y = height - top - size  # baseline from the bottom edge
            ops.append(f"BT /F1 {size} Tf {x:.2f} {y:.2f} Td ({_esc(text)}) Tj ET")
        stream = "\n".join(ops).encode("latin-1")
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
                    f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {page_ids[i] + 1} 0 R >>".encode())
        objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
        kids.append(page_ids[i])
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


FILLER = [
    "This is wrapped column text that runs across",
    "the column width so each line fills most of the",
    "column, the way policy wording is printed in",
]


def column_lines(x: float, top: float, n: int, step: float = 13.0) -> list[tuple[float, float, str]]:
    """n lines of filler text starting at (x, top)."""
    return [(x, top + k * step, FILLER[k % len(FILLER)]) for k in range(n)]
