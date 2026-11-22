"""Passes: support(atom, spans) and attack(atom, spans). Each returns evidence, never a verdict.

The two passes are separate prompts with separate system prompts. The attack
pass never sees the support pass's output; it reads the same atom and the same
retrieved spans, blind. Each pass gets only the atom and the retrieved spans,
not the packet.

The model returns, per span: the span id, a one-line reading, and a verbatim
quote of the characters that bear on the atom. Code checks:
- a span id outside the input set is a hard failure: the pass fails, no repair;
- the quote must occur exactly once in the span (whitespace runs may differ, the
  characters may not). Then code builds the citation from the span's position,
  never from the model, and the one verifier checks it against the file.
A failed check gets one repair retry that carries the errors, then the pass fails.
"""

from __future__ import annotations

import re
from typing import Callable

from proofgraph.checker import Source, verify_citation
from proofgraph.model import ModelReply, complete_json
from proofgraph.schema import (
    Atom,
    Citation,
    Evidence,
    EvidenceProposal,
    Excerpt,
    Instrument,
    PassResult,
    RetrievalResult,
    Side,
    Span,
    TraceRecord,
)
from proofgraph.trace import Trace

Complete = Callable[..., ModelReply]

SUPPORT_SYSTEM = (
    "You read short passages from insurance documents and find the ones whose text, if true, makes a stated "
    "proposition true. You do not decide whether the proposition is true overall, and you do not do arithmetic. "
    "Return JSON only, matching the schema."
)
SUPPORT_TEMPLATE = """Proposition:
{atom}

Passages (id: text):
{spans}

List every passage whose text supports the proposition: it states the same value for the same thing, or
states the fact the proposition asserts. For each, give:
- span_id: the passage id, exactly as listed;
- reading: one line, what this passage says about the proposition;
- quote: the characters in the passage that bear on it, copied exactly (one line, no paraphrase).
If no passage supports it, return an empty list."""

ATTACK_SYSTEM = (
    "You read short passages from insurance documents and find the ones whose text would make a stated "
    "proposition false or doubtful. You do not decide whether the proposition is true overall, and you do not "
    "do arithmetic. Return JSON only, matching the schema."
)
ATTACK_TEMPLATE = """Proposition:
{atom}

Passages (id: text):
{spans}

List every passage whose text cuts against the proposition: a different value for the same thing, a
condition or exclusion that defeats it, a different period, or a statement that it does not apply.
For each, give:
- span_id: the passage id, exactly as listed;
- reading: one line, what this passage says against the proposition;
- quote: the characters in the passage that bear on it, copied exactly (one line, no paraphrase).
If no passage cuts against it, return an empty list."""

REPAIR = """{prompt}

Your previous answer failed validation:
{errors}
Return a corrected answer."""


def support(atom: Atom, retrieval: RetrievalResult, instruments: tuple[Instrument, ...], src: Source,
            trace: Trace, complete: Complete = complete_json) -> PassResult:
    return _run(Side.SUPPORT, SUPPORT_SYSTEM, SUPPORT_TEMPLATE, atom, retrieval, instruments, src, trace, complete)


def attack(atom: Atom, retrieval: RetrievalResult, instruments: tuple[Instrument, ...], src: Source,
           trace: Trace, complete: Complete = complete_json) -> PassResult:
    return _run(Side.ATTACK, ATTACK_SYSTEM, ATTACK_TEMPLATE, atom, retrieval, instruments, src, trace, complete)


def _run(side, system, template, atom, retrieval, instruments, src, trace, complete) -> PassResult:
    spans = {sp.span_id: sp for inst in instruments for sp in inst.spans}
    insts = {inst.doc_id: inst for inst in instruments}
    ids = [h.span_id for h in retrieval.hits]
    prompt = template.format(
        atom=describe(atom),
        spans="\n".join(f"[{i}] {' '.join(spans[i].text.split())}" for i in ids),
    )
    schema = _wire_schema(ids)
    rejects, errors, evidence = 0, [], []
    for attempt in range(2):
        text = prompt if attempt == 0 else REPAIR.format(prompt=prompt, errors="\n".join(f"- {e}" for e in errors))
        reply = complete(text, schema, system=system, template=template, effort="medium")
        proposal = EvidenceProposal.model_validate_json(reply.text)
        evidence, errors, hard = _check(side, proposal, set(ids), spans, insts, src)
        rejects += len(errors)
        trace.write(TraceRecord(
            stage=side.value, packet_id=None, atom_id=atom.atom_id,
            span_ids=tuple(e.span_id for e in evidence), model=reply.model, prompt_hash=reply.prompt_hash,
            input_tokens=reply.input_tokens, output_tokens=reply.output_tokens, latency_ms=reply.latency_ms,
            cache_hit=reply.cache_hit, verdict=None, rejects=tuple(errors), repairs=attempt,
            detail=f"proposed={len(proposal.evidence)} kept={len(evidence)}" + (" HARD FAILURE" if hard else ""),
        ))
        if hard:
            return PassResult(side=side, atom_id=atom.atom_id, evidence=(), failed=True, errors=tuple(errors),
                              rejects=rejects, repairs=attempt)
        if not errors:
            break
    failed = bool(errors)
    return PassResult(side=side, atom_id=atom.atom_id, evidence=() if failed else tuple(evidence), failed=failed,
                      errors=tuple(errors), rejects=rejects, repairs=attempt)


def describe(atom: Atom) -> str:
    """The atom as plain lines. Only the fields it has; nothing is filled in."""
    fields = [("predicate", atom.predicate), ("kind", atom.kind), ("subject", atom.subject), ("slot", atom.slot),
              ("value", atom.quantity_raw or atom.value), ("basis", atom.basis.value if atom.basis else None),
              ("period", atom.period), ("territory", atom.territory), ("conditions", atom.conditions)]
    lines = [f"{k}: {v}" for k, v in fields if v]
    if atom.negated:
        lines.append("negated: the proposition asserts the opposite")
    return "\n".join(lines)


def _wire_schema(ids: list[str]) -> dict:
    item = {
        "type": "object",
        "properties": {
            "span_id": {"type": "string", "enum": ids},
            "reading": {"type": "string"},
            "quote": {"type": "string"},
        },
        "required": ["span_id", "reading", "quote"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"evidence": {"type": "array", "items": item}},
            "required": ["evidence"], "additionalProperties": False}


def _check(side, proposal, allowed, spans, insts, src) -> tuple[list[Evidence], list[str], bool]:
    kept: list[Evidence] = []
    errors: list[str] = []
    for p in proposal.evidence:
        if p.span_id not in allowed:
            return [], [f"span {p.span_id} was not among the passages given"], True
        sp = spans[p.span_id]
        found = locate(p.quote, sp.text)
        if found is None:
            errors.append(f"span {p.span_id}: quote {p.quote!r} does not occur exactly once in the passage")
            continue
        start, end = found
        citation = _cite(sp, insts[sp.doc_id], start, end, src)
        broken = verify_citation(citation, src, within=insts[sp.doc_id])
        if broken:
            errors.append(f"span {p.span_id}: {broken}")
            continue
        kept.append(Evidence(side=side, span_id=sp.span_id, doc_id=sp.doc_id, reading=p.reading,
                             quote=Excerpt(start=start, end=end, text=sp.text[start:end]), citation=citation))
    return kept, errors, False


def locate(quote: str, text: str) -> tuple[int, int] | None:
    """Offsets of `quote` in `text` if it occurs exactly once. Runs of whitespace may differ; characters may not."""
    words = quote.split()
    if not words:
        return None
    pat = re.compile(r"\s+".join(re.escape(w) for w in words))
    hits = list(pat.finditer(text))
    return (hits[0].start(), hits[0].end()) if len(hits) == 1 else None


def _cite(sp: Span, inst: Instrument, start: int, end: int, src: Source) -> Citation:
    text = sp.text[start:end]
    if inst.file_start is not None:  # text source: exact offsets in the raw file
        shift = inst.file_start - inst.source_start
        locator = {"kind": "raw_offsets", "start": shift + sp.start + start, "end": shift + sp.start + end}
    else:  # PDF: page plus quote; the verifier requires it once on the page
        locator = {"kind": "page_quote", "page": sp.page}
        text = " ".join(text.split())
    return Citation.model_validate({"source_file": src.path.name, "sha256_of_file": src.sha256, "locator": locator, "text": text})
