"""Checker: does a citation say what it claims, at the place it claims, in the file it claims?

verify_citation is the only verifier. It resolves the citation's locator
through a source adapter:
- raw_offsets: the raw file's characters at [start, end) equal the expected text;
- page_quote: each line of the expected text occurs exactly once on that PDF
  page, as found by the PDF parser (pdfplumber), not by this project's own text
  rebuild. When the citation records the region of the passage the model was
  shown (D12 item 2), "exactly once" is counted inside that region; repeats
  elsewhere on the page are not ambiguity. The lines run top to bottom, all in one
  column, with no other line between them. Columns come from the page's own
  coordinates (proofgraph.geometry, D12 item 3), never from the page midpoint.
  A recorded hash of the quoted text that does not match means the citation is
  stale. No offsets are used.
A file hash mismatch raises (fatal). Anything else that fails returns a reason,
and the caller marks the assertion invalid. Nothing is repaired.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from proofgraph.geometry import column_of, page_layout, page_words
from proofgraph.schema import BBox, Citation, Instrument, PageLayout, PageQuote, RawOffsets

_REGION_TOL = 1.0  # points: a hit's box may sit this far outside the passage's box (rounding of the two readers)


class CitationHashMismatch(RuntimeError):
    pass


@dataclass
class Source:
    """A source adapter: the file's hash, plus the one way its locators resolve."""

    path: Path
    sha256: str
    raw_text: str | None  # text sources
    _pdf: object | None = field(default=None, repr=False)  # opened lazily
    _geometry: dict = field(default_factory=dict, repr=False)  # page -> (layout, words)

    def page_hits(self, page: int, quote: str) -> int | None:
        found = self.page_find(page, quote)
        return None if found is None else len(found)

    def page_find(self, page: int, quote: str) -> list[tuple[float, float]] | None:
        """(x0, top) of every occurrence of `quote` on the page, or None if the page does not exist."""
        boxes = self.page_boxes(page, quote)
        return None if boxes is None else [(b.x0, b.top) for b in boxes]

    def page_boxes(self, page: int, quote: str) -> list[BBox] | None:
        """The box of every occurrence of `quote` on the page, or None if the page does not exist."""
        import pdfplumber

        if self._pdf is None:
            self._pdf = pdfplumber.open(self.path)
        pages = self._pdf.pages
        if not 1 <= page <= len(pages):
            return None
        return [BBox(x0=float(h["x0"]), top=float(h["top"]), x1=float(h["x1"]), bottom=float(h["bottom"]))
                for h in pages[page - 1].search(quote, regex=False, case=True)]

    def page_geometry(self, page: int) -> tuple[PageLayout, list[dict]]:
        """The page's columns and words, from pdfplumber's coordinates (stamps dropped). Never our extracted text."""
        if page not in self._geometry:
            p = self._pdf.pages[page - 1]
            words = page_words(p)
            self._geometry[page] = (page_layout(words, p.width), words)
        return self._geometry[page]


def open_source(path: Path) -> Source:
    data = path.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    if path.suffix.lower() == ".pdf":
        return Source(path=path, sha256=sha, raw_text=None)
    return Source(path=path, sha256=sha, raw_text=data.decode("ascii"))


def verify_citation(c: Citation, src: Source, within: Instrument | None = None) -> str | None:
    """None if the citation holds; otherwise why it is broken. Raises on a hash mismatch."""
    if c.sha256_of_file != src.sha256:
        raise CitationHashMismatch(f"{c.source_file}: citation hashes {c.sha256_of_file[:12]}, file is {src.sha256[:12]}")
    loc = c.locator
    if isinstance(loc, RawOffsets):
        if src.raw_text is None:
            return "raw_offsets locator on a source with no raw text layer"
        found = src.raw_text[loc.start:loc.end]
        if found != c.text:
            return f"broken citation at {loc.start}-{loc.end}: file has {found!r}"
        if within is not None and (within.file_start is None or not within.file_start <= loc.start <= loc.end <= within.file_end):
            return f"citation {loc.start}-{loc.end} lies outside {within.doc_id}"
        return None
    if isinstance(loc, PageQuote):
        if src.raw_text is not None:
            return "page_quote locator on a text source"
        if loc.text_sha256 is not None and loc.text_sha256 != hashlib.sha256(c.text.encode("utf-8")).hexdigest():
            return f"stale citation on page {loc.page}: the quoted text no longer matches its recorded hash; read again"
        where = " inside the passage's region" if loc.region is not None else ""
        boxes: list[BBox] = []
        for k, line in enumerate(c.text.split("\n"), 1):
            found = src.page_boxes(loc.page, line.strip())
            if found is None:
                return f"page {loc.page} does not exist"
            if loc.region is not None:
                found = [b for b in found if _inside(b, loc.region)]
            if len(found) != 1:
                what = "quote" if "\n" not in c.text else f"line {k} of the block"
                return f"{what} occurs {len(found)} times{where} on page {loc.page}; must be exactly once"
            boxes.append(found[0])
        if len(boxes) > 1:
            if any(b.top <= a.top for a, b in zip(boxes, boxes[1:])):
                return f"block lines on page {loc.page} are not in top-to-bottom order"
            layout, words = src.page_geometry(loc.page)
            if len({column_of(layout, b.x0, b.x1) for b in boxes}) > 1:
                return f"block lines on page {loc.page} span more than one column"
            for a, b in zip(boxes, boxes[1:]):
                lo, hi = min(a.x0, b.x0), max(a.x1, b.x1)
                if any(w["top"] >= a.bottom - 1 and w["bottom"] <= b.top + 1 and w["x0"] < hi and w["x1"] > lo for w in words):
                    return f"block lines on page {loc.page} are not consecutive: another line lies between them"
        if within is not None and not within.first_page <= loc.page <= within.last_page:
            return f"page {loc.page} lies outside {within.doc_id} (pages {within.first_page}-{within.last_page})"
        return None
    return f"unknown locator {type(loc).__name__}"


def _inside(b: BBox, region: BBox) -> bool:
    t = _REGION_TOL
    return region.x0 - t <= b.x0 and b.x1 <= region.x1 + t and region.top - t <= b.top and b.bottom <= region.bottom + t
