"""Blind card check. A model that did not write the card re-reads it.

The checker sees two strings: the card's quote and the claim part's text. It never
sees the relation, the reason, the page, the document or any other card. Its answer
is a witness, recorded on the card as ``check``. It never hides a card and never
changes a part status; status stays pure code (``status.py``).

Adjudication, C17 (docs/council/2026-10-31-roadmap-sprint.md): ``supports`` agrees
on ``entails``; ``contradicts`` agrees on ``contradicts``; ``weakens`` is consistent
on anything but ``entails`` (so ``contradicts`` and ``not_mentioned`` agree).
Any other pairing disagrees. A checker error, a timeout or an unknown answer is
``unavailable``. A ``set_aside`` card or a card without a quote is ``not_run``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

from proofgraph.clients.checker import blind_wording
from proofgraph.review.models import Card, CheckName, Part

MAX_WORKERS = 4

Checker = Callable[[str, str], str]

_AGREES: dict[str, frozenset[str]] = {
    "supports": frozenset({"entails"}),
    "contradicts": frozenset({"contradicts"}),
    "weakens": frozenset({"contradicts", "not_mentioned"}),
}
_ANSWERS = frozenset({"entails", "contradicts", "not_mentioned"})


def check_card(
    card_quote: str,
    part_text: str,
    *,
    relation: str,
    checker: Checker = blind_wording,
) -> CheckName:
    """Check one card. The checker gets exactly (card_quote, part_text).

    ``relation`` is used only after the checker answers, to compare.
    """
    if relation not in _AGREES:
        return "not_run"
    if not isinstance(card_quote, str) or card_quote.strip() == "":
        return "not_run"
    try:
        answer = checker(card_quote, part_text)
    except Exception:
        return "unavailable"
    if answer not in _ANSWERS:
        return "unavailable"
    return "agrees" if answer in _AGREES[relation] else "disagrees"


def check_cards(
    cards: Iterable[Card],
    parts: Iterable[Part],
    *,
    checker: Checker = blind_wording,
) -> list[Card]:
    """Return copies of ``cards`` with ``check`` set, in input order.

    Runs at most MAX_WORKERS checks at once. One failure never stops the others.
    """
    cards = list(cards)
    texts = {p.id: p.text for p in parts}

    def run(card: Card) -> CheckName:
        text = texts.get(card.part)
        if card.relation == "set_aside":
            return "not_run"
        if text is None:
            return "unavailable"
        return check_card(card.quote, text, relation=card.relation, checker=checker)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        names = list(pool.map(run, cards))
    return [c.model_copy(update={"check": n}) for c, n in zip(cards, names)]
