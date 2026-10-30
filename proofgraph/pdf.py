"""Local text-in-box coordinates for one PDF page.

The 0–1000 box uses a top-down y axis, matching pdfplumber's ``top``.
pdfplumber is not a project dependency, so this reader only accepts an
uncompressed or FlateDecode content stream that paints Courier with an
unrotated text matrix. It does not render pages, and it does not upload.

``map_text_span`` never takes a file id. After the Files API returns one,
the upload owner calls ``bind_file_id``.
"""

from __future__ import annotations

import re
import zlib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from proofgraph.engine.numbers import normalise_text

# Adobe Courier AFM. Every character is 600 units wide; the glyph box uses
# Ascender 629 and Descender -157. That is the stand-in for pdfplumber's
# top and bottom when the library is not installed.
_COURIER_WIDTH = 600 / 1000
_COURIER_ASCENT = 629 / 1000
_COURIER_DESCENT = -157 / 1000

# Smallest page-fraction whose word centres contain the fact value.
TEXT_BOX_MARGINS = (0.02, 0.03, 0.04)

_OBJ = re.compile(rb"(\d+)\s+0\s+obj\b(.*?)endobj", re.S)
_MEDIA = re.compile(
    rb"/MediaBox\s*\[\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)"
    rb"\s+([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\]"
)


class PdfTextError(ValueError):
    """The local PDF span could not be mapped."""


class UnsupportedPdf(PdfTextError):
    """This PDF uses a feature the local reader does not handle."""


class SpanNotFound(PdfTextError):
    """The quote is not on the requested page."""


class MarginMiss(PdfTextError):
    """No 2%, 3%, or 4% margin contains the value."""


@dataclass(frozen=True)
class PdfWord:
    """One Courier word. ``top`` and ``bottom`` are distances from the page top."""

    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    page: int
    page_width: float
    page_height: float


@dataclass(frozen=True)
class MarginMatch:
    """Smallest margin whose word centres contain ``text``."""

    margin: float
    box: tuple[int, int, int, int]
    expanded_box: tuple[int, int, int, int]
    words: tuple[str, ...]
    text: str


@dataclass(frozen=True)
class TextSpanBox:
    """Span box on the 0–1000 grid. ``file_id`` stays empty until ``bind_file_id``."""

    page: int
    box: tuple[int, int, int, int]
    margin: float
    expanded_box: tuple[int, int, int, int]
    quote: str
    value: str
    words: tuple[str, ...]
    text: str
    file_id: str | None = None


def read_page_words(source: str | Path | bytes, *, page: int = 1) -> tuple[PdfWord, ...]:
    """Read Courier words from one 1-based page of a local PDF."""
    if page < 1:
        raise ValueError("page is 1-based")
    objects = _objects(_read(source))
    pages = _page_bodies(objects)
    if page > len(pages):
        raise ValueError(f"page {page} is not in the PDF")
    words = _words_on_page(pages[page - 1], page, objects)
    return tuple(sorted(words, key=lambda word: (word.top, word.x0)))


def map_text_span(
    source: str | Path | bytes,
    quote: str,
    *,
    page: int = 1,
    value: str | None = None,
) -> TextSpanBox:
    """Map a quote on a local page to a 0–1000 box and the smallest fitting margin.

    The box is the span itself. The margin is the first of 2%, 3%, and 4% of
    the page whose word centres, inside that expanded box, contain ``value``.
    When ``value`` is omitted, the quote is the value. This does not take a
    file id and does not call the network.
    """
    sought = normalise_text(quote)
    if not sought:
        raise ValueError("quote is empty")
    checked = quote if value is None else value
    if not normalise_text(checked):
        raise ValueError("value is empty")
    words = read_page_words(source, page=page)
    x0, top, x1, bottom = _locate(words, sought)
    box = _clamp(_grid_box(x0, top, x1, bottom, words[0].page_width, words[0].page_height))
    match = select_margin(words, box, checked)
    return TextSpanBox(
        page=page,
        box=box,
        margin=match.margin,
        expanded_box=match.expanded_box,
        quote=quote,
        value=checked,
        words=match.words,
        text=match.text,
        file_id=None,
    )


def select_margin(
    words: Sequence[PdfWord],
    box: Sequence[int],
    value: str,
) -> MarginMatch:
    """Keep the smallest of 2%, 3%, and 4% whose words contain ``value``.

    A word counts when its centre falls inside the box expanded by that
    fraction of the page. On the 0–1000 grid the pad is ``margin * 1000``
    on each edge. The hit test uses the unclamped pad; the reported box is
    clamped to 0–1000.
    """
    grid = _require_box(box)
    needle = normalise_text(value)
    if not needle:
        raise ValueError("value is empty")
    for margin in TEXT_BOX_MARGINS:
        expanded = _pad(grid, margin)
        chosen = [word for word in words if _centre_inside(word, expanded)]
        chosen.sort(key=lambda word: (word.top, word.x0))
        text = " ".join(word.text for word in chosen)
        if needle in normalise_text(text):
            return MarginMatch(
                margin=margin,
                box=grid,
                expanded_box=_clamp(expanded),
                words=tuple(word.text for word in chosen),
                text=text,
            )
    raise MarginMiss("no margin in 2%, 3%, or 4% contains the value")


def bind_file_id(span: TextSpanBox, file_id: str) -> TextSpanBox:
    """Attach a Files API id to a local span box.

    The upload owner calls this after ``files.create``. It does not read the
    PDF, call the network, or import the Muse client. Copy ``box`` onto the
    fact and ``file_id`` onto the source when the bundle is wired.
    """
    if not isinstance(file_id, str) or not file_id.strip():
        raise ValueError("file_id is required")
    return replace(span, file_id=file_id.strip())


def _read(source: str | Path | bytes) -> bytes:
    if isinstance(source, bytes):
        return source
    return Path(source).read_bytes()


def _objects(data: bytes) -> dict[int, bytes]:
    found = {int(match.group(1)): match.group(2) for match in _OBJ.finditer(data)}
    if not found:
        raise UnsupportedPdf("PDF has no objects")
    return found


def _page_bodies(objects: dict[int, bytes]) -> list[bytes]:
    for body in objects.values():
        if re.search(rb"/Type\s*/Pages\b", body):
            kids = re.search(rb"/Kids\s*\[(.*?)\]", body, re.S)
            if kids:
                ids = [int(number) for number in re.findall(rb"(\d+)\s+0\s+R", kids.group(1))]
                try:
                    return [objects[number] for number in ids]
                except KeyError as exc:
                    raise UnsupportedPdf("page tree points at a missing object") from exc
    pages = [
        objects[number]
        for number in sorted(objects)
        if re.search(rb"/Type\s*/Page\b", objects[number])
    ]
    if not pages:
        raise UnsupportedPdf("PDF has no pages")
    return pages


def _words_on_page(page_body: bytes, page: int, objects: dict[int, bytes]) -> list[PdfWord]:
    llx, lly, urx, ury = _mediabox(page_body, objects)
    width = urx - llx
    height = ury - lly
    if width <= 0 or height <= 0:
        raise UnsupportedPdf("page MediaBox is empty")
    fonts = _fonts(page_body, objects)
    words: list[PdfWord] = []
    for content_id in _content_ids(page_body):
        try:
            stream = _stream(objects[content_id])
        except KeyError as exc:
            raise UnsupportedPdf("page content is missing") from exc
        words.extend(_paint(stream, fonts, page, llx, ury, width, height))
    return words


def _mediabox(page_body: bytes, objects: dict[int, bytes]) -> tuple[float, float, float, float]:
    found = _parse_mediabox(page_body)
    if found is not None:
        return found
    parent = re.search(rb"/Parent\s+(\d+)\s+0\s+R", page_body)
    if parent:
        found = _parse_mediabox(objects[int(parent.group(1))])
        if found is not None:
            return found
    raise UnsupportedPdf("page has no MediaBox")


def _parse_mediabox(body: bytes) -> tuple[float, float, float, float] | None:
    match = _MEDIA.search(body)
    if match is None:
        return None
    return tuple(float(piece) for piece in match.groups())  # type: ignore[return-value]


def _fonts(page_body: bytes, objects: dict[int, bytes]) -> dict[str, str]:
    block = re.search(rb"/Font\s*<<\s*(.*?)\s*>>", page_body, re.S)
    if block is None:
        raise UnsupportedPdf("page has no font")
    fonts: dict[str, str] = {}
    for name, number in re.findall(rb"/([A-Za-z0-9]+)\s+(\d+)\s+0\s+R", block.group(1)):
        try:
            font_body = objects[int(number)]
        except KeyError as exc:
            raise UnsupportedPdf("font object is missing") from exc
        base = re.search(rb"/BaseFont\s*/([A-Za-z0-9-]+)", font_body)
        if base is None:
            raise UnsupportedPdf("font has no BaseFont")
        fonts[name.decode("ascii")] = base.group(1).decode("ascii")
    if not fonts:
        raise UnsupportedPdf("page has no font")
    return fonts


def _content_ids(page_body: bytes) -> list[int]:
    match = re.search(rb"/Contents\s*(\[.*?\]|\d+\s+0\s+R)", page_body, re.S)
    if match is None:
        raise UnsupportedPdf("page has no contents")
    return [int(number) for number in re.findall(rb"(\d+)\s+0\s+R", match.group(1))]


def _stream(body: bytes) -> bytes:
    if re.search(rb"/Filter\s*\[", body):
        raise UnsupportedPdf("multiple stream filters are not supported")
    length = re.search(rb"/Length\s+(\d+)\b", body)
    marker = re.search(rb"stream\r?\n", body)
    if length is None or marker is None:
        raise UnsupportedPdf("content stream is missing")
    start = marker.end()
    data = body[start : start + int(length.group(1))]
    filters = re.findall(rb"/Filter\s*/([A-Za-z0-9]+)", body)
    if not filters:
        return data
    if filters == [b"FlateDecode"]:
        try:
            return zlib.decompress(data)
        except zlib.error as exc:
            raise UnsupportedPdf("FlateDecode stream could not be read") from exc
    raise UnsupportedPdf(f"unsupported stream filter: {filters[0].decode('ascii', 'replace')}")


def _paint(
    stream: bytes,
    fonts: dict[str, str],
    page: int,
    llx: float,
    ury: float,
    width: float,
    height: float,
) -> list[PdfWord]:
    words: list[PdfWord] = []
    stack: list[tuple[str, object]] = []
    in_text = False
    x = y = 0.0
    leading = 0.0
    size: float | None = None
    for kind, value in _tokens(stream):
        if kind != "op":
            stack.append((kind, value))
            continue
        op = str(value)
        if op == "cm":
            raise UnsupportedPdf("page transforms are not supported")
        if op in {"TJ", "'", '"', "Tc", "Tw", "Tz"}:
            raise UnsupportedPdf(f"{op} text is not supported")
        if op == "Tf":
            size = float(_pop(stack, "num"))
            name = str(_pop(stack, "name"))
            if fonts.get(name) != "Courier":
                found = fonts.get(name, "missing")
                raise UnsupportedPdf(f"only Courier is supported, found {found}")
            continue
        if op == "BT":
            in_text = True
            x = y = 0.0
            stack.clear()
            continue
        if op == "ET":
            in_text = False
            stack.clear()
            continue
        if op == "Tj" and not in_text:
            raise UnsupportedPdf("text showing outside BT")
        if not in_text:
            stack.clear()
            continue
        if op == "TL":
            leading = float(_pop(stack, "num"))
            continue
        if op == "Tm":
            numbers = [_pop(stack, "num") for _ in range(6)]
            numbers.reverse()
            a, b, c, d, e, f = (float(number) for number in numbers)
            if (a, b, c, d) != (1.0, 0.0, 0.0, 1.0):
                raise UnsupportedPdf("rotated text is not supported")
            x, y = e, f
            continue
        if op in {"Td", "TD"}:
            ty = float(_pop(stack, "num"))
            tx = float(_pop(stack, "num"))
            if op == "TD":
                leading = -ty
            x += tx
            y += ty
            continue
        if op == "T*":
            y -= leading
            continue
        if op == "Tj":
            if size is None:
                raise UnsupportedPdf("text size is missing")
            text = str(_pop(stack, "string"))
            x = _emit(text, x, y, size, page, llx, ury, width, height, words)
            continue
        raise UnsupportedPdf(f"unsupported text operator {op}")
    return words


def _emit(
    text: str,
    x: float,
    y: float,
    size: float,
    page: int,
    llx: float,
    ury: float,
    width: float,
    height: float,
    words: list[PdfWord],
) -> float:
    char_w = size * _COURIER_WIDTH
    top = ury - (y + size * _COURIER_ASCENT)
    bottom = ury - (y + size * _COURIER_DESCENT)
    cursor = x
    index = 0
    while index < len(text):
        if text[index] == " ":
            cursor += char_w
            index += 1
            continue
        end = index
        while end < len(text) and text[end] != " ":
            end += 1
        word = text[index:end]
        advance = char_w * len(word)
        words.append(
            PdfWord(
                text=word,
                x0=cursor - llx,
                x1=cursor + advance - llx,
                top=top,
                bottom=bottom,
                page=page,
                page_width=width,
                page_height=height,
            )
        )
        cursor += advance
        index = end
    return cursor


def _tokens(stream: bytes):
    index = 0
    length = len(stream)
    while index < length:
        char = stream[index]
        if char in b" \t\r\n\f\0":
            index += 1
            continue
        if char == ord("%"):
            while index < length and stream[index] not in b"\r\n":
                index += 1
            continue
        if char == ord("("):
            text, index = _literal(stream, index + 1)
            yield ("string", text)
            continue
        if char == ord("<"):
            raise UnsupportedPdf("hex strings are not supported")
        if char == ord("/"):
            start = index + 1
            index = start
            while index < length and stream[index] not in b" \t\r\n\f\0()<>[]{}/%":
                index += 1
            yield ("name", stream[start:index].decode("latin-1"))
            continue
        if char in b"0123456789+-.":
            start = index
            index += 1
            while index < length and stream[index] in b"0123456789.":
                index += 1
            try:
                yield ("num", float(stream[start:index]))
            except ValueError as exc:
                raise UnsupportedPdf("content stream has a bad number") from exc
            continue
        start = index
        while index < length and stream[index] not in b" \t\r\n\f\0()<>[]{}/%":
            index += 1
        yield ("op", stream[start:index].decode("latin-1"))


def _literal(stream: bytes, index: int) -> tuple[str, int]:
    chars: list[str] = []
    length = len(stream)
    while index < length:
        char = stream[index]
        if char == ord("\\"):
            index += 1
            if index >= length:
                break
            escaped = stream[index]
            named = {ord("n"): "\n", ord("r"): "\r", ord("t"): "\t", ord("b"): "\b", ord("f"): "\f"}
            if escaped in named:
                chars.append(named[escaped])
                index += 1
                continue
            if escaped in b"()\\":
                chars.append(chr(escaped))
                index += 1
                continue
            if escaped in b"01234567":
                octal = bytes([escaped])
                index += 1
                for _ in range(2):
                    if index < length and stream[index] in b"01234567":
                        octal += bytes([stream[index]])
                        index += 1
                chars.append(chr(int(octal, 8)))
                continue
            chars.append(chr(escaped))
            index += 1
            continue
        if char == ord(")"):
            return "".join(chars), index + 1
        chars.append(chr(char))
        index += 1
    raise UnsupportedPdf("text string is not closed")


def _pop(stack: list[tuple[str, object]], kind: str) -> object:
    if not stack or stack[-1][0] != kind:
        raise UnsupportedPdf(f"expected a {kind} operand")
    return stack.pop()[1]


def _locate(words: Sequence[PdfWord], quote: str) -> tuple[float, float, float, float]:
    if not words:
        raise SpanNotFound("quote not found on an empty page")
    lines: list[list[PdfWord]] = []
    for word in words:
        if lines and abs(word.top - lines[-1][0].top) <= 0.5:
            lines[-1].append(word)
        else:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda word: word.x0)
        raw = " ".join(word.text for word in line)
        folded = normalise_text(raw)
        if quote not in folded:
            continue
        if folded == raw:
            start = raw.find(quote)
            x0 = _x_at(line, start)
            x1 = _x_at(line, start + len(quote))
        else:
            x0 = line[0].x0
            x1 = line[-1].x1
        top = min(word.top for word in line)
        bottom = max(word.bottom for word in line)
        return x0, top, x1, bottom
    raise SpanNotFound(f"quote not found: {quote!r}")


def _x_at(words: Sequence[PdfWord], index: int) -> float:
    cursor = 0
    for position, word in enumerate(words):
        end = cursor + len(word.text)
        if index < end or (index == end and position == len(words) - 1):
            char_w = (word.x1 - word.x0) / len(word.text)
            return word.x0 + (index - cursor) * char_w
        cursor = end
        if position == len(words) - 1:
            break
        if index == cursor:
            return word.x1
        cursor += 1
    if words and index == cursor:
        return words[-1].x1
    raise SpanNotFound("quote span does not land on a word")


def _grid_box(
    x0: float,
    top: float,
    x1: float,
    bottom: float,
    page_width: float,
    page_height: float,
) -> tuple[int, int, int, int]:
    def scale_x(value: float) -> int:
        return round(value / page_width * 1000)

    def scale_y(value: float) -> int:
        return round(value / page_height * 1000)

    return (scale_x(x0), scale_y(top), scale_x(x1), scale_y(bottom))


def _require_box(box: Sequence[int]) -> tuple[int, int, int, int]:
    if len(box) != 4 or any(isinstance(value, bool) or not isinstance(value, int) for value in box):
        raise ValueError("box is four integers, [x_min, y_min, x_max, y_max]")
    x0, y0, x1, y1 = (int(value) for value in box)
    if x0 > x1 or y0 > y1:
        raise ValueError("box edges are reversed")
    return (x0, y0, x1, y1)


def _pad(box: tuple[int, int, int, int], margin: float) -> tuple[float, float, float, float]:
    pad = margin * 1000
    x0, y0, x1, y1 = box
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _clamp(box: Sequence[float]) -> tuple[int, int, int, int]:
    return tuple(min(1000, max(0, round(value))) for value in box)  # type: ignore[return-value]


def _centre_inside(word: PdfWord, box: tuple[float, float, float, float]) -> bool:
    cx = (word.x0 + word.x1) / 2 / word.page_width * 1000
    cy = (word.top + word.bottom) / 2 / word.page_height * 1000
    x0, y0, x1, y1 = box
    return x0 <= cx <= x1 and y0 <= cy <= y1
