"""Render a Review as one self-contained HTML page (viewer S1)."""

import base64
import html
from pathlib import Path

from proofgraph.review.models import Banner, Card, Doc, Page, Part, Review
from proofgraph.review.reasons import check_reason
from proofgraph.review.status import supports_reason

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


# What each state means and what to do, in plain words.
STATE_HELP = {
    "checking": "Still being checked. This is not a result yet.",
    "not_found": "Nothing on the pages read supports or contradicts this part.",
    "cannot_tell": "The pages read are not enough to decide. Check the original document yourself.",
    "error": "This part could not be checked because of an error. Run the check again.",
}
BANNER_HELP = {
    "cap": ("Spend cap reached.", "No more checks were run. Raise the limit or try again later."),
    "checker_unavailable": (
        "The second check was unavailable.",
        "Results below were not confirmed by a second check. Try again later.",
    ),
    "unreadable": ("A file or page could not be read.", "Upload a text PDF or retype the passage."),
    "injection": ("A file contains instructions aimed at the checker.", "They were ignored. Read that file yourself."),
}
CHECK_LABEL = {
    "agrees": "Second check agrees",
    "disagrees": "Second check disagrees",
    "unavailable": "Second check unavailable",
    "not_run": "Second check not run",
}
UNCONFIRMED_TEXT = "The second check did not confirm the supporting quote."
NOT_DOUBLE_CHECKED_TEXT = "Not double-checked"
REPLAY_TEXT = "Replayed from a saved run, not a live check"


# Multi-card mode only (some part has 2+ cards): supports first, bad news last.
MULTI_GROUPS = [
    ("supports", "Supports"),
    ("weakens", "Weakens"),
    ("contradicts", "Contradicts"),
    ("set_aside", "Set aside"),
]
NOT_HOLD_UP_TEXT = "Where it does not hold up"
WEAKER_TEXT = "Weaker evidence: the second check did not confirm this quote"
ONE_PASSAGE_TEXT = "Only one passage found"
# Appended only in multi-card mode so single-card output stays byte-identical.
MULTI_CSS = (
    "<style>.group-sub{margin:14px 0 0;font-size:12px;font-weight:600;color:var(--mut)}"
    "details.weaker{margin:0 0 8px}details.weaker>summary{cursor:pointer;color:var(--mut);margin-bottom:6px}"
    ".one-passage{margin:4px 0 0;color:var(--mut)}</style>"
)
# A card in a closed <details> cannot take focus, so open them before j/k/[/] navigation.
MULTI_JS = (
    "<script>document.addEventListener('keydown',function(e){"
    "if('jk[]'.indexOf(e.key)<0||e.ctrlKey||e.metaKey||e.altKey)return;"
    "document.querySelectorAll('details.weaker').forEach(function(d){d.open=true;});},true);</script>"
)


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: int) -> str:
    return f"{value / 10:g}%"


def _conflict_names(part: Part, cards: list[Card], names: dict[str, str]) -> str:
    own = [c for c in cards if c.part == part.id]
    sup = next((c for c in own if c.relation == "supports"), None)
    con = next((c for c in own if c.relation == "contradicts"), None)
    if sup is None or con is None:
        return "Sources disagree on this part."
    a, b = names.get(sup.doc, sup.doc), names.get(con.doc, con.doc)
    return f"Sources disagree: {_e(a)} vs {_e(b)}"


def _part(
    part: Part,
    reason_kind: str | None = None,
    multi: tuple[list[Card], dict[str, str]] | None = None,
) -> str:
    conflict = ""
    if part.conflict:
        text = "Sources disagree on this part." if multi is None else _conflict_names(part, *multi)
        conflict = f'<p class="conflict">{text}</p>'
    if multi is not None and sum(c.part == part.id for c in multi[0]) == 1:
        conflict += f'<p class="one-passage">{ONE_PASSAGE_TEXT}</p>'
    reason = f'<p class="reason">{_e(part.reason)}</p>' if part.reason else ""
    help_ = ""
    if part.status in STATE_HELP:
        extra = ""
        if part.receipt and part.status == "not_found":
            extra = f" Pages read: {part.receipt.pages_read}."
            if part.receipt.unread:
                extra += f" Pages not read: {', '.join(map(str, part.receipt.unread))}."
        help_ = f'<p class="state-help {part.status}">{_e(STATE_HELP[part.status])}{_e(extra)}</p>'
    unconfirmed = (
        f'<p class="reason-line unconfirmed">{UNCONFIRMED_TEXT}</p>' if reason_kind == "unconfirmed" else ""
    )
    return (
        f'<li class="part {_e(part.status)}" data-part-id="{_e(part.id)}">'
        f'<span class="chip {_e(part.status)}">{_e(STATUS_LABEL[part.status])}</span> '
        f"<span>{_e(part.text)}</span>{unconfirmed}{help_}{reason}{conflict}</li>"
    )


def _card(card: Card, reason_kind: str | None = None, doc_name: str | None = None) -> str:
    unchecked = (
        f' <span class="not-double-checked">{NOT_DOUBLE_CHECKED_TEXT}</span>'
        if reason_kind == "not_double_checked" and card.relation == "supports" and card.check != "disagrees"
        else ""
    )
    weakener = f" · {_e(card.weakener_type)}" if card.weakener_type else ""
    computed = f'<p class="computed">{_e(card.computed.text)}</p>' if card.computed else ""
    line = check_reason(card.relation, card.check, card.check_answer)
    answer = f'<p class="reason-line check-answer">{_e(line)}</p>' if line else ""
    return (
        f'<article class="card {_e(card.relation)}" tabindex="0" '
        f'data-card-id="{_e(card.id)}" data-part="{_e(card.part)}" '
        f'data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'<blockquote>{_e(card.quote)}</blockquote>'
        f'<p class="why">{_e(card.why)}</p>{computed}'
        f'<p class="meta">{_e(doc_name or card.doc)} p{card.page}{weakener} · '
        f"box {_e(card.box_status)} · "
        f'<span class="mark {_e(card.check)}">{_e(CHECK_LABEL[card.check])}</span>{unchecked}</p>{answer}</article>'
    )


def _cards(cards: list[Card], reasons: dict[str, str | None], names: dict[str, str]) -> str:
    out = []
    for relation, label in GROUPS:
        group = [c for c in cards if c.relation == relation]
        if group:
            out.append(f'<section class="group"><h3>{label}</h3>{"".join(_card(c, reasons.get(c.part), names.get(c.doc)) for c in group)}</section>')
    return "".join(out)


def _cards_multi(cards: list[Card], reasons: dict[str, str | None], names: dict[str, str]) -> str:
    per_part: dict[str, int] = {}
    for c in cards:
        per_part[c.part] = per_part.get(c.part, 0) + 1
    out, sub_done = [], False
    for relation, label in MULTI_GROUPS:
        group = [c for c in cards if c.relation == relation]
        if not group:
            continue
        weak = [c for c in group if c.check == "disagrees" and per_part[c.part] > 1]
        main = [c for c in group if c not in weak]
        html_ = "".join(_card(c, reasons.get(c.part), names.get(c.doc)) for c in main)
        if weak:
            inner = "".join(_card(c, reasons.get(c.part), names.get(c.doc)) for c in weak)
            html_ += f'<details class="weaker"><summary>{WEAKER_TEXT}</summary>{inner}</details>'
        if relation in ("weakens", "contradicts") and not sub_done:
            out.append(f'<p class="group-sub">{NOT_HOLD_UP_TEXT}</p>')
            sub_done = True
        out.append(f'<section class="group"><h3>{label}</h3>{html_}</section>')
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


def _banner(banner: Banner) -> str:
    head, tip = BANNER_HELP[banner.kind]
    return f'<p class="banner {_e(banner.kind)}"><strong>{_e(head)}</strong> {_e(banner.text)} {_e(tip)}</p>'


def _unreadable_notes(review: Review) -> str:
    return "".join(
        f'<p class="pagenote unreadable">{_e(d.name)} p{p.n}: image only, not transcribed, '
        "so nothing on it was checked. Upload a text PDF or retype it.</p>"
        for d in review.docs
        for p in d.pages
        if not p.readable
    )


def render(
    review: Review, page_images: dict[tuple[str, int], bytes] | None = None, replay: bool = False
) -> str:
    """The whole review as one self-contained page. replay=True adds the saved-run badge."""
    images = page_images or {}
    notes = "".join(f'<p class="docnote">{_e(d.name)}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += _unreadable_notes(review)
    banners = "".join(map(_banner, review.banners))
    badge = f'<p class="replay-badge" role="note">{REPLAY_TEXT}</p>' if replay else ""
    reasons = {p.id: supports_reason(c for c in review.cards if c.part == p.id) for p in review.parts}
    names = {d.id: d.name for d in review.docs}
    counts: dict[str, int] = {}
    for c in review.cards:
        counts[c.part] = counts.get(c.part, 0) + 1
    is_multi = any(n >= 2 for n in counts.values())
    multi = (review.cards, names) if is_multi else None
    cards_html = (_cards_multi if is_multi else _cards)(review.cards, reasons, names)
    pages = "".join(_page(d, p, review.cards, images) for d in review.docs for p in d.pages)
    # "<" escaped so the JSON can never close its script tag.
    data = review.model_dump_json().replace("<", "\\u003c")
    body = (
        f'<header><h1>{_e(STATUS_LABEL[review.status])}</h1><p class="claim">{_e(review.claim.text)}</p>'
        f"{badge}{banners}</header>"
        f'<main><nav aria-label="Claim parts"><ul>{"".join(_part(p, reasons[p.id], multi) for p in review.parts)}</ul>{notes}</nav>'
        f'<section aria-label="Evidence cards">{cards_html}</section>'
        f'<section aria-label="Page">{pages}</section></main>'
        f'<script type="application/json" id="review">{data}</script>'
    )
    out = TEMPLATE.read_text().replace("<!--BODY-->", body)
    if is_multi:
        out = out.replace("</head>", MULTI_CSS + "</head>", 1).replace("</body>", MULTI_JS + "</body>", 1)
    return out
