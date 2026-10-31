"""Part and overall status from accepted cards. Pure, no model, no network."""

from collections.abc import Iterable
from typing import get_args

from proofgraph.review.models import BoxStatus, Card, PartStatus, Relation

# Worst first (docs/council/reports/product-2.md, verdict banner order).
WORST_FIRST: tuple[PartStatus, ...] = (
    "contradicted", "weakened", "cannot_tell", "not_found", "supported",
)

# Only a box the PDF text proves can turn a part red; approximate and unpinned cannot.
_RED_BOXES = {"pinned", "located"}


def part_status(cards: Iterable[Card], *, receipt_complete: bool) -> tuple[PartStatus, bool]:
    """Return (status, conflict) for one part. Unknown input raises ValueError."""
    if not isinstance(receipt_complete, bool):
        raise ValueError("receipt_complete must be a bool")
    cards = list(cards)
    for c in cards:
        if not isinstance(c, Card):
            raise ValueError(f"expected Card, got {type(c).__name__}")
        if c.relation not in get_args(Relation):
            raise ValueError(f"unknown relation {c.relation!r}")
        if c.box_status not in get_args(BoxStatus):
            raise ValueError(f"unknown box status {c.box_status!r}")

    def has(relation: str, boxes: set[str]) -> bool:
        return any(c.relation == relation and c.box_status in boxes for c in cards)

    if has("contradicts", _RED_BOXES):
        return "contradicted", has("contradicts", {"pinned"}) and has("supports", {"pinned"})
    if has("weakens", set(get_args(BoxStatus))):
        return "weakened", False
    if has("supports", set(get_args(BoxStatus))):
        return "supported", False
    return ("not_found" if receipt_complete else "cannot_tell"), False


def overall_status(parts: Iterable[PartStatus]) -> PartStatus:
    """Worst part status. Empty or unknown (including checking/error) raises ValueError."""
    parts = list(parts)
    if not parts:
        raise ValueError("no parts")
    for p in parts:
        if p not in WORST_FIRST:
            raise ValueError(f"cannot roll up part status {p!r}")
    return min(parts, key=WORST_FIRST.index)
