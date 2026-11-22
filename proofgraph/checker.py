"""Checker: does a citation say what it claims, at the place it claims, in the file it claims?

verify_citation is the only verifier. It resolves the citation's locator
through a source adapter:
- raw_offsets: the raw file's characters at [start, end) equal the expected text;
- page_quote: the expected text occurs exactly once on that PDF page, as found
  by the PDF parser (pdfplumber), not by this project's own text rebuild.
A file hash mismatch raises (fatal). Anything else that fails returns a reason,
and the caller marks the assertion invalid. Nothing is repaired.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from proofgraph.schema import Citation, Instrument, PageQuote, RawOffsets


class CitationHashMismatch(RuntimeError):
    pass


@dataclass
class Source:
    """A source adapter: the file's hash, plus the one way its locators resolve."""

    path: Path
    sha256: str
    raw_text: str | None  # text sources
    _pdf: object | None = field(default=None, repr=False)  # opened lazily

    def page_hits(self, page: int, quote: str) -> int | None:
        import pdfplumber

        if self._pdf is None:
            self._pdf = pdfplumber.open(self.path)
        pages = self._pdf.pages
        if not 1 <= page <= len(pages):
            return None
        return len(pages[page - 1].search(quote, regex=False, case=True))


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
        hits = src.page_hits(loc.page, c.text)
        if hits is None:
            return f"page {loc.page} does not exist"
        if hits != 1:
            return f"quote occurs {hits} times on page {loc.page}; must be exactly once"
        if within is not None and not within.first_page <= loc.page <= within.last_page:
            return f"page {loc.page} lies outside {within.doc_id} (pages {within.first_page}-{within.last_page})"
        return None
    return f"unknown locator {type(loc).__name__}"
