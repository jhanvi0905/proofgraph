"""The proof-path review page (F4), drawn only with PROOFGRAPH_GRAPH=1 and a graph on the review.

A reviewer's marked-up working paper: the claim with each part underlined in its answer's colour, the proof path as a
breadcrumb, an evidence grid (parts down, documents across) whose cells are verbatim quotes that open the page, and the
tier legend. Reads the graph payload as it is and tolerates missing or extra keys.
"""

from __future__ import annotations

import html
from pathlib import Path

from app.viewer.render import MAP_STATUS_LABEL, _page, _short_names
from proofgraph.review.models import Card, Part, Review

HERE = Path(__file__).parent
TOKENS = HERE / "tokens.css"
CSS = HERE / "graph_view.css"
JS = HERE / "graph_view.js"
FONTS = ("https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:ital,wght@0,400;0,700;1,400"
         "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap")

COLOUR = {"contradicted": "red", "weakened": "ochre", "supported": "blue"}
WORD = {"contradicts": "Goes against it", "weakens": "Qualifies it", "supports": "Backs it up", "set_aside": "Set aside"}
# Tier mark by how the quote was placed on its page: tick = read from the page, ~ = model's reading, ? = unclear.
TIER = {"pinned": "tick", "located": "tick", "approximate": "model", "unpinned": "unclear"}
TIER_WORD = {"page": "read from the page", "model": "model's reading", "unclear": "unclear"}
TIER_SR = {"tick": "read from the page", "model": "model's reading", "unclear": "unclear"}
TICK = ('<svg class="tk" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true"><path d="M2.5 8.5l3.5 3.5 7.5-8" '
        'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')
ARROW = ('<svg class="ar" viewBox="0 0 28 12" width="28" height="12" aria-hidden="true"><path d="M1 6h24M19 1.5l6 4.5-6 4.5" '
         'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
CIRCLE = ('<svg class="circle" viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" '
          'd="M52 3C24 1 3 12 4 31c1 18 25 27 52 26 28-1 41-13 40-29C95 12 76 4 46 5" fill="none" '
          'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


def _e(v: object) -> str:
    return html.escape(str(v), quote=True)


def _claim(review: Review) -> str:
    text, out, at = review.claim.text, [], 0
    spans = sorted((p.span, p) for p in review.parts)
    for (a, b), part in spans:
        if a < at or b > len(text) or a >= b:
            return _e(text)  # spans that do not fit the text: no underline rather than a wrong one
        out.append(_e(text[at:a]))
        out.append(f'<span class="u {COLOUR.get(part.status, "none")}" data-part-id="{_e(part.id)}">{_e(text[a:b])}</span>')
        at = b
    out.append(_e(text[at:]))
    return "".join(out)


def _label(node: str, docs: dict[str, str]) -> str:
    if node.startswith("e:"):
        return node[2:]
    doc = node.rsplit("-r", 1)[0]
    return docs.get(doc, node)


def _path(info: dict, docs: dict[str, str]) -> list[str]:
    labels = info.get("path_labels") or [_label(n, docs) for n in info.get("path") or []]
    return [str(x) for x in labels]


def _crumbs(labels: list[str]) -> str:
    if len(labels) < 2:
        return ""
    items = "".join(f"<li>{_e(x)}</li>" for x in labels)
    return f'<ol class="crumbs" aria-label="Proof path">{items}</ol>'


def _agreement(info: dict) -> str:
    read_only, flag = info.get("read_only") or [], info.get("agreement")
    if flag == "disagree":
        return "The walk and the full read cite different evidence. Compare both before relying on this answer."
    if read_only and flag == "partial":
        n = len(read_only)
        return f"The full read also cites {n} passage{'s' if n != 1 else ''} the walk did not reach."
    return ""


def _cell(card: Card, names: dict[str, str]) -> str:
    tier = TIER.get(card.box_status, "unclear")
    mark = TICK if tier == "tick" else f'<span class="tm" aria-hidden="true">{"~" if tier == "model" else "?"}</span>'
    deciding = card.controls and card.relation == "contradicts"
    exception = card.weakener_type == "exception"
    over = f'<span class="over">{ARROW}<span>overridden by {_e(card.superseded_by)}</span></span>' if card.superseded_by else ""
    q = f'<q class="says{" exc" if exception else ""}">{_e(card.quote)}</q>'
    return (
        f'<button type="button" class="cell {_e(card.relation)}{" decides" if deciding else ""}" aria-pressed="false" '
        f'data-card-id="{_e(card.id)}" data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'{q}<span class="cm">{mark}<span class="sr">{TIER_SR[tier]}. </span>'
        f'<span>{_e(WORD[card.relation])}{" (exception)" if exception else ""} · {_e(names.get(card.doc, card.doc))} p{card.page}</span></span>'
        f'{over}{CIRCLE if deciding else ""}</button>'
    )


def _cited(review: Review) -> str:
    seen: dict[str, str] = {}
    for part in review.parts:
        for item in part.evidence_map or []:
            if item.kind == "referenced" and item.ref_text:
                seen.setdefault(" ".join(item.ref_text.split()).casefold(), item.ref_text)
    for item in (review.graph or {}).get("cited") or []:  # optional: [{"phrase": ..., "date": ...}] or plain strings
        text = item.get("phrase") if isinstance(item, dict) else item
        if text:
            seen.setdefault(" ".join(str(text).split()).casefold(), str(text))
    if not seen:
        return ""
    lis = "".join(f"<li><span class=\"says\">{_e(t)}</span></li>" for t in seen.values())
    return f'<section class="cited"><h2>Cited, not supplied</h2><p>The documents refer to these; they are not in the packet.</p><ul>{lis}</ul></section>'


def _row(part: Part, review: Review, cards: list[Card], docs: list, names: dict[str, str], info: dict, driver: bool) -> str:
    cells = []
    for d in docs:
        mine = [c for c in cards if c.part == part.id and c.doc == d.id]
        body = "".join(_cell(c, names) for c in mine) or '<span class="none">Nothing relevant</span>'
        cells.append(f'<td>{body}</td>')
    colour = COLOUR.get(part.status, "none")
    note = _agreement(info)
    path = "" if driver else _crumbs(_path(info, {d.id: names[d.id] for d in docs}))
    reason = f'<p class="why">{_e(part.reason)}</p>' if part.reason else ""
    notes = f'<p class="agree">{_e(note)}</p>' if note else ""
    tier = info.get("tier")
    tier_line = f'<p class="tierline">Weakest evidence: {_e(TIER_WORD.get(tier, tier))}</p>' if tier else ""
    return (
        f'<tr data-part-id="{_e(part.id)}"><th scope="row" class="{colour}"><span class="says">{_e(part.text)}</span>'
        f'<strong class="st">{_e(MAP_STATUS_LABEL.get(part.status, part.status))}</strong>{reason}{path}{notes}{tier_line}</th>{"".join(cells)}</tr>'
    )


def render_graph(review: Review, images: dict, replay: bool = False, ask: bool = False) -> str:
    graph = review.graph or {}
    parts_info = graph.get("parts") or {}
    names = _short_names(review.docs)
    names.injected = any(b.kind == "injection" for b in review.banners)
    names.parts = {p.id: p.text for p in review.parts}
    driver = next((p for p in review.parts if p.id == review.driver_part), review.parts[0] if review.parts else None)
    docs_by_id = {d.id: names[d.id] for d in review.docs}
    status = review.status
    head = _e(MAP_STATUS_LABEL.get(status, status))
    reason = f'<p class="answer-why">{_e(driver.reason)}</p>' if driver and driver.reason else ""
    stats = graph.get("stats") or {}
    receipt = ""
    if stats.get("pages") is not None:
        receipt = (f'<p class="receipt">Read {_e(stats.get("pages"))} page{"s" if stats.get("pages") != 1 else ""}: '
                   f'{_e(stats.get("rules", 0))} rules about {_e(stats.get("entities", 0))} things.</p>')
    crumbs = _crumbs(_path(parts_info.get(driver.id, {}), docs_by_id)) if driver else ""
    notes = "".join(f'<p class="banner"><strong>{_e(b.kind.replace("_", " ").capitalize())}.</strong> {_e(b.text)}</p>' for b in review.banners)
    notes += "".join(f'<p class="banner">{_e(names[d.id])}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += "".join(f'<p class="banner">{_e(names[d.id])} page {p.n}: no text layer, not read.</p>'
                     for d in review.docs for p in d.pages if not p.readable)
    badge = '<p class="banner">Replayed from a saved run, not a live check.</p>' if replay else ""
    cards = review.cards
    cols = "".join(f'<th scope="col"><span>{_e(names[d.id])}</span></th>' for d in review.docs)
    rows = "".join(_row(p, review, cards, review.docs, names, parts_info.get(p.id, {}), bool(driver and p.id == driver.id))
                   for p in review.parts)
    pages = "".join(_page(d, p, cards, images, names[d.id]) for d in review.docs for p in d.pages)
    asker = ""
    if ask:
        asker = ('<form class="ask" id="ask" hidden><label for="ask-claim">Ask another claim about this packet</label>'
                 '<div><input id="ask-claim" name="claim" autocomplete="off"><button class="btn" type="submit">Check claim</button></div></form>')
    legend = ('<p class="legend" aria-label="Marks">' + TICK + ' read from the page <span class="tm" aria-hidden="true">~</span> model\'s reading '
              '<span class="tm" aria-hidden="true">?</span> unclear</p>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>ProofGraph review</title><link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="stylesheet" href="{FONTS}"><style>{TOKENS.read_text()}{CSS.read_text()}</style></head><body>'
        f'<div class="wrap"><header class="top"><p class="claim says"><span class="sr">Your claim: </span>{_claim(review)}</p>'
        f'<h1 class="answer {COLOUR.get(status, "none")}">{head}</h1>{reason}{crumbs}{receipt}{badge}{notes}</header>'
        f'<div class="split"><main><div class="gridwrap" tabindex="0" role="region" aria-label="What the documents say">'
        f'<table class="grid"><caption class="sr">What the documents say, by part of the claim</caption>'
        f'<thead><tr><th scope="col"><span>Part of the claim</span></th>{cols}</tr></thead><tbody>{rows}</tbody></table></div>'
        f'{_cited(review)}</main><aside class="pane" aria-label="Page"><p class="hint" id="hint">Open a quote to see its page.</p>'
        f'{pages}</aside></div>'
        f'<footer class="foot">{legend}{asker}<div class="actions"><button class="btn quiet" type="button" id="download">Download review</button></div></footer></div>'
        f'<div id="live" class="sr" role="status" aria-live="polite"></div><script>{JS.read_text()}</script></body></html>'
    )
