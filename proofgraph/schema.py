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
from typing import Literal

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
    # Relabelled from documents_disagree (D7). Still four verdicts; the reason says which kind.
    UNRESOLVED = "unresolved"
    NOT_FOUND = "not_found"


class UnresolvedReason(str, Enum):
    DOCUMENTS_DISAGREE = "documents_disagree"  # numerals differ and no rule picks one
    UNCOMPARED_AGREEMENT = "uncompared_agreement"  # numerals agree, but currency or basis blocked the comparison


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
    # Not precedence rules. Each names why the slot stays unresolved; they are the
    # only way `unresolved` can be produced, never a fallback.
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    UNTESTED_AGREEMENT = "untested_agreement"


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


class RawOffsets(_Model):
    """Offsets into the raw file as stored on disk (ASCII, so bytes == chars). For text sources."""

    kind: Literal["raw_offsets"]
    start: int = Field(ge=0)
    end: int


class PageQuote(_Model):
    """For PDFs: a page, plus the expected text as a quote that must occur exactly once on that page.

    The PDF parser checks it (pdfplumber's page search), never this project's
    column rebuild. A citation that verified against our own converter would only
    prove the pipeline agrees with itself. The quote must sit on one physical
    line: the parser does not match across line breaks.
    """

    kind: Literal["page_quote"]
    page: int = Field(ge=1)


class Citation(_Model):
    """Where a value is written: file hash, a typed locator, and the expected text.

    It does not depend on the clause splitter or the extractor. Checked by one
    function, checker.verify_citation:
    - hash mismatch: fatal (the file is not the file);
    - locator does not resolve to exactly the expected text: the citation is
      broken, and the assertion is invalid and left out of comparison.
    """

    source_file: str
    sha256_of_file: str
    locator: RawOffsets | PageQuote = Field(discriminator="kind")
    text: str

    @model_validator(mode="after")
    def _check(self) -> Citation:
        loc = self.locator
        if isinstance(loc, RawOffsets) and len(self.text) != loc.end - loc.start:
            raise ValueError("citation text length does not match offsets")
        if isinstance(loc, PageQuote) and ("\n" in self.text or not self.text.strip()):
            raise ValueError("a page quote must be one non-empty line")
        return self


class Excerpt(_Model):
    """A slice of a verified citation's text, by offsets relative to that text. Never retyped."""

    start: int = Field(ge=0)
    end: int
    text: str

    @model_validator(mode="after")
    def _check(self) -> Excerpt:
        if len(self.text) != self.end - self.start:
            raise ValueError("excerpt text length does not match offsets")
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
    first_page: int = Field(ge=1)
    last_page: int = Field(ge=1)
    file_start: int | None  # extent in the raw file; None when the source has no raw text layer (PDF)
    file_end: int | None
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


# ---------------------------------------------------------------- retrieval


class RetrievalHit(_Model):
    rank: int = Field(ge=1)
    span_id: str
    doc_id: str
    page: int
    section_path: tuple[str, ...]
    bm25_rank: int | None
    dense_rank: int | None
    term_rank: int | None  # rank in the defined-term list, if the span holds a defined term from the query
    rrf: float  # reciprocal rank fusion score, k = 60; ranks are comparable, raw scores are not


class RetrievalResult(_Model):
    atom_id: str
    query_terms: tuple[str, ...]  # stored so a miss can be traced to a wrong query first
    hits: tuple[RetrievalHit, ...]
    candidates: int  # spans searched after dedupe
    deduped: int  # spans dropped as duplicates of another span's text
    capped: int  # spans dropped by the per-document cap
    dense: bool  # whether a dense ranking took part


class GoldQuote(_Model):
    doc_id: str
    quote: str  # matched against span text with whitespace collapsed


class RetrievalQuery(_Model):
    query_id: str
    atom: Atom
    gold: tuple[GoldQuote, ...]
    note: str


class RetrievalEval(_Model):
    note: str
    queries: tuple[RetrievalQuery, ...]


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
    value: Excerpt  # exactly the characters of the value inside `citation`, e.g. "1,000,000"
    amount: Amount
    basis: Basis | None
    basis_phrase: Excerpt | None
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
    unresolved_reason: UnresolvedReason | None
    not_found_reason: NotFoundReason | None
    unresolved_pairs: int  # counted in the eval (D6)
    weakest_routes: tuple[RouteRef, ...]  # per assertion, in `assertions` order: what each one rests on


# ---------------------------------------------------------------- evidence and verdicts


class Side(str, Enum):
    SUPPORT = "support"
    ATTACK = "attack"


class ProposedEvidence(_Model):
    """What a pass returns for one span, before code checks it."""

    span_id: str
    reading: str  # one line: what this span says about the atom
    quote: str  # the characters in the span that bear on the atom, copied verbatim


class EvidenceProposal(_Model):
    evidence: tuple[ProposedEvidence, ...]


class Evidence(_Model):
    """A checked pass result: the quote was found in the span, exactly once, and cited."""

    side: Side
    span_id: str
    doc_id: str
    reading: str
    quote: Excerpt  # offsets relative to the span's text
    citation: Citation  # built by code from the span and the quote, never by the model


class PassResult(_Model):
    side: Side
    atom_id: str
    evidence: tuple[Evidence, ...]  # empty when the pass failed or found nothing
    failed: bool  # true after a failed repair or a hard failure; evidence is then empty
    errors: tuple[str, ...]  # what failed validation on the last attempt
    rejects: int  # validation errors across attempts
    repairs: int  # 0 or 1


class Rule(_Model):
    name: RuleName
    governing_doc_id: str | None  # None only for unresolved_conflict
    other_doc_ids: tuple[str, ...] = Field(min_length=1)
    span_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Rule:
        is_conflict = self.name in (RuleName.UNRESOLVED_CONFLICT, RuleName.UNTESTED_AGREEMENT)
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
        names_conflict = any(r.name in (RuleName.UNRESOLVED_CONFLICT, RuleName.UNTESTED_AGREEMENT) for r in self.rules_fired)
        if (self.verdict is Verdict.UNRESOLVED) != names_conflict:
            raise ValueError("unresolved appears exactly when a rule names why")
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
