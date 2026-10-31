"""Gold normaliser: one `gold-1` schema for suite cases and our packs.

Final-plan section 1.7 and R-09. Only scripts (`scripts/eval_review.py`,
`scripts/report_review.py`) and tests may call `load_gold`; `review/run.py` must not.
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from proofgraph.review.models import Box, WeakenerType

GoldStatus = Literal["supported", "weakened", "contradicted", "not_found", "cannot_tell"]
GoldRelationName = Literal["supports", "contradicts", "weakens", "set_aside", "not_enough"]

# The eight packs in the final set and their split (final-plan section 1.3).
PACK_SPLIT: dict[str, Literal["dev", "held_out"]] = {
    "frt-03": "dev", "frt-07": "dev", "fin-08": "dev", "aipm-05": "dev",
    "frt-01": "held_out", "frt-05": "held_out", "fin-07": "held_out", "leg-02": "held_out",
}

_PART_STATUS = {
    "supported": "supported",
    "supported_with_qualifier": "weakened",
    "supported_with_scope_caveat": "weakened",
    "supported_headline_weakened": "weakened",
    "supported_weakly": "weakened",
    "conditional": "weakened",
    "weakened": "weakened",
    "contradicted": "contradicted",
    "not_found": "not_found",
    "cannot_tell": "cannot_tell",
    "conditional_not_met_in_packet": "cannot_tell",
}

_PACK_RELATION = {
    "supports": "supports",
    "contradicts": "contradicts",
    "weakens": "weakens",
    "conditions": "weakens",
    "irrelevant": "set_aside",
    "not_enough": "not_enough",
}

# Suite `expected_verdict` -> (part and overall status, conflict).
SUITE_VERDICT_MAP: dict[str, tuple[GoldStatus, bool]] = {
    "supported": ("supported", False),
    "contradicted": ("contradicted", False),
    "conflicting_evidence": ("contradicted", True),
    "insufficient_evidence": ("not_found", False),
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GoldReference(_Strict):
    verdict: str
    origin: Literal["curated", "external_label", "author"]


class GoldPart(_Strict):
    id: str
    text: str
    span: tuple[int, int] | None  # None when the part text paraphrases the claim
    status: GoldStatus
    conflict: bool = False
    origin: Literal["derived", "curated"]


class GoldRelation(_Strict):
    part: str
    relation: GoldRelationName
    weakener_type: WeakenerType | Literal["absence"] | None = None
    file: str | None = None
    page: int
    quote: str
    quote_pdf: str
    boxes: list[Box] | None = None
    box_origin: Literal["snapped", "authored", "none"]
    anchor_ref: str | None = None
    origin: Literal["external", "curated", "relabelled"]


class Gold(_Strict):
    version: Literal["gold-1"] = "gold-1"
    case: str
    pool: Literal["suite", "pack"]
    source_dataset: str
    split: Literal["dev", "held_out"]
    claim: str
    reference: GoldReference
    parts: list[GoldPart]
    relations: list[GoldRelation]
    unacceptable: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "Gold":
        ids = [p.id for p in self.parts]
        if len(set(ids)) != len(ids):
            raise ValueError("part ids must be unique")
        for rel in self.relations:
            if rel.part not in ids:
                raise ValueError(f"relation points at unknown part {rel.part!r}")
        for part in self.parts:
            if part.span is not None and self.claim[slice(*part.span)] != part.text:
                raise ValueError(f"part {part.id} span does not select its text in the claim")
            if not part.conflict:
                continue
            if part.status != "contradicted":
                raise ValueError(f"part {part.id}: conflict is only valid on a contradicted part")
            seen = {r.relation for r in self.relations if r.part == part.id}
            if not {"supports", "contradicts"} <= seen:
                raise ValueError(f"part {part.id}: conflict needs both supports and contradicts")
        return self


def map_part_status(raw: str) -> GoldStatus:
    try:
        return _PART_STATUS[raw]  # type: ignore[return-value]
    except KeyError:
        raise ValueError(f"unmapped part status {raw!r}") from None


def suite_verdict(verdict: str, *, judgment_missing: bool = False) -> tuple[GoldStatus, bool]:
    """Map a suite verdict; insufficient evidence is cannot_tell when a judgment is missing."""
    try:
        status, conflict = SUITE_VERDICT_MAP[verdict]
    except KeyError:
        raise ValueError(f"unmapped suite verdict {verdict!r}") from None
    if verdict == "insufficient_evidence" and judgment_missing:
        return "cannot_tell", conflict
    return status, conflict


def _quote_pdf(quote: str) -> str:
    return " ".join(quote.replace("|", " ").split())


def _derive_status(relations: list[dict]) -> GoldStatus:
    """Guideline rule: contradicts, else weakens, else supports, else absence or cannot tell."""
    kinds = {r["relation"] for r in relations}
    if "contradicts" in kinds:
        return "contradicted"
    if kinds & {"weakens", "conditions"}:
        return "weakened"
    if "supports" in kinds:
        return "supported"
    if any(r["weakener_type"] == "absence" for r in relations if r["relation"] == "not_enough"):
        return "not_found"
    return "cannot_tell"


def _pack_relation(raw: dict) -> dict:
    return {
        "part": raw["part"],
        "relation": _PACK_RELATION[raw["relation"]],
        "weakener_type": raw.get("weakener_type"),
        "file": raw.get("file"),
        "page": raw["page"],
        "quote": raw["quote"],
        "quote_pdf": _quote_pdf(raw["quote"]),
        "boxes": [[round(v) for v in raw["bbox"]]],
        "box_origin": "authored",
        "origin": "curated",
    }


def _normalise_pack(raw: dict) -> Gold:
    key = "-".join(raw["id"].split("-")[:2])
    if key not in PACK_SPLIT:
        raise ValueError(f"{raw['id']!r} is not one of the eight final-set packs")
    claim, gold = raw["claim"], raw["gold"]
    statuses = gold.get("part_status") or gold.get("part_verdicts") or {}
    parts = []
    for part in raw["parts"]:
        start = claim.find(part["text"])
        span = [start, start + len(part["text"])] if start >= 0 else None
        own = [r for r in gold["relations"] if r["part"] == part["id"]]
        raw_status = statuses.get(part["id"])
        parts.append({
            "id": part["id"], "text": part["text"], "span": span,
            "status": map_part_status(raw_status) if raw_status else _derive_status(own),
            "origin": "curated" if raw_status else "derived",
        })
    return Gold.model_validate({
        "case": key, "pool": "pack", "source_dataset": "ProofGraph synthetic packs",
        "split": PACK_SPLIT[key], "claim": claim,
        "reference": {"verdict": gold["overall"], "origin": "author"},
        "parts": parts, "relations": [_pack_relation(r) for r in gold["relations"]],
    })


def load_gold(path: Path) -> Gold:
    """Load gold for a case: a pack directory (normalised) or a `gold-1` JSON file (validated)."""
    path = Path(path)
    if path.is_dir():
        return _normalise_pack(json.loads((path / "pack.json").read_text()))
    return Gold.model_validate_json(path.read_text())
