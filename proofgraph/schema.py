"""Typed objects passed between pipeline stages.

Every model is strict, frozen, and rejects extra fields. If a function needs a
dict argument, this file is unfinished.

The four verdicts and their reason codes are enums here because they define the
problem. The predicate set is NOT an enum: it lives in data/predicates.json and
atoms are validated against it, so adding a predicate is a data change with a
version bump, not a code change.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "2.0.0"


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    def to_json(self) -> str:
        """Stable, key-sorted JSON so eval outputs diff cleanly between runs."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------- answers


class Verdict(str, Enum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    DOCUMENTS_DISAGREE = "documents_disagree"
    NOT_FOUND = "not_found"


class NotFoundReason(str, Enum):
    # No instrument of the type the atom needs is in the packet. Mechanically
    # checkable from the packet's instrument list.
    GOVERNING_INSTRUMENT_ABSENT = "governing_instrument_absent"
    # The right instruments are present but no span addresses the atom.
    NO_ADDRESSING_SPAN = "no_addressing_span"


class RuleName(str, Enum):
    # Order here is documentation only; the arbiter states its own order.
    # The two precedence rules pick a governing document.
    ENDORSEMENT_OVER_BASE = "endorsement_over_base"
    LATER_EFFECTIVE_DATE = "later_effective_date"
    # Not a precedence rule: it names a conflict that neither rule above resolves.
    # It is the only way documents_disagree can be produced.
    UNRESOLVED_CONFLICT = "unresolved_conflict"


# ---------------------------------------------------------------- documents


class InstrumentType(str, Enum):
    POLICY_FORM = "policy_form"
    DECLARATIONS = "declarations"
    ENDORSEMENT = "endorsement"
    BINDER = "binder"
    COVER_NOTE = "cover_note"
    CORRESPONDENCE = "correspondence"


class BBox(_Model):
    x0: float
    top: float
    x1: float
    bottom: float


def span_id_for(doc_id: str, version: str, text: str, start: int, end: int) -> str:
    """sha256 of (doc_id, version, normalised text, start, end), first 16 hex chars."""
    normalised = " ".join(text.split()).lower()
    payload = "\x1f".join([doc_id, version, normalised, str(start), str(end)])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class Span(_Model):
    """A contiguous slice of a source text. Offsets index the source, not the doc."""

    span_id: str
    doc_id: str
    version: str
    page: int = Field(ge=1)
    start: int = Field(ge=0)
    end: int
    text: str
    section_path: tuple[str, ...]
    bbox: BBox | None = None

    @model_validator(mode="after")
    def _check(self) -> Span:
        if self.end <= self.start:
            raise ValueError(f"span end {self.end} <= start {self.start}")
        if len(self.text) != self.end - self.start:
            raise ValueError("span text length does not match offsets")
        expected = span_id_for(self.doc_id, self.version, self.text, self.start, self.end)
        if self.span_id != expected:
            raise ValueError("span_id does not match its content")
        return self


class Definition(_Model):
    term: str  # lower-cased defined term, without quotes
    span_id: str


class SourceText(_Model):
    """The exact text every offset refers to, plus how it was produced."""

    source_id: str
    sha256_of_file: str
    extractor: str  # e.g. "edgar_sgml/EX-10.(E)/4" or "pdf_columns/v1"
    text: str
    page_starts: tuple[int, ...]  # offset where page i+1 begins
    file_offset: int | None  # where text[0] sits in the raw file; None when text is rebuilt (PDF)


# ---------------------------------------------------------------- citations


class CitationLayer(str, Enum):
    # Offsets index the raw file, decoded as ASCII (bytes == chars). They are
    # compared exactly, with no whitespace tolerance. The splitter and the
    # extractor never touch this layer.
    RAW_FILE = "raw_file"
    # PDFs have no raw text layer. Offsets index the text rebuilt by the named
    # extractor version, and a new extractor version breaks these citations on purpose.
    PDF_COLUMNS_V1 = "pdf_columns/v1"


class Citation(_Model):
    """Where a value is written: file hash, offsets into one named text layer, and the expected text.

    It does not depend on the clause splitter. Checked at load:
    - hash mismatch: fatal (the file is not the file);
    - text mismatch: the citation is broken, and the assertion is invalid and
      left out of comparison.
    """

    source_file: str
    sha256_of_file: str
    layer: CitationLayer
    start: int = Field(ge=0)
    end: int
    text: str

    @model_validator(mode="after")
    def _check(self) -> Citation:
        if len(self.text) != self.end - self.start:
            raise ValueError("citation text length does not match offsets")
        return self


class MappingMethod(str, Enum):
    CELL_POSITION = "cell_position"  # nth part of a composite cell, split by code
    POLICY_NUMBER = "policy_number"  # a written number normalised to the policy id used in slots
    LABEL = "label"  # the span names the slot part in its own words
    CROSS_REFERENCE = "cross_reference"  # identified through another document's span
    JUDGMENT = "judgment"  # rests on reasoning or wording not in the packet; `reasoning` says what


class RouteStrength(str, Enum):
    """How a route is supported. A reviewer reads this per assertion, not only in the record."""

    READ = "read"  # the cited span says it in its own words
    DERIVED = "derived"  # a mechanical step over spans in the packet (cell position, number normalisation)
    JUDGMENT = "judgment"  # an identification or meaning the packet does not state


class MappingRecord(_Model):
    """One route by which a cited text reaches part of a slot (D2). Hand-labelled, one per route."""

    mapping_id: str
    method: MappingMethod
    instrument_doc_id: str  # the instrument whose text `cited` lies in
    cited: Citation
    position: int | None = Field(default=None, ge=1)  # CELL_POSITION only, 1-based
    produces: str  # the slot part this route yields
    strength: RouteStrength
    reasoning: str | None  # required when strength is judgment: the argument, written out
    justified_by: tuple[Citation, ...]
    note: str

    @model_validator(mode="after")
    def _check(self) -> MappingRecord:
        if self.strength is RouteStrength.JUDGMENT and not self.reasoning:
            raise ValueError(f"{self.mapping_id}: a judgment route must write out its reasoning")
        if self.method is MappingMethod.JUDGMENT and self.strength is not RouteStrength.JUDGMENT:
            raise ValueError(f"{self.mapping_id}: method judgment must have strength judgment")
        if self.method is MappingMethod.LABEL and self.strength is not RouteStrength.READ and not self.reasoning:
            raise ValueError(f"{self.mapping_id}: a label route weaker than read must say why")
        return self


class AssertionInput(_Model):
    """One citation the assertion rests on, plus the routes that take it to a slot."""

    assertion_id: str
    instrument_doc_id: str
    citation: Citation
    route_ids: tuple[str, ...]  # one route to the policy part, one to part.measure


class MappingFile(_Model):
    note: str
    records: tuple[MappingRecord, ...]
    assertions: tuple[AssertionInput, ...]


class Instrument(_Model):
    """One document in a packet: an endorsement, a binder, a policy form."""

    doc_id: str
    version: str
    instrument_type: InstrumentType
    issuer: str
    policy_numbers: tuple[str, ...]
    effective_date: dt.date | None
    source_id: str
    source_start: int = Field(ge=0)
    source_end: int
    spans: tuple[Span, ...]
    definitions: tuple[Definition, ...]


class Extractor(str, Enum):
    EDGAR_SGML = "edgar_sgml"
    PDF_COLUMNS = "pdf_columns"


class InstrumentLabel(_Model):
    doc_id: str
    version: str
    instrument_type: InstrumentType
    issuer: str
    policy_numbers: tuple[str, ...]
    effective_date: dt.date | None
    first_page: int = Field(ge=1)
    last_page: int = Field(ge=1)


class SourceLabel(_Model):
    source_id: str
    file: str
    sha256_of_file: str
    extractor: Extractor
    edgar_type: str | None
    edgar_sequence: int | None
    instruments: tuple[InstrumentLabel, ...]


class SourceManifest(_Model):
    note: str
    sources: tuple[SourceLabel, ...]


class IngestResult(_Model):
    source: SourceText
    instruments: tuple[Instrument, ...]


# ---------------------------------------------------------------- numbers


class Currency(str, Enum):
    USD = "USD"


class Basis(str, Enum):
    EACH_OCCURRENCE = "each_occurrence"
    ANY_ONE_CLAIM = "any_one_claim"
    PER_PERSON = "per_person"
    AGGREGATE = "aggregate"
    # As written. No equivalence with any_one_claim or each_occurrence is assumed (D6).
    EACH_CLAIM = "each_claim"
    EACH_LOSS = "each_loss"
    UNKNOWN = "unknown"  # legal: no lexicon match


class Amount(_Model):
    minor_units: int  # integer cents; no floats anywhere
    decimals: int = Field(ge=0)  # decimal places as written, for faithful rendering
    currency: Currency | None  # None = not stated in the cited text (D1); never filled in


class ParseFailure(_Model):
    """A string the number parser could not read. Logged: this list is the next rule."""

    raw: str
    reason: str


class Quantity(_Model):
    """An amount read from a document span. Comparable only on equal currency and basis."""

    amount: Amount
    basis: Basis
    raw: str
    span_id: str


# ---------------------------------------------------------------- claims


class Atom(_Model):
    """Smallest unit of a claim that can be independently true or false."""

    atom_id: str
    predicate: str  # validated against data/predicates.json, not an enum
    kind: str | None  # predicate argument, e.g. subject_to -> follow_form
    negated: bool
    subject: str | None
    slot: str | None  # dotted path, required for `states`
    quantity_raw: str | None  # as written in the claim; parsed by numbers.py, never by the model
    quantity: Amount | None
    value: str | None  # non-numeric value
    period: str | None
    territory: str | None
    basis: Basis | None
    conditions: str | None


class ProposedAtom(_Model):
    """What the model returns for one atom, before code validates it. Every slot is present; null means null."""

    predicate: str
    kind: str | None
    negated: bool
    subject: str | None
    slot: str | None
    quantity_raw: str | None
    value: str | None
    period: str | None
    territory: str | None
    basis: Basis | None
    conditions: str | None


class AtomProposal(_Model):
    atoms: tuple[ProposedAtom, ...]
    no_fit_reason: str | None


class AtomErrorCode(str, Enum):
    UNKNOWN_PREDICATE = "unknown_predicate"
    BAD_KIND = "bad_kind"
    MISSING_SLOT = "missing_slot"
    BAD_SLOT = "bad_slot"
    UNRESOLVED_REF = "unresolved_ref"
    MISSING_UNIT = "missing_unit"
    UNPARSEABLE_QUANTITY = "unparseable_quantity"
    CONJUNCTION_IN_VALUE = "conjunction_in_value"
    NO_PREDICATE_FITS = "no_predicate_fits"


class AtomError(_Model):
    code: AtomErrorCode
    field: str | None
    detail: str


class AtomizeResult(_Model):
    claim_id: str
    atoms: tuple[Atom, ...]
    errors: tuple[AtomError, ...]  # non-empty only when atomisation failed after repair
    rejects: int  # validation errors seen across attempts
    repairs: int  # 0 or 1


# ---------------------------------------------------------------- trace


class TraceRecord(_Model):
    """One JSON line per stage. grep is the viewer."""

    stage: str
    packet_id: str | None
    atom_id: str | None
    span_ids: tuple[str, ...]
    model: str | None  # model that actually served the call
    prompt_hash: str | None  # sha256(template + model name)[:16]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cache_hit: bool
    verdict: Verdict | None
    rejects: tuple[str, ...]
    repairs: int
    detail: str | None


class Claim(_Model):
    claim_id: str
    text: str


class Packet(_Model):
    packet_id: str
    claim: Claim
    instruments: tuple[Instrument, ...]
    required_instrument_types: tuple[InstrumentType, ...]


# ---------------------------------------------------------------- assertions


class RouteRef(_Model):
    mapping_id: str
    method: MappingMethod
    strength: RouteStrength


class InstrumentRef(_Model):
    """What precedence reads about the asserting instrument (D3 scope test)."""

    doc_id: str
    version: str
    instrument_type: InstrumentType
    policy_numbers: tuple[str, ...]  # the policies this instrument binds: its own (binder), or the one it is attached to (endorsement)
    effective_date: dt.date | None


class Assertion(_Model):
    """One cited text, as one typed assertion on one slot. Fields the citation cannot source are None (D1)."""

    assertion_id: str
    slot: str
    instrument: InstrumentRef
    citation: Citation  # the one citation the assertion rests on
    value: Citation  # exactly the characters of the value, e.g. "1,000,000", inside `citation`
    amount: Amount
    basis: Basis | None
    basis_phrase: Citation | None
    routes: tuple[RouteRef, ...]  # every route used to reach the slot
    weakest: RouteStrength


class InvalidAssertion(_Model):
    mapping_id: str
    reason: str


# ---------------------------------------------------------------- comparison and slot verdicts


class ValueComparison(str, Enum):
    """Numerals only: currency tokens dropped, integers compared. Knows nothing about documents."""

    EQUAL = "equal"
    DIFFERENT = "different"
    NOT_COMPARABLE = "not_comparable"  # at least one side has no numeral (NIL, unparseable)


class ComparisonReason(str, Enum):
    NO_NUMERAL = "no_numeral"
    EQUAL = "equal"
    DIFFERENT = "different"
    CURRENCY_NOT_STATED = "currency_not_stated"
    CURRENCY_MISMATCH = "currency_mismatch"
    BASIS_NOT_STATED = "basis_not_stated"
    BASIS_MISMATCH = "basis_mismatch"


class Comparison(_Model):
    """One pair of asserters on a slot. Every pair is recorded, compared or not (D6)."""

    a: str  # assertion_id
    b: str
    compared: bool
    reason: ComparisonReason
    detail: str  # e.g. "each_claim vs each_loss"
    value: ValueComparison  # numerals alone, whether or not currency and basis allow comparison


class RuleEvaluation(_Model):
    name: RuleName
    fired: bool
    reason: str
    governing_assertion: str | None


class SlotVerdict(_Model):
    schema_version: str = SCHEMA_VERSION
    slot: str
    verdict: Verdict
    assertions: tuple[str, ...]
    in_scope: tuple[str, ...]  # asserters issued under the slot's policy (D3)
    pairs: tuple[Comparison, ...]
    rules: tuple[RuleEvaluation, ...]
    governing_assertion: str | None
    unresolved_pairs: int  # counted in the eval (D6)
    weakest_routes: tuple[RouteRef, ...]  # per assertion, in `assertions` order: what each one rests on


# ---------------------------------------------------------------- evidence and verdicts


class Side(str, Enum):
    SUPPORT = "support"
    ATTACK = "attack"


class SlotStatement(_Model):
    """A document asserting a value for a slot.

    The slot names what the value is about (FD960228.corp_reimbursement.retention).
    asserted_by names the instrument whose text says it (coda_end13, because Item
    VII is a table inside Endorsement 13). Keep them separate, or the trace loses
    which document said what. The checker requires the quantity's span to belong
    to asserted_by.
    """

    slot: str
    quantity: Quantity
    asserted_by: str  # doc_id of the asserting instrument


class Evidence(_Model):
    side: Side
    span_id: str
    reading: str  # one line: what this span says about the atom
    statement: SlotStatement | None  # set when the span binds the atom's slot


class Rule(_Model):
    name: RuleName
    governing_doc_id: str | None  # None only for unresolved_conflict
    other_doc_ids: tuple[str, ...] = Field(min_length=1)
    span_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Rule:
        is_conflict = self.name is RuleName.UNRESOLVED_CONFLICT
        if is_conflict != (self.governing_doc_id is None):
            raise ValueError("only unresolved_conflict has no governing document")
        return self


class Derivation(_Model):
    schema_version: str = SCHEMA_VERSION
    packet_id: str
    atom: Atom
    support: tuple[Evidence, ...]
    attack: tuple[Evidence, ...]
    rules_fired: tuple[Rule, ...]
    verdict: Verdict
    governing_doc_id: str | None
    not_found_reason: NotFoundReason | None
    cited_span_ids: tuple[str, ...]

    @model_validator(mode="after")
    def _check(self) -> Derivation:
        if (self.verdict is Verdict.NOT_FOUND) != (self.not_found_reason is not None):
            raise ValueError("not_found_reason is set exactly when verdict is not_found")
        names_conflict = any(r.name is RuleName.UNRESOLVED_CONFLICT for r in self.rules_fired)
        if (self.verdict is Verdict.DOCUMENTS_DISAGREE) != names_conflict:
            raise ValueError("documents_disagree appears exactly when a rule names a conflict")
        return self


# ---------------------------------------------------------------- predicate set


class PredicateSpec(_Model):
    name: str
    meaning: str
    kinds: tuple[str, ...]


class PredicateSet(_Model):
    predicate_set_version: str
    frozen: dt.date
    note: str
    predicates: tuple[PredicateSpec, ...]

    def get(self, name: str) -> PredicateSpec | None:
        return next((p for p in self.predicates if p.name == name), None)


def load_predicate_set(path: Path) -> PredicateSet:
    return PredicateSet.model_validate_json(path.read_text(encoding="utf-8"))
