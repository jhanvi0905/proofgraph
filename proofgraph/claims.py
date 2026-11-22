"""Claims: load the author's claims and resolve each slot against the registry, before anything else runs.

resolve() returns the key or raises UnknownSlot. It has no aliases, no fuzzy
match and no default: a slot that is not in data/slots.json exactly is an
error at load time, before any model call, comparison or trace line.
"""

from __future__ import annotations

from pathlib import Path

from proofgraph.schema import Claim, ClaimFile, SlotRegistry


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
    return claims
