"""Atomise: one claim -> atoms in the closed predicate set. The model proposes; code validates.

Validation is a pure function over each proposed atom. It returns typed errors,
not a bool. A failed attempt gets exactly one repair retry that carries the
errors, and then atomisation fails. A claim that fits no predicate is a
first-class outcome (NO_PREDICATE_FITS). It is never forced into the nearest
predicate.
"""

from __future__ import annotations

import re
from typing import Callable

from proofgraph.model import ModelReply, complete_json
from proofgraph.numbers import parse_amount
from proofgraph.schema import (
    Amount,
    Atom,
    AtomError,
    AtomErrorCode,
    AtomizeResult,
    AtomProposal,
    Basis,
    Claim,
    ParseFailure,
    PredicateSet,
    ProposedAtom,
    TraceRecord,
)
from proofgraph.trace import Trace

Complete = Callable[..., ModelReply]

SYSTEM = (
    "You split a claim about insurance documents into atomic propositions. "
    "You do not judge whether the claim is true and you do not do arithmetic. "
    "Return JSON only, matching the schema."
)

# The worked examples are deliberately outside insurance (an invoice), so they teach the
# output format without teaching the vocabulary of either document family, the holdout included.
TEMPLATE = """Split the claim into atoms. An atom is the smallest unit that can be independently true or false.

Predicates (closed set; use exactly one per atom):
{predicates}

Slots on an atom:
- subject: what the atom is about, with every reference resolved (no "it", "the policy").
- slot: required for `states`. A dotted path <identifier>.<part>.<measure>: the identifier as written (upper case),
  then lower snake case, e.g. INV-2291.freight.unit_price for "the unit price of freight on invoice INV-2291".
  The first segment is what the value belongs to, not the document that might state it.
- quantity_raw: the amount exactly as written in the claim, with its currency if the claim writes one (e.g. "EUR 4,200"). Never compute.
- value: a non-numeric value, if any.
- period, territory, conditions: as written, or null.
- basis: one of {bases}, or null if the claim does not say.
- kind: only for predicates that list kinds; otherwise null.
- negated: true if the claim asserts the opposite.

Rules: one fact per atom; no "and" inside a value; leave a slot null rather than guess.
If no predicate fits, return no atoms and say why in no_fit_reason.

Claim: {claim}"""

REPAIR = """{prompt}

Your previous answer failed validation:
{errors}
Return a corrected answer."""

_NULLABLE_STR = {"anyOf": [{"type": "string"}, {"type": "null"}]}
_SLOT_RE = re.compile(r"^[A-Z0-9][A-Z0-9/ -]*[A-Z0-9](\.[a-z][a-z0-9_]*){2}$")
_PRONOUN_RE = re.compile(r"^\s*(it|this|that|they|the policy|this policy|that policy|the document)\s*$", re.I)
_CONJ_RE = re.compile(r"\b(and|&)\b", re.I)
_FIELDS = list(ProposedAtom.model_fields)  # every slot required: filled or explicitly null


def atomize(claim: Claim, predicates: PredicateSet, trace: Trace, complete: Complete = complete_json) -> AtomizeResult:
    prompt = TEMPLATE.format(
        predicates="\n".join(
            f"- {p.name}: {p.meaning}" + (f" kinds: {', '.join(p.kinds)}" if p.kinds else "") for p in predicates.predicates
        ),
        bases=", ".join(b.value for b in Basis),
        claim=claim.text,
    )
    schema = _wire_schema(predicates)
    rejects = 0
    errors: list[AtomError] = []
    atoms: list[Atom] = []
    for attempt in range(2):
        text = prompt if attempt == 0 else REPAIR.format(prompt=prompt, errors="\n".join(f"- {e.code.value} ({e.field}): {e.detail}" for e in errors))
        reply = complete(text, schema, system=SYSTEM, template=TEMPLATE)
        atoms, errors = _parse(claim, reply.text, predicates)
        rejects += len(errors)
        trace.write(TraceRecord(
            stage="atomize", packet_id=None, atom_id=None, span_ids=(), model=reply.model,
            prompt_hash=reply.prompt_hash, input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
            latency_ms=reply.latency_ms, cache_hit=reply.cache_hit, verdict=None,
            rejects=tuple(e.code.value for e in errors), repairs=attempt,
            detail=f"claim={claim.claim_id} atoms={len(atoms)}",
        ))
        no_fit = any(e.code is AtomErrorCode.NO_PREDICATE_FITS for e in errors)
        if not errors or no_fit:
            break
    return AtomizeResult(
        claim_id=claim.claim_id,
        atoms=tuple(atoms) if not errors else (),
        errors=tuple(errors),
        rejects=rejects,
        repairs=attempt,
    )


def _wire_schema(predicates: PredicateSet) -> dict:
    atom = {
        "type": "object",
        "properties": {
            "predicate": {"type": "string", "enum": [p.name for p in predicates.predicates]},
            "kind": _NULLABLE_STR,
            "negated": {"type": "boolean"},
            "subject": _NULLABLE_STR,
            "slot": _NULLABLE_STR,
            "quantity_raw": _NULLABLE_STR,
            "value": _NULLABLE_STR,
            "period": _NULLABLE_STR,
            "territory": _NULLABLE_STR,
            "basis": {"anyOf": [{"type": "string", "enum": [b.value for b in Basis]}, {"type": "null"}]},
            "conditions": _NULLABLE_STR,
        },
        "required": _FIELDS,
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"atoms": {"type": "array", "items": atom}, "no_fit_reason": _NULLABLE_STR},
        "required": ["atoms", "no_fit_reason"],
        "additionalProperties": False,
    }


def _parse(claim: Claim, text: str, predicates: PredicateSet) -> tuple[list[Atom], list[AtomError]]:
    proposal = AtomProposal.model_validate_json(text)
    wires = proposal.atoms
    if not wires:
        reason = proposal.no_fit_reason or "model returned no atoms"
        return [], [AtomError(code=AtomErrorCode.NO_PREDICATE_FITS, field=None, detail=reason)]
    atoms: list[Atom] = []
    errors: list[AtomError] = []
    for i, w in enumerate(wires):
        errs, amount = validate_atom_fields(w, predicates)
        errors += errs
        if not errs:
            atoms.append(Atom(atom_id=f"{claim.claim_id}.a{i}", quantity=amount, **w.model_dump()))
    return atoms, errors


def validate_atom_fields(w: ProposedAtom, predicates: PredicateSet) -> tuple[list[AtomError], Amount | None]:
    """Pure validation of one proposed atom. Exposed for tests; not a pipeline stage."""
    errs: list[AtomError] = []

    def err(code: AtomErrorCode, field: str | None, detail: str) -> None:
        errs.append(AtomError(code=code, field=field, detail=detail))

    spec = predicates.get(w.predicate)
    if spec is None:
        err(AtomErrorCode.UNKNOWN_PREDICATE, "predicate", f"{w.predicate!r} is not in the predicate set")
        return errs, None
    if spec.kinds and w.kind not in spec.kinds:
        err(AtomErrorCode.BAD_KIND, "kind", f"{spec.name} needs kind in {list(spec.kinds)}, got {w.kind!r}")
    if not spec.kinds and w.kind is not None:
        err(AtomErrorCode.BAD_KIND, "kind", f"{spec.name} takes no kind")
    for f in ("subject", "value"):
        v = getattr(w, f)
        if v and _PRONOUN_RE.match(v):
            err(AtomErrorCode.UNRESOLVED_REF, f, f"{v!r} is an unresolved reference")
    for f in ("value", "quantity_raw"):
        v = getattr(w, f)
        if v and _CONJ_RE.search(v):
            err(AtomErrorCode.CONJUNCTION_IN_VALUE, f, f"{v!r} holds more than one value")

    amount: Amount | None = None
    if spec.name == "states":
        slot = w.slot
        if not slot:
            err(AtomErrorCode.MISSING_SLOT, "slot", "states needs a slot")
        elif not _SLOT_RE.match(slot):
            err(AtomErrorCode.BAD_SLOT, "slot", f"{slot!r} is not <POLICY>.<part>.<measure>")
        if not w.quantity_raw and not w.value:
            err(AtomErrorCode.MISSING_SLOT, "quantity_raw", "states needs a quantity or a value")
    if w.quantity_raw and not any(e.field == "quantity_raw" for e in errs):
        parsed = parse_amount(w.quantity_raw)
        if isinstance(parsed, ParseFailure):
            err(AtomErrorCode.UNPARSEABLE_QUANTITY, "quantity_raw", f"{parsed.raw!r}: {parsed.reason}")
        elif parsed.currency is None:  # pre-D1 rule for claims; revisited in the atomize cleanup
            err(AtomErrorCode.MISSING_UNIT, "quantity_raw", f"{w.quantity_raw!r}: missing_unit")
        else:
            amount = parsed
    return errs, amount
