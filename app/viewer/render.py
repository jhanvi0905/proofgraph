"""Render a Review as one self-contained HTML page (viewer S1)."""

import base64
import html
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from proofgraph.review.models import Banner, Card, Doc, Page, Part, Review
from proofgraph.review.evidence import evidence_lines_on, evidence_map_on, graph_on
from proofgraph.review.qualifiers import qualifier_phrase
from proofgraph.review.reasons import check_reason
from proofgraph.review.status import supports_reason

TEMPLATE = Path(__file__).with_name("viewer.html")
MAP_JS = Path(__file__).with_name("map.js")

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
MAP_STATUS_LABEL = {
    "contradicted": "Goes against the claim",
    "weakened": "Casts doubt on the claim",
    "supported": "Backs up the claim",
    "not_found": "Nothing found about this",
    "cannot_tell": "Not enough to decide",
    "checking": "Still checking",
    "error": "Could not check",
}
CHECK_LABEL = {
    "agrees": "Second check agrees",
    "disagrees": "Second check disagrees",
    "unavailable": "Second check unavailable",
    "not_run": "Second check not run",
}
OPEN_THIS_TEXT = "Open this passage"
RULE_TEXT = "One passage that goes against a claim is enough to count against it."
SECOND_CHECK_TEXT = (
    "Each passage was re-read on its own, without the rest of the page. "
    "Not settled means the quote alone was not enough. Open the page to read it in context."
)
_NO_CHECK = {
    "unavailable": "The second read could not run this time.",
    "not_run": "The second read did not run on this one.",
}
CONTEXT_TEXT = "Open the page to see it in context."
AI_LABEL = "AI's reading:"
AI_MAX = 140
UNCONFIRMED_TEXT = "The second check did not confirm the supporting quote."
NOT_DOUBLE_CHECKED_TEXT = "Not double-checked"
REPLAY_TEXT = "Replayed from a saved run, not a live check"
ONE_SHOWN_TEXT = "One passage shown: the one the model judged most decisive. Others were not listed here."
LIMIT_TEXT = "Search reads text only and matches words, so a passage worded differently can be missed."
EVIDENCE_CSS = (
    "<style>.ev{margin:4px 0 0;color:var(--mut)}.ev-limit{border-left:3px solid var(--gry);padding-left:8px}"
    ".ev-mark{font-weight:600;border:1px dashed var(--gry);border-radius:4px;padding:0 6px;margin-right:6px}"
    ".ev-list{margin:4px 0 0}.ev-list li{margin:4px 0}</style>"
)
LEDGER_CSS = (
    "<style>"
    ":root{--l-bg:#f7f6f3;--l-surface:#fff;--l-ink:#1d2127;--l-muted:#555d68;--l-line:#d9d6cf;--l-against:#a3201b;"
    "--l-against-bg:#fbeceb;--l-doubt:#8a5a00;--l-doubt-bg:#fbf3e0;--l-back:#17695b;--l-back-bg:#e8f3f0;--l-focus:#1f5fbf}"
    "@media (prefers-color-scheme:dark){:root{--l-bg:#14171b;--l-surface:#1c2025;--l-ink:#eceae5;--l-muted:#a9b0b9;"
    "--l-line:#3a4048;--l-against:#ff8a82;--l-against-bg:#3a1f1e;--l-doubt:#f1bd5c;--l-doubt-bg:#38301a;"
    "--l-back:#6fd0bd;--l-back-bg:#17302b;--l-focus:#8cb8ff}}"
    "body{background:var(--l-bg);color:var(--l-ink);font:16px/1.5 system-ui,-apple-system,'Segoe UI',sans-serif}"
    ".wrap{max-width:1100px;margin:0 auto;padding:24px 16px 48px;box-sizing:border-box}"
    ".wrap *{box-sizing:border-box}.wrap header.top{padding:0;border:0}.wrap main{display:block;padding:0}"
    ".wrap button{font:inherit;color:inherit;cursor:pointer}.wrap :focus-visible{outline:3px solid var(--l-focus);outline-offset:2px}"
    ".wrap blockquote{font-style:normal;margin:0}.wrap ul{list-style:none;margin:0;padding:0}"
    ".s-contradicted,.against{--c:var(--l-against);--cb:var(--l-against-bg)}.s-weakened,.doubt{--c:var(--l-doubt);--cb:var(--l-doubt-bg)}"
    ".s-supported,.back{--c:var(--l-back);--cb:var(--l-back-bg)}.row.contradicts{--c:var(--l-against)}"
    ".row.weakens{--c:var(--l-doubt)}.row.supports{--c:var(--l-back)}.row.set_aside{--c:var(--l-muted)}"
    ".claim{margin:0 0 16px}.claim small{display:block;font-size:14px;color:var(--l-muted)}"
    ".claim q{font-size:1.25rem;font-weight:600;quotes:'\\201C' '\\201D'}"
    ".verdict-band{background:var(--cb,var(--l-surface));border:2px solid var(--c,var(--l-muted));border-radius:10px;padding:16px 20px}"
    ".vt{margin:0;font-size:1.5rem;color:var(--c,var(--l-ink));display:flex;gap:10px;align-items:center}"
    ".gl{flex:none;width:24px;height:24px;border-radius:50%;display:inline-grid;place-items:center;font-weight:800;font-size:14px;"
    "border:2px solid currentColor}"
    ".rule{margin:8px 0 0;font-size:16px;font-weight:600}"
    ".why-line{margin:12px 0 0;border-left:4px solid var(--c);padding-left:12px;overflow-wrap:anywhere}"
    ".why-line a{color:inherit;border-bottom:1px solid currentColor;text-decoration:none}.why-src{display:block;font-size:14px;color:var(--l-muted)}"
    ".why-open{display:inline-block;margin-top:4px;font-size:14px;font-weight:600}"
    ".why-note{margin:6px 0 0;font-size:14px;color:var(--l-muted)}"
    ".counts-line{margin:12px 0 0;font-size:14px;color:var(--l-muted);overflow-wrap:anywhere}"
    ".gap-line{border:2px dashed var(--l-muted);border-radius:8px;padding:10px 14px;margin:12px 0 0;background:var(--l-surface);overflow-wrap:anywhere}"
    ".replay-badge{color:var(--l-ink)}.wrap .banner,.wrap .pagenote,.wrap .docnote{font-size:14px;overflow-wrap:anywhere}"
    ".wrap .part{padding:0;border:0;margin:0}.wrap .part.flash{outline:none;animation:none}"
    ".part h2{font-size:1.1rem;margin:32px 0 8px;display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline;justify-content:space-between}"
    ".part h2 .pn{font-size:14px;color:var(--l-muted);font-weight:400;width:100%}.part h2 .ph{font-weight:600;overflow-wrap:anywhere}"
    ".pv{font-size:1rem;font-weight:700;color:var(--c);display:inline-flex;gap:8px;align-items:center}"
    ".part-note{margin:0 0 8px;font-size:14px;color:var(--l-muted);overflow-wrap:anywhere}.wrap .conflict{color:var(--l-ink);margin:0 0 8px}"
    ".cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:720px){.cols{grid-template-columns:1fr}}"
    ".col,.aside{background:var(--l-surface);border:1px solid var(--l-line);border-radius:10px;padding:12px 14px;min-width:0}"
    ".aside{margin-top:16px}.sub+.sub{margin-top:16px}"
    ".wrap h3{margin:0 0 8px;font-size:1rem;text-transform:none;letter-spacing:0;color:var(--c);display:flex;gap:8px;align-items:center}"
    ".none{color:var(--l-muted);margin:0 0 8px}"
    ".row{border-top:1px solid var(--l-line)}.row:first-child{border-top:0}"
    ".row.nc{border-left:4px dashed var(--l-muted);padding-left:8px}"
    ".rowbtn{width:100%;display:flex;gap:10px;align-items:flex-start;text-align:left;background:none;border:0;padding:10px 4px;"
    "min-height:44px;border-radius:6px}.rowbtn:hover{background:var(--l-bg)}.row .gl{color:var(--c)}"
    ".rt{flex:1;min-width:0}.q{display:block;overflow-wrap:anywhere}.m{display:block;font-size:14px;color:var(--l-muted);margin-top:2px;overflow-wrap:anywhere}"
    ".act{flex:none;font-size:14px;font-weight:600;color:var(--l-focus);text-decoration:underline;padding-top:2px}"
    ".rowbtn[aria-expanded=false] .q{display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.rowbtn[aria-expanded=true] .act{color:var(--l-muted)}.panel{padding:4px 4px 14px 38px;min-width:0;overflow-wrap:anywhere}"
    ".wrap .panel .card{border:0;padding:0;margin:0;cursor:default}.wrap .panel .card.active{outline:none}"
    ".panel .meta{font-size:14px;color:var(--l-muted);margin:6px 0 0;overflow-wrap:anywhere}"
    ".panel .qualifier,.panel .computed,.panel .reason-line,.panel .poshint{margin:6px 0 0;font-size:14px;overflow-wrap:anywhere}"
    ".panel .ai{margin:6px 0 0;font-size:14px;color:var(--l-muted);overflow-wrap:anywhere}.panel .ai span{font-weight:600}"
    ".slot{margin-top:8px}.slot .page{max-width:560px;border-radius:4px}.slot .noimg{padding:12px;font-size:14px}"
    ".close{margin-top:8px;background:none;border:1px solid var(--l-line);border-radius:6px;padding:6px 12px;min-height:44px}"
    ".grp{margin-top:6px}.grp:first-child{margin-top:0}"
    ".gbtn,.more{width:100%;display:flex;justify-content:space-between;gap:8px;text-align:left;background:var(--l-bg);"
    "border:1px solid var(--l-line);border-radius:6px;padding:8px 12px;min-height:44px;font-weight:600}"
    ".gbtn::after,.more::after{content:'+';font-weight:400}.gbtn[aria-expanded=true]::after,.more[aria-expanded=true]::after{content:'\\2212'}"
    ".more{margin-top:6px;font-weight:500}"
    ".store{display:none}"
    "footer.foot{max-width:1100px;margin:32px auto 0;border-top:1px solid var(--l-line);padding:12px 16px 0;font-size:14px;color:var(--l-muted);overflow-wrap:anywhere}"
    "footer.foot p{margin:0 0 4px}"
    "@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}"
    "</style>"
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
    """One card in the ledger, with the date code found for it."""

    card: Card
    date: str | None
    date_source: str | None


@dataclass
class MapRef:
    """One distinct unsupplied reference, cited `count` times."""

    text: str
    count: int
    places: list[tuple[str | None, int | None]]


@dataclass
class MapView:
    entries: list[MapEntry]
    refs: list[MapRef]


def _ref_key(text: str | None) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", (text or "").casefold()).split())


def _map_items(part: Part, cards: dict[str, Card]) -> MapView:
    """Pure: one entry per known card in map order, and the unsupplied references with repeats counted once."""
    refs: dict[str, MapRef] = {}
    entries: list[MapEntry] = []
    for it in part.evidence_map or []:
        if it.kind == "referenced":
            ref = refs.setdefault(_ref_key(it.ref_text), MapRef(it.ref_text or "", 0, []))
            ref.count += 1
            ref.places.append((it.ref_doc, it.ref_page))
        elif it.card_id in cards:
            entries.append(MapEntry(cards[it.card_id], it.date, it.date_source))
    return MapView(entries, list(refs.values()))


def _part_summary(part: Part, cards: dict[str, Card], names: dict[str, str]) -> str:
    """Counts-and-sources line from card fields and map counts. Irrelevant is counted, never rendered."""
    mine = [c for c in cards.values() if c.part == part.id]
    by = {r: sum(c.relation == r for c in mine) for r in ("supports", "contradicts", "weakens")}
    irrelevant = max((part.map_counts or {}).get("examined", 0) - (part.map_counts or {}).get("relevant", 0), 0)
    docs = len({c.doc for c in mine})
    s, c, w = by["supports"], by["contradicts"], by["weakens"]
    out = (
        f"{s} {'backs' if s == 1 else 'back'} it up, {c} {'goes' if c == 1 else 'go'} against it, "
        f"{w} {'casts' if w == 1 else 'cast'} doubt. "
        f"{_n(irrelevant, 'passage')} not about this part {'is' if irrelevant == 1 else 'are'} hidden. "
        f"From {docs} of {len(names)} uploaded documents."
    )
    r = len(_map_items(part, cards).refs)
    if r:
        out += f" Mentioned but not uploaded: {_n(r, 'document')}."
    return out


class _Names(dict):
    """Short display names by document id; `.full` holds the file names for hover."""

    full: dict[str, str]
    scans: set[tuple[str, int]]  # (doc id, page) pairs that are photos or scans, not text pages
    injected: bool  # the review carries an injection banner, so no model text is shown
    parts: dict[str, str]  # part id -> part text, to check the AI line against


_NAME_MAX = 30


def _tidy(name: str) -> str:
    stem = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    stem = re.sub(r"^\d+[-_ ]+", "", stem).replace("_", " ")
    stem = re.sub(r"(?<=[A-Za-z])-|-(?=[A-Za-z])", " ", stem)
    return " ".join(re.sub(r"\bArticle\b", "Art.", stem).split())


def _middle(text: str) -> str:
    """Shorten in the middle, on word boundaries, so the start and the end of the name both survive."""
    if len(text) <= _NAME_MAX:
        return text
    words = text.split()
    head, tail = [], []
    while words and len(" ".join(head + words[:1])) <= 16:
        head.append(words.pop(0))
    while words and len(" ".join(words[-1:] + tail)) <= 12:
        tail.insert(0, words.pop())
    return f"{' '.join(head)} \u2026 {' '.join(tail)}".strip()


def _short_names(docs: list[Doc]) -> _Names:
    """Map mode only: deterministic short names (no extension, no shared leading word, middle-truncated)."""
    tidy = {d.id: _tidy(d.name) or d.name for d in docs}
    firsts = [t.split(" ", 1)[0] for t in tidy.values()]
    shared = {f for f in firsts if firsts.count(f) > 1 and f.isupper()}  # an acronym prefix such as IHP_
    tidy = {k: (v.split(" ", 1)[1] if v.split(" ", 1)[0] in shared and " " in v else v) for k, v in tidy.items()}
    out = _Names({k: _middle(v) for k, v in tidy.items()})
    if len(set(out.values())) != len(out):
        out = _Names(tidy)
    if len(set(out.values())) != len(out):
        out = _Names({d.id: d.name for d in docs})
    out.full = {d.id: d.name for d in docs}
    out.scans = {(d.id, p.n) for d in docs for p in d.pages if p.kind != "text_layer"}
    return out


# Owner-approved wording (docs/sprint/journey/product-fear-second-check.md). A check that did not run never reads as "not settled".
_SECOND = {
    "agrees": "Quote alone: confirmed",
    "disagrees": "Quote alone: not settled",
    "unavailable": "Second read could not run this time",
    "not_run": "Second read did not run on this one",
}
_STATE = {"contradicts": "Goes against the claim", "weakens": "Casts doubt on the claim", "supports": "Backs up the claim",
          "set_aside": "Not relevant to this part"}
_FIRST = {"supports": "support", "weakens": "doubt", "contradicts": "going against the claim"}
_ALONE = {"entails": "supports", "contradicts": "goes against", "not_mentioned": "does not mention"}
_SEVERITY = {"contradicted": 0, "weakened": 1, "error": 2, "checking": 3, "cannot_tell": 4, "not_found": 5, "supported": 6}
_REL_GLYPH = {"contradicts": "✕", "weakens": "!", "supports": "✓", "set_aside": "–"}
_STATUS_GLYPH = {"contradicted": "✕", "weakened": "!", "supported": "✓"}
_PART_WORD = {"contradicted": "Goes against", "weakened": "Casts doubt", "supported": "Backs it up"}
_COLUMN = {"contradicts": "Goes against it", "weakens": "Casts doubt on it", "supports": "Backs it up", "set_aside": "Not relevant to this part"}
_ROW_CAP = 4  # rows shown in a document group before "Show all N"
_QUOTE_MAX = 240
_AI_BANNED = ("disagree", "failed", "unverified", "wrong", "flagged")


def _day_or_none(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None  # a date we cannot read is never shown as a date


def _long_day(d: date) -> str:
    return f"{d.day} {d:%B} {d.year}"


def _glyph(g: str) -> str:
    return f'<span class="gl" aria-hidden="true">{g}</span>'


def _counts(card: Card) -> bool:
    """False only where the second read changes the status: a backing quote it did not settle cannot, alone, make a part supported."""
    return not (card.relation == "supports" and card.check == "disagrees")


def _second_line(card: Card) -> str:
    """One short code-written paragraph on what the second read did, for a card it did not confirm."""
    first = _FIRST.get(card.relation)
    tail = f"The first read counted it as {first}" if first else ""
    if card.check in _NO_CHECK:
        head = _NO_CHECK[card.check]
    elif check_reason(card.relation, card.check, card.check_answer):
        saw = _ALONE.get(card.check_answer)
        head = f"Read on its own, the quote {saw} this part." if saw else "Read on its own, the quote did not settle this part."
    else:
        return ""
    if not tail:
        return head
    if _counts(card):
        tail += ", and it still counts."
    else:
        tail += f". On its own it cannot make this part \u201c{_PART_WORD['supported']}\u201d."
    return f"{head} {tail} {CONTEXT_TEXT}"


_WORD = re.compile(r"[^\W_][\w'\u2019-]*")


def _ai_reading(card: Card, names: dict[str, str]) -> str:
    """The model's one-sentence reason, only where code can vouch for it. Display only: never read by status, counts or order."""
    if card.check != "agrees" or getattr(names, "injected", False):
        return ""
    why = " ".join(card.why.split())
    if not why or any(b in why.casefold() for b in _AI_BANNED):
        return ""
    if len(why) > AI_MAX:
        why = why[: AI_MAX + 1].rsplit(" ", 1)[0]
    seen = f"{card.quote} {getattr(names, 'parts', {}).get(card.part, '')}".casefold()
    if any(d not in seen for d in re.findall(r"\d+", why)):
        return ""
    if any(w[0].isupper() and w.casefold() not in seen for w in _WORD.findall(why)[1:]):
        return ""
    return f'<p class="ai"><span>{AI_LABEL}</span> {_e(why)}</p>'


def _position_note(card: Card, names: dict[str, str]) -> str:
    """Plain words for a box we could not draw exactly. The quote is the row title just above, so it is not repeated."""
    scan = (card.doc, card.page) in getattr(names, "scans", set())
    if card.box_status == "unpinned":
        text = (
            "This page is a photo or scan, so we can\u2019t mark the exact spot. Look for the quoted passage on it."
            if scan
            else "We couldn\u2019t mark the exact spot on this page. Look for the quoted passage on it."
        )
    elif card.box_status == "approximate":
        text = "The box is an estimate because this page is a photo or scan." if scan else "The box is an estimate."
    else:
        return ""
    return f'<p class="poshint">{_e(text)}</p>'


def _passage(card: Card, entry: MapEntry, names: dict[str, str]) -> str:
    """The card itself, inside the row's panel: full verbatim quote, source line, one slot for the page image."""
    full = getattr(names, "full", {}).get(card.doc, card.doc)
    where = f'<span title="{_e(full)}">{_e(names.get(card.doc, card.doc))}</span>'
    phrase = qualifier_phrase(card.weakener_type)
    qualifier = f'<p class="qualifier">{_e(phrase)}</p>' if phrase else ""
    computed = f'<p class="computed">{_e(card.computed.text)}</p>' if card.computed else ""
    note = _second_line(card)
    note = f'<p class="reason-line">{_e(note)}</p>' if note else ""
    day = _day_or_none(entry.date)
    when = f" · {_e(_long_day(day))}" if day else ""
    return (
        f'<article class="card {_e(card.relation)}" tabindex="-1" data-card-id="{_e(card.id)}" '
        f'data-part="{_e(card.part)}" data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f"{qualifier}{computed}"
        f'<p class="meta">{where} · Page {card.page}{when}</p>{note}{_ai_reading(card, names)}'
        f'{_position_note(card, names)}<div class="slot"></div></article>'
    )


def _row(entry: MapEntry, names: dict[str, str], decide: str | None = None, plabel: str = "") -> str:
    """One passage as one text row. Everything the reader needs is words: quote, document, page, date, second check."""
    c = entry.card
    full = getattr(names, "full", {}).get(c.doc, c.doc)
    day = _day_or_none(entry.date)
    nc = "" if c.check == "agrees" else " nc"
    label = " ".join(
        x for x in (
            f"{_STATE[c.relation]}.", f"{plabel}." if plabel else "", f"{_SECOND[c.check]}.",
            "The finding still counts." if c.check == "disagrees" and _counts(c) else "",
            f"\u201c{c.quote}\u201d.", f"{names.get(c.doc, c.doc)}, Page {c.page}.",
            f"{_long_day(day) if day else 'No date in this passage'}.",
        ) if x
    )
    deciding = c.id == decide
    default = ' data-default-open="true"' if deciding else ""
    act = f' data-shut-act="{OPEN_THIS_TEXT}"' if deciding else ""
    return (
        f'<li class="row {_e(c.relation)}{nc}">'
        f'<button type="button" class="rowbtn" aria-expanded="false" aria-controls="p-{_e(c.id)}"{default}{act} aria-label="{_e(label)}">'
        f'{_glyph(_REL_GLYPH[c.relation])}<span class="rt"><span class="q">“{_e(c.quote)}”</span>'
        f'<span class="m"><span title="{_e(full)}">{_e(names.get(c.doc, c.doc))}</span> · Page {c.page} · '
        f'{_e(_long_day(day) if day else "No date in this passage")} · {_e(_SECOND[c.check])}</span></span>'
        f'<span class="act" aria-hidden="true">{OPEN_THIS_TEXT if deciding else "Open"}</span></button>'
        f'<div class="panel" id="p-{_e(c.id)}" hidden>{_passage(c, entry, names)}'
        f'<button type="button" class="close">Close</button></div></li>'
    )


def _order(entries: list[MapEntry], decide: str | None) -> list[MapEntry]:
    """Deciding passage first, then confirmed and dated before the rest. Stable, so date order is kept."""
    return sorted(entries, key=lambda e: (e.card.id != decide, e.card.check != "agrees", e.date is None))


def _group(
    gid: str, label: str, title: str | None, entries: list[MapEntry], opened: bool, names: dict[str, str], decide: str | None = None,
    plabel: str = "",
) -> str:
    """A folded list: a button, then the first rows, then the rest behind 'Show all N'."""
    shown, rest = entries[:_ROW_CAP], entries[_ROW_CAP:]
    body = f'<ul>{"".join(_row(e, names, decide, plabel) for e in shown)}</ul>'
    if rest:
        total = f"Show all {len(entries)}"
        body += (
            f'<ul class="rest" id="{gid}-x" hidden>{"".join(_row(e, names, decide, plabel) for e in rest)}</ul>'
            f'<button type="button" class="more" aria-expanded="false" aria-controls="{gid}-x" '
            f'data-shut="{total}" data-open="Show fewer">{total}</button>'
        )
    tip = f' title="{_e(title)}"' if title else ""
    return (
        f'<div class="grp"><button type="button" class="gbtn" aria-expanded="{str(opened).lower()}" aria-controls="{gid}">'
        f"<span{tip}>{_e(label)}</span><span>({len(entries)})</span></button>"
        f'<div id="{gid}"{"" if opened else " hidden"}>{body}</div></div>'
    )


def _open_list(rel: str, entries: list[MapEntry], names: dict[str, str], decide: str | None, plabel: str = "") -> str:
    label = f"{_COLUMN[rel]} ({len(entries)})"
    rows = "".join(_row(e, names, decide, plabel) for e in _order(entries, decide))
    return f'<div class="sub {"against" if rel == "contradicts" else "doubt"}"><h3>{_glyph(_REL_GLYPH[rel])}{_e(label)}</h3><ul>{rows}</ul></div>'


def _columns(part: Part, view: MapView, names: dict[str, str], decide: str | None, plabel: str = "") -> str:
    by = {rel: [e for e in view.entries if e.card.relation == rel] for rel in _REL_GLYPH}
    left = "".join(_open_list(rel, by[rel], names, decide, plabel) for rel in ("contradicts", "weakens") if by[rel])
    backs = _order(by["supports"], decide)
    right = ""
    if backs:
        docs: dict[str, list[MapEntry]] = {}
        for e in backs:
            docs.setdefault(e.card.doc, []).append(e)
        full = getattr(names, "full", {})
        groups = "".join(
            _group(f"g-{part.id}-{n}", names.get(d, d), full.get(d, d), es, n == 0, names, decide, plabel) for n, (d, es) in enumerate(docs.items())
        )
        right = f'<div class="col back"><h3>{_glyph(_REL_GLYPH["supports"])}{_e(_COLUMN["supports"])} ({len(backs)})</h3>{groups}</div>'
    if left and right:
        out = f'<div class="cols"><div class="col against">{left}</div>{right}</div>'
    elif left:
        out = f'<div class="col against">{left}</div><p class="none">Nothing in the documents backs it up.</p>'
    elif right:
        out = f'<p class="none">Nothing goes against it or casts doubt on it.</p>{right}'
    else:
        out = '<p class="none">No passages to show for this part.</p>'
    if by["set_aside"]:
        out += f'<div class="aside">{_group(f"g-{part.id}-aside", _COLUMN["set_aside"], None, by["set_aside"], False, names, decide, plabel)}</div>'
    return out


def _state_help(part: Part) -> str:
    if part.status not in STATE_HELP:
        return ""
    extra = ""
    if part.receipt and part.status == "not_found":
        extra = f" Pages read: {part.receipt.pages_read}."
        if part.receipt.unread:
            extra += f" Pages not read: {', '.join(map(str, part.receipt.unread))}."
    return f'<p class="state-help {part.status}">{_e(STATE_HELP[part.status])}{_e(extra)}</p>'


def _ledger_part(
    part: Part, number: str, reason_kind: str | None, cards: dict[str, Card], names: dict[str, str], show_evidence: bool,
    decide: str | None,
) -> str:
    """One part: its number and own words, its verdict word, the notes code wrote, then the two columns."""
    word = _PART_WORD.get(part.status) or MAP_STATUS_LABEL[part.status]
    pn = f'<span class="pn">{_e(number)}</span>' if number else ""
    text = part.text if number else "The whole claim"
    ph = f"“{_e(text)}”" if number else _e(text)
    notes = _state_help(part)
    if reason_kind == "unconfirmed":
        notes += f'<p class="reason-line unconfirmed">{UNCONFIRMED_TEXT}</p>'
    if part.reason:
        notes += f'<p class="reason">{_e(part.reason)}</p>'
    if part.conflict:
        notes += '<p class="conflict">Sources point different ways on this part.</p>'
    if show_evidence:
        notes += _evidence(part, names)
    body = _columns(part, _map_items(part, cards), names, decide, number) if part.evidence_map is not None else ""
    return (
        f'<section class="part s-{_e(part.status)}" data-part-id="{_e(part.id)}" aria-labelledby="h-{_e(part.id)}">'
        f'<h2 id="h-{_e(part.id)}">{pn}<span class="ph">{ph}</span>'
        f'<span class="pv">{_glyph(_STATUS_GLYPH.get(part.status, "?"))} {_e(word)}</span></h2>{notes}{body}</section>'
    )


def _footer(review: Review, cards: dict[str, Card], names: dict[str, str]) -> str:
    """Counts, hidden passages and caveats, last on the page."""
    full = getattr(names, "full", {})
    docs = ", ".join(f'<span title="{_e(full.get(d.id, d.name))}">{_e(names[d.id])}</span>' for d in review.docs)
    out = [f'<p class="ev ev-docs">{_n(len(review.docs), "document")} read: {docs}.</p>']
    for i, p in enumerate(review.parts, 1):
        if p.evidence_map is None:
            continue
        pre = f"Part {i}: " if len(review.parts) > 1 else ""
        limit = MAP_LIMIT_TEXT.format(n=(p.map_counts or {}).get("examined", 0), m=len(names))
        out.append(f'<p class="ev ev-summary">{_e(pre + _part_summary(p, cards, names))}</p>')
        out.append(f'<p class="ev ev-limit">{_e(limit)} {_e(MAP_DATE_TEXT)}</p>')
    out.append(f'<p class="ev ev-second"><strong>Quote alone</strong> {_e(SECOND_CHECK_TEXT)}</p>')
    return f'<footer class="foot">{"".join(out)}</footer>'


_DAYS = {
    m: i
    for i, m in enumerate(
        ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"],
        1,
    )
}
_DAYS.update({k[:3]: v for k, v in list(_DAYS.items())})
_MON = "|".join(sorted(_DAYS, key=len, reverse=True))
_DATE_RES = (
    re.compile(rf"\b({_MON})\.? (\d{{1,2}})(?:st|nd|rd|th)?,? (\d{{4}})\b", re.I),
    re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)? ({_MON})\.?,? (\d{{4}})\b", re.I),
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
)
_GENERIC = {"letter", "dated", "agreement", "document", "attached", "exhibit", "section", "article", "policy", "notice", "which"}


def _dates_in(text: str) -> set[date]:
    out = set()
    for n, rx in enumerate(_DATE_RES):
        for m in rx.finditer(text or ""):
            a, b, c = m.groups()
            try:
                if n == 0:
                    out.add(date(int(c), _DAYS[a.lower()], int(b)))
                elif n == 1:
                    out.add(date(int(c), _DAYS[b.lower()], int(a)))
                else:
                    out.add(date(int(a), int(b), int(c)))
            except ValueError:
                pass
    return out


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{5,}", (text or "").casefold()) if w not in _GENERIC}


def _settles(ref_text: str, ref_date: str | None, claim: str) -> bool:
    """Code-only match: the missing document's date is a date in the claim, or two distinctive words are shared."""
    mine = _dates_in(ref_text)
    if (d := _day_or_none(ref_date)) is not None:
        mine.add(d)
    return bool(mine & _dates_in(claim)) or len(_words(ref_text) & _words(claim)) >= 2


def _gap_line(review: Review) -> str:
    """Facts only: each cited-but-not-uploaded document, how often it is cited, and whether code can tie it to the claim."""
    refs: dict[str, list] = {}
    for p in review.parts:
        for it in p.evidence_map or []:
            if it.kind == "referenced":
                r = refs.setdefault(_ref_key(it.ref_text), [it.ref_text or "", set(), it.date])
                r[1].add((it.ref_doc, it.ref_page))
                r[2] = r[2] or it.date
    out = []
    for text, places, day in list(refs.values())[:3]:
        line = f"Not uploaded: {text.rstrip('. ')}. Cited {_n(len(places), 'time')}."
        if _settles(text, day, review.claim.text):
            line += " It is the document that would settle this."
        out.append(line)
    if len(refs) > 3:
        out.append(f"{len(refs) - 3} more documents are cited and not uploaded.")
    return f'<p class="gap-line">{_e(" ".join(out))}</p>' if out else ""


def _counts_line(review: Review, cards: dict[str, Card]) -> str:
    """One line from real counts. It says every passage was re-read only when no check was left out."""
    seen = [e.card for p in review.parts for e in _map_items(p, cards).entries if e.card.relation != "set_aside"]
    if not seen:
        return ""
    k = len(seen)
    by = {c: sum(x.check == c for x in seen) for c in ("agrees", "disagrees", "unavailable", "not_run")}
    n, m, u, r = by["agrees"], by["disagrees"], by["unavailable"], by["not_run"]
    ran = n + m
    if u + r == 0:
        out = ["Every passage was re-read on its own."]
    else:
        out = [f"{ran} of {k} passages {'was' if ran == 1 else 'were'} re-read on {'its' if ran == 1 else 'their'} own."]
        if u:
            out.append(f"{u} could not be re-read this time.")
        if r:
            out.append(f"{r} {'was' if r == 1 else 'were'} not re-read.")
    out.append(f"{n} confirmed.")
    if m:
        out.append(f"{m} did not settle, because a quote read alone often needs the page around it.")
        held = sum(not _counts(c) for c in seen)
        if held:
            out.append(
                f"Of these, {held} {'backs' if held == 1 else 'back'} up the claim and cannot make a part "
                f"\u201c{_PART_WORD['supported']}\u201d on {'its' if held == 1 else 'their'} own."
            )
            out.append(f"The other {k - held} still count.")
        else:
            out.append(f"All {k} still count.")
    return f'<p class="counts-line">{_e(" ".join(out))}</p>'


_DECIDES = {"contradicted": "contradicts", "weakened": "weakens", "supported": "supports"}


def _decider(review: Review, cards: dict[str, Card]) -> Card | None:
    """The deciding passage, chosen by code: first confirmed, then lowest page, in the driver part first."""
    rel = _DECIDES.get(review.status)
    if not rel:
        return None
    parts = sorted((p for p in review.parts if p.status == review.status), key=lambda p: p.id != review.driver_part)
    for p in parts:
        mine = [c for c in cards.values() if c.part == p.id and c.relation == rel]
        if mine:
            return sorted(mine, key=lambda c: (c.check != "agrees", c.page))[0]
    return None


def _why(review: Review, card: Card | None, names: dict[str, str], cards: dict[str, Card], part_no: str = "") -> str:
    """Verbatim quote, short name and page of the deciding passage. The quote opens its card and its page."""
    if card is None:
        return ""
    quote = card.quote
    cut = quote if len(quote) <= _QUOTE_MAX else quote[:_QUOTE_MAX].rsplit(" ", 1)[0]
    day = next((_day_or_none(i.date) for p in review.parts for i in p.evidence_map or [] if i.card_id == card.id), None)
    full = getattr(names, "full", {}).get(card.doc, card.doc)
    when = _long_day(day) if day else "no date in this passage"
    src = (
        f'<span class="why-src" title="{_e(full)}">{_e(names.get(card.doc, card.doc))}, Page {card.page}{_e(part_no)} '
        f"({_e(when)}, {_e(_SECOND[card.check][0].lower() + _SECOND[card.check][1:])})</span>"
    )
    more = "\u2026" if cut != quote else ""
    link = f'<a href="#" data-reveal="{_e(card.id)}">\u201c{_e(cut)}\u201d</a>{more}'
    go = f'<a class="why-open" href="#" data-reveal="{_e(card.id)}">{OPEN_THIS_TEXT}</a>'
    out = f'<p class="why-line"><strong>Why</strong> {link} {src} {go}</p>'
    opposing = [c for c in cards.values() if c.relation == "contradicts"]
    if card.relation == "contradicts" and len(opposing) == 1 and card.check == "disagrees":
        out += '<p class="why-note">Only one passage goes against it, and read on its own the quote did not settle this part.</p>'
    return out


def _part(
    part: Part,
    reason_kind: str | None = None,
    names: dict[str, str] | None = None,
    extra: str = "",
) -> str:
    conflict = '<p class="conflict">Sources disagree on this part.</p>' if part.conflict else ""
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


def _card(card: Card, reason_kind: str | None = None, doc_name: str | None = None, plain: bool = False) -> str:
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
    answer = f'<p class="reason-line check-answer">{_e(line)}</p>' if line else ""
    badge = f'<span class="mark {_e(card.check)}">{_e(CHECK_LABEL[card.check])}</span>'
    where = _e(doc_name or card.doc)
    return (
        f'<article class="card {_e(card.relation)}" tabindex="0" '
        f'data-card-id="{_e(card.id)}" data-part="{_e(card.part)}" '
        f'data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'<blockquote>{_e(card.quote)}</blockquote>'
        f'<p class="why">{_e(card.why)}</p>{computed}'
        f'<p class="meta">{where} p{card.page}{weakener} · '
        f"box {_e(card.box_status)} \u00b7 "
        f"{badge}{unchecked}</p>{answer}</article>"
    )


def _cards(cards: list[Card], reasons: dict[str, str | None], names: dict[str, str], plain: bool = False) -> str:
    out = []
    for relation, label in GROUPS:
        group = [c for c in cards if c.relation == relation]
        if group:
            out.append(f'<section class="group"><h3>{label}</h3>{"".join(_card(c, reasons.get(c.part), names.get(c.doc), plain) for c in group)}</section>')
    return "".join(out)


def _one_box(boxes: list) -> list:
    """One rectangle for a passage that runs over many printed lines, so one click draws one box."""
    if not boxes:
        return []
    return [[min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]]


def _page(
    doc: Doc,
    page: Page,
    cards: list[Card],
    images: dict[tuple[str, int], bytes],
    name: str | None = None,
    merge: bool = False,
) -> str:
    name = name or doc.name
    data = images.get((doc.id, page.n))
    if data is None:
        img = f'<div class="noimg">{_e(name)} {"Page " if merge else "p"}{page.n}: image not available</div>'
    else:
        encoded = base64.b64encode(data).decode("ascii")
        img = f'<img alt="{_e(name)} page {page.n}" src="data:image/png;base64,{encoded}">'
    boxes = "".join(
        f'<div class="box {_e(c.box_status)}" data-box-for="{_e(c.id)}" '
        f'style="left:{_pct(x0)};top:{_pct(y0)};width:{_pct(x1 - x0)};height:{_pct(y1 - y0)}"></div>'
        for c in cards
        if (c.doc, c.page) == (doc.id, page.n)
        for x0, y0, x1, y1 in (_one_box(c.boxes) if merge else c.boxes)
    )
    return (
        f'<div class="page" hidden data-doc="{_e(doc.id)}" data-page="{page.n}" '
        f'style="aspect-ratio:{page.w}/{page.h}">{img}{boxes}</div>'
    )


def _banner(banner: Banner) -> str:
    head, tip = BANNER_HELP[banner.kind]
    return f'<p class="banner {_e(banner.kind)}"><strong>{_e(head)}</strong> {_e(banner.text)} {_e(tip)}</p>'


def _unreadable_notes(review: Review, names: dict[str, str] | None = None) -> str:
    return "".join(
        f'<p class="pagenote unreadable">{_e((names or {}).get(d.id, d.name))} p{p.n}: image only, not transcribed, '
        "so nothing on it was checked. Upload a text PDF or retype it.</p>"
        for d in review.docs
        for p in d.pages
        if not p.readable
    )


def _ledger_body(review: Review, cards: dict[str, Card], names: dict[str, str], reasons, on: bool, extras: str, pages: str,
                 data: str) -> str:
    """Map mode: claim, one verdict band, parts worst first (two columns each), the page store, footer."""
    total = len(review.parts)
    number = {p.id: i for i, p in enumerate(review.parts, 1)}
    decider = _decider(review, cards)
    decide = decider.id if decider else None
    order = sorted(review.parts, key=lambda p: (_SEVERITY.get(p.status, 9), p.id != review.driver_part, number[p.id]))
    parts = "".join(
        _ledger_part(p, f"Part {number[p.id]} of {total}" if total > 1 else "", reasons[p.id], cards, names, on, decide)
        for p in order
    )
    rule = ""
    if review.status == "contradicted":
        where = f" It is in Part {number[decider.part]}." if decider and total > 1 and decider.part in number else ""
        rule = f'<p class="rule">{_e(RULE_TEXT + where)}</p>'
    part_no = f", in Part {number[decider.part]}" if decider and total > 1 and decider.part in number else ""
    band = (
        f'<section class="verdict-band s-{_e(review.status)}" aria-labelledby="verdict"><h1 id="verdict" class="vt">'
        f'{_glyph(_STATUS_GLYPH.get(review.status, "?"))} {_e(MAP_STATUS_LABEL[review.status])}</h1>{rule}'
        f"{_why(review, decider, names, cards, part_no)}{_gap_line(review)}</section>"
    )
    claim = f'<p class="claim"><small>Your claim</small><q>{_e(review.claim.text)}</q></p>'
    return (
        f'{EVIDENCE_CSS}{LEDGER_CSS}<div class="wrap"><header class="top">{claim}{band}{_counts_line(review, cards)}{extras}</header>'
        f'<main>{parts}<section class="store" aria-hidden="true">{pages}</section></main>'
        f"{_footer(review, cards, names)}</div>"
        f'<script type="application/json" id="review">{data}</script>'
    )


def render(
    review: Review, page_images: dict[tuple[str, int], bytes] | None = None, replay: bool = False, ask: bool = False,
    share: bool = False, share_url: str | None = None,
) -> str:
    """The whole review as one self-contained page. replay=True adds the saved-run badge.

    With PROOFGRAPH_GRAPH=1 and a graph on the review, the proof-path page is drawn instead (ask=True adds the
    Ask another claim form for the served page)."""
    if graph_on() and review.graph:
        from app.viewer.graph_view import render_graph

        return render_graph(review, page_images or {}, replay, ask, share, share_url)
    images = page_images or {}
    on = evidence_lines_on()
    mapped = evidence_map_on()
    names = _short_names(review.docs) if mapped else {d.id: d.name for d in review.docs}
    if mapped:
        names.injected = any(b.kind == "injection" for b in review.banners)
        names.parts = {p.id: p.text for p in review.parts}
    cards = {c.id: c for c in review.cards}
    notes = "".join(f'<p class="docnote">{_e(names[d.id])}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += _unreadable_notes(review, names)
    banners = "".join(map(_banner, review.banners))
    badge = f'<p class="replay-badge" role="note">{REPLAY_TEXT}</p>' if replay else ""
    reasons = {p.id: supports_reason(c for c in review.cards if c.part == p.id) for p in review.parts}
    pages = "".join(_page(d, p, review.cards, images, names[d.id], mapped) for d in review.docs for p in d.pages)
    # "<" escaped so the JSON can never close its script tag.
    data = review.model_dump_json().replace("<", "\\u003c")
    if mapped:
        body = _ledger_body(review, cards, names, reasons, on, f"{badge}{banners}{notes}", pages, data)
    else:
        rows = "".join(_part(p, reasons[p.id], names if on else None) for p in review.parts)
        body = (
            f"<header><h1>{_e(STATUS_LABEL[review.status])}</h1><p class=\"claim\">{_e(review.claim.text)}</p>{badge}{banners}</header>"
            f'<main><nav aria-label="Claim parts"><ul>{rows}</ul>{notes}{EVIDENCE_CSS if on else ""}</nav>'
            f'<section aria-label="Evidence cards">{_cards(review.cards, reasons, names, on)}</section>'
            f'<section aria-label="Page">{pages}</section></main>'
            f'<script type="application/json" id="review">{data}</script>'
        )
    page = TEMPLATE.read_text().replace("<!--BODY-->", body)
    return page.replace("/*MAP_JS*/", "\n" + MAP_JS.read_text() if mapped else "")
