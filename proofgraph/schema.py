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

SCHEMA_VERSION = "2.1.0"  # D9


class _Model(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    def to_json(self) -> str:
        """Stable, key-sorted JSON so eval outputs diff cleanly between runs."""
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)


# ---------------------------------------------------------------- answers


class Verdict(str, Enum):
    SUPPORTED = "supported"  # amount claims: the governing value equals the claim's value (D9)
    CONTRADICTED = "contradicted"  # amount claims: the governing value differs from the claim's value (D9)
    # Relabelled from documents_disagree (D7). The reason says which kind.
    UNRESOLVED = "unresolved"
    NOT_FOUND = "not_found"
    # Wording claims only (D9). Not an answer: the governing clause is quoted verbatim and nothing
    # was checked. Code never says a wording claim is right or wrong.
    QUOTED = "quoted"


class SupportedReason(str, Enum):
    """How the governing value was chosen (D9: `governing_reason`, whatever the verdict)."""

    NO_CONFLICT = "no_conflict"  # nothing disagrees: one asserter, all agree, or a rule named a document over equal values
    RESOLVED_BY_RULE = "resolved_by_rule"  # some pair was compared and its numerals differ, and a precedence rule picked one


class UnresolvedReason(str, Enum):
    DOCUMENTS_DISAGREE = "documents_disagree"  # numerals differ and no rule picks one
    # D9, renamed from uncompared_agreement: two amounts could not be compared, between two
    # asserters or between the claim and the governing value. `unresolved_detail` names the mismatch.
    AMOUNTS_NOT_COMPARABLE = "amounts_not_comparable"
    # D9, moved from NotFoundReason: a document asserting on the question amends an instrument
    # of the question's policies, and that instrument is not in the packet.
    GOVERNING_INSTRUMENT_ABSENT = "governing_instrument_absent"


class NotFoundReason(str, Enum):
    NO_ADDRESSING_SPAN = "no_addressing_span"  # no admitted passage addresses the question


class RuleName(str, Enum):
    # Order here is documentation only; the arbiter states its own order.
    # The two precedence rules pick a governing document.
    ENDORSEMENT_OVER_BASE = "endorsement_over_base"
    LATER_EFFECTIVE_DATE = "later_effective_date"
    # Not precedence rules. Each names why the slot stays unresolved; they are the
    # only way `unresolved` can be produced, never a fallback.
    UNRESOLVED_CONFLICT = "unresolved_conflict"
    UNTESTED_AGREEMENT = "untested_agreement"
    AMENDED_INSTRUMENT_ABSENT = "amended_instrument_absent"  # D9: evaluated before the precedence rules
    CLAIM_NOT_COMPARABLE = "claim_not_comparable"  # D9: the claim's value and the governing value cannot be compared


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
    """For PDFs: a page, plus the expected text as a block of one or more physical lines.

    On a PDF, the page and the text are authoritative, and there are no offsets:
    offsets into extracted text move whenever the extractor changes, even when the
    page does not. Each line of the block must occur exactly once on the page, as
    found by the PDF parser (pdfplumber's page search), never by this project's
    column rebuild. The lines must run top to bottom within one column.
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
        if isinstance(loc, PageQuote) and (not self.text.strip() or any(not ln.strip() for ln in self.text.split("\n"))):
            raise ValueError("a page quote is one or more non-empty lines")
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


class DocumentRoute(_Model):
    """How one document identifies one policy it describes. Identification belongs to the document:
    a binder names its primary once, and its lines do not repeat it."""

    policy: str
    method: MappingMethod
    strength: RouteStrength
    reasoning: str | None  # required for judgment
    citation: Citation
    # D10: "citation" admits only text inside the citation (hand-labelled scopes). "document" admits the
    # whole document once its identifying citation verifies: for uploads a person confirmed, where no
    # one has marked a narrower block. The citation is still checked before anything is admitted.
    scope: Literal["citation", "document"] = "citation"

    @model_validator(mode="after")
    def _check(self) -> DocumentRoute:
        if self.strength is RouteStrength.JUDGMENT and not self.reasoning:
            raise ValueError(f"{self.policy}: a judgment identification must write out its reasoning")
        return self


class AmendsRoute(_Model):
    """The instrument a document amends, as the document prints it (D9). Hand-labelled, cited, verified."""

    instrument: str  # the amended instrument's id as printed, e.g. "HO 00 03", "GS-212C"
    instrument_doc_id: str | None  # its doc_id in data/instruments.json; None when it is not catalogued
    policy: str  # the policy the amended instrument belongs to
    method: MappingMethod
    strength: RouteStrength
    reasoning: str | None  # required for judgment
    citation: Citation  # the printed words that say what it amends; verified by checker.verify_citation

    @model_validator(mode="after")
    def _check(self) -> AmendsRoute:
        if self.strength is RouteStrength.JUDGMENT and not self.reasoning:
            raise ValueError(f"{self.instrument}: a judgment amends route must write out its reasoning")
        return self


class DocumentMapping(_Model):
    doc_id: str
    describes: tuple[DocumentRoute, ...]  # a schedule or a restating cover note describes several policies
    amends: AmendsRoute | None = None  # D9: optional; only documents that print what they amend carry one


class DocumentMappingFile(_Model):
    note: str
    documents: tuple[DocumentMapping, ...]


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
    url: str | None  # where `pgrun fetch` downloads it from; None if it must be placed by hand
    fetch_note: str  # how to obtain it, for a reader with a clean clone
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
    """What the model returns for one atom, before code validates it. Every field is present; null means null.

    There is no slot field. The slot is the claim author's canonical key, typed in the
    claim file and resolved against data/slots.json. The model never names it, so its
    spelling cannot drift (it drifted in 2 of 2 runs when the model did name it).
    """

    predicate: str
    kind: str | None
    negated: bool
    subject: str | None
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
    text: str  # written by the author, not generated
    slot: str | None  # canonical key from data/slots.json, typed by the author; None for non-`states` claims
    # D9: declared by the author, never inferred at runtime.
    kind: Literal["amount", "wording"]
    value: str | None = None  # amount claims only: the amount as the author wrote it, e.g. "USD 1,000,000"

    @model_validator(mode="after")
    def _check(self) -> Claim:
        if (self.kind == "amount") != (self.value is not None):
            raise ValueError(f"{self.claim_id}: an amount claim declares its value, and a wording claim has none")
        return self


class ClaimFile(_Model):
    note: str
    claims: tuple[Claim, ...]


class SlotEntry(_Model):
    key: str
    note: str
    # D9: the question's policy set, for the missing-document check. None means the key's first segment.
    policies: tuple[str, ...] | None = None


class SlotRegistry(_Model):
    note: str
    slots: tuple[SlotEntry, ...]


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


class Side(str, Enum):
    SUPPORT = "support"
    ATTACK = "attack"


class AmendsCheck(_Model):
    """One asserting document's amends route, as the missing-document check saw it (D9). Never dropped."""

    doc_id: str  # the asserting document
    amends: str  # the amended instrument, as printed
    amends_doc_id: str | None
    amends_policy: str
    outcome: Literal["present", "absent", "excluded"]  # excluded: the amended instrument is outside the question's policies
    reason: str  # e.g. "coda_end13 amends GS-212C, outside this question's policies FD960228"
    strength: RouteStrength  # of the amends route


class Clause(_Model):
    """Wording claims (D9): one quoted passage, tied to its instrument. Never parsed for an amount."""

    clause_id: str
    side: Side
    instrument: InstrumentRef
    citation: Citation  # built by code from the passage and verified; the text is verbatim
    page: int
    reading: str  # the model's one line
    identification: RouteRef


class QuotedClause(_Model):
    clause_id: str
    doc_id: str
    page: int
    text: str  # verbatim, the citation's text
    reading: str
    side: Side
    strength: RouteStrength  # judgment for a clash: the passes' reading, never a code verdict
    checked: Literal[False] = False  # always: quoted, not checked


class SlotVerdict(_Model):
    schema_version: str = SCHEMA_VERSION
    slot: str
    verdict: Verdict
    assertions: tuple[str, ...]  # assertion ids (amount) or clause ids (wording)
    in_scope: tuple[str, ...]  # asserters issued under the slot's policy (D3)
    pairs: tuple[Comparison, ...]
    rules: tuple[RuleEvaluation, ...]
    governing_assertion: str | None
    supported_reason: SupportedReason | None  # equals governing_reason when the verdict is supported
    governing_doc_id: str | None  # the instrument whose value governs
    governing_rule: RuleName | None  # the precedence rule that picked it, if one did
    unresolved_reason: UnresolvedReason | None
    not_found_reason: NotFoundReason | None
    unresolved_pairs: int  # counted in the eval (D6)
    weakest_routes: tuple[RouteRef, ...]  # per assertion, in `assertions` order: what each one rests on
    # ---- D9
    claim_kind: Literal["amount", "wording"] = "amount"
    claim_value: str | None = None  # the author's declared value (amount claims)
    policies: tuple[str, ...] = ()  # the question's policy set, used by the missing-document check
    governing_reason: SupportedReason | None = None  # how the governing value was chosen, whatever the verdict
    governing_value: str | None = None  # the value text the claim was compared with
    claim_comparison: Comparison | None = None  # a="claim", b=the assertion compared with; None when no value governs
    unresolved_detail: str | None = None  # names the mismatch or both documents, for every unresolved verdict
    amends_checks: tuple[AmendsCheck, ...] = ()  # every asserting document's amends route: present, absent or excluded
    quoted: QuotedClause | None = None  # wording claims: the governing clause, verbatim, not checked
    clauses: tuple[QuotedClause, ...] = ()  # wording claims: every clause the passes quoted, governing or not
    clashes: tuple[QuotedClause, ...] = ()  # wording claims: attack-pass clauses, judgment routes, never a verdict


# ---------------------------------------------------------------- evidence and verdicts


class ProposedEvidence(_Model):
    """What a pass returns for one span, before code checks it."""

    span_id: str
    reading: str  # one line: what this span says about the atom
    quote: str  # the characters in the span that bear on the atom, copied verbatim
    value: str  # the value it states for the atom's subject, copied verbatim from the quote; "" if none


class EvidenceProposal(_Model):
    evidence: tuple[ProposedEvidence, ...]


class Evidence(_Model):
    """A checked pass result: the quote was found in the span, exactly once, and cited."""

    side: Side
    span_id: str
    doc_id: str
    identification: DocumentRoute  # how this passage's document was tied to the claim's policy, decided in code
    reading: str
    quote: Excerpt  # offsets relative to the span's text
    citation: Citation  # built by code from the span and the quote, never by the model
    value: Excerpt | None  # the model's pointer to the value, located by code inside citation.text; None if it gave none


class PassResult(_Model):
    side: Side
    atom_id: str
    evidence: tuple[Evidence, ...]  # empty when the pass failed or found nothing
    failed: bool  # true after a failed repair or a hard failure; evidence is then empty
    errors: tuple[str, ...]  # what failed validation on the last attempt
    rejects: int  # validation errors across attempts
    repairs: int  # 0 or 1


_REFUSALS = (RuleName.UNRESOLVED_CONFLICT, RuleName.UNTESTED_AGREEMENT, RuleName.AMENDED_INSTRUMENT_ABSENT,
             RuleName.CLAIM_NOT_COMPARABLE)


class Rule(_Model):
    name: RuleName
    governing_doc_id: str | None  # None only for unresolved_conflict
    other_doc_ids: tuple[str, ...] = Field(min_length=1)
    span_ids: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> Rule:
        is_conflict = self.name in _REFUSALS
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
        names_conflict = any(r.name in _REFUSALS for r in self.rules_fired)
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
