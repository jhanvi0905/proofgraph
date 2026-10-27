"""Frozen Day 1 contracts. See docs/03-architecture.md."""

from typing import Literal

from pydantic import BaseModel, Field

VerdictName = Literal["SUPPORTED", "CONTRADICTED", "UNRESOLVED"]
LabelName = Literal["COMPUTED", "CHECKED", "ASSUMED"]
ScaleName = Literal["units", "thousands", "millions", "billions", "percent"]


class Source(BaseModel):
    id: str
    kind: Literal["text", "table", "pdf", "image"]
    text: str | None = None
    file_id: str | None = None
    path: str | None = None


class Case(BaseModel):
    id: str
    dataset: Literal["findver", "contractnli", "traps", "freight"]
    mode: Literal["passage", "whole"]
    claim: str
    sources: list[Source]
    answer: VerdictName | None = None
    gold_evidence: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    id: str
    label: str
    source_id: str
    quote: str | None = None
    page: int | None = None
    box: list[int] | None = None
    points: list[list[int]] | None = None
    value: float | str | None = None
    scale: ScaleName | None = None
    kind: Literal["number", "date", "time", "text", "count"]
    entity: str | None = None
    period: str | None = None


class Link(BaseModel):
    id: str
    kind: Literal["compute", "temporal", "wording", "rule"]
    inputs: list[str]
    statement: str
    expr: str | None = None
    rule_source: Literal["evidence", "assumed"] | None = None
    claim_span: str


class ClaimProgram(BaseModel):
    facts: list[Fact]
    links: list[Link]
    required: list[str]
    unverifiable_parts: list[str]


class FactCheck(BaseModel):
    fact_id: str
    status: Literal["grounded", "ungrounded", "conflict"]
    method: Literal["quote", "text_in_box", "blind_reread", "count_agreement"]
    detail: str


class LinkResult(BaseModel):
    link_id: str
    status: Literal["pass", "fail", "blocked", "not_mentioned"]
    strength: LabelName
    detail: str


class Verdict(BaseModel):
    case_id: str
    verdict: VerdictName
    label: LabelName | None = None
    reasons: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    fetch: list[str] = Field(default_factory=list)
    rounds: int = 0
    fact_checks: list[FactCheck] = Field(default_factory=list)
    link_results: list[LinkResult] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
