"""Evidence map for one claim part (flag PROOFGRAPH_EVIDENCE_MAP=1).

Code finds the candidate passages and orders them; the model only labels each one. Every passage labelled
supports, contradicts or weakens becomes a card, and part status is computed from all of them by
``part_status``. Irrelevant passages are dropped: no card, no map item. Dates are inferred from the text by
pattern; "referenced, not supplied" is a pattern match on a cited document date no header carries.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from proofgraph.clients.muse import MuseClient
from proofgraph.review.candidates import build_candidates, unit_for
from proofgraph.review.check import Checker, check_cards
from proofgraph.review.label import label_candidates
from proofgraph.review.models import Banner, Card, MapItem, Part
from proofgraph.review.relate import PageText, relate
from proofgraph.review.scan import locate
from proofgraph.review.snap import snap
from proofgraph.review.timeline import _header_date, infer_dates, order, referenced_documents
from proofgraph.spend import SpendCapReached

CAP = 40


@dataclass(frozen=True)
class MapResult:
    cards: list[Card]
    items: list[MapItem]
    counts: dict
    banners: list[Banner]


def build_map(part: Part, texts: list[PageText], words: dict, scan_lines: dict, muse: MuseClient,
              checker: Checker, names: dict[str, str] | None = None) -> MapResult:
    cs = build_candidates(part.text, texts, CAP)
    extra = _suggested(part.text, texts, muse, {(c.doc, c.page, c.offset) for c in cs.candidates})
    cands = cs.candidates + tuple(replace(c, id=f"k{len(cs.candidates) + n}") for n, c in enumerate(extra, 1))
    res = label_candidates(part.text, cands, muse, names)
    banners = []
    if res.injection_quote:
        banners.append(Banner(kind="injection",
                              text=f"A page contains an instruction aimed at the reviewer: {res.injection_quote}"))
    cards: list[Card] = []
    by_cand: dict[str, Card] = {}
    for cand, lab in res.pairs:
        if lab.relation == "irrelevant":
            continue
        page_words = words.get((cand.doc, cand.page))
        transcript = scan_lines.get((cand.doc, cand.page))
        if page_words is None and transcript is None:
            continue
        pinned = snap(cand.text, page_words) if page_words is not None else locate(cand.text, transcript)
        card = Card(id=f"{part.id}-c{len(cards) + 1}", part=part.id, relation=lab.relation,
                    weakener_type=lab.weakener_type, quote=cand.text, doc=cand.doc, page=cand.page,
                    boxes=pinned.boxes, box_status=pinned.status, why=lab.why, check="not_run")
        cards.append(card)
        by_cand[cand.id] = card
    cards = check_cards(cards, [part], checker=checker)
    by_id = {c.id: c for c in cards}

    page_text = {(t.doc, t.page): t.text for t in texts}
    kept = [(c, lab) for c, lab in res.pairs if c.id in by_cand]
    dated = infer_dates([c for c, _ in kept], page_text)
    headers = {t.doc: _header_date(page_text.get((t.doc, 1), "")) for t in texts}
    items: list[MapItem] = []
    for cand, d in order([(c, dated[c.id]) for c, _ in kept]):
        card = by_id[by_cand[cand.id].id]
        items.append(MapItem(kind="card", card_id=card.id, date=d.date, date_source=d.source))
        for ref in referenced_documents([(card.id, card.quote)], headers):
            if ref.status == "not supplied":
                items.append(MapItem(kind="referenced", ref_text=ref.phrase, ref_doc=card.doc,
                                     ref_page=card.page, date=ref.date, date_source="cited date"))
    counts = {"examined": res.examined, "relevant": res.relevant, "unlabelled": res.unlabelled,
              "matched": cs.total_matched, "suggested": len(extra), "shown": len(cards)}
    return MapResult(cards, items, counts, banners)


def _suggested(part_text: str, texts: list[PageText], muse: MuseClient, have: set) -> list:
    """The unit holding the model's own pick, found by reading the packet; it is labelled like any other."""
    try:
        found = relate(part_text, texts, muse)
    except SpendCapReached:
        raise
    except Exception:
        return []
    page = next((t.text for t in texts if (t.doc, t.page) == (found.doc, found.page)), None)
    if found.relation == "set_aside" or not found.quote.strip() or page is None:
        return []
    unit = unit_for(page, found.quote, found.doc, found.page)
    if unit is None or (unit.doc, unit.page, unit.offset) in have:
        return []
    return [unit]
