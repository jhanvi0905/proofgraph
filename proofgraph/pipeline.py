"""Run one claim and one evidence packet through the existing engine.

Mapping from the shared request into the frozen Case (docs/03-architecture.md).
The engine never sees the extra request fields:

- claim.id -> Case.id
- claim.statement -> Case.claim
- claim.claimant_role -> ClaimRun.claimant_role only. Case has no role.
- claim.domain -> ClaimRun.domain only. Case has no domain.
- Case.dataset is the frozen eval-corpus tag. Route, ground, and combine
  do not read it. Every packet uses findver / passage so the literal
  validates. That tag is not chosen from the domain, and it is not a
  logistics or product-management rule.
- for_engine clears the sealed case fields before propose and run_program.
- evidence_packet.id / title -> ClaimRun only.
- items[].id -> Source.id
- items[].text -> Source.text (kind text). Blank text is dropped before
  propose and is not a source.
- items[].title, source, url, and locator stay on the request. They are
  not copied into Source, so they cannot change grounding.

expected_pattern, answer, and gold_evidence are answer keys. run_payload
does not read them.

Execution is propose once, then run_program (ground, route, combine) and
to_dot. The objection loop is not in this tree, so rounds stays 0. A
recorded offline_program is replayed through propose with a local transport.
This module does not construct a live Meta client and does not call an
external API.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofgraph.adapters.base import for_engine
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.engine.graph import to_dot
from proofgraph.engine.route import run_program
from proofgraph.propose import propose
from proofgraph.schema import Case, ClaimProgram, Fact, Link, Source, Verdict

# Frozen Case.dataset slot for a text passage. Not the caller's domain.
_PASSAGE_CORPUS = "findver"
_LINK_RELATION = {
    "pass": "supports",
    "fail": "contradicts",
    "blocked": "unresolved",
    "not_mentioned": "unresolved",
}
_ITEM_RANK = {"contradicts": 0, "unresolved": 1, "supports": 2}
ItemStatus = Literal["supports", "contradicts", "unresolved", "dropped"]
RelationName = Literal["supports", "contradicts", "unresolved"]
ProposerName = Literal["offline_program", "client"]


class LiveModelUnwired(RuntimeError):
    """The run has no local proposer reply and will not call a model API."""


class ClaimInput(BaseModel):
    id: str
    statement: str
    claimant_role: str
    domain: str


class EvidenceItem(BaseModel):
    id: str
    title: str
    source: str
    url: str
    locator: str
    text: str


class EvidencePacket(BaseModel):
    id: str
    title: str
    items: list[EvidenceItem]


class ItemDisposition(BaseModel):
    item_id: str
    status: ItemStatus
    reason: str


class Relation(BaseModel):
    """One engine link, named by the packet items whose facts it reads."""

    link_id: str
    item_ids: list[str]
    relation: RelationName
    link_status: Literal["pass", "fail", "blocked", "not_mentioned"]
    detail: str


class ClaimRun(BaseModel):
    claim_id: str
    statement: str
    claimant_role: str
    domain: str
    packet_id: str
    packet_title: str
    proposer: ProposerName
    verdict: Verdict
    items: list[ItemDisposition]
    relations: list[Relation]
    graph: str = Field(description="Graphviz DOT from the proof graph.")


def run_payload(payload: Mapping[str, Any]) -> ClaimRun:
    """Run the claim and packet stored on a fixture. Answer keys are not read."""

    claim = ClaimInput.model_validate(payload["claim"])
    packet = EvidencePacket.model_validate(payload["evidence_packet"])
    if "offline_program" not in payload:
        return run_claim(claim, packet)
    program = ClaimProgram.model_validate(payload["offline_program"])
    return run_claim(claim, packet, program=program)


def run_claim(
    claim: ClaimInput,
    packet: EvidencePacket,
    *,
    client: MuseClient | None = None,
    program: ClaimProgram | None = None,
) -> ClaimRun:
    """Map the request, propose once, and return the engine verdict."""

    if client is not None and program is not None:
        raise ValueError("pass a client or an offline program, not both")
    if client is None and program is None:
        raise LiveModelUnwired(
            "Live model execution is unwired. Pass a Muse client or an offline program."
        )
    case = for_engine(to_case(claim, packet))
    if program is not None:
        proposed = _propose_recorded(case, program)
        proposer: ProposerName = "offline_program"
    else:
        assert client is not None
        proposed = propose(case, client=client)
        proposer = "client"
    verdict = run_program(case, proposed)
    relations = _relations(packet, proposed, verdict)
    return ClaimRun(
        claim_id=claim.id,
        statement=claim.statement,
        claimant_role=claim.claimant_role,
        domain=claim.domain,
        packet_id=packet.id,
        packet_title=packet.title,
        proposer=proposer,
        verdict=verdict,
        items=_items(packet, proposed, verdict, relations),
        relations=relations,
        graph=to_dot(proposed, verdict),
    )


def to_case(claim: ClaimInput, packet: EvidencePacket) -> Case:
    """Adapt the request into a passage case. Blank items are omitted."""

    sources = [
        Source(id=item.id, kind="text", text=item.text)
        for item in packet.items
        if item.text.strip()
    ]
    return Case(
        id=claim.id,
        dataset=_PASSAGE_CORPUS,
        mode="passage",
        claim=claim.statement,
        sources=sources,
    )


def _propose_recorded(case: Case, program: ClaimProgram) -> ClaimProgram:
    """Send the recorded reply through propose. No network and no cache write."""

    with tempfile.TemporaryDirectory() as directory:
        settings = load_settings(
            {
                "MODEL_API_KEY": "offline",
                "CACHE_DIR": directory,
                "SPEND_LIMIT_USD": "0",
            }
        )
        client = MuseClient(settings, transport=_ReplayTransport(program))
        return propose(case, client=client, bypass_cache=True)


class _ReplayTransport:
    """One local proposer reply in the Responses envelope. Not an answer key."""

    def __init__(self, program: ClaimProgram) -> None:
        self._text = program.model_dump_json()

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        del body
        return {
            "id": "resp_offline",
            "object": "response",
            "status": "completed",
            "model": "offline-program",
            "output_text": self._text,
        }


def _relations(
    packet: EvidencePacket,
    program: ClaimProgram,
    verdict: Verdict,
) -> list[Relation]:
    known = {item.id for item in packet.items}
    by_result = {item.link_id: item for item in verdict.link_results}
    relations: list[Relation] = []
    for link in program.links:
        result = by_result[link.id]
        relations.append(
            Relation(
                link_id=link.id,
                item_ids=_link_items(link, program.facts, known),
                relation=_LINK_RELATION[result.status],
                link_status=result.status,
                detail=result.detail,
            )
        )
    return relations


def _link_items(link: Link, facts: list[Fact], known: set[str]) -> list[str]:
    by_id = {fact.id: fact for fact in facts}
    item_ids: list[str] = []
    for fact_id in link.inputs:
        fact = by_id.get(fact_id)
        if fact is None or fact.source_id not in known or fact.source_id in item_ids:
            continue
        item_ids.append(fact.source_id)
    return item_ids


def _items(
    packet: EvidencePacket,
    program: ClaimProgram,
    verdict: Verdict,
    relations: list[Relation],
) -> list[ItemDisposition]:
    facts_by_source: dict[str, list[Fact]] = {}
    for fact in program.facts:
        facts_by_source.setdefault(fact.source_id, []).append(fact)
    checks = {item.fact_id: item for item in verdict.fact_checks}
    dispositions: list[ItemDisposition] = []
    for item in packet.items:
        if not item.text.strip():
            dispositions.append(
                ItemDisposition(item_id=item.id, status="dropped", reason="empty text")
            )
            continue
        facts = facts_by_source.get(item.id, [])
        if not facts:
            dispositions.append(
                ItemDisposition(
                    item_id=item.id,
                    status="dropped",
                    reason="no proposed fact cites this item",
                )
            )
            continue
        related = [relation for relation in relations if item.id in relation.item_ids]
        if not related:
            check = checks.get(facts[0].id)
            reason = check.detail if check is not None and check.detail else "no link uses this item"
            dispositions.append(
                ItemDisposition(item_id=item.id, status="unresolved", reason=reason)
            )
            continue
        chosen = min(related, key=lambda relation: _ITEM_RANK[relation.relation])
        dispositions.append(
            ItemDisposition(
                item_id=item.id,
                status=chosen.relation,
                reason=chosen.detail or chosen.relation,
            )
        )
    return dispositions
