"""The audit tick-and-tie review page (F4), drawn only with PROOFGRAPH_GRAPH=1 and a graph on the review.

A workpaper: the claim with each part tied out by a pencil mark, the one-line answer, the tie-out trail from the thing the
claim names to the deciding rule, a date strip when two dates decide, an evidence grid (parts down, documents across) whose
cells are verbatim quotes that open the page, the legend, the open items and a sign-off box. Reads the graph payload as it
is and tolerates missing or extra keys.
"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path

from app.viewer.render import _page, _short_names
from proofgraph.review.models import Card, Part, Review

HERE = Path(__file__).parent
TOKENS, CSS, JS = HERE / "tokens.css", HERE / "graph_view.css", HERE / "graph_view.js"
FONTS = ("https://fonts.googleapis.com/css2?family=Schibsted+Grotesk:wght@400;500;700"
         "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap")

# status -> (word, mark, pen colour class)
ANSWER = {
    "supported": ("Supported", "tick", "green"),
    "contradicted": ("Contradicted", "circle", "red"),
    "weakened": ("Qualified", "caret", "amber"),
    "not_found": ("Not in these documents", "bracket", "slate"),
    "cannot_tell": ("Not mentioned anywhere", "question", "grey"),
    "error": ("Could not check", "question", "grey"),
    "checking": ("Still checking", "question", "grey"),
}
CLASH = ("The documents disagree", "clash", "clash")
# Hand-drawn strokes on a 24 grid, a little loose like pencil.
_STROKES = {
    "tick": '<path d="M3.5 13.2C5.6 15 7.2 16.8 8.6 19.6 11.4 12.6 15.4 7.2 20.8 3.8"/>',
    "circle": '<path d="M12.4 3.1C6.8 2.4 2.7 7 3.3 12.5c.6 5.5 6.2 8.7 11.2 7.5 5-1.2 7.1-6 6-10.4-1-4-4.8-6.3-9.4-5.8"/>',
    "caret": '<path d="M3.8 19.6C7.2 14 9.6 9.6 12 5.4c2.6 4.6 5.2 9.2 8.2 14.2"/>',
    "bracket": '<path d="M15.4 3.6H8.6c-.7 0-1.1.3-1.1.9v15c0 .6.4.9 1.1.9h6.8"/>',
    "question": '<path d="M8.4 9.2C8.2 5.6 15.8 5.4 15.6 9.4c-.1 2.8-3.7 3-3.6 6.2M12 19.6v.1"/>',
    "clash": '<path class="c1" d="M3.4 13.4C5.2 15 6.6 16.6 7.8 19 10 13.6 12.8 9.4 16 6.4"/>'
             '<path class="c2" d="M12.6 17.8 20.6 5.2M12.8 5.6l7.4 11.6"/>',
}
TIER = {"pinned": "tick", "located": "tick", "approximate": "model", "unpinned": "unclear"}
TIER_WORD = {"tick": "Read from the page", "model": "Model's reading", "unclear": "Unclear, never decides"}
TIER_LEVEL = {"page": "read from the page", "model": "model's reading", "unclear": "unclear"}
RELATION = {"contradicts": "Goes against it", "weakens": "Qualifies it", "supports": "Ties out", "set_aside": "Set aside"}
RELATION_MARK = {"contradicts": "circle", "weakens": "caret", "supports": "tick", "set_aside": "bracket"}
ARROW = ('<svg class="ar" viewBox="0 0 28 12" width="28" height="12" aria-hidden="true"><path d="M1 6h24M19 1.5l6 4.5-6 4.5" '
         'fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
CIRCLE = ('<svg class="ring" viewBox="0 0 100 60" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" '
          'd="M52 3C24 1 3 12 4 31c1 18 25 27 52 26 28-1 41-13 40-29C95 12 76 4 46 5" fill="none" '
          'stroke="currentColor" stroke-width="2.4" stroke-linecap="round" vector-effect="non-scaling-stroke"/></svg>')


def mark(name: str) -> str:
    return (f'<svg class="mark m-{name}" data-mark="{name}" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" '
            f'fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">{_STROKES[name]}</svg>')


def _e(v: object) -> str:
    return html.escape(str(v), quote=True)


def _d(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _l(value: object) -> list:
    return value if isinstance(value, list) else []


def _answer(part: Part, info: dict) -> tuple[str, str, str]:
    if info.get("documents_disagree"):
        return CLASH
    return ANSWER.get(part.status, ANSWER["cannot_tell"])


def _day(iso: object) -> date | None:
    try:
        return date.fromisoformat(str(iso)[:10])
    except ValueError:
        return None


def _long(d: date) -> str:
    return f"{d.day} {d.strftime('%B %Y')}"


def _claim(review: Review, infos: dict) -> str:
    text, out, at = review.claim.text, [], 0
    for (a, b), part in sorted((p.span, p) for p in review.parts):
        if a < at or b > len(text) or a >= b:
            return _e(text)  # spans that do not fit the text: no underline rather than a wrong one
        _, m, cls = _answer(part, _d(infos.get(part.id)))
        out += [_e(text[at:a]), f'<span class="u {cls}" data-part-id="{_e(part.id)}">{_e(text[a:b])}</span>']
        at = b
    return "".join(out) + _e(text[at:])


def _label(node: str, docs: dict[str, str]) -> str:
    if node.startswith("e:"):
        return node[2:]
    return docs.get(node.rsplit("-r", 1)[0], node)


def _trail(info: dict, docs: dict[str, str]) -> str:
    labels = [str(x) for x in (_l(info.get("path_labels")) or [_label(str(n), docs) for n in _l(info.get("path"))])]
    if len(labels) < 2:
        return ""
    return f'<ol class="trail" aria-label="Tie-out trail">{"".join(f"<li>{_e(x)}</li>" for x in labels)}</ol>'


def _strip(review: Review, info: dict, dates: dict) -> str:
    stm = _d(dates.get("statements"))
    days = sorted({d for r in _l(info.get("deciding")) for v in _d(stm.get(r)).values() if (d := _day(v))})
    if len(days) < 2:
        return ""
    a, b = days[0], days[-1]
    gap = (b - a).days
    return (f'<p class="strip" aria-label="Dates that decide"><span class="num">{_e(_long(a))}</span>'
            f'<span class="gap"><span class="num">{gap} day{"s" if gap != 1 else ""}</span></span>'
            f'<span class="num">{_e(_long(b))}</span></p>')


def _agreement(info: dict) -> str:
    read_only, flag = _l(info.get("read_only")), info.get("agreement")
    if flag == "disagree":
        return "The walk and the full read cite different evidence. Compare both before relying on this answer."
    if read_only and flag == "partial":
        n = len(read_only)
        return f"The full read also cites {n} passage{'s' if n != 1 else ''} the walk did not reach."
    return ""


def _cell(card: Card, codes: dict[str, str]) -> str:
    tier = TIER.get(card.box_status, "unclear")
    deciding = card.controls and card.relation == "contradicts"
    exception = card.weakener_type == "exception"
    over = f'<span class="over">{ARROW}<span>overridden by {_e(card.superseded_by)}</span></span>' if card.superseded_by else ""
    q = f'<q class="says{" exc" if exception else ""}">{_e(card.quote)}</q>'
    ref = f'<span class="ref">{_e(codes.get(card.doc, "?"))}-{card.page}</span>'
    return (
        f'<button type="button" class="cell {_e(card.relation)} t-{tier}{" decides" if deciding else ""}" aria-pressed="false" '
        f'data-card-id="{_e(card.id)}" data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'{q}<span class="cm">{mark(RELATION_MARK[card.relation])}<span class="sr">{TIER_WORD[tier]}. </span>'
        f'<span>{_e(RELATION[card.relation])}{" (exception)" if exception else ""}</span>{ref}</span>'
        f'{over}{CIRCLE if deciding else ""}</button>'
    )


def _open_items(review: Review, graph: dict) -> str:
    seen: dict[str, str] = {}
    for item in _l(graph.get("cited")):
        item = _d(item)
        if item.get("phrase") and item.get("status") != "supplied":
            when = _day(item.get("date"))
            seen.setdefault(" ".join(str(item["phrase"]).split()).casefold(),
                            f'{item["phrase"]}{f" ({_long(when)})" if when and str(when.year) not in str(item["phrase"]) else ""}')
    for part in review.parts:
        for it in part.evidence_map or []:
            if it.kind == "referenced" and it.ref_text:
                seen.setdefault(" ".join(it.ref_text.split()).casefold(), it.ref_text)
    if not seen:
        return ""
    lis = "".join(f'<li><span class="says">{_e(t)}</span></li>' for t in seen.values())
    return (f'<section class="open"><h2>Cited, not in the packet</h2>'
            f'<p>The documents refer to these; they were not supplied, so nothing here rests on them.</p><ul>{lis}</ul></section>')


def _row(part: Part, cards: list[Card], docs: list, names: dict, codes: dict, info: dict, driver: bool, scen: dict) -> str:
    word, m, cls = _answer(part, info)
    cells = []
    for d in docs:
        mine = [c for c in cards if c.part == part.id and c.doc == d.id]
        body = "".join(_cell(c, codes) for c in mine) or '<span class="none">Nothing relevant</span>'
        cells.append(f"<td>{body}</td>")
    note = _agreement(info)
    trail = "" if driver else _trail(info, {d.id: names[d.id] for d in docs})
    name = scen.get(str(info.get("scenario")))
    bits = [f'<p class="why">{_e(part.reason)}</p>' if part.reason else "",
            f'<p class="scen">{_e(name)}</p>' if name else "", trail,
            f'<p class="agree">{_e(note)}</p>' if note else "",
            f'<p class="tierline">Weakest evidence: {_e(TIER_LEVEL.get(info.get("tier"), info.get("tier")))}</p>' if info.get("tier") else ""]
    return (f'<tr data-part-id="{_e(part.id)}"><th scope="row" class="{cls}"><span class="partline">{_e(part.text)}</span>'
            f'<strong class="st {cls}">{mark(m)}{_e(word)}</strong>{"".join(bits)}</th>{"".join(cells)}</tr>')


def _signoff(graph: dict, infos: dict, replay: bool) -> str:
    stats = _d(graph.get("stats"))
    reads: dict[str, int] = {}
    set_aside = 0
    for info in infos.values():
        info = _d(info)
        for k, v in _d(info.get("second_reads")).items():
            if isinstance(v, int):
                reads[k] = reads.get(k, 0) + v
        set_aside += sum(v for v in _d(info.get("rejected")).values() if isinstance(v, int))
    lines = []
    if stats.get("pages") is not None:
        p = stats["pages"]
        lines.append(f'<li><span>Prepared by ProofGraph</span> <span class="num">Read {_e(p)} page{"s" if p != 1 else ""}: '
                     f'{_e(stats.get("rules", 0))} rules about {_e(stats.get("entities", 0))} things.</span></li>')
    if reads:
        parts = [f"{reads[k]} {w}" for k, w in (("agrees", "agree"), ("disagrees", "disagree"), ("not_run", "not run")) if reads.get(k)]
        if parts:
            lines.append(f'<li><span>Second reader (Muse Spark Open)</span> <span class="num">{_e(", ".join(parts))}</span></li>')
    lines.append(f'<li><span>Statements</span> <span class="num">Set aside: {set_aside}</span></li>')
    if replay:
        lines.append("<li><span>Saved run</span> <span>Replayed, not a live check.</span></li>")
    return f'<section class="signoff" aria-label="Sign-off"><ul>{"".join(lines)}</ul></section>'


def _legend() -> str:
    items = [("tick", "Ties out"), ("circle", "Goes against it"), ("caret", "Qualified"), ("bracket", "Not in these documents"),
             ("question", "Not mentioned anywhere"), ("clash", "The documents disagree")]
    marks = "".join(f'<li>{mark(m)}<span>{w}</span></li>' for m, w in items)
    tiers = "".join(f"<li><span>{w}</span></li>" for w in TIER_WORD.values())
    return (f'<section class="legend" aria-label="Legend"><h2>Legend</h2><ul class="marks">{marks}</ul>'
            f'<ul class="tiers">{tiers}</ul></section>')


def render_graph(review: Review, images: dict, replay: bool = False, ask: bool = False) -> str:
    graph = review.graph or {}
    infos = _d(graph.get("parts"))
    names = _short_names(review.docs)
    names.injected = any(b.kind == "injection" for b in review.banners)
    names.parts = {p.id: p.text for p in review.parts}
    codes = {d.id: chr(65 + i % 26) for i, d in enumerate(review.docs)}  # workpaper letters: A, B, C
    driver = next((p for p in review.parts if p.id == review.driver_part), review.parts[0] if review.parts else None)
    dinfo = _d(infos.get(driver.id)) if driver else {}
    word, m, cls = _answer(driver, dinfo) if driver else ANSWER["cannot_tell"]
    answer = (f'<h1 class="answer {cls}">{mark(m)}<span class="st {cls}">{_e(word)}</span></h1>'
              + (f'<p class="line">{_e(driver.reason)}</p>' if driver and driver.reason else ""))
    docs_by_id = {d.id: names[d.id] for d in review.docs}
    scen = {str(k): str(v) for k, v in _d(graph.get("scenario_names")).items()}
    notes = "".join(f'<p class="banner"><strong>{_e(b.kind.replace("_", " ").capitalize())}.</strong> {_e(b.text)}</p>' for b in review.banners)
    notes += "".join(f'<p class="banner">{_e(names[d.id])}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += "".join(f'<p class="banner">{_e(names[d.id])} page {p.n}: no text layer, not read.</p>'
                     for d in review.docs for p in d.pages if not p.readable)
    cols = "".join(f'<th scope="col"><span class="wp">{codes[d.id]}</span>{_e(names[d.id])}</th>' for d in review.docs)
    rows = "".join(_row(p, review.cards, review.docs, names, codes, _d(infos.get(p.id)), bool(driver and p.id == driver.id), scen)
                   for p in review.parts)
    pages = "".join(_page(d, p, review.cards, images, names[d.id]) for d in review.docs for p in d.pages)
    asker = ""
    if ask:
        asker = ('<form class="ask" id="ask" hidden><label for="ask-claim">Ask another claim about this packet</label>'
                 '<div><input id="ask-claim" name="claim" autocomplete="off"><button class="btn" type="submit">Check claim</button></div></form>')
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>ProofGraph review</title><link rel="preconnect" href="https://fonts.googleapis.com">'
        f'<link rel="stylesheet" href="{FONTS}"><style>{TOKENS.read_text()}{CSS.read_text()}</style></head><body>'
        f'<div class="wrap"><div class="layout"><header class="head"><p class="claim"><span class="sr">Your claim: </span>{_claim(review, infos)}</p>'
        f'{answer}{_trail(dinfo, docs_by_id) if driver else ""}{_strip(review, dinfo, _d(graph.get("dates"))) if driver else ""}{notes}</header>'
        f'<aside class="pane" aria-label="Page"><p class="hint" id="hint">Open a quote to see its page.</p>{pages}</aside>'
        f'<main><div class="gridwrap" tabindex="0" role="region" aria-label="What the documents say">'
        f'<table class="grid"><caption class="sr">What the documents say, by part of the claim</caption>'
        f'<thead><tr><th scope="col"><span>Part of the claim</span></th>{cols}</tr></thead><tbody>{rows}</tbody></table></div>'
        f'{_open_items(review, graph)}</main>'
        f'<footer class="foot">{_signoff(graph, infos, replay)}{_legend()}{asker}'
        '<div class="actions"><button class="btn quiet" type="button" id="download">Download review</button></div></footer></div></div>'
        f'<div id="live" class="sr" role="status" aria-live="polite"></div><script>{JS.read_text()}</script></body></html>'
    )
