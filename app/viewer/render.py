"""Render a Review as one self-contained HTML page (viewer S1)."""

import base64
import html
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from proofgraph.review.models import Banner, Card, Doc, Page, Part, Review
from proofgraph.review.evidence import evidence_lines_on, evidence_map_on
from proofgraph.review.qualifiers import qualifier_phrase
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
SECOND_READ = {
    "agrees": "Second read of this quote alone: confirmed.",
    "disagrees": "Second read of this quote alone: not settled.",
    "unavailable": CHECK_LABEL["unavailable"],
    "not_run": CHECK_LABEL["not_run"],
}
_SEES = "It sees only the quote and the part."
_LABELLED = {"supports": "as support", "contradicts": "as contradicting", "weakens": "as weakening"}
_SAW = {
    "entails": "found it supports this part",
    "contradicts": "found it goes against this part",
    "not_mentioned": "found it does not mention this part",
}
UNCONFIRMED_TEXT = "The second check did not confirm the supporting quote."
NOT_DOUBLE_CHECKED_TEXT = "Not double-checked"
REPLAY_TEXT = "Replayed from a saved run, not a live check"
ONE_SHOWN_TEXT = "One passage shown: the one the model judged most decisive. Others were not listed here."
LIMIT_TEXT = "Search reads text only and matches words, so a passage worded differently can be missed."
EVIDENCE_CSS = (
    "<style>.ev{margin:4px 0 0;color:var(--mut)}.ev-limit{border-left:3px solid var(--gry);padding-left:8px}"
    ".ev-mark{font-weight:600;border:1px dashed var(--gry);border-radius:4px;padding:0 6px;margin-right:6px}"
    ".ev-list{margin:4px 0 0}.ev-list li{margin:4px 0}"
    ".map{list-style:none;padding:0}.map>li{margin:6px 0}.map-date,.map-rel{font-size:.85em;color:var(--mut)}"
    ".map-rel{font-weight:600;margin-right:6px}.map-undated{font-weight:600;border-top:1px solid var(--gry);padding-top:4px}"
    ".mark.second-read{font-weight:600;color:var(--mut)}"
    ".map-ref{border:1px dashed var(--gry);border-radius:4px;padding:4px 8px}</style>"
)


def _e(value: object) -> str:
    return html.escape(str(value), quote=True)


def _pct(value: int) -> str:
    return f"{value / 10:g}%"


def _n(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _evidence(part: Part, names: dict[str, str]) -> str:
    """Code-written disclosure under a part (flag on only). Never says anything about absence."""
    out = []
    if len(part.card_ids) == 1:
        out.append(f'<p class="ev ev-shown">{_e(ONE_SHOWN_TEXT)}</p>')
    r = part.receipt
    if r is not None and r.matched_passages is not None:
        counts = (
            f"Word search matched {_n(r.matched_passages, 'passage')} in {_n(r.matched_docs or 0, 'document')}. "
            f"{_n(len(r.uncited_passages), 'matched passage')} "
            f"{'was' if len(r.uncited_passages) == 1 else 'were'} not assessed."
        )
        out.append(f'<p class="ev ev-counts">{_e(counts)}</p>')
        if r.uncited_passages:
            items = "".join(
                f'<li><span class="ev-mark">matched, not assessed</span>'
                f"{_e(names.get(p.doc, p.doc))} p{p.page}: {_e(p.text)}</li>"
                for p in r.uncited_passages
            )
            out.append(
                '<details class="ev ev-matched"><summary>Matched by word search, not assessed</summary>'
                f'<ul class="ev-list">{items}</ul></details>'
            )
    limit = LIMIT_TEXT
    if r is not None and r.unsearched:
        pages = ", ".join(f"{names.get(p.doc, p.doc)} p{p.page}" for p in r.unsearched)
        limit += f" Pages {pages} are images and were not searched."
    elif r is not None and r.unread:
        limit += f" Pages {', '.join(map(str, r.unread))} are images and were not searched."
    out.append(f'<p class="ev ev-limit">{_e(limit)}</p>')
    return "".join(out)


MAP_LIMIT_TEXT = "Text pages only; {n} passages in {m} documents examined; scans/images not read; may be incomplete."
MAP_DATE_TEXT = "Dates are inferred from the text, not legal dates."


@dataclass
class MapEntry:
    """One card in the map. `also` holds near-duplicates merged into it (same relation, same check state)."""

    card: Card
    date: str | None
    date_source: str | None
    also: list[Card] = field(default_factory=list)


@dataclass
class MapRef:
    """One distinct unsupplied reference, cited `count` times."""

    text: str
    count: int
    places: list[tuple[str | None, int | None]]


@dataclass
class MapView:
    entries: list[MapEntry]
    disagreeing: list[MapEntry]
    refs: list[MapRef]


def _ref_key(text: str | None) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").casefold()).split())


def _near(a: MapEntry, b: MapEntry) -> bool:
    x, y = a.card, b.card
    if x.relation != y.relation or x.doc != y.doc:
        return False
    return x.page == y.page or (abs(x.page - y.page) == 1 and a.date == b.date)


def _map_items(part: Part, cards: dict[str, Card]) -> MapView:
    """Pure: dedupe references, merge near-duplicates inside one relation, split out unsettled second reads."""
    refs: dict[str, MapRef] = {}
    pools: tuple[list[MapEntry], list[MapEntry]] = ([], [])
    for it in part.evidence_map or []:
        if it.kind == "referenced":
            ref = refs.setdefault(_ref_key(it.ref_text), MapRef(it.ref_text or "", 0, []))
            ref.count += 1
            ref.places.append((it.ref_doc, it.ref_page))
            continue
        if it.card_id not in cards:
            continue
        card = cards[it.card_id]
        entry = MapEntry(card, it.date, it.date_source)
        pool = pools[card.check == "disagrees"]
        primary = next((e for e in pool if _near(e, entry)), None)
        if primary:
            primary.also.append(card)
        else:
            pool.append(entry)
    return MapView(pools[0], pools[1], list(refs.values()))


def _day(d: date, year: bool) -> str:
    return f"{d.day} {d:%b}" + (f" {d.year}" if year else "")


def _summary(entries: list[MapEntry], names: dict[str, str]) -> str:
    """One line from counts, document names and dates only. No model text."""
    cards = [c for e in entries for c in (e.card, *e.also)]
    docs = list(dict.fromkeys(names.get(c.doc, c.doc) for c in cards))
    out = f"{_n(len(cards), 'passage')} from {', '.join(docs)}"
    days = []
    for e in entries:
        try:
            days.append(date.fromisoformat(e.date)) if e.date else None
        except ValueError:
            pass
    if days:
        lo, hi = min(days), max(days)
        if lo == hi:
            out += f", {_day(lo, True)}"
        else:
            out += f", {_day(lo, lo.year != hi.year)} to {_day(hi, True)}"
    return out


def _class_header(label: str, cards: list[Card]) -> str:
    """Class header: N = confirmed + not settled + without a second read, so no card is silent."""
    c = sum(x.check == "agrees" for x in cards)
    s = sum(x.check == "disagrees" for x in cards)
    u = len(cards) - c - s
    clauses = [
        t
        for n, t in (
            (c, f"{c} confirmed by a second read of its quote alone"),
            (s, f"{s} need other passages to settle"),
            (u, f"{u} without a second read"),
        )
        if n
    ]
    return f"{label} ({len(cards)}): {', '.join(clauses)}." if clauses else f"{label} ({len(cards)})"


def _part_summary(part: Part, cards: dict[str, Card], names: dict[str, str]) -> str:
    """Counts-and-sources line from card fields and map counts. Irrelevant is counted, never rendered."""
    mine = [c for c in cards.values() if c.part == part.id]
    by = {r: sum(c.relation == r for c in mine) for r in ("supports", "contradicts", "weakens")}
    irrelevant = max((part.map_counts or {}).get("examined", 0) - (part.map_counts or {}).get("relevant", 0), 0)
    docs = len({c.doc for c in mine})
    out = (
        f"{by['supports']} supports, {by['contradicts']} contradicts, {by['weakens']} weakens, "
        f"{irrelevant} irrelevant (hidden), from {docs} of {len(names)} documents"
    )
    r = len(_map_items(part, cards).refs)
    if r:
        out += f"; {_n(r, 'document')} referenced, not supplied"
    return out


def _map(part: Part, cards: dict[str, Card], names: dict[str, str], reasons: dict[str, str | None]) -> str:
    """Ordered evidence map under a part (flag on only): one list, dates inferred, relation as a word."""
    n = (part.map_counts or {}).get("examined", 0)
    items, seen_dated = [], False
    for it in part.evidence_map or []:
        if it.kind == "card" and it.card_id not in cards:
            continue
        if it.kind == "referenced":
            cite = f" (cited in {_e(names.get(it.ref_doc, it.ref_doc))} p{it.ref_page})" if it.ref_doc else ""
            items.append(f'<li class="map-ref">Referenced, not supplied: {_e(it.ref_text)}{cite}</li>')
            continue
        if it.date is None and seen_dated:
            items.append('<li class="map-undated">Undated</li>')
            seen_dated = False
        c = cards[it.card_id]
        try:
            d = date.fromisoformat(it.date) if it.date else None
            when = f"{d:%B} {d.day}, {d.year}" if d else None
        except ValueError:
            when = it.date
        label = f"{when} · inferred from {it.date_source or 'the text'}" if when else "Undated"
        seen_dated = seen_dated or bool(when)
        items.append(
            f'<li><span class="map-rel">{_e(dict(GROUPS)[c.relation])}</span><span class="map-date">{_e(label)}</span>'
            f"{_card(c, reasons.get(c.part), names.get(c.doc), True, True)}</li>"
        )
    limit = MAP_LIMIT_TEXT.format(n=n, m=len(names))
    skipped = n - (part.map_counts or {}).get("relevant", 0)
    if skipped > 0:
        limit += f" {skipped} matched passages were judged not to bear on this part by the labelling step."
    summary = f'<p class="ev ev-summary">{_e(_part_summary(part, cards, names))}</p>'
    return f'{summary}<p class="ev ev-limit">{_e(limit)} {_e(MAP_DATE_TEXT)}</p><ol class="map">{"".join(items)}</ol>'


def _part(part: Part, reason_kind: str | None = None, names: dict[str, str] | None = None, extra: str = "") -> str:
    conflict = (
        '<p class="conflict">Sources disagree on this part.</p>' if part.conflict else ""
    )
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
        f"<span>{_e(part.text)}</span>{unconfirmed}{help_}{reason}{conflict}"
        f"{_evidence(part, names) if names is not None else ''}{extra}</li>"
    )


def _card(
    card: Card, reason_kind: str | None = None, doc_name: str | None = None, plain: bool = False, second_read: bool = False
) -> str:
    unchecked = (
        f' <span class="not-double-checked">{NOT_DOUBLE_CHECKED_TEXT}</span>'
        if reason_kind == "not_double_checked" and card.relation == "supports" and card.check != "disagrees"
        else ""
    )
    weakener = f" · {_e(card.weakener_type)}" if card.weakener_type else ""
    phrase = qualifier_phrase(card.weakener_type) if plain else None
    if phrase:
        weakener += f" · {_e(phrase)}"
    computed = f'<p class="computed">{_e(card.computed.text)}</p>' if card.computed else ""
    line = check_reason(card.relation, card.check, card.check_answer)
    if second_read and line:
        saw = _SAW.get(card.check_answer)
        line = (
            f"The second read of this quote alone {saw}, while this card is labelled {_LABELLED[card.relation]}. {_SEES}"
            if saw and card.relation in _LABELLED
            else f"The second read of this quote alone is not available here. {_SEES}"
        )
    answer = f'<p class="reason-line check-answer">{_e(line)}</p>' if line else ""
    if second_read:
        text = _e(SECOND_READ[card.check])
        badge = f'<span class="mark second-read" aria-label="{text}">{text}</span>'
    else:
        badge = f'<span class="mark {_e(card.check)}">{_e(CHECK_LABEL[card.check])}</span>'
    return (
        f'<article class="card {_e(card.relation)}" tabindex="0" '
        f'data-card-id="{_e(card.id)}" data-part="{_e(card.part)}" '
        f'data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'<blockquote>{_e(card.quote)}</blockquote>'
        f'<p class="why">{_e(card.why)}</p>{computed}'
        f'<p class="meta">{_e(doc_name or card.doc)} p{card.page}{weakener} · '
        f"box {_e(card.box_status)} · "
        f"{badge}{unchecked}</p>{answer}</article>"
    )


def _cards(cards: list[Card], reasons: dict[str, str | None], names: dict[str, str], plain: bool = False) -> str:
    out = []
    for relation, label in GROUPS:
        group = [c for c in cards if c.relation == relation]
        if group:
            out.append(f'<section class="group"><h3>{label}</h3>{"".join(_card(c, reasons.get(c.part), names.get(c.doc), plain) for c in group)}</section>')
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
    on = evidence_lines_on()
    names = {d.id: d.name for d in review.docs}
    cards = {c.id: c for c in review.cards}
    mapped = evidence_map_on()
    notes = "".join(f'<p class="docnote">{_e(d.name)}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += _unreadable_notes(review)
    banners = "".join(map(_banner, review.banners))
    badge = f'<p class="replay-badge" role="note">{REPLAY_TEXT}</p>' if replay else ""
    reasons = {p.id: supports_reason(c for c in review.cards if c.part == p.id) for p in review.parts}
    pages = "".join(_page(d, p, review.cards, images) for d in review.docs for p in d.pages)
    maps = {p.id: _map(p, cards, names, reasons) if mapped and p.evidence_map is not None else "" for p in review.parts}
    # "<" escaped so the JSON can never close its script tag.
    data = review.model_dump_json().replace("<", "\\u003c")
    body = (
        f'<header><h1>{_e(STATUS_LABEL[review.status])}</h1><p class="claim">{_e(review.claim.text)}</p>'
        f"{badge}{banners}</header>"
        f'<main><nav aria-label="Claim parts"><ul>{"".join(_part(p, reasons[p.id], names if on else None, maps[p.id]) for p in review.parts)}</ul>{notes}{EVIDENCE_CSS if on or mapped else ""}</nav>'
        f'<section aria-label="Evidence cards">{"" if mapped and any(p.evidence_map is not None for p in review.parts) else _cards(review.cards, reasons, names, on)}</section>'
        f'<section aria-label="Page">{pages}</section></main>'
        f'<script type="application/json" id="review">{data}</script>'
    )
    return TEMPLATE.read_text().replace("<!--BODY-->", body)
