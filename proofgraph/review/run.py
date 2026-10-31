"""Walking skeleton: uploads and one claim in, one Review out.

Path: ingest, whole claim as ONE part, relate over page-tagged text, snap the returned
quote on its page, part_status. Errors become banners, never stack traces. A spend stop
or model failure marks the part ``error``; it is never read as a finding.

No gold, no pack files, no scan transcription, no claim split (later tickets).
"""

from __future__ import annotations

import hashlib
import io
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from proofgraph.clients.muse import MuseClient
from proofgraph.review import ingest as ingest_mod
from proofgraph.review.models import (
    Banner, Card, Claim, Doc, Page, Part, Receipt, Review, Run,
)
from proofgraph.review.relate import PageText, relate
from proofgraph.review.snap import snap
from proofgraph.review.status import overall_status, part_status
from proofgraph.spend import MuseError, SpendCapReached

PART_ID = "P1"
LINE_GAP = 8  # grid units; words whose top differs by more start a new text line
_KIND = {"text": "text_layer", "image_only": "image_only", "image": "image"}


@dataclass(frozen=True)
class RunResult:
    review: Review
    page_images: dict[tuple[str, int], bytes] = field(default_factory=dict)


def default_muse() -> MuseClient:
    """The live client, built from the environment (key, cache dir, spend cap)."""
    return MuseClient()


def run_review(claim: str, paths: Iterable[str | Path], muse: MuseClient) -> RunResult:
    claim = claim.strip()
    if not claim:
        raise ValueError("claim is empty")
    banners: list[Banner] = []
    docs: list[Doc] = []
    images: dict[tuple[str, int], bytes] = {}
    texts: list[PageText] = []
    words: dict[tuple[str, int], list] = {}
    unread: list[int] = []

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
            images[(item.doc_id, page.page)] = page.png
            pages.append(Page(n=page.page, kind=_KIND[page.kind], png=f"{item.doc_id}-{page.page}.png",
                              w=width, h=height, readable=readable, note=note))
        docs.append(Doc(id=item.doc_id, name=item.name, pages=pages))

    cards: list[Card] = []
    status, conflict, reason = "cannot_tell", False, None
    if texts:
        try:
            found = relate(claim, texts, muse)
        except SpendCapReached as exc:
            banners.append(Banner(kind="cap", text=str(exc)))
            status, reason = "error", "Stopped at the spend cap; nothing was checked."
        except Exception as exc:  # model failure of any kind is a banner, not a crash
            note = str(exc) if isinstance(exc, MuseError) else f"{type(exc).__name__}: {exc}"
            banners.append(Banner(kind="checker_unavailable", text=f"The model call failed: {note}"))
            status, reason = "error", "The model call failed; nothing was checked."
        else:
            if found.injection_quote:
                banners.append(Banner(kind="injection",
                                      text=f"A page contains an instruction aimed at the reviewer: {found.injection_quote}"))
            page_words = words.get((found.doc, found.page))
            if found.relation != "set_aside" and found.quote.strip() and page_words is not None:
                pinned = snap(found.quote, page_words)
                cards.append(Card(id="c1", part=PART_ID, relation=found.relation,
                                  weakener_type=found.weakener_type, quote=found.quote,
                                  doc=found.doc, page=found.page, boxes=pinned.boxes,
                                  box_status=pinned.status, why=found.why, check="not_run"))
            status, conflict = part_status(cards, receipt_complete=not unread)
    else:
        reason = "No page had readable text, so nothing was checked."

    part = Part(id=PART_ID, text=claim, span=(0, len(claim)), status=status, reason=reason,
                card_ids=[c.id for c in cards], conflict=conflict,
                receipt=Receipt(pages_read=len(texts), unread=unread))
    digest = hashlib.sha256((claim + "|".join(d.id for d in docs)).encode()).hexdigest()[:12]
    review = Review(
        version="review-1", review_id=f"run-{digest}", claim=Claim(text=claim, origin="pasted"),
        status=overall_status([status]) if status != "error" else "error",
        driver_part=PART_ID, run=Run(mode="live", recorded_at=datetime.now(timezone.utc).isoformat(),
                                     models={"proposer": muse.settings.muse_model}, cost_usd=0.0),
        docs=docs, parts=[part], cards=cards, banners=banners,
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
