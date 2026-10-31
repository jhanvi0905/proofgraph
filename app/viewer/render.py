"""Render a Review as one self-contained HTML page (viewer S1)."""

import base64
import html
from pathlib import Path

from proofgraph.review.models import Card, Doc, Page, Part, Review

TEMPLATE = Path(__file__).with_name("viewer.html")

GROUPS = [
    ("contradicts", "Contradicts"),
    ("weakens", "Weakens"),
    ("supports", "Supports"),
    ("set_aside", "Set aside"),
]
STATUS_LABEL = {
    "contradicted": "Contradicted",
    "weakened": "Weakened",
    "supported": "Supported",
    "not_found": "Not found",
    "cannot_tell": "Can't tell",
    "checking": "Checking",
    "error": "Error",
}


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: int) -> str:
    return f"{value / 10:g}%"


def _part(part: Part) -> str:
    conflict = (
        '<p class="conflict">Sources disagree on this part.</p>' if part.conflict else ""
    )
    reason = f'<p class="reason">{_e(part.reason)}</p>' if part.reason else ""
    return (
        f'<li class="part" data-part-id="{_e(part.id)}">'
        f'<span class="chip {_e(part.status)}">{_e(STATUS_LABEL[part.status])}</span> '
        f"<span>{_e(part.text)}</span>{reason}{conflict}</li>"
    )


def _card(card: Card) -> str:
    weakener = f" · {_e(card.weakener_type)}" if card.weakener_type else ""
    computed = f'<p class="computed">{_e(card.computed.text)}</p>' if card.computed else ""
    return (
        f'<article class="card {_e(card.relation)}" tabindex="0" '
        f'data-card-id="{_e(card.id)}" data-part="{_e(card.part)}" '
        f'data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'<blockquote>{_e(card.quote)}</blockquote>'
        f'<p class="why">{_e(card.why)}</p>{computed}'
        f'<p class="meta">{_e(card.doc)} p{card.page}{weakener} · '
        f"box {_e(card.box_status)} · check {_e(card.check)}</p></article>"
    )


def _cards(cards: list[Card]) -> str:
    out = []
    for relation, label in GROUPS:
        group = [c for c in cards if c.relation == relation]
        if group:
            out.append(f'<section class="group"><h3>{label}</h3>{"".join(map(_card, group))}</section>')
    return "".join(out)


def _page(doc: Doc, page: Page, cards: list[Card], images: dict[tuple[str, int], bytes]) -> str:
    data = images.get((doc.id, page.n))
    if data is None:
        img = f'<div class="noimg">{_e(doc.name)} p{page.n}: image not available</div>'
    else:
        encoded = base64.b64encode(data).decode("ascii")
        img = f'<img alt="{_e(doc.name)} page {page.n}" src="data:image/png;base64,{encoded}">'
    boxes = "".join(
        f'<div class="box {_e(c.box_status)}" data-box-for="{_e(c.id)}" '
        f'style="left:{_pct(x0)};top:{_pct(y0)};width:{_pct(x1 - x0)};height:{_pct(y1 - y0)}"></div>'
        for c in cards
        if (c.doc, c.page) == (doc.id, page.n)
        for x0, y0, x1, y1 in c.boxes
    )
    return (
        f'<div class="page" hidden data-doc="{_e(doc.id)}" data-page="{page.n}" '
        f'style="aspect-ratio:{page.w}/{page.h}">{img}{boxes}</div>'
    )


def render(review: Review, page_images: dict[tuple[str, int], bytes] | None = None) -> str:
    images = page_images or {}
    notes = "".join(f'<p class="docnote">{_e(d.name)}: {_e(d.note)}</p>' for d in review.docs if d.note)
    banners = "".join(f'<p class="banner {_e(b.kind)}">{_e(b.text)}</p>' for b in review.banners)
    pages = "".join(_page(d, p, review.cards, images) for d in review.docs for p in d.pages)
    # "<" escaped so the JSON can never close its script tag.
    data = review.model_dump_json().replace("<", "\\u003c")
    body = (
        f'<header><h1>{_e(STATUS_LABEL[review.status])}</h1><p class="claim">{_e(review.claim.text)}</p>'
        f"{banners}</header>"
        f'<main><nav aria-label="Claim parts"><ul>{"".join(map(_part, review.parts))}</ul>{notes}</nav>'
        f'<section aria-label="Evidence cards">{_cards(review.cards)}</section>'
        f'<section aria-label="Page">{pages}</section></main>'
        f'<script type="application/json" id="review">{data}</script>'
    )
    return TEMPLATE.read_text().replace("<!--BODY-->", body)
