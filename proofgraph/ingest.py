"""Ingest: raw file -> exact source text -> instruments -> clause spans.

Offsets are recorded on the source text this module builds, and they are never
re-found by searching. The text is never stripped before offsets are taken.
Normalisation happens only inside span_id_for, for hashing.

There are two extractors:
- edgar_sgml: select one <DOCUMENT> by <TYPE>/<SEQUENCE>. The source text is that
  document's raw <TEXT> body, byte for byte, and <PAGE> markers give page numbers.
- pdf_columns: build the text from pdfplumber words, in reading order. Columns come
  from page coordinates (proofgraph.geometry, D12): a page is single (whole-page
  reading order) or has one or more gutters. Lines that cross a gutter count as full
  width. The columns are emitted left to right, then the full-width line. Pages are
  joined with a form feed. The geometry in force is recorded on each passage.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from proofgraph.geometry import FULL_WIDTH_MAX_GAP, column_of, page_layout, page_words, rows
from proofgraph.schema import (
    BBox,
    PageLayout,
    Definition,
    Extractor,
    IngestResult,
    Instrument,
    InstrumentLabel,
    SourceLabel,
    SourceText,
    Span,
    span_id_for,
)

PDF_EXTRACTOR_VERSION = "pdf_columns/v1"


def ingest(label: SourceLabel, raw_dir: Path) -> IngestResult:
    raw_path = raw_dir / label.file
    digest = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    if digest != label.sha256_of_file:
        raise ValueError(f"{label.file}: sha256 {digest} does not match manifest")

    if label.extractor is Extractor.EDGAR_SGML:
        text, page_starts, lines, file_offset = _edgar_text(raw_path, label)
        extractor = f"edgar_sgml/{label.edgar_type}/{label.edgar_sequence}"
    else:
        text, page_starts, lines = _pdf_text(raw_path)
        file_offset = None
        extractor = PDF_EXTRACTOR_VERSION

    source = SourceText(
        source_id=label.source_id,
        sha256_of_file=digest,
        extractor=extractor,
        text=text,
        page_starts=tuple(page_starts),
        file_offset=file_offset,
    )
    allcaps = label.extractor is Extractor.PDF_COLUMNS
    instruments = tuple(_instrument(il, source, lines, allcaps) for il in label.instruments)
    return IngestResult(source=source, instruments=instruments)


# ---------------------------------------------------------------- lines


@dataclass(frozen=True)
class _Line:
    """One physical line of source text. start/end index SourceText.text."""

    page: int
    start: int
    end: int
    bbox: BBox | None
    bold: bool | None  # every word bold; None when the source has no fonts (EDGAR)
    layout: PageLayout | None = None  # D12: the page's geometry (PDFs)


# ---------------------------------------------------------------- EDGAR

_DOC_RE = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.S)
_TEXT_RE = re.compile(r"<TEXT>\n?(.*?)</TEXT>", re.S)
_PAGE_RE = re.compile(r"^<PAGE>\s*(\d+)\s*$", re.M)


def _edgar_text(path: Path, label: SourceLabel) -> tuple[str, list[int], list[_Line], int]:
    raw = path.read_text(encoding="ascii")
    for m in _DOC_RE.finditer(raw):
        block = m.group(1)
        type_m = re.search(r"^<TYPE>(.+)$", block, re.M)
        seq_m = re.search(r"^<SEQUENCE>(\d+)$", block, re.M)
        if type_m and seq_m and type_m.group(1).strip() == label.edgar_type and int(seq_m.group(1)) == label.edgar_sequence:
            text_m = _TEXT_RE.search(block)
            if text_m is None:
                raise ValueError("EDGAR document has no <TEXT> body")
            text = text_m.group(1)
            file_offset = m.start(1) + text_m.start(1)
            break
    else:
        raise ValueError(f"no <DOCUMENT> with TYPE {label.edgar_type} SEQUENCE {label.edgar_sequence}")

    markers = list(_PAGE_RE.finditer(text))
    page_starts = [0] + [mk.start() for mk in markers[1:]]
    for i, mk in enumerate(markers, 1):
        if int(mk.group(1)) != i:
            raise ValueError(f"<PAGE> markers out of order at marker {i}")

    lines: list[_Line] = []
    pos = 0
    for raw_line in text.split("\n"):
        start, end = pos, pos + len(raw_line)
        pos = end + 1
        page = _page_of(start, page_starts)
        lines.append(_Line(page=page, start=start, end=end, bbox=None, bold=None))
    if raw[file_offset:file_offset + len(text)] != text:
        raise ValueError("EDGAR text body is not at its recorded file offset")
    return text, page_starts, lines, file_offset


# ---------------------------------------------------------------- PDF


def _pdf_text(path: Path) -> tuple[str, list[int], list[_Line]]:
    import pdfplumber

    parts: list[str] = []
    page_starts: list[int] = []
    lines: list[_Line] = []
    offset = 0
    with pdfplumber.open(path) as pdf:
        for page_no, page in enumerate(pdf.pages, 1):
            if page_no > 1:
                parts.append("\f")
                offset += 1
            page_starts.append(offset)
            page_lines, layout = _page_lines_layout(page)
            for i, (line_text, bbox, bold) in enumerate(page_lines):
                if i > 0:
                    parts.append("\n")
                    offset += 1
                parts.append(line_text)
                lines.append(_Line(page=page_no, start=offset, end=offset + len(line_text), bbox=bbox, bold=bold,
                                   layout=layout))
                offset += len(line_text)
    return "".join(parts), page_starts, lines


def pdf_text_layer(path: Path, first_pages: int = 3) -> tuple[int, list[str], bool]:
    """(page count, the first pages' text as the project's own column-aware lines, whether any page has a text layer).

    A page with no extractable non-blank characters (a scan, an image-only page) has no text layer. Additive
    helper for uploads; the extractor above is unchanged.
    """
    import pdfplumber

    texts: list[str] = []
    has_text = False
    with pdfplumber.open(path) as pdf:
        n = len(pdf.pages)
        for i, page in enumerate(pdf.pages):
            if any(c.get("text", "").strip() for c in page.chars):
                has_text = True
            if i < first_pages:
                texts.append("\n".join(t for t, _, _ in _page_lines(page)))
    return n, texts, has_text


def _page_lines(page) -> list[tuple[str, BBox, bool]]:
    return _page_lines_layout(page)[0]


def _page_lines_layout(page) -> tuple[list[tuple[str, BBox, bool]], PageLayout]:
    """The page's lines in reading order, and the geometry that set it (D12 item 3).

    Columns come from the page's coordinates (proofgraph.geometry, shared with the checker). A row with a
    word across a gutter, or with too narrow a gap between two columns' words, is full width: the columns
    read so far are emitted in order, then the row. A single-column page (no separable columns, or a table)
    is read row by row, left to right.
    """
    words = page_words(page, extra_attrs=["fontname"])
    layout = page_layout(words, page.width)
    rws = rows(words)
    if layout.kind == "single":
        return [_join(r) for r in rws], layout
    gutters = layout.gutters
    out: list[tuple[str, BBox, bool]] = []
    cols: list[list[tuple[str, BBox, bool]]] = [[] for _ in range(len(gutters) + 1)]
    for row in rws:
        parts: list[list[dict]] = [[] for _ in cols]
        crosses = False
        for w in row:
            k = column_of(layout, w["x0"], w["x1"])
            if k < 0:
                crosses = True
                break
            parts[k].append(w)
        occupied = [p for p in parts if p]
        narrow_gap = not crosses and any(
            min(w["x0"] for w in b) - max(w["x1"] for w in a) < FULL_WIDTH_MAX_GAP for a, b in zip(occupied, occupied[1:]))
        if crosses or narrow_gap:
            out += [ln for c in cols for ln in c] + [_join(row)]
            cols = [[] for _ in cols]
        else:
            for k, p in enumerate(parts):
                if p:
                    cols[k].append(_join(p))
    return out + [ln for c in cols for ln in c], layout


def _join(words: list[dict]) -> tuple[str, BBox, bool]:
    text = " ".join(w["text"] for w in words)
    bbox = BBox(
        x0=float(min(w["x0"] for w in words)),
        top=float(min(w["top"] for w in words)),
        x1=float(max(w["x1"] for w in words)),
        bottom=float(max(w["bottom"] for w in words)),
    )
    bold = all("Bold" in w["fontname"] for w in words)
    return text, bbox, bold


# ---------------------------------------------------------------- instruments and clauses


def _page_of(offset: int, page_starts: list[int] | tuple[int, ...]) -> int:
    page = 1
    for i, ps in enumerate(page_starts, 1):
        if offset >= ps:
            page = i
    return page


def _instrument(il: InstrumentLabel, source: SourceText, lines: list[_Line], allcaps: bool) -> Instrument:
    ps = source.page_starts
    if il.last_page > len(ps):
        raise ValueError(f"{il.doc_id}: last_page {il.last_page} beyond {len(ps)} pages")
    start = ps[il.first_page - 1]
    end = ps[il.last_page] if il.last_page < len(ps) else len(source.text)
    own = [ln for ln in lines if start <= ln.start and ln.end <= end]
    spans = tuple(_clauses(il, source.text, own, allcaps))
    return Instrument(
        doc_id=il.doc_id,
        version=il.version,
        instrument_type=il.instrument_type,
        issuer=il.issuer,
        policy_numbers=il.policy_numbers,
        effective_date=il.effective_date,
        source_id=source.source_id,
        source_start=start,
        source_end=end,
        first_page=il.first_page,
        last_page=il.last_page,
        file_start=None if source.file_offset is None else source.file_offset + start,
        file_end=None if source.file_offset is None else source.file_offset + end,
        spans=spans,
        definitions=tuple(_definitions(spans)),
    )


_SKIP_RE = re.compile(
    r"^\s*(</?(TABLE|CAPTION|S|C|PAGE|TEXT)>.*|[-=\s]*|.*Copyright, Insurance Services Office.*)\s*$"
)
# (level, pattern). Lower level = higher in the section path.
# Level 1 (an all-caps line) is used only for PDFs. EDGAR exhibits are mostly
# upper case, so there it would make every line a heading.
_SECTION_RE = re.compile(r"^\s*(SECTIONS? [IVX]+.*)$")
_ALLCAPS_RE = re.compile(r"^\s*([A-Z][A-Z ,&'–-]{4,44}[A-Z])\s*$")  # no trailing period: "EXCLUSIONS." is a cross-reference
_NUMBERED: list[tuple[int, re.Pattern[str]]] = [
    (2, re.compile(r"^\s*(\d{1,2})\.\s*(?=[A-Z\"$“])")),  # "10.Falling objects" has no space
    (3, re.compile(r"^\s*([a-z])\.\s+\S")),
    (4, re.compile(r"^\s*\((\d{1,2})\)\s+\S")),
]


def _heading(line: str, allcaps: bool, bold: bool | None) -> tuple[int, str] | None:
    # Where fonts are known, only bold lines are SECTION/all-caps headings.
    # Regular-weight "SECTION I – CONDITION 2.d." is a cross-reference.
    if bold is False:
        allcaps = False
    m = _SECTION_RE.match(line)
    if m and bold is not False:
        return 0, " ".join(m.group(1).split())
    if allcaps:
        m = _ALLCAPS_RE.match(line)
        if m:
            return 1, " ".join(m.group(1).split())
    for level, pat in _NUMBERED:
        m = pat.match(line)
        if m:
            return level, m.group(1)
    return None


# A key-value form field: a short label at line start, then a colon ("RETENTIONS:",
# "Retention:", "8. LIMIT OF LIABILITY:"). The label is context for the lines
# below it until the next label or numbered heading, across blank lines.
_FIELD_RE = re.compile(r"^\s*(?:\d{1,2}\.\s+|[A-Z]\.\s+|(?:-\s*)+)?([A-Z][A-Za-z0-9 &/()'.,-]{1,38}[A-Za-z)]):(?:\s|$)")


def _clauses(il: InstrumentLabel, text: str, lines: list[_Line], allcaps: bool):
    """Split at headings and numbered items. Blank lines also split (fallback).

    A SECTION heading wraps onto the next line ("SECTION I – PERILS" /
    "INSURED AGAINST"). An all-caps line that directly follows a SECTION
    heading continues it; it is not a new level.

    A form field's label is recorded as the last section_path entry of every
    span under it, so "USD 1,000,000 each Claim" keeps its "RETENTIONS"
    context after a blank line splits it off. Labels never move a span
    boundary, so span text, offsets and ids are unchanged.
    """
    field: str | None = None
    prev_was_section = False
    path: list[tuple[int, str]] = []
    cur: list[_Line] = []
    cur_path: tuple[str, ...] = ()

    def flush():
        nonlocal cur
        body = [ln for ln in cur if not _SKIP_RE.match(text[ln.start:ln.end])]
        cur = []
        if not body:
            return None
        # trim leading/trailing whitespace by moving offsets, never by stripping text
        s, e = body[0].start, body[-1].end
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        boxes = [ln.bbox for ln in body if ln.bbox is not None]
        bbox = (
            BBox(x0=min(b.x0 for b in boxes), top=min(b.top for b in boxes),
                 x1=max(b.x1 for b in boxes), bottom=max(b.bottom for b in boxes))
            if boxes and len({ln.page for ln in body}) == 1 else None
        )
        span_text = text[s:e]
        regions = _regions(body) if bbox is not None else ()
        return Span(
            span_id=span_id_for(il.doc_id, il.version, span_text, s, e),
            doc_id=il.doc_id,
            version=il.version,
            page=body[0].page,
            start=s,
            end=e,
            text=span_text,
            section_path=(il.doc_id,) + cur_path + ((field,) if field else ()),
            bbox=bbox,
            layout=body[0].layout,
            regions=regions,
        )

    for ln in lines:
        line_text = text[ln.start:ln.end]
        h = _heading(line_text, allcaps, ln.bold)
        blank = not line_text.strip()
        page_change = bool(cur) and cur[-1].page != ln.page
        continues_section = (
            prev_was_section and not page_change and h is not None and h[0] == 1
        ) or (prev_was_section and line_text.lstrip().startswith("–"))
        prev_was_section = h is not None and h[0] == 0
        if continues_section:
            level, name = path[-1]
            path[-1] = (level, f"{name} {' '.join(line_text.split())}")
            cur_path = tuple(n for _, n in path)
            cur.append(ln)
            prev_was_section = False
            continue
        if h is not None or blank or page_change:
            sp = flush()
            if sp is not None:
                yield sp
        if h is not None:
            level, name = h
            path = [p for p in path if p[0] < level] + [(level, name)]
            cur_path = tuple(n for _, n in path)
        if not blank:
            fm = _FIELD_RE.match(line_text)
            if fm:
                field = " ".join(fm.group(1).split())
            elif h is not None and h[0] <= 2:
                field = None
            cur.append(ln)
    sp = flush()
    if sp is not None:
        yield sp


def _regions(body: list[_Line]) -> tuple[BBox, ...]:
    """The passage's box in each column it covers (D12 item 2): consecutive lines in one column share a box."""
    runs: list[tuple[int, list[BBox]]] = []
    for ln in body:
        if ln.bbox is None:
            continue
        col = column_of(ln.layout, ln.bbox.x0, ln.bbox.x1) if ln.layout is not None else 0
        if runs and runs[-1][0] == col:
            runs[-1][1].append(ln.bbox)
        else:
            runs.append((col, [ln.bbox]))
    return tuple(BBox(x0=min(b.x0 for b in bs), top=min(b.top for b in bs), x1=max(b.x1 for b in bs),
                      bottom=max(b.bottom for b in bs)) for _, bs in runs)


_DEF_RE = re.compile(r"[\"“]([^\"”]{1,60})[\"”]\s+(?:means|includes)\b", re.I)


def _definitions(spans: tuple[Span, ...]):
    seen: set[str] = set()
    for sp in spans:
        for m in _DEF_RE.finditer(sp.text):
            term = " ".join(m.group(1).split()).lower()
            if term not in seen:
                seen.add(term)
                yield Definition(term=term, span_id=sp.span_id)
