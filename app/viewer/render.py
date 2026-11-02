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
SECOND_READ = {
    "agrees": "Second check: confirmed.",
    "disagrees": "Second check: not sure.",
    "unavailable": "Second check: not available.",
    "not_run": "Second check: not done.",
}
_SEES = "It sees only the quote and the part."
LEGEND_TEXT = "We split your claim into parts and checked each one against your documents."
RULE_TEXT = "One passage that goes against a claim is enough to count against it."
SECOND_CHECK_TEXT = (
    "A second look at this passage alone. Not sure means it did not reach the same label; the finding still counts."
)
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
    ".map-group{border:1px solid var(--line);border-left:4px solid var(--gry);border-radius:6px;margin:8px 0;overflow-wrap:anywhere}"
    ".map-group.contradicts{border-left-color:var(--red)}.map-group.weakens{border-left-color:var(--amb)}"
    ".map-group.supports{border-left-color:var(--grn)}"
    ".map-group summary,.map-more>summary,.map-unsettled>summary,.map-also>summary{cursor:pointer;padding:8px 10px;list-style:none}"
    ".map-group summary::before{content:'\\25B8';display:inline-block;width:1.2em;color:var(--mut)}"
    ".map-group details[open]>summary::before,.map-group[open]>summary::before{content:'\\25BE'}"
    ".map-group>summary{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px}"
    ".map-group>summary::before{flex:none}"
    ".map-head{font-weight:600;flex:1 1 14em}.map-sum{flex:1 1 100%;color:var(--mut);font-size:.9em;padding-left:1.2em}"
    ".map-show{font-weight:600;border:1px solid var(--gry);border-radius:4px;padding:0 8px}"
    ".map-group[open]>summary .map-show{display:none}"
    ".map-group summary:focus-visible{outline:3px solid currentColor;outline-offset:-3px}"
    ".map-group>*:not(summary){margin-left:10px;margin-right:10px}.map-group .map-more,.map-group .map-unsettled,.map-group .map-also{border-top:1px solid var(--line);margin:6px 0 8px}"
    ".map-more>summary,.map-unsettled>summary,.map-also>summary{padding:6px 0;color:var(--mut);font-weight:600}"
    ".map-note{margin:6px 10px;color:var(--mut);font-size:.9em}.map-date{margin:8px 0 2px;font-size:.85em;color:var(--mut)}"
    ".map-entry{margin:6px 0}"
    ".stance{container-type:inline-size;margin:8px 0}.stance .st-row{display:flex;flex-wrap:wrap;align-items:flex-start;gap:4px 12px;padding:8px 0;border-top:1px solid var(--line)}"
    ".st-name{flex:1 1 100%;font-weight:600;font-size:13px}.st-none{color:var(--mut);font-size:13px}"
    ".st-cell{display:flex;flex-direction:column;gap:2px}.st-marks{display:flex;flex-wrap:wrap;gap:2px}"
    ".st-cell.undated{border-left:2px dashed var(--gry);padding-left:10px}.st-name+.st-cell.undated{border-left:0;padding-left:0}"
    ".st-cd,.st-axis .st-d{font-size:12px;color:var(--mut);border-bottom:1px dotted currentColor}"
    ".st-cell.undated .st-cd,.st-axis .st-d.undated{border-bottom:0}"
    ".stance .st-axis{display:none;font-size:12px;color:var(--mut);border-top:0}"
    ".st-mark{position:relative;box-sizing:border-box;width:44px;height:44px;padding:0;border:0;border-radius:6px;background:none;cursor:pointer;color:var(--gry)}"
    ".st-mark.contradicts{color:var(--red-text)}.st-mark.weakens{color:var(--amb)}.st-mark.supports{color:var(--grn)}"
    ".st-mark svg{width:28px;height:28px;display:block;margin:auto;fill:none;stroke:currentColor;stroke-width:2.5;stroke-linejoin:round}"
    ".st-mark.filled svg{fill:currentColor}.st-mark:hover{background:var(--line)}"
    ".st-mark:focus-visible{outline:3px solid var(--fg);outline-offset:1px}"
    ".st-n{position:absolute;top:-2px;right:-2px;min-width:16px;padding:0 3px;box-sizing:border-box;border:1px solid var(--fg);border-radius:8px;"
    "background:var(--bg);color:var(--fg);font:700 12px/14px system-ui,sans-serif;text-align:center}"
    ".st-refs{display:flex;flex-wrap:wrap;gap:6px;margin-top:6px}"
    ".st-ref{margin:0;border:1px dashed var(--gry);border-radius:4px;padding:4px 8px;font-size:12px;overflow-wrap:anywhere}"
    "@container (min-width:34rem){.stance.wide .st-row,.stance.wide .st-axis{display:grid;grid-template-columns:7rem repeat(var(--cols),minmax(0,1fr)) 6.5rem;gap:0 4px;align-items:start}"
    ".stance.wide .st-name{flex:none;align-self:center}.stance.wide .st-cd{display:none}.stance.wide .st-cell.undated{padding-left:8px}"
    ".stance.wide .st-none{grid-column:2/-1}.stance.wide .st-d{padding-bottom:4px}}"
    ".chip.verdict{display:inline-block;font-size:18px;margin:0}.rule{margin:8px 0 0;font-size:16px;font-weight:600}"
    ".why-line{margin:10px 0 0;font-size:15px;overflow-wrap:anywhere}.why-line a{color:inherit;font-style:italic;border-bottom:1px solid currentColor}"
    ".why-line a:focus-visible,.st-item:focus-visible{outline:3px solid currentColor;outline-offset:2px}"
    ".why-src{color:var(--mut)}.why-note,.gap-line{margin:6px 0 0;overflow-wrap:anywhere}"
    ".gap-line{padding:6px 8px;border:1px dashed var(--gry);border-radius:4px}"
    ".legend{margin:0 0 6px}.part-n{font-weight:600;margin-right:6px}"
    ".st-key{margin:8px 0;padding:6px 8px;border-left:3px solid var(--gry);font-size:14px}.st-key p{margin:3px 0}"
    ".st-k{width:14px;height:14px;vertical-align:-2px;fill:none;stroke:currentColor;stroke-width:2.5;stroke-linejoin:round}"
    ".st-mark.decides{box-shadow:0 0 0 2px var(--bg),0 0 0 4px var(--fg);border-radius:50%}"
    ".st-empty{margin:0;padding:6px 0;border-top:1px solid var(--line);color:var(--mut);font-size:13px}"
    ".st-list{display:flex;flex-direction:column;gap:2px;margin-top:2px}.st-list[hidden]{display:none}"
    ".st-item{min-height:44px;text-align:left;padding:4px 8px;border:1px solid var(--line);border-radius:6px;background:none;color:inherit;font:inherit;font-size:14px;cursor:pointer}"
    ".st-item:hover{background:var(--line)}.qualifier{margin:6px 0 0;font-weight:600}"
    "footer.foot{padding:8px 16px 16px;border-top:1px solid var(--line);font-size:13px;overflow-wrap:anywhere}</style>"
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
    """Class header: N = confirmed + not sure + not checked, so no card is silent."""
    c = sum(x.check == "agrees" for x in cards)
    s = sum(x.check == "disagrees" for x in cards)
    u = len(cards) - c - s
    clauses = [
        t
        for n, t in (
            (c, f"{c} confirmed by the second check"),
            (s, f"{s} not sure"),
            (u, f"{u} not checked"),
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


MAP_NOTE_TEXT = (
    "Not sure means the second check, which sees only the quote and the part, did not reach the same label. "
    "These passages stay counted and linked here."
)
_OPEN_CARDS = {"contradicts": 3, "weakens": 2}
_DATE_SOURCE = {"in passage": "the passage", "document header": "the document header"}
_SHOW_ALL = {"supports": "passages that back it up"}
_MAP_GROUPS = [
    ("contradicts", "Goes against it"),
    ("weakens", "Casts doubt"),
    ("supports", "Backs it up"),
    ("set_aside", "Set aside"),
]
class _Names(dict):
    """Short display names by document id; `.full` holds the file names for hover."""

    full: dict[str, str]


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
    return out


def _when(day: str | None, source: str | None) -> str:
    try:
        d = date.fromisoformat(day) if day else None
    except ValueError:
        return f"{day} \u00b7 inferred from {_DATE_SOURCE.get(source or '', source or 'the text')}"
    if not d:
        return "No date found in this passage"
    return f"{d:%B} {d.day}, {d.year} \u00b7 inferred from {_DATE_SOURCE.get(source or '', source or 'the text')}"


def _map_card(card: Card, reasons: dict[str, str | None], names: dict[str, str]) -> str:
    full = getattr(names, "full", {}).get(card.doc)
    return _card(card, reasons.get(card.part), names.get(card.doc), True, True, True, full)


def _entry(e: MapEntry, reasons: dict[str, str | None], names: dict[str, str], flat: bool) -> str:
    out = f'<div class="map-entry"><p class="map-date">{_e(_when(e.date, e.date_source))}</p>{_map_card(e.card, reasons, names)}'
    extra = "".join(_map_card(c, reasons, names) for c in e.also)
    if extra and flat:
        out += extra
    elif extra:
        out += (
            f'<details class="map-also"><summary>Also {_n(len(e.also), "similar passage")} on the same page</summary>'
            f"{extra}</details>"
        )
    return out + "</div>"


def _weight(entries: list[MapEntry]) -> int:
    return sum(1 + len(e.also) for e in entries)


def _group(part: Part, rel: str, label: str, view: MapView, reasons, names) -> str:
    settled = [e for e in view.entries if e.card.relation == rel]
    unsettled = [e for e in view.disagreeing if e.card.relation == rel]
    everything = [c for e in settled + unsettled for c in (e.card, *e.also)]
    if not everything:
        return ""
    head = _class_header(label, everything)
    k = _OPEN_CARDS.get(rel, 0)
    show = (
        f'<span class="map-show" aria-label="Show all {len(everything)} {_SHOW_ALL.get(rel, "passages")}">'
        f"Show all {len(everything)}</span>"
        if not k
        else ""
    )
    body = f'<p class="ev map-note">{_e(MAP_NOTE_TEXT)}</p>' if unsettled else ""
    body += "".join(_entry(e, reasons, names, False) for e in settled[:k])
    rest = settled[k:]
    if rest and k:
        body += (
            f'<details class="map-more"><summary>Show {_weight(rest)} more</summary>'
            f'{"".join(_entry(e, reasons, names, False) for e in rest)}</details>'
        )
    else:
        body += "".join(_entry(e, reasons, names, False) for e in rest)
    if unsettled:
        opened = " open" if k and not settled else ""  # a lone contradiction or weakening is never folded away
        body += (
            f'<details class="map-unsettled"{opened}><summary>{_weight(unsettled)} not sure after the second check'
            f'</summary>{"".join(_entry(e, reasons, names, True) for e in unsettled)}</details>'
        )
    return (
        f'<details class="map-group {_e(rel)}" data-part="{_e(part.id)}" data-rel="{_e(rel)}"{" open" if k else ""}>'
        f'<summary><span class="map-head" aria-label="{_e(head)}">{_e(head)}</span>{show}'
        f'<span class="map-sum">{_e(_summary(settled + unsettled, names))}</span></summary>{body}</details>'
    )


_LANES = [
    ("contradicts", "Goes against it", "diamond"),
    ("weakens", "Casts doubt", "triangle"),
    ("supports", "Backs it up", "circle"),
]
_SHAPE = {
    "diamond": '<polygon points="12,2 22,12 12,22 2,12"/>',
    "triangle": '<polygon points="12,3 22,21 2,21"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
}
_COLLAPSE_OVER = 3  # more marks than this on one lane and day become one mark with a count
_WIDE_MAX_DAYS = 8


@dataclass
class StanceMark:
    """One mark on the stance map: a card, or the near-duplicates merged into it, or one lane-day's crowd."""

    rel: str
    day: date | None
    cards: list[Card]


def _day_or_none(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None  # a date we cannot read is never placed on the axis


def _stance_marks(part: Part, view: MapView) -> list[StanceMark]:
    """Pure: one mark per entry, then lane-days holding more than _COLLAPSE_OVER marks collapse to one."""
    order = {it.card_id: i for i, it in enumerate(part.evidence_map or []) if it.kind == "card"}
    cells: dict[tuple[str, date | None], list[StanceMark]] = {}
    for e in sorted(view.entries + view.disagreeing, key=lambda e: order.get(e.card.id, 0)):
        if e.card.relation in {r for r, _, _ in _LANES}:
            day = _day_or_none(e.date)
            cells.setdefault((e.card.relation, day), []).append(StanceMark(e.card.relation, day, [e.card, *e.also]))
    out = []
    for (rel, day), marks in cells.items():
        if len(marks) > _COLLAPSE_OVER:
            marks = [StanceMark(rel, day, [c for m in marks for c in m.cards])]
        out += marks
    return out


_SECOND = {"agrees": "confirmed", "disagrees": "not sure", "unavailable": "not available", "not_run": "not done"}


def _long_day(d: date) -> str:
    return f"{d.day} {d:%B} {d.year}"


def _state(cards: list[Card]) -> tuple[str, str]:
    """(class, words): solid only when every second check in the mark confirmed."""
    counts = {k: sum(x.check == k for x in cards) for k in _SECOND}
    cls = "filled" if counts["agrees"] == len(cards) else "hollow"
    seen = [k for k, n in counts.items() if n]
    if len(seen) == 1:
        return cls, f"second check {_SECOND[seen[0]]}"
    return cls, "second check: " + ", ".join(f"{counts[k]} {_SECOND[k]}" for k in seen)


def _stance_mark(m: StanceMark, label: str, names: dict[str, str], decide: str | None = None) -> tuple[str, str]:
    """(button, list): a numbered mark opens a list of its cards; a single mark reveals its one card."""
    first = m.cards[0]
    cls, state = _state(m.cards)
    when = _long_day(m.day) if m.day else "no date found"
    where = f"{names.get(first.doc, first.doc)}, page {first.page}"
    many = len(m.cards) > 1
    text = (
        f"{label}, {len(m.cards)} passages, first in {where}, {when}, {state}, opens a list"
        if many
        else f"{label}, {where}, {when}, {state}"
    )
    tip = _e(text)
    ring = " decides" if decide and any(c.id == decide for c in m.cards) else ""
    badge = f'<span class="st-n" aria-hidden="true">{len(m.cards)}</span>' if many else ""
    shape = next(sh for r, _, sh in _LANES if r == m.rel)
    if many:
        lid = f"st-{first.id}"
        act = f'data-opens="{_e(lid)}" aria-expanded="false" aria-controls="{_e(lid)}"'
        items = "".join(
            f'<button type="button" class="st-item" data-reveal="{_e(c.id)}">{_e(names.get(c.doc, c.doc))}, page {c.page}'
            f" \u00b7 second check {_SECOND[c.check]}</button>"
            for c in m.cards
        )
        lst = f'<div class="st-list" id="{_e(lid)}" hidden>{items}</div>'
    else:
        act, lst = f'data-reveal="{_e(first.id)}"', ""
    btn = (
        f'<button type="button" class="st-mark {m.rel} {cls}{ring}" {act} data-count="{len(m.cards)}" '
        f'data-shape="{shape}" aria-label="{tip}" title="{tip}">'
        f'<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">{_SHAPE[shape]}</svg>{badge}</button>'
    )
    return btn, lst


def _stance_map(part: Part, view: MapView, names: dict[str, str], decide: str | None = None) -> str:
    """Per part, lanes (Contradicts, Weakens, Supports) over days in order, plus a No-date column. Facts only."""
    marks = _stance_marks(part, view)
    days = sorted({m.day for m in marks if m.day})
    col = {d: i + 2 for i, d in enumerate(days)}
    wide = " wide" if 1 <= len(days) <= _WIDE_MAX_DAYS else ""
    axis = ""
    if wide:
        axis = (
            '<div class="st-row st-axis" aria-hidden="true"><span></span>'
            + "".join(f'<span class="st-d" style="grid-column:{col[d]}">{_e(_day(d, True))}</span>' for d in days)
            + f'<span class="st-d undated" style="grid-column:{len(days) + 2}">No date found</span></div>'
        )
    lanes, empty = [], []
    for rel, label, _ in _LANES:
        mine = [m for m in marks if m.rel == rel]
        n = sum(len(m.cards) for m in mine)
        if not mine:
            empty.append(
                f'<p class="st-empty" data-lane="{rel}" role="group" aria-label="{_e(label)}: none found">{_e(label)}: none found</p>'
            )
            continue
        cells = []
        for key in [*days, None]:
            here = [_stance_mark(m, label, names, decide) for m in mine if m.day == key]
            if not here:
                continue
            if key:
                head, gc, cls, data = _day(key, True), col[key], "", f' data-day="{key.isoformat()}"'
            else:
                head, gc, cls, data = "No date found", len(days) + 2, " undated", ""
            cells.append(
                f'<div class="st-cell{cls}"{data} style="grid-column:{gc}"><span class="st-cd">{_e(head)}</span>'
                f'<div class="st-marks">{"".join(b for b, _ in here)}</div>{"".join(l for _, l in here)}</div>'
            )
        lanes.append(
            f'<div class="st-row st-lane {rel}" data-lane="{rel}" role="group" aria-label="{_e(label)} ({n})">'
            f'<span class="st-name">{_e(label)} ({n})</span>{"".join(cells)}</div>'
        )
    items = []
    for r in view.refs:
        tip = _e(f"Mentioned but not uploaded: {r.text}, cited {_n(r.count, 'time')}")
        items.append(
            f'<p class="st-ref" role="group" aria-label="{tip}"><strong>Mentioned but not uploaded</strong> '
            f'{_e(r.text)} (cited in {_n(r.count, "place")})</p>'
        )
    refs = "".join(items)
    refs = f'<div class="st-refs">{refs}</div>' if refs else ""
    return (
        f'<figure class="stance{wide}" data-part="{_e(part.id)}" style="--cols:{len(days)};margin-inline:0" role="group" '
        f'aria-label="Stance map">{axis}{"".join(lanes)}{"".join(empty)}{refs}</figure>'
    )


def _key(ring: bool) -> str:
    """The key sits above each map, in body-size type: every mark and column explained in four short lines."""

    def sh(name: str) -> str:
        return f'<svg class="st-k" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{_SHAPE[name]}</svg>'

    rows = [
        f"<strong>Shapes</strong> {sh('circle')} circle backs it up, {sh('triangle')} triangle casts doubt, "
        f"{sh('diamond')} diamond goes against it. Solid = second check confirmed, hollow = second check not sure.",
        f"<strong>Second check</strong> {_e(SECOND_CHECK_TEXT)}",
        "<strong>Number on a mark</strong> N passages on that day, click to see them. "
        "<strong>Dashed row</strong> mentioned in your documents but not uploaded.",
        "<strong>Columns</strong> Dates are in order, not to scale. Dates come from the text. "
        "No date found: these passages state no date.",
    ]
    if ring:
        rows.append("<strong>Ring</strong> the passage quoted at the top of the page.")
    return f'<div class="st-key">{"".join(f"<p>{r}</p>" for r in rows)}</div>'


def _map(
    part: Part, cards: dict[str, Card], names: dict[str, str], reasons: dict[str, str | None], decide: str | None = None
) -> str:
    """Under a part (flag on only): the key, the stance map, then one <details> per relation. Counts go to the footer."""
    view = _map_items(part, cards)
    groups = "".join(_group(part, rel, label, view, reasons, names) for rel, label in _MAP_GROUPS)
    ring = bool(decide) and any(c.id == decide for c in cards.values() if c.part == part.id)
    return f'{_key(ring)}{_stance_map(part, view, names, decide)}<div class="map">{groups}</div>'


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


_DECIDES = {"contradicted": "contradicts", "weakened": "weakens", "supported": "supports"}
_QUOTE_MAX = 240


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


def _why(review: Review, card: Card | None, names: dict[str, str], cards: dict[str, Card]) -> str:
    """Verbatim quote, short name and page of the deciding passage. The quote opens its card and its page."""
    if card is None:
        return ""
    quote = card.quote
    cut = quote if len(quote) <= _QUOTE_MAX else quote[:_QUOTE_MAX].rsplit(" ", 1)[0]
    day = next((_day_or_none(i.date) for p in review.parts for i in p.evidence_map or [] if i.card_id == card.id), None)
    full = getattr(names, "full", {}).get(card.doc, card.doc)
    when = _long_day(day) if day else "no date found"
    src = (
        f'<span class="why-src" title="{_e(full)}">{_e(names.get(card.doc, card.doc))}, p{card.page} '
        f"({_e(when)}, second check: {_SECOND[card.check]})</span>"
    )
    more = "\u2026" if cut != quote else ""
    link = f'<a href="#" data-reveal="{_e(card.id)}">\u201c{_e(cut)}\u201d</a>{more}'
    out = f'<p class="why-line"><strong>Why</strong> {link} {src}</p>'
    opposing = [c for c in cards.values() if c.relation == "contradicts"]
    if card.relation == "contradicts" and len(opposing) == 1 and card.check == "disagrees":
        out += '<p class="why-note">Only one passage goes against it, and the second check was not sure.</p>'
    return out


def _part(
    part: Part,
    reason_kind: str | None = None,
    names: dict[str, str] | None = None,
    extra: str = "",
    mapped: bool = False,
    plain: bool = False,
    number: str = "",
) -> str:
    said = "Sources point different ways on this part." if mapped else "Sources disagree on this part."
    conflict = f'<p class="conflict">{said}</p>' if part.conflict else ""
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
    num = f'<span class="part-n">{_e(number)}</span>' if number else ""
    return (
        f'<li class="part {_e(part.status)}" data-part-id="{_e(part.id)}">'
        f'<span class="chip {_e(part.status)}">{_e((MAP_STATUS_LABEL if plain else STATUS_LABEL)[part.status])}</span> '
        f"{num}<span>{_e(part.text)}</span>{unconfirmed}{help_}{reason}{conflict}"
        f"{_evidence(part, names) if names is not None else ''}{extra}</li>"
    )


def _card(
    card: Card,
    reason_kind: str | None = None,
    doc_name: str | None = None,
    plain: bool = False,
    second_read: bool = False,
    brief: bool = False,
    full: str | None = None,
) -> str:
    unchecked = (
        f' <span class="not-double-checked">{NOT_DOUBLE_CHECKED_TEXT}</span>'
        if reason_kind == "not_double_checked" and card.relation == "supports" and card.check != "disagrees"
        else ""
    )
    weakener = f" · {_e(card.weakener_type)}" if card.weakener_type else ""
    phrase = qualifier_phrase(card.weakener_type) if plain else None
    if second_read:  # map mode: the reason is a line of its own above the source line, not footer words
        weakener = ""
    elif phrase:
        weakener += f" · {_e(phrase)}"
    qualifier = f'<p class="qualifier">{_e(phrase)}</p>' if second_read and phrase else ""
    computed = f'<p class="computed">{_e(card.computed.text)}</p>' if card.computed else ""
    line = check_reason(card.relation, card.check, card.check_answer)
    if second_read and line:
        saw = _SAW.get(card.check_answer)
        line = (
            f"The second check of this quote alone {saw}, while this card is labelled {_LABELLED[card.relation]}. {_SEES}"
            if saw and card.relation in _LABELLED
            else f"The second check of this quote alone is not available here. {_SEES}"
        )
    answer = f'<p class="reason-line check-answer">{_e(line)}</p>' if line and not brief else ""
    if second_read:
        text = _e(SECOND_READ[card.check])
        tip = f' title="{_e(line)}"' if brief and line else ""
        badge = f'<span class="mark second-read" aria-label="{text}"{tip}>{text}</span>'
    else:
        badge = f'<span class="mark {_e(card.check)}">{_e(CHECK_LABEL[card.check])}</span>'
    where = _e(doc_name or card.doc)
    if second_read and full:
        where = f'<span title="{_e(full)}">{where}</span>'
    position = {"pinned": "", "approximate": "position approximate \u00b7 ", "unpinned": "position not found \u00b7 "}
    box = f"box {_e(card.box_status)} \u00b7 " if not second_read else position[card.box_status]
    return (
        f'<article class="card {_e(card.relation)}" tabindex="0" '
        f'data-card-id="{_e(card.id)}" data-part="{_e(card.part)}" '
        f'data-doc="{_e(card.doc)}" data-page="{card.page}">'
        f'<blockquote>{_e(card.quote)}</blockquote>'
        f'<p class="why">{_e(card.why)}</p>{qualifier}{computed}'
        f'<p class="meta">{where} p{card.page}{weakener} · '
        f"{box}"
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
        img = f'<div class="noimg">{_e(name)} p{page.n}: image not available</div>'
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


def render(
    review: Review, page_images: dict[tuple[str, int], bytes] | None = None, replay: bool = False
) -> str:
    """The whole review as one self-contained page. replay=True adds the saved-run badge."""
    images = page_images or {}
    on = evidence_lines_on()
    mapped = evidence_map_on()
    names = _short_names(review.docs) if mapped else {d.id: d.name for d in review.docs}
    cards = {c.id: c for c in review.cards}
    notes = "".join(f'<p class="docnote">{_e(names[d.id])}: {_e(d.note)}</p>' for d in review.docs if d.note)
    notes += _unreadable_notes(review, names)
    banners = "".join(map(_banner, review.banners))
    badge = f'<p class="replay-badge" role="note">{REPLAY_TEXT}</p>' if replay else ""
    reasons = {p.id: supports_reason(c for c in review.cards if c.part == p.id) for p in review.parts}
    pages = "".join(_page(d, p, review.cards, images, names[d.id], mapped) for d in review.docs for p in d.pages)
    decider = _decider(review, cards) if mapped else None
    decide = decider.id if decider else None
    maps = {
        p.id: _map(p, cards, names, reasons, decide) if mapped and p.evidence_map is not None else "" for p in review.parts
    }
    legend = f'<p class="ev legend">{_e(LEGEND_TEXT)}</p>' if mapped and len(review.parts) > 1 else ""
    top = ""
    if mapped:
        rule = f'<p class="rule">{_e(RULE_TEXT)}</p>' if review.status == "contradicted" else ""
        top = f'{rule}<p class="claim">{_e(review.claim.text)}</p>{_why(review, decider, names, cards)}{_gap_line(review)}'
    # "<" escaped so the JSON can never close its script tag.
    data = review.model_dump_json().replace("<", "\\u003c")
    if mapped:
        chip = f'<h1 class="chip verdict {_e(review.status)}">{_e(MAP_STATUS_LABEL[review.status])}</h1>{top}'
    else:
        chip = f'<h1>{_e(STATUS_LABEL[review.status])}</h1><p class="claim">{_e(review.claim.text)}</p>'
    total = len(review.parts)
    rows = "".join(
        _part(p, reasons[p.id], names if on else None, maps[p.id], bool(maps[p.id]), mapped, f"Part {i}" if mapped and total > 1 else "")
        for i, p in enumerate(review.parts, 1)
    )
    foot = _footer(review, cards, names) if mapped else ""
    body = (
        f"<header>{chip}{badge}{banners}</header>"
        f'<main><nav aria-label="Claim parts">{legend}<ul>{rows}</ul>{notes}{EVIDENCE_CSS if on or mapped else ""}</nav>'
        f'<section aria-label="Evidence cards">{"" if mapped and any(p.evidence_map is not None for p in review.parts) else _cards(review.cards, reasons, names, on)}</section>'
        f'<section aria-label="Page">{pages}</section></main>{foot}'
        f'<script type="application/json" id="review">{data}</script>'
    )
    page = TEMPLATE.read_text().replace("<!--BODY-->", body)
    return page.replace("/*MAP_JS*/", "\n" + MAP_JS.read_text() if mapped else "")
