"""Display-only disclosure of what the word search looked at (flag PROOFGRAPH_EVIDENCE_LINES=1).

Nothing here reaches a status, a card or a model call. The code groups the absence sweep's hits
into passages and keeps them on the part's receipt so the viewer can list them.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from proofgraph.review.absence import CONTEXT_CHARS, AbsencePage, AbsenceReceipt, SweepHit
from proofgraph.review.models import Passage, Receipt

SNIPPET_CHARS = 200
ONLY_ONE_LISTED = "Only one passage listed"


def evidence_lines_on() -> bool:
    return os.environ.get("PROOFGRAPH_EVIDENCE_LINES") == "1"


def snippet(text: str, limit: int = SNIPPET_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _passages(hits: Sequence[SweepHit], texts: dict[tuple[str, int], str]) -> list[tuple[Passage, bool]]:
    """Hits on one page that sit close together are one passage. (passage, every hit in it cited)."""
    out: list[tuple[Passage, bool]] = []
    ordered = sorted(hits, key=lambda h: (h.doc, h.page, h.offset, h.term))
    i = 0
    while i < len(ordered):
        j = i
        while (j + 1 < len(ordered) and (ordered[j + 1].doc, ordered[j + 1].page) == (ordered[i].doc, ordered[i].page)
               and ordered[j + 1].offset - ordered[j].offset <= 2 * CONTEXT_CHARS):
            j += 1
        group = ordered[i:j + 1]
        text = texts.get((group[0].doc, group[0].page)) or ""
        body = text[max(0, group[0].offset - CONTEXT_CHARS): group[-1].offset + CONTEXT_CHARS] or group[0].context
        out.append((Passage(doc=group[0].doc, page=group[0].page, text=snippet(body)), all(h.cited for h in group)))
        i = j + 1
    return out


def receipt_with_evidence(receipt: Receipt, absence: AbsenceReceipt, pages: Sequence[AbsencePage]) -> Receipt:
    texts = {(p.doc, p.page): p.text for p in pages if p.text}
    found = _passages([h for hs in absence.hits.values() for h in hs], texts)
    return receipt.model_copy(update={
        "matched_passages": len(found),
        "matched_docs": len({p.doc for p, _ in found}),
        "uncited_passages": [p for p, cited in found if not cited],
        "unsearched": [Passage(doc=d, page=n) for d, n in absence.unread],
    })
