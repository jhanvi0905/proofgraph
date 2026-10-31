"""Part and overall status from accepted cards. Pure, no model, no network."""

from collections.abc import Iterable
from typing import Literal, get_args

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
    supporting = [c for c in cards if c.relation == "supports"]
    if any(_stands(c) for c in supporting):
        return "supported", False
    if supporting:  # every supporting card was disagreed with by the second check (D38)
        return "cannot_tell", False
    return ("not_found" if receipt_complete else "cannot_tell"), False


# D38 (provisional): a supporting card the blind second check disagreed with cannot, alone,
# make a part `supported`. To revert to "badge only", make this return True.
def _stands(card: Card) -> bool:
    return card.check != "disagrees"


def supports_reason(cards: Iterable[Card]) -> Literal["unconfirmed", "not_double_checked"] | None:
    """Why the viewer should qualify a part's support, or None when it needs no note.

    "unconfirmed": every supporting card was disagreed with (the part is cannot_tell).
    "not_double_checked": support stands but no supporting card was confirmed (agrees).
    """
    supporting = [c for c in cards if c.relation == "supports"]
    if not supporting or any(c.check == "agrees" for c in supporting):
        return None
    return "not_double_checked" if any(_stands(c) for c in supporting) else "unconfirmed"


def overall_status(parts: Iterable[PartStatus]) -> PartStatus:
    """Worst part status. Empty or unknown (including checking/error) raises ValueError."""
    parts = list(parts)
    if not parts:
        raise ValueError("no parts")
    for p in parts:
        if p not in WORST_FIRST:
            raise ValueError(f"cannot roll up part status {p!r}")
    return min(parts, key=WORST_FIRST.index)
