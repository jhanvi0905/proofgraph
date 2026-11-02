"""Plain-words phrase for each weakener type. Pure, fixed, no model.

No digits, no percent, no "confidence": it names the kind of qualification, never how sure we are.
"""

QUALIFIER_PHRASE: dict[str, str] = {
    "exception": "An exception applies",
    "condition": "Depends on a condition",
    "qualifier": "Adds a qualifier",
    "scope": "Covers only part of what is claimed",
    "time": "Only true for a time period",
    "magnitude": "The amount or size differs",
    "definition": "A defined term changes the meaning",
    "weak_source": "Comes from a weaker source",
}


def qualifier_phrase(weakener_type: str | None) -> str | None:
    """The phrase for a weakener type; None when the type is absent or unknown."""
    return QUALIFIER_PHRASE.get(weakener_type) if weakener_type else None
