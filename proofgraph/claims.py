"""Claims: load the author's claims and resolve each slot against the registry, before anything else runs.

resolve() returns the key or raises UnknownSlot. It has no aliases, no fuzzy
match and no default: a slot that is not in data/slots.json exactly is an
error at load time, before any model call, comparison or trace line.

A claim declares its kind and, for an amount, its value (D9). Neither is inferred: an
amount claim whose declared value the number rules cannot read is an error at load time.
"""

from __future__ import annotations

from pathlib import Path

from proofgraph.numbers import claim_amount_text, parse_amount
from proofgraph.schema import Claim, ClaimFile, ParseFailure, SlotRegistry


class UnknownSlot(ValueError):
    def __init__(self, candidate: str, known: list[str]):
        super().__init__(f"unknown slot {candidate!r}; known: {known}")
        self.candidate, self.known = candidate, known


def resolve(candidate: str, registry: SlotRegistry) -> str:
    known = sorted(e.key for e in registry.slots)
    if candidate not in known:
        raise UnknownSlot(candidate, known)
    return candidate


def load_claims(claims_path: Path, slots_path: Path) -> tuple[Claim, ...]:
    registry = SlotRegistry.model_validate_json(slots_path.read_text(encoding="utf-8"))
    claims = ClaimFile.model_validate_json(claims_path.read_text(encoding="utf-8")).claims
    for c in claims:
        if c.slot is not None:
            resolve(c.slot, registry)
        if c.value is not None and isinstance(parse_amount(claim_amount_text(c.value)), ParseFailure):
            raise ValueError(f"{c.claim_id}: declared value {c.value!r} is not an amount the number rules can read")
    return claims


def question_policies(slot: str, slots_path: Path) -> tuple[str, ...]:
    """The question's policy set (D9): the registry entry's `policies`, else the slot key's first segment."""
    registry = SlotRegistry.model_validate_json(slots_path.read_text(encoding="utf-8"))
    entry = next(e for e in registry.slots if e.key == resolve(slot, registry))
    return entry.policies or (slot.split(".", 1)[0],)
