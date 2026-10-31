"""Per-part review run: uploads and one claim in, a stream of events and one Review out.

Path: ingest, gate on the spend cap, split the claim, then each part runs relate, snap and
the blind card check in a bounded thread pool. ``run_review`` is a generator: ``PartsReady``
right after the split (every part "checking"), one ``PartDone`` per part in COMPLETION
order, then ``AllDone`` with the Review whose parts and cards are in PART order.

Worker threads compute and return plain data only. They never touch Streamlit; the caller's
script thread consumes the events and draws. Errors become banners, never stack traces. A
spend stop or model failure marks that part ``error``; it is never read as a finding.

No gold, no pack files, no scan transcription yet (unread pages reach the absence sweep as None).
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from proofgraph.clients.checker import blind_wording
from proofgraph.clients.muse import MuseClient
from proofgraph.review import ingest as ingest_mod
from proofgraph.review.absence import AbsencePage, build_receipt
from proofgraph.review.check import Checker, check_cards
from proofgraph.review.models import (
    Banner, Card, Claim, Doc, Page, Part, PartStatus, Receipt, Review, Run,
)
from proofgraph.review.relate import PageText, relate
from proofgraph.review.snap import snap
from proofgraph.review.split import split
from proofgraph.review.status import WORST_FIRST, overall_status, part_status
from proofgraph.spend import MuseError, SpendCapReached

MAX_WORKERS = 4
LINE_GAP = 8  # grid units; words whose top differs by more start a new text line
_KIND = {"text": "text_layer", "image_only": "image_only", "image": "image"}


@dataclass(frozen=True)
class RunResult:
    review: Review
    page_images: dict[tuple[str, int], bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class PartsReady:
    parts: list[Part]  # every part status "checking"


@dataclass(frozen=True)
class PartDone:
    part_id: str
    status: PartStatus
    reason: str | None = None


@dataclass(frozen=True)
class AllDone:
    result: RunResult


@dataclass(frozen=True)
class _Outcome:
    """Plain data a worker returns. No Streamlit, no shared state."""

    part: Part
    cards: list[Card]
    banners: list[Banner]


def default_muse() -> MuseClient:
    """The live client, built from the environment (key, cache dir, spend cap)."""
    return MuseClient()


def run_review(
    claim: str,
    paths: Iterable[str | Path],
    muse: MuseClient,
    *,
    checker: Checker = blind_wording,
    max_workers: int = MAX_WORKERS,
) -> Iterator[PartsReady | PartDone | AllDone]:
    claim = claim.strip()
    if not claim:
        raise ValueError("claim is empty")
    banners: list[Banner] = []
    docs: list[Doc] = []
    images: dict[tuple[str, int], bytes] = {}
    texts: list[PageText] = []
    words: dict[tuple[str, int], list] = {}
    unread: list[int] = []
    sweep: list[AbsencePage] = []  # every page, text None when it was not read

    for item in ingest_mod.ingest(paths):
        if item.error:
            banners.append(Banner(kind="unreadable", text=f"{item.name}: {item.error}"))
            continue
        pages = []
        for page in item.pages:
            readable = page.kind == "text"
            width, height = Image.open(io.BytesIO(page.png)).size
            note = None if readable else "No text layer; this page was not read."
            if not readable:
                unread.append(page.page)
                banners.append(Banner(kind="unreadable", text=f"{item.name} p{page.page}: {note}"))
            else:
                texts.append(PageText(item.doc_id, page.page, _page_text(page.words)))
                words[(item.doc_id, page.page)] = page.words
            sweep.append(AbsencePage(item.doc_id, page.page, texts[-1].text if readable else None))
            images[(item.doc_id, page.page)] = page.png
            pages.append(Page(n=page.page, kind=_KIND[page.kind], png=f"{item.doc_id}-{page.page}.png",
                              w=width, h=height, readable=readable, note=note))
        docs.append(Doc(id=item.doc_id, name=item.name, pages=pages))

    def finish(parts: list[Part], cards: list[Card], extra: list[Banner]) -> AllDone:
        return AllDone(_assemble(claim, muse, docs, images, parts, cards, banners + extra))

    receipt = Receipt(pages_read=len(texts), unread=unread)
    whole = Part(id="p1", text=claim, span=(0, len(claim)), status="cannot_tell", receipt=receipt)
    if not texts:
        whole.reason = "No page had readable text, so nothing was checked."
        yield finish([whole], [], [])
        return

    # Gates first: the spend cap is checked before split, so a stopped run sends nothing.
    try:
        muse.ensure_budget()
        pieces = split(claim, muse)
    except Exception as exc:  # a stop or split failure is a banner, not a crash
        whole.status, whole.reason = "error", "The claim was not split; nothing was checked."
        yield finish([whole], [], [_failure_banner(exc)])
        return

    parts = [Part(id=p.id, text=p.text, span=p.span, status="checking", receipt=receipt) for p in pieces]
    yield PartsReady([p.model_copy() for p in parts])

    pool = ThreadPoolExecutor(max_workers=max(1, min(max_workers, MAX_WORKERS)))
    try:
        futures = {pool.submit(_run_part, p, texts, words, sweep, muse, checker): p for p in parts}
        outcomes: dict[str, _Outcome] = {}
        for future in as_completed(futures):
            outcome = future.result()
            outcomes[outcome.part.id] = outcome
            yield PartDone(outcome.part.id, outcome.part.status, outcome.part.reason)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)

    ordered = [outcomes[p.id] for p in parts]
    yield finish([o.part for o in ordered], [c for o in ordered for c in o.cards],
                 [b for o in ordered for b in o.banners])


def _run_part(part: Part, texts: list[PageText], words: dict, sweep: list[AbsencePage],
              muse: MuseClient, checker: Checker) -> _Outcome:
    """Worker: relate, snap, blind check, status for ONE part. Returns plain data; never raises."""
    banners: list[Banner] = []
    cards: list[Card] = []
    done = part.model_copy()
    try:
        found = relate(part.text, texts, muse)
    except Exception as exc:
        banners.append(_failure_banner(exc))
        done.status = "error"
        done.reason = ("Stopped at the spend cap; nothing was checked." if isinstance(exc, SpendCapReached)
                       else "The model call failed; nothing was checked.")
        return _Outcome(done, cards, banners)
    if found.injection_quote:
        banners.append(Banner(kind="injection",
                              text=f"A page contains an instruction aimed at the reviewer: {found.injection_quote}"))
    page_words = words.get((found.doc, found.page))
    if found.relation != "set_aside" and found.quote.strip() and page_words is not None:
        pinned = snap(found.quote, page_words)
        card = Card(id=f"{part.id}-c1", part=part.id, relation=found.relation,
                    weakener_type=found.weakener_type, quote=found.quote, doc=found.doc,
                    page=found.page, boxes=pinned.boxes, box_status=pinned.status,
                    why=found.why, check="not_run")
        cards = check_cards([card], [part], checker=checker)
    complete = build_receipt(part.text, sweep, cards).complete
    done.status, done.conflict = part_status(cards, receipt_complete=complete)
    done.card_ids = [c.id for c in cards]
    return _Outcome(done, cards, banners)


def _failure_banner(exc: Exception) -> Banner:
    if isinstance(exc, SpendCapReached):
        return Banner(kind="cap", text=str(exc))
    note = str(exc) if isinstance(exc, MuseError) else f"{type(exc).__name__}: {exc}"
    return Banner(kind="checker_unavailable", text=f"The model call failed: {note}")


def _assemble(claim: str, muse: MuseClient, docs: list[Doc], images: dict, parts: list[Part],
              cards: list[Card], banners: list[Banner]) -> RunResult:
    renamed: dict[str, str] = {}
    final_cards: list[Card] = []
    for n, card in enumerate(cards, start=1):
        renamed[card.id] = f"c{n}"
        final_cards.append(card.model_copy(update={"id": f"c{n}"}))
    for part in parts:
        part.card_ids = [renamed[i] for i in part.card_ids]
    done = [p.status for p in parts if p.status != "error"]
    status: PartStatus = overall_status(done) if done else "error"
    if len(done) < len(parts) and status not in ("contradicted", "weakened"):
        status = "error"  # an unchecked part must not read as clean
    driver = next((p.id for s in WORST_FIRST for p in parts if p.status == s), parts[0].id)
    digest = hashlib.sha256((claim + "|".join(d.id for d in docs)).encode()).hexdigest()[:12]
    review = Review(
        version="review-1", review_id=f"run-{digest}", claim=Claim(text=claim, origin="pasted"),
        status=status, driver_part=driver,
        run=Run(mode="live", recorded_at=datetime.now(timezone.utc).isoformat(),
                models={"proposer": muse.settings.muse_model}, cost_usd=0.0),
        docs=docs, parts=parts, cards=final_cards, banners=banners,
    )
    return RunResult(review, images)


def _page_text(words: list) -> str:
    lines: list[list[str]] = []
    top = None
    for word in sorted(words, key=lambda w: (w.box[1], w.box[0])):
        if top is None or word.box[1] - top > LINE_GAP:
            lines.append([])
            top = word.box[1]
        lines[-1].append(word.text)
    return "\n".join(" ".join(line) for line in lines)
