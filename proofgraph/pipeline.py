"""ProofGraph: decide whether a packet of versioned insurance documents supports one atomic claim.

A packet is a set of instruments: a policy form, its endorsements, binders, schedules. The
claim, written by a person, states a value for one slot, such as a special limit or a
retention. The answer is one of four: supported, contradicted, unresolved or not found. It
names the governing instrument and the precedence rule that made it govern, and it cites the
exact characters every value came from. Versioning and precedence are the problem. Two
documents disagreeing is the hard case, and no winner is picked without a rule. The model
reads and points; code admits text, compares numbers, applies precedence and checks every
citation.

run_packet is the whole pipeline, one stage per line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from proofgraph.arbiter import arbitrate, arbitrate_wording
from proofgraph.assertions import assert_from_evidence, clause_from_evidence
from proofgraph.atomize import atomize
from proofgraph.checker import open_source, verify_citation
from proofgraph.ingest import ingest
from proofgraph.model import embed
from proofgraph.passes import attack, support
from proofgraph.retrieve import admit, retrieve
from proofgraph.schema import (
    Assertion,
    Claim,
    Clause,
    DocumentMapping,
    DocumentMappingFile,
    Evidence,
    InvalidAssertion,
    SlotVerdict,
    SourceManifest,
    TraceRecord,
    load_predicate_set,
)
from proofgraph.trace import Trace


@dataclass
class PacketRun:
    claim: Claim
    atom_text: str | None
    documents: list[tuple[str, int]] = field(default_factory=list)  # (doc_id, passages admitted)
    evidence: list[Evidence] = field(default_factory=list)
    assertions: list[Assertion] = field(default_factory=list)
    invalid: list[InvalidAssertion] = field(default_factory=list)
    clauses: list[Clause] = field(default_factory=list)  # wording claims (D9)
    instruments: dict = field(default_factory=dict)  # doc_id -> admitted Instrument (D13: a figure picked at confirmation)
    verdict: SlotVerdict | None = None
    failure: str | None = None


class AmendsCitationBroken(RuntimeError):
    pass


def verified_amends(mappings: DocumentMappingFile, doc_ids: list[str], raw: Path) -> tuple[DocumentMapping, ...]:
    """The packet's document mappings, each amends citation checked by the one verifier (D9).

    A broken amends citation stops the run: a missing-document check resting on a citation that
    does not hold would pass silently, and that is the drop D6 forbids.
    """
    out = []
    for m in mappings.documents:
        if m.doc_id not in doc_ids:
            continue
        if m.amends is not None:
            broken = verify_citation(m.amends.citation, open_source(raw / m.amends.citation.source_file))
            if broken:
                raise AmendsCitationBroken(f"{m.doc_id}: amends citation: {broken}")
        out.append(m)
    return tuple(out)


def gather(packet_id: str, claim: Claim, doc_ids: list[str], mappings: DocumentMappingFile,
           data: Path, trace: Trace) -> tuple[PacketRun, tuple[DocumentMapping, ...]]:
    """Everything before the decision: admission, atomize, retrieval, the for and against reads, and
    every quote verified and turned into an assertion (amount) or clause (wording) on `claim.slot`.
    No verdict. D11 runs this under a run-local key, then re-keys the lines a person confirms."""
    manifest = SourceManifest.model_validate_json((data / "instruments.json").read_text(encoding="utf-8"))
    policy = claim.slot.split(".", 1)[0]
    run = PacketRun(claim=claim, atom_text=None)
    checked = verified_amends(mappings, doc_ids, data / "raw")  # before any model call

    atoms = atomize(claim, load_predicate_set(data / "predicates.json"), trace)
    if not atoms.atoms:
        run.failure = f"the claim could not be split into atoms: {[e.code.value for e in atoms.errors]}"
        return run, checked
    atom = atoms.atoms[0]
    run.atom_text = atom.subject

    for label in (s for s in manifest.sources if any(i.doc_id in doc_ids for i in s.instruments)):
        ingested = ingest(label, data / "raw")
        src = open_source(data / "raw" / label.file)
        mine = tuple(i for i in ingested.instruments if i.doc_id in doc_ids)
        admitted, routes = admit(mine, mappings, policy, src, trace, ingested.source.extractor)
        run.documents += [(i.doc_id, len(i.spans)) for i in admitted]
        if not admitted:
            continue
        hits = retrieve(atom, admitted, trace, embed=embed)
        by_doc = {i.doc_id: i for i in admitted}
        run.instruments.update(by_doc)
        for side in (support, attack):
            for ev in side(atom, hits, admitted, routes, src, trace).evidence:
                run.evidence.append(ev)
                if claim.kind == "wording":
                    run.clauses.append(clause_from_evidence(ev, by_doc[ev.doc_id], trace))
                    continue
                a = assert_from_evidence(ev, by_doc[ev.doc_id], claim.slot, trace)
                (run.assertions if isinstance(a, Assertion) else run.invalid).append(a)
    return run, checked


def run_packet(packet_id: str, claim: Claim, doc_ids: list[str], mappings: DocumentMappingFile,
               data: Path, trace: Trace, policies: tuple[str, ...] | None = None) -> PacketRun:
    """`policies`: the question's policy set (D9); None means the slot key's first segment."""
    run, checked = gather(packet_id, claim, doc_ids, mappings, data, trace)
    if run.failure:
        return run
    if claim.kind == "wording":
        run.verdict = arbitrate_wording(claim, tuple(run.clauses), tuple(doc_ids), checked, policies)
    else:
        run.verdict = arbitrate(claim, tuple(run.assertions), tuple(doc_ids), checked, policies)
    trace.write(TraceRecord(stage="arbiter", packet_id=packet_id, atom_id=claim.slot, span_ids=(), model=None,
                            prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
                            verdict=run.verdict.verdict, rejects=(), repairs=0, detail=run.verdict.to_json()))
    return run
