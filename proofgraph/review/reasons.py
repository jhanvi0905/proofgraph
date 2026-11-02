"""Fixed wording for what the blind second check did on a disagreed card. Pure, no model.

Every line describes the second check's reading, never whether the claim or quote holds.
"""

_SEES = "It sees only the quote and the part."
_LABEL = {"supports": "as support", "contradicts": "as contradicting", "weakens": "as weakening"}
_SAW = {
    "entails": "found it supports this part",
    "contradicts": "found it goes against this part",
    "not_mentioned": "found it does not mention this part",
}

REASONS: dict[tuple[str, str], str] = {
    (relation, answer): (
        f"The second check read this quote on its own and {saw}, "
        f"while this card is labelled {label}. {_SEES}"
    )
    for relation, label in _LABEL.items()
    for answer, saw in _SAW.items()
}

FALLBACK = f"The second check disagreed with this card, and its reading is not available here. {_SEES}"


def check_reason(relation: str, check: str, check_answer: str | None) -> str | None:
    """Reason line for a disagreed card; None for any other check. Never raises."""
    if check != "disagrees":
        return None
    return REASONS.get((relation, check_answer), FALLBACK)
