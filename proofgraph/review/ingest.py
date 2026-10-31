"""Turn uploaded files into pages: kind, PNG, and words on the 0 to 1000 grid.

``ingest`` never raises. A file that cannot be read comes back with an
``error`` and no pages, so one bad upload does not stop the others.
"""

from __future__ import annotations

import hashlib
import io
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote

import pdfplumber
from PIL import Image, ImageOps, ImageStat

GRID = 1000
LONG_SIDE_PX = 1600
RENDER_DPI = 144
# Invert only a dark two-tone image (white-on-black negative or inverted scan):
# mean below DARK_MEAN AND at least NEGATIVE_BLACK_SHARE of pixels near-black
# (gray <= NEAR_BLACK). A dark photo of a page has mid-tone surround, so it
# stays as is. Tuned on synthetic images; when unsure, do not invert.
DARK_MEAN = 100
NEAR_BLACK = 30
NEGATIVE_BLACK_SHARE = 0.5
MIN_TEXT_WORDS = 5
CID_SHARE = 0.10

DOCX_ERROR = "Save as PDF and upload again."
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class Word:
    text: str
    box: tuple[int, int, int, int]  # x0, y0, x1, y1 on the 0 to 1000 grid


@dataclass(frozen=True)
class Page:
    page: int  # 1-based
    kind: str  # "text", "image_only" or "image"
    png: bytes
    words: list[Word] = field(default_factory=list)


@dataclass(frozen=True)
class IngestedDoc:
    doc_id: str
    name: str
    original_name: str
    pages: list[Page] = field(default_factory=list)
    error: str | None = None


def ingest(paths: Iterable[str | Path]) -> list[IngestedDoc]:
    return [_ingest_one(Path(p)) for p in paths]


def _clean_name(raw: str) -> str:
    name = _CONTROL.sub("", unquote(raw)).replace("\\", "/").rsplit("/", 1)[-1]
    return name.strip()


def _ingest_one(path: Path) -> IngestedDoc:
    original = path.name
    name = _clean_name(original) or "file"
    try:
        data = path.read_bytes()
    except Exception as exc:  # unreadable or missing
        return IngestedDoc("", name, original, error=f"Could not read file: {exc}")
    doc_id = hashlib.sha256(data).hexdigest()[:12]

    def failed(message: str) -> IngestedDoc:
        return IngestedDoc(doc_id, name, original, error=message)

    suffix = Path(name).suffix.lower()
    if suffix == ".docx":
        return failed(DOCX_ERROR)
    try:
        if suffix == ".pdf":
            pages = _pdf_pages(data)
        elif suffix in _IMAGE_SUFFIXES:
            pages = [_image_page(data)]
        else:
            return failed(f"Unsupported file type {suffix or '(none)'}. Upload a PDF.")
    except Exception as exc:
        return failed(f"Could not read {name}: {exc}")
    if not pages:
        return failed(f"Could not read {name}: no pages found.")
    return IngestedDoc(doc_id, name, original, pages)


def _to_png(image: Image.Image) -> bytes:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def _grid(value: float, size: float) -> int:
    return max(0, min(GRID, round(value / size * GRID)))


def _pdf_pages(data: bytes) -> list[Page]:
    pages: list[Page] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            width, height = float(page.width), float(page.height)
            words = [
                Word(
                    w["text"],
                    (
                        _grid(w["x0"], width),
                        _grid(w["top"], height),
                        _grid(w["x1"], width),
                        _grid(w["bottom"], height),
                    ),
                )
                for w in page.extract_words()
            ]
            dpi = min(RENDER_DPI, LONG_SIDE_PX / (max(width, height) / 72))
            png = _to_png(page.to_image(resolution=dpi).original.convert("RGB"))
            pages.append(Page(number, _pdf_kind(words), png, words))
    return pages


def _pdf_kind(words: list[Word]) -> str:
    if len(words) < MIN_TEXT_WORDS:
        return "image_only"
    cid = sum(w.text.startswith("(cid:") for w in words)
    return "image_only" if cid / len(words) > CID_SHARE else "text"


def _image_page(data: bytes) -> Page:
    gray = Image.open(io.BytesIO(data)).convert("L")
    hist = gray.histogram()
    black_share = sum(hist[: NEAR_BLACK + 1]) / sum(hist)
    if ImageStat.Stat(gray).mean[0] < DARK_MEAN and black_share >= NEGATIVE_BLACK_SHARE:
        gray = ImageOps.invert(gray)
    if max(gray.size) > LONG_SIDE_PX:
        gray.thumbnail((LONG_SIDE_PX, LONG_SIDE_PX))
    return Page(1, "image", _to_png(gray))
