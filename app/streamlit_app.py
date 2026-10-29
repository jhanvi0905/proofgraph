"""Freight packet review. A check runs only on files uploaded in this session."""

from __future__ import annotations

import html
import json
import re
import tempfile
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from proofgraph.adapters.base import for_engine
from proofgraph.engine.route import run_program
from proofgraph.engine.spans import propose_spans
from proofgraph.pdf import PdfTextError, map_text_span, read_page_words
from proofgraph.propose import propose
from proofgraph.schema import Case, ClaimProgram, Source, Verdict

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures"
FIXTURES = {
    "Detention": FIXTURE_DIR / "detention_program.json",
    "The sum": FIXTURE_DIR / "sum_program.json",
}

STORY_LEAD = (
    "A reviewer is asked to accept a detention charge. "
    "The citations can be the right lines and the figure can still be wrong. "
    "Upload the claim and the packet. The mark on the page is the evidence. "
    "The amount and the reason sit beside it."
)
PACKET_STORY = (
    "A freight billing reviewer uploads the claim and the evidence packet: "
    "a rate confirmation, a proof of delivery, and an invoice. "
    "ProofGraph shows the extracted facts, a mark on the page, and the claim amount beside the reason. "
    "The freight packet is a designed demonstration."
)
SAMPLE_NOTE = (
    "Upload the evidence files and type the claim. "
    "The check runs on those files after you press the button. "
    "No saved case is played."
)
PACKET_HELP = "A rate confirmation, a proof of delivery, and an invoice. PDF or image."

_DOC_TITLES = {
    "rate_conf": "Rate confirmation",
    "pod": "Proof of delivery",
    "invoice": "Invoice",
}
_PAGE_FONT = 14
_PAGE_WIDTH = 612
_PAGE_HEIGHT = 180
_PAGE_SCALE = 2
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/Library/Fonts/Courier New.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)
_PAPER_RGB = (250, 250, 249)
_INK_RGB = (28, 25, 23)
_HAIR_RGB = (231, 229, 228)
_ROSE_RGB = (159, 18, 57)
_DASH_RGB = (168, 162, 158)

VERDICT_GLOSS = {
    "SUPPORTED": "The checked links hold.",
    "CONTRADICTED": "A checked link does not hold.",
    "UNRESOLVED": "The documents do not settle this claim.",
}

LABEL_GLOSS = {
    "COMPUTED": "Every required link was a grounded fact or an executed calculation.",
    "CHECKED": "At least one link was confirmed by an independent wording check.",
    "ASSUMED": "The chain uses a rule the documents do not state.",
}

_INK = "#1c1917"
_SECONDARY = "#44403c"
_EYEBROW = "#78716c"
_HAIRLINE = "#e7e5e4"
_WASH = "#f5f5f4"
_DASH = "#a8a29e"

_STAMP = {
    "SUPPORTED": ("#166534", "#f0fdf4"),
    "CONTRADICTED": ("#9f1239", "#fff1f2"),
    "UNRESOLVED": ("#9a3412", "#fff7ed"),
}

_BADGE = {
    "COMPUTED": ("#1e3a8a", "#dbeafe", None),
    "CHECKED": ("#5b21b6", "#ede9fe", None),
    "ASSUMED": ("#44403c", "#f5f5f4", "#a8a29e"),
}

_SHOULD_BE = re.compile(
    r"should be (\$\d{1,3}(?:,\d{3})*(?:\.\d+)?), not (\$\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
)
_CLAIMED_MATCH = re.compile(
    r"matching the claimed (\$\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
)
_COMPUTED_TO = re.compile(
    r"computes? to (\$\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
)
_MONEY = re.compile(r"\$\d{1,3}(?:,\d{3})*(?:\.\d+)?")
_UNIT_TAIL = re.compile(
    r"(?:/[A-Za-z]+|\s+(?:hours?|hrs?|minutes?|mins?|days?|seconds?|secs?))\b"
)

_NO_LABEL = "No label. The chain did not settle."
_GAP = (
    "On this invoice the billed amount is {gap} above the figure those lines support."
)


class ReplayError(Exception):
    """A fixture problem the screen can show as text."""


@dataclass(frozen=True)
class FactRow:
    quote: str
    grounded: bool
    value: str = ""
    kind: str = "text"
    source_id: str = ""
    page: int = 1
    box: tuple[int, int, int, int] | None = None


@dataclass(frozen=True)
class LinkRow:
    link_id: str
    status: str
    strength: str
    detail: str


@dataclass(frozen=True)
class SpanRow:
    quote: str
    value: int | float | str
    scale: str | None
    kind: str


@dataclass(frozen=True)
class SourceView:
    source_id: str
    kind: str
    text: str
    title: str
    path: str | None = None


@dataclass(frozen=True)
class OverlayMark:
    """A located span. ``box`` is None when the quote is not on the page."""

    quote: str
    fact_quote: str
    role: str
    box: tuple[int, int, int, int] | None
    page: int = 1


@dataclass(frozen=True)
class MarkedPage:
    title: str
    source_id: str
    pdf: bytes | None
    marks: tuple[OverlayMark, ...]
    text: str


@dataclass(frozen=True)
class ReplayPacket:
    claim: str
    verdict: str
    label: str | None
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    fetch: tuple[str, ...]
    fact_checks: tuple[FactRow, ...]
    link_results: tuple[LinkRow, ...]
    sources: tuple[SourceView, ...]


def build_packet(path: Path) -> ReplayPacket:
    """Run one local fixture through the engine. No network."""

    case, program = _load_fixture(path)
    verdict = run_program(case, program)
    return _packet(case, program, verdict)


def live_case() -> Case:
    """Detention claim text. The saved program in that fixture is ignored."""

    case, _program = _load_fixture(FIXTURES["Detention"])
    return case


def check_claim(case: Case, *, client=None) -> ReplayPacket:
    """Propose a program, then let the engine decide. No saved program."""

    if not isinstance(case, Case):
        raise TypeError("case must be a Case")
    visible = for_engine(case)
    program = propose(visible, client=client)
    verdict = run_program(visible, program)
    return _packet(visible, program, verdict)


def _load_fixture(path: Path) -> tuple[Case, ClaimProgram]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"could not read fixture: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayError("fixture must contain case and program")
    try:
        case = Case.model_validate(payload["case"])
        program = ClaimProgram.model_validate(payload["program"])
    except KeyError as exc:
        raise ReplayError("fixture must contain case and program") from exc
    except ValidationError as exc:
        raise ReplayError(f"fixture does not match the schema: {exc}") from exc
    return case, program


def span_rows(text: str) -> tuple[SpanRow, ...]:
    """Candidate spans from plain text. No model call."""

    if not text.strip():
        return ()
    rows: list[SpanRow] = []
    for fact in propose_spans(text):
        value = fact.value if fact.value is not None else ""
        rows.append(
            SpanRow(
                quote=fact.quote or "",
                value=value,
                scale=fact.scale,
                kind=fact.kind,
            )
        )
    return tuple(rows)


def value_text(value: int | float | str) -> str:
    """Show a whole number without a trailing decimal."""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def failure_message(exc: BaseException) -> str:
    """Text for the page. A traceback is not included."""

    text = str(exc).strip()
    if not text or text.startswith("Traceback"):
        return exc.__class__.__name__
    return text.splitlines()[0].strip() or exc.__class__.__name__


def sample_packet() -> ReplayPacket:
    """The prepared detention packet, checked locally. No network."""

    return build_packet(FIXTURES["Detention"])


def locate_overlay(
    quote: str,
    *,
    pdf: bytes | str | Path | None = None,
    page: int = 1,
    box: Sequence[int] | None = None,
) -> tuple[int, int, int, int] | None:
    """Return a 0–1000 box from a fact box or from PDF word positions.

    An explicit box is used only when it is four integers on the 0–1000 grid.
    Otherwise the quote is located with the PDF text helper. A miss returns
    None. No rectangle is guessed.
    """

    if box is not None:
        return _grid_box(box)
    if pdf is None:
        return None
    sought = quote.strip()
    if not sought:
        return None
    try:
        return map_text_span(pdf, sought, page=page).box
    except (PdfTextError, ValueError):
        return None


def box_pixels(
    box: tuple[int, int, int, int],
    width: int,
    height: int,
) -> tuple[float, float, float, float]:
    """Map a 0–1000 top-down box onto an image of ``width`` by ``height``."""

    x0, y0, x1, y1 = box
    return (
        x0 / 1000 * width,
        y0 / 1000 * height,
        x1 / 1000 * width,
        y1 / 1000 * height,
    )


def mark_rects(
    marks: Sequence[OverlayMark],
    width: int,
    height: int,
) -> tuple[tuple[str, tuple[float, float, float, float]], ...]:
    """Rectangles to paint. A mark with no box is omitted."""

    rects = []
    for mark in marks:
        if mark.box is None:
            continue
        rects.append((mark.role, box_pixels(mark.box, width, height)))
    return tuple(rects)


def page_marks(packet: ReplayPacket) -> tuple[MarkedPage, ...]:
    """One page per source. Boxes come from fact boxes or quote positions."""

    claimed = _parsed_amounts(packet).claimed
    pages: list[MarkedPage] = []
    for source in packet.sources:
        pdf = _source_pdf(source)
        rows = tuple(row for row in packet.fact_checks if row.source_id == source.source_id)
        marks = tuple(
            _mark_on_pdf(row, claimed, pdf) for row in rows if row.quote.strip()
        )
        pages.append(
            MarkedPage(
                title=source.title,
                source_id=source.source_id,
                pdf=pdf,
                marks=marks,
                text=source.text,
            )
        )
    return tuple(pages)


def marks_for_text(
    text: str,
    facts: Sequence[tuple[str, bool]],
    *,
    claimed: str | None = None,
) -> tuple[OverlayMark, ...]:
    """Locate quotes on one text page. A missing quote has no box."""

    pdf = courier_pdf(text) if text.strip() else None
    marks = []
    for quote, grounded in facts:
        row = FactRow(quote=quote, grounded=grounded)
        marks.append(_mark_on_pdf(row, claimed, pdf))
    return tuple(marks)


def courier_pdf(text: str) -> bytes:
    """One Courier page whose words the local PDF helper can locate."""

    lines = text.splitlines() or [""]
    line_gap = _PAGE_FONT + 12
    height = 28 + line_gap * len(lines) + 24
    commands = ["BT", f"/F1 {_PAGE_FONT} Tf"]
    y = height - 28 - round(_PAGE_FONT * 0.629)
    for line in lines:
        commands.append(f"1 0 0 1 72 {y} Tm")
        commands.append(f"({_pdf_literal(line)}) Tj")
        y -= line_gap
    commands.append("ET")
    stream = ("\n".join(commands) + "\n").encode("latin-1")
    return _pdf_document(stream, height=height)


def render_marked_pdf(
    pdf: bytes,
    marks: Sequence[OverlayMark],
    *,
    page: int = 1,
) -> bytes:
    """Paint one PDF page and the marks whose boxes were located."""

    from io import BytesIO

    from PIL import Image, ImageDraw

    words = read_page_words(pdf, page=page)
    scale = _PAGE_SCALE
    if words:
        width = max(1, round(words[0].page_width * scale))
        height = max(1, round(words[0].page_height * scale))
    else:
        width, height = _PAGE_WIDTH * scale, _PAGE_HEIGHT * scale
    image = Image.new("RGB", (width, height), _PAPER_RGB)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width - 1, height - 1), outline=_HAIR_RGB)
    if words:
        font = _courier_font(_font_px(words[0], scale))
        for word in words:
            baseline = (word.top + _point_size(word) * 0.629) * scale
            draw.text(
                (word.x0 * scale, baseline),
                word.text,
                font=font,
                fill=_INK_RGB,
                anchor="ls",
            )
    chosen = tuple(mark for mark in marks if mark.page == page)
    for role, rect in mark_rects(chosen, width, height):
        _paint_rect(draw, rect, role)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def pdf_text(pdf: bytes) -> str:
    """Text layer of a Courier PDF. Other PDFs raise PdfTextError."""

    chunks = []
    for number in range(1, pdf_page_count(pdf) + 1):
        chunks.append(_words_text(read_page_words(pdf, page=number)))
    return "\n".join(chunk for chunk in chunks if chunk)


def pdf_page_count(pdf: bytes) -> int:
    count = 0
    while count < 30:
        try:
            read_page_words(pdf, page=count + 1)
        except ValueError:
            break
        count += 1
    return count


def span_marks(
    pdf: bytes,
    rows: Sequence[SpanRow],
    claim: str,
) -> tuple[OverlayMark, ...]:
    """Boxes for figure spans, from word positions on the uploaded PDF."""

    claimed = _first_money(claim)
    count = pdf_page_count(pdf)
    marks: list[OverlayMark] = []
    for row in rows:
        quote = (row.quote or "").strip()
        if not quote:
            continue
        role = _evidence_role(quote, True, claimed)
        snippet = _tight_quote(quote, row.kind, value_text(row.value), claimed)
        box, found_page, shown = _locate_on_pages(pdf, snippet, quote, count)
        marks.append(OverlayMark(shown, quote, role, box, found_page))
    return tuple(marks)


def main() -> None:
    """Draw the packet review. Streamlit stays inside this call."""

    import streamlit as st

    st.set_page_config(page_title="ProofGraph", layout="wide")
    _story(st)
    claim = st.text_area(
        "Claim",
        value="",
        height=88,
        placeholder="Type the claim these documents are supposed to support.",
    )
    files = st.file_uploader(
        "Evidence packet",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        help=PACKET_HELP,
    )
    if files:
        _show_upload(st, claim, files)
    else:
        st.caption(SAMPLE_NOTE)


def _packet(case: Case, program: ClaimProgram, verdict: Verdict) -> ReplayPacket:
    facts = {fact.id: fact for fact in program.facts}
    return ReplayPacket(
        claim=case.claim,
        verdict=verdict.verdict,
        label=verdict.label,
        reasons=tuple(verdict.reasons),
        reason_codes=tuple(verdict.reason_codes),
        fetch=tuple(verdict.fetch),
        fact_checks=tuple(_fact_row(facts.get(check.fact_id), check) for check in verdict.fact_checks),
        link_results=tuple(
            LinkRow(
                link_id=result.link_id,
                status=result.status,
                strength=result.strength,
                detail=result.detail,
            )
            for result in verdict.link_results
        ),
        sources=tuple(_source_view(source) for source in case.sources),
    )


def _fact_row(fact, check) -> FactRow:
    quote = ""
    value = ""
    kind = "text"
    source_id = ""
    page = 1
    box = None
    if fact is not None:
        quote = fact.quote or ""
        if fact.value is not None:
            value = value_text(fact.value)
        kind = fact.kind
        source_id = fact.source_id
        page = fact.page or 1
        if fact.box is not None:
            box = _grid_box(fact.box)
    return FactRow(
        quote=quote,
        grounded=check.status == "grounded",
        value=value,
        kind=kind,
        source_id=source_id,
        page=page,
        box=box,
    )


def _source_view(source: Source) -> SourceView:
    title = _DOC_TITLES.get(source.id)
    if title is None:
        title = source.id.replace("_", " ").strip().title() or "Document"
    return SourceView(
        source_id=source.id,
        kind=source.kind,
        text=source.text or "",
        title=title,
        path=source.path,
    )


def _detention_claim() -> str:
    try:
        return live_case().claim
    except ReplayError:
        return "The invoice detention charge of $450.00 is correct."


def _show_upload(st, claim: str, files) -> None:
    """Extract what the file can give offline. Propose runs only from the button."""

    texts: list[str] = []
    saw_pdf = False
    failed_pdf = False
    for uploaded in files:
        name = str(getattr(uploaded, "name", "document"))
        data = uploaded.getvalue()
        kind = _file_kind(name)
        st.html(_eyebrow(name))
        if kind == "image":
            st.image(data, width="stretch")
            st.html(_quiet("No region was located on this image, so nothing is boxed."))
            continue
        if kind != "pdf":
            st.html(_quiet("This file is not a PDF or an image, so nothing is boxed."))
            continue
        saw_pdf = True
        try:
            text = pdf_text(data)
            count = pdf_page_count(data)
        except PdfTextError:
            failed_pdf = True
            st.html(_quiet("This PDF's text could not be read offline, so there is no mark."))
            continue
        if text.strip():
            texts.append(text)
        rows = span_rows(text)
        st.html(_spans_html(text, rows))
        marks = span_marks(data, rows, claim)
        for number in range(1, max(count, 1) + 1):
            chosen = tuple(mark for mark in marks if mark.page == number)
            png = _safe_png(data, chosen, number)
            if png is not None:
                st.image(png, width="stretch", alt=name)
            _mark_captions(st, chosen)
    pasted = ""
    if failed_pdf or not saw_pdf:
        pasted = st.text_area(
            "Packet text",
            height=160,
            placeholder="Paste the packet if the file has no readable text.",
        )
        if pasted.strip():
            texts.append(pasted)
            st.html(_spans_html(pasted, span_rows(pasted)))
            st.html(_quiet("No box. Pasted text has no page positions."))
    st.caption("A live propose runs only when you press the button. A PDF or an image is uploaded with the claim.")
    if st.button("Check this claim", type="primary"):
        usable = [text for text in texts if text.strip()]
        saved = _write_uploads(files)
        if not claim.strip() or not (saved or usable):
            st.session_state["live_packet"] = None
            st.session_state["live_error"] = (
                "The claim and a packet file, or packet text, are both needed before a check."
            )
        else:
            case = _upload_case_files(claim, saved) if saved else _upload_case(claim, usable)
            status = None
            holder = nullcontext()
            if hasattr(st, "status"):
                holder = st.status("Checking this claim", expanded=True)
            try:
                with holder as status:
                    packet = check_claim(case)
                    if status is not None and hasattr(status, "update"):
                        status.update(state="complete", expanded=True)
                    st.session_state["live_packet"] = packet
                    st.session_state["live_error"] = ""
            except Exception as exc:
                if status is not None and hasattr(status, "update"):
                    status.update(state="error", expanded=True)
                st.session_state["live_packet"] = None
                st.session_state["live_error"] = failure_message(exc)
    error = st.session_state.get("live_error") or ""
    if error:
        st.error(error)
        return
    packet = st.session_state.get("live_packet")
    if packet is not None:
        _show_review(st, packet, show_claim=False)


def _show_review(st, packet: ReplayPacket, *, show_claim: bool = True) -> None:
    left, right = st.columns([1.15, 0.85], gap="large")
    with left:
        facts = _facts_html(packet)
        if facts:
            st.html(facts)
        for page in page_marks(packet):
            _show_marked_page(st, page)
    with right:
        st.html(_stamp_html(packet, show_claim=show_claim))


def _show_marked_page(st, page: MarkedPage) -> None:
    st.html(_eyebrow(page.title))
    png = _safe_png(page.pdf, page.marks, 1) if page.pdf is not None else None
    if png is not None:
        st.image(png, width="stretch", alt=page.title)
    elif page.text:
        grounded = tuple(
            mark.fact_quote for mark in page.marks if mark.role == "in the source" and mark.fact_quote
        )
        loose = tuple(
            mark.fact_quote
            for mark in page.marks
            if mark.role == "not in the source" and mark.fact_quote
        )
        claimed = next(
            (_first_money(mark.fact_quote) for mark in page.marks if mark.role == "claimed"),
            None,
        )
        st.html(_source_block(page.text, _figure_marks(page.text, grounded, loose, claimed)))
    _mark_captions(st, page.marks)


def _mark_captions(st, marks: Sequence[OverlayMark]) -> None:
    for mark in marks:
        if mark.box is None:
            st.html(_quiet(f"No box. {mark.fact_quote or mark.quote}"))
        else:
            st.html(_quiet(f"{mark.role} · {mark.quote}"))


def _safe_png(pdf: bytes, marks: Sequence[OverlayMark], page: int) -> bytes | None:
    try:
        return render_marked_pdf(pdf, marks, page=page)
    except (PdfTextError, ValueError, OSError):
        return None


def _story(st) -> None:
    st.html(
        "<div style='max-width:40rem'>"
        "<p style='font-size:0.75rem;font-weight:600;letter-spacing:0.06em;"
        f"text-transform:uppercase;color:{_EYEBROW};margin:0 0 0.35rem'>Verification</p>"
        "<p style='font-size:1.25rem;font-weight:650;line-height:1.2;"
        f"color:{_INK};margin:0 0 0.4rem'>ProofGraph</p>"
        "<p style='font-size:1.05rem;font-weight:600;line-height:1.45;"
        f"color:{_INK};margin:0'>{html.escape(STORY_LEAD)}</p>"
        "<p style='font-size:1rem;font-weight:400;line-height:1.5;"
        f"color:{_SECONDARY};margin:0.7rem 0 0'>{html.escape(PACKET_STORY)}</p>"
        "</div>"
    )


def _facts_html(packet: ReplayPacket) -> str:
    if not packet.fact_checks:
        return ""
    parts = ["<div style='margin:0.4rem 0 1rem'>", _eyebrow("Extracted")]
    for row in packet.fact_checks:
        state = "Grounded" if row.grounded else "Not grounded"
        color = "#166534" if row.grounded else "#9f1239"
        value = row.value or "—"
        parts.append(
            "<div style='border-top:1px solid "
            f"{_HAIRLINE};padding:0.45rem 0'>"
            f"<p style='margin:0;font-size:1rem;line-height:1.45;color:{_INK}'>"
            f"{html.escape(row.quote)}</p>"
            f"<p style='margin:0.15rem 0 0;font-size:0.8125rem;line-height:1.4;color:{_EYEBROW}'>"
            f"{html.escape(value)}"
            f" · <span style='color:{color};font-weight:650'>{state}</span></p>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _spans_html(text: str, rows: Sequence[SpanRow]) -> str:
    body = html.escape(text).replace("\n", "<br>")
    parts = [
        _eyebrow("Extracted"),
        "<p style='font-size:1rem;font-weight:400;line-height:1.5;"
        f"color:{_INK};margin:0'>{body}</p>",
    ]
    if not rows:
        parts.append(_quiet("No number, date, or time in that text."))
        return "".join(parts)
    parts.append("<div style='margin-top:0.8rem'>" + _eyebrow("Figures") + "</div>")
    for row in rows:
        parts.append(
            "<p style='font-size:1rem;font-weight:400;line-height:1.45;"
            f"color:{_INK};margin:0.2rem 0 0'>{html.escape(row.quote)} · "
            f"{html.escape(value_text(row.value))} · {html.escape(row.kind)}</p>"
        )
    return "".join(parts)


def _write_uploads(files) -> list[tuple[str, str]]:
    """Save uploaded PDFs and images. The live check uploads these paths."""

    saved: list[tuple[str, str]] = []
    if not files:
        return saved
    folder = Path(tempfile.mkdtemp(prefix="proofgraph-upload-"))
    for uploaded in files:
        name = Path(str(getattr(uploaded, "name", "document"))).name
        kind = _file_kind(name)
        if kind not in {"pdf", "image"}:
            continue
        dest = folder / name
        dest.write_bytes(uploaded.getvalue())
        saved.append((kind, str(dest)))
    return saved


def _upload_case_files(claim: str, saved: Sequence[tuple[str, str]]) -> Case:
    """One source per file. The path is what propose uploads."""

    sources = []
    for index, (kind, path) in enumerate(saved, start=1):
        if kind == "pdf":
            sources.append(Source(id=f"src_{index}", kind="pdf", path=path))
        else:
            sources.append(Source(id=f"src_{index}", kind="image", path=path))
    return Case(
        id="upload",
        dataset="freight",
        mode="whole",
        claim=claim.strip(),
        sources=sources,
    )


def _upload_case(claim: str, texts: Sequence[str]) -> Case:
    return Case(
        id="upload",
        dataset="freight",
        mode="passage",
        claim=claim.strip(),
        sources=[
            Source(id=f"src_{index}", kind="text", text=text)
            for index, text in enumerate(texts, start=1)
        ],
    )


def _file_kind(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".png", ".jpg", ".jpeg"}:
        return "image"
    return "other"


def _source_pdf(source: SourceView) -> bytes | None:
    if source.path:
        try:
            return Path(source.path).read_bytes()
        except OSError:
            return None
    if source.text.strip():
        return courier_pdf(source.text)
    return None


def _mark_on_pdf(row: FactRow, claimed: str | None, pdf: bytes | None) -> OverlayMark:
    role = _evidence_role(row.quote, row.grounded, claimed)
    if row.box is not None:
        return OverlayMark(row.quote, row.quote, role, row.box, row.page)
    if pdf is None or not row.quote.strip():
        return OverlayMark(row.quote, row.quote, role, None, 1)
    snippet = _tight_quote(row.quote, row.kind, row.value, claimed)
    box = locate_overlay(snippet, pdf=pdf, page=1)
    if box is not None:
        return OverlayMark(snippet, row.quote, role, box, 1)
    if snippet != row.quote:
        full = locate_overlay(row.quote, pdf=pdf, page=1)
        if full is not None:
            return OverlayMark(row.quote, row.quote, role, full, 1)
    return OverlayMark(row.quote, row.quote, role, None, 1)


def _locate_on_pages(
    pdf: bytes,
    snippet: str,
    quote: str,
    count: int,
) -> tuple[tuple[int, int, int, int] | None, int, str]:
    pages = range(1, max(count, 1) + 1)
    for number in pages:
        box = locate_overlay(snippet, pdf=pdf, page=number)
        if box is not None:
            return box, number, snippet
    if snippet != quote:
        for number in pages:
            box = locate_overlay(quote, pdf=pdf, page=number)
            if box is not None:
                return box, number, quote
    return None, 1, quote


def _evidence_role(quote: str, grounded: bool, claimed: str | None) -> str:
    if claimed and any(_same_money(match.group(0), claimed) for match in _MONEY.finditer(quote)):
        return "claimed"
    if grounded:
        return "in the source"
    return "not in the source"


def _tight_quote(quote: str, kind: str, value: str, claimed: str | None) -> str:
    if claimed:
        for match in _MONEY.finditer(quote):
            if _same_money(match.group(0), claimed):
                return match.group(0)
    if kind == "time" and value and value in quote:
        return value
    if kind == "number" and value:
        for match in _MONEY.finditer(quote):
            if _money_matches_value(match.group(0), value):
                return match.group(0)
    return quote


def _money_matches_value(token: str, value: str) -> bool:
    money = _money_value(token)
    if money is None or not value:
        return False
    try:
        return money == Decimal(value)
    except Exception:
        return False


def _first_money(text: str) -> str | None:
    match = _MONEY.search(text)
    if match is None:
        return None
    return match.group(0)


def _grid_box(box: Sequence[int]) -> tuple[int, int, int, int] | None:
    if isinstance(box, (str, bytes)) or len(box) != 4:
        return None
    values = tuple(box)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
        return None
    x0, y0, x1, y1 = values
    if not (0 <= x0 <= x1 <= 1000 and 0 <= y0 <= y1 <= 1000):
        return None
    return (x0, y0, x1, y1)


def _pdf_literal(text: str) -> str:
    cleaned = text.encode("latin-1", "replace").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_document(stream: bytes, *, height: int) -> bytes:
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PAGE_WIDTH} {height}] "
            f"/Contents 5 0 R /Resources << /Font << /F1 3 0 R >> >> >>"
        ).encode("ascii"),
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{number} 0 obj\n".encode("ascii"))
        out.extend(body)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    out.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    out.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


def _words_text(words: Sequence[object]) -> str:
    lines: list[list[object]] = []
    for word in words:
        if lines and abs(word.top - lines[-1][0].top) <= 0.5:  # type: ignore[attr-defined]
            lines[-1].append(word)
        else:
            lines.append([word])
    return "\n".join(
        " ".join(word.text for word in line)  # type: ignore[attr-defined]
        for line in lines
    )


def _point_size(word: object) -> float:
    char_w = (word.x1 - word.x0) / max(1, len(word.text))  # type: ignore[attr-defined]
    return char_w / 0.6


def _font_px(word: object, scale: float) -> int:
    return max(8, round(_point_size(word) * scale))


def _courier_font(size: int):
    from PIL import ImageFont

    for path in _FONT_CANDIDATES:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _paint_rect(draw, rect: tuple[float, float, float, float], role: str) -> None:
    x0, y0, x1, y1 = rect
    if role == "claimed":
        draw.rectangle((x0, y0, x1, y1), outline=_ROSE_RGB, width=2)
        mid = (y0 + y1) / 2
        draw.line((x0, mid - 2, x1, mid - 2), fill=_ROSE_RGB, width=1)
        draw.line((x0, mid + 2, x1, mid + 2), fill=_ROSE_RGB, width=1)
        return
    color = _INK_RGB if role == "in the source" else _DASH_RGB
    draw.rectangle((x0, y0, x1, y1), outline=color, width=2)


def _stamp_html(packet: ReplayPacket, *, show_claim: bool) -> str:
    ink, wash = _STAMP.get(packet.verdict, (_INK, _WASH))
    parsed = _parsed_amounts(packet)
    parts: list[str] = [
        "<div style='background:"
        f"{wash};border-left:6px solid {ink};border-radius:0.75rem;"
        "padding:1.05rem 1.2rem 1.1rem 1.15rem;margin:1.15rem 0 0'>"
    ]
    if show_claim:
        parts.append(_eyebrow("Claim"))
        parts.append(_claim_sentence(packet.claim, claimed=parsed.claimed))
        parts.append(
            "<div style='height:1px;background:"
            f"{_HAIRLINE};margin:0.85rem 0'></div>"
        )
    parts.append(_eyebrow("Verdict"))
    parts.append(
        "<p style='font-size:0.8125rem;font-weight:700;letter-spacing:0.06em;"
        "text-transform:uppercase;line-height:1.3;margin:0.1rem 0 0;"
        f"color:{ink}'>{html.escape(packet.verdict)}</p>"
    )
    badge = _badge_html(packet.label)
    if badge:
        parts.append(f"<p style='margin:0.5rem 0 0'>{badge}</p>")
    gloss = _gloss(packet.label)
    if gloss:
        parts.append(_quiet(gloss, color=_SECONDARY))
    if parsed.hero:
        parts.append(
            "<p style='font-size:2.75rem;font-weight:650;line-height:1.05;"
            "font-variant-numeric:tabular-nums;letter-spacing:-0.03em;"
            f"color:{ink};margin:0.7rem 0 0'>{html.escape(parsed.hero)}</p>"
        )
    for reason in packet.reasons:
        parts.append(
            "<p style='font-size:1.125rem;font-weight:600;line-height:1.45;"
            f"color:{_INK};margin:0.55rem 0 0'>{html.escape(reason)}</p>"
        )
    if parsed.gap:
        parts.append(_quiet(parsed.gap))
    chain = _chain_caption(packet)
    if chain:
        parts.append(_quiet(chain))
    parts.append("</div>")
    return "".join(parts)


def _sources_html(packet: ReplayPacket) -> str:
    claimed = _parsed_amounts(packet).claimed
    grounded = tuple(row.quote for row in packet.fact_checks if row.grounded and row.quote)
    loose = tuple(row.quote for row in packet.fact_checks if not row.grounded and row.quote)
    blocks = [
        _source_block(source.text, _figure_marks(source.text, grounded, loose, claimed))
        for source in packet.sources
        if source.text
    ]
    return "".join(blocks)


def _case_lines(case: Case) -> tuple[str, ...]:
    return tuple(source.text for source in case.sources if source.text)


@dataclass(frozen=True)
class _Amounts:
    hero: str | None
    claimed: str | None
    gap: str | None


def _parsed_amounts(packet: ReplayPacket) -> _Amounts:
    """Hero and strike come only from the engine reason. No invented figure."""

    text = " ".join(packet.reasons)
    should = _SHOULD_BE.search(text)
    if should and packet.verdict == "CONTRADICTED":
        hero, claimed = should.group(1), should.group(2)
        return _Amounts(hero, claimed, _gap_caption(hero, claimed))
    if packet.verdict == "SUPPORTED":
        matched = _CLAIMED_MATCH.search(text)
        if matched:
            return _Amounts(matched.group(1), None, None)
        computed = _COMPUTED_TO.search(text)
        if computed:
            return _Amounts(computed.group(1), None, None)
    return _Amounts(None, None, None)


def _gap_caption(hero: str, claimed: str) -> str | None:
    hero_n = _money_value(hero)
    claimed_n = _money_value(claimed)
    if hero_n is None or claimed_n is None or claimed_n <= hero_n:
        return None
    places = max(_money_places(hero), _money_places(claimed))
    gap = _format_money(claimed_n - hero_n, places)
    return _GAP.format(gap=gap)


def _money_value(token: str) -> Decimal | None:
    match = re.fullmatch(r"\$(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?", token.strip())
    if match is None:
        return None
    whole = match.group(1).replace(",", "")
    frac = match.group(2)
    return Decimal(whole if frac is None else f"{whole}.{frac}")


def _money_places(token: str) -> int:
    if "." not in token:
        return 0
    return len(token.rsplit(".", 1)[1])


def _format_money(amount: Decimal, places: int) -> str:
    quantum = Decimal(1).scaleb(-places)
    amount = amount.quantize(quantum)
    negative = amount < 0
    text = f"{abs(amount):.{places}f}"
    whole, _, frac = text.partition(".")
    grouped = f"{int(whole):,}"
    body = grouped if places == 0 else f"{grouped}.{frac}"
    return f"-${body}" if negative else f"${body}"


def _gloss(label: str | None) -> str:
    if not label:
        return _NO_LABEL
    return LABEL_GLOSS.get(label, "")


def _chain_caption(packet: ReplayPacket) -> str | None:
    ids = [row.link_id for row in packet.link_results if row.link_id]
    codes = [code for code in packet.reason_codes if code]
    parts: list[str] = []
    if ids:
        parts.append(", ".join(ids))
    if codes:
        parts.append(", ".join(codes))
    if not parts:
        return None
    return " · ".join(parts)


def _badge_html(label: str | None) -> str:
    """Weakest-link pill inside the stamp. A separate widget would leave the wash."""

    if not label:
        return ""
    ink, wash, edge = _BADGE.get(label, (_SECONDARY, _WASH, _DASH))
    border = f"border:1px solid {edge};" if edge else "border:0;"
    return (
        f"<span style='display:inline-block;{border}background:{wash};color:{ink};"
        "font-size:0.75rem;font-weight:700;letter-spacing:0.04em;line-height:1.2;"
        f"padding:0.15rem 0.5rem;border-radius:999px'>{html.escape(label)}</span>"
    )


def _eyebrow(text: str) -> str:
    return (
        "<p style='font-size:0.75rem;font-weight:600;letter-spacing:0.06em;"
        "text-transform:uppercase;line-height:1.3;"
        f"color:{_EYEBROW};margin:0 0 0.35rem'>{html.escape(text)}</p>"
    )


def _quiet(text: str, *, color: str = _EYEBROW) -> str:
    return (
        "<p style='font-size:0.75rem;font-weight:400;line-height:1.45;"
        f"color:{color};margin:0.45rem 0 0'>{html.escape(text)}</p>"
    )


def _claim_sentence(text: str, *, claimed: str | None) -> str:
    marks = _money_marks(text, claimed)
    body = _render_marks(text, marks, strike_size="1.35rem")
    return (
        "<p style='font-size:1.125rem;font-weight:600;line-height:1.45;"
        f"color:{_INK};margin:0'>{body}</p>"
    )


def _source_block(text: str, marks: list[tuple[int, int, str]]) -> str:
    body = _render_marks(text, marks, strike_size=None)
    caption = _line_caption(marks)
    caption_html = _quiet(caption) if caption else ""
    return (
        "<div style='margin:1rem 0 0'>"
        "<p style='font-size:1rem;font-weight:400;line-height:1.5;"
        f"color:{_INK};margin:0'>{body}</p>"
        f"{caption_html}</div>"
    )


def _line_caption(marks: list[tuple[int, int, str]]) -> str | None:
    roles = {role for _, _, role in marks}
    labels: list[str] = []
    if "claimed" in roles:
        labels.append("claimed")
    if "grounded" in roles:
        labels.append("in the source")
    if "ungrounded" in roles:
        labels.append("not in the source")
    if not labels:
        return None
    return " · ".join(labels)


def _money_marks(text: str, claimed: str | None) -> list[tuple[int, int, str]]:
    if not claimed:
        return []
    marks: list[tuple[int, int, str]] = []
    for match in _MONEY.finditer(text):
        if _same_money(match.group(0), claimed):
            marks.append((match.start(), match.end(), "claimed"))
    return marks


def _figure_marks(
    text: str,
    grounded: tuple[str, ...],
    loose: tuple[str, ...],
    claimed: str | None,
) -> list[tuple[int, int, str]]:
    """Underline grounded amounts and times. Strike only the contradicted amount."""

    grounded_at = _locate(text, grounded)
    loose_at = _locate(text, loose)
    marks: list[tuple[int, int, str]] = []
    cursor = 0
    for fact in propose_spans(text):
        if fact.kind not in ("number", "time"):
            continue
        quote = fact.quote or ""
        if not quote:
            continue
        idx = text.find(quote, cursor)
        if idx < 0:
            continue
        start = idx
        end = idx + len(quote)
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        extended = end
        if fact.kind == "number":
            tail = _UNIT_TAIL.match(text, end)
            if tail is not None:
                extended = tail.end()
        chosen = _choose_span(
            text, start, end, extended, grounded_at, loose_at, claimed
        )
        if chosen is not None:
            marks.append(chosen)
        cursor = end
    return marks


def _choose_span(
    text: str,
    start: int,
    end: int,
    extended: int,
    grounded_at: list[tuple[int, int]],
    loose_at: list[tuple[int, int]],
    claimed: str | None,
) -> tuple[int, int, str] | None:
    if start >= end:
        return None
    for stop in (extended, end):
        if stop <= start:
            continue
        role = _span_role(text[start:stop], start, stop, grounded_at, loose_at, claimed)
        if role is not None:
            return (start, stop, role)
    return None


def _span_role(
    snippet: str,
    start: int,
    end: int,
    grounded_at: list[tuple[int, int]],
    loose_at: list[tuple[int, int]],
    claimed: str | None,
) -> str | None:
    if claimed and _same_money(snippet, claimed):
        return "claimed"
    if _inside(start, end, grounded_at):
        return "grounded"
    if _inside(start, end, loose_at):
        return "ungrounded"
    return None


def _locate(text: str, quotes: tuple[str, ...]) -> list[tuple[int, int]]:
    found: list[tuple[int, int]] = []
    for quote in quotes:
        if not quote:
            continue
        start = 0
        while True:
            idx = text.find(quote, start)
            if idx < 0:
                break
            found.append((idx, idx + len(quote)))
            start = idx + len(quote)
    return found


def _inside(start: int, end: int, ranges: list[tuple[int, int]]) -> bool:
    return any(left <= start and end <= right for left, right in ranges)


def _same_money(snippet: str, claimed: str) -> bool:
    left = _money_value(snippet)
    right = _money_value(claimed)
    return left is not None and right is not None and left == right


def _render_marks(
    text: str,
    marks: list[tuple[int, int, str]],
    *,
    strike_size: str | None,
) -> str:
    parts: list[str] = []
    pos = 0
    for start, end, role in marks:
        if start < pos or end > len(text):
            continue
        parts.append(html.escape(text[pos:start]))
        parts.append(_wrap_mark(text[start:end], role, strike_size=strike_size))
        pos = end
    parts.append(html.escape(text[pos:]))
    return "".join(parts)


def _wrap_mark(snippet: str, role: str, *, strike_size: str | None) -> str:
    safe = html.escape(snippet)
    if role == "claimed":
        size = f"font-size:{strike_size};" if strike_size else ""
        return (
            f"<span style='{size}color:#9f1239;font-weight:650;"
            "text-decoration:line-through double #9f1239'>"
            f"{safe}</span>"
        )
    if role == "ungrounded":
        return (
            "<span style='text-decoration-line:underline;"
            "text-decoration-style:dashed;text-decoration-thickness:2px;"
            f"text-decoration-color:{_DASH}'>{safe}</span>"
        )
    return (
        "<span style='text-decoration-line:underline;"
        "text-decoration-style:solid;text-decoration-thickness:2px;"
        f"text-decoration-color:{_INK}'>{safe}</span>"
    )


def _highlight_figures(text: str, rows: tuple[SpanRow, ...]) -> tuple[str, tuple[str, ...]]:
    parts: list[str] = []
    captions: list[str] = []
    cursor = 0
    for row in rows:
        quote = row.quote.strip() or row.quote
        if not quote:
            continue
        idx = text.find(quote, cursor)
        if idx < 0:
            continue
        parts.append(html.escape(text[cursor:idx]))
        parts.append(
            "<span style='background:"
            f"{_WASH};padding:0 0.12rem'>{html.escape(text[idx : idx + len(quote)])}</span>"
        )
        scale = row.scale if row.scale else "none"
        captions.append(f"{value_text(row.value)} · {scale} · {row.kind}")
        cursor = idx + len(quote)
    parts.append(html.escape(text[cursor:]))
    return "".join(parts), tuple(captions)


if __name__ == "__main__":
    main()
