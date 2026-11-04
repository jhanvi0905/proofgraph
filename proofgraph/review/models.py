"""Review JSON contract shared by backend, viewer, export, cache and scorer.

Shape: the review contract, plus
`parts[].conflict` and `docs[].note` (final-plan.md section 4.5, R-04).
"""

from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, Field, model_serializer, model_validator

GRID = 1000

PartStatus = Literal[
    "contradicted", "weakened", "supported", "not_found", "cannot_tell", "checking", "error"
]
Relation = Literal["contradicts", "weakens", "supports", "set_aside"]
WeakenerType = Literal[
    "exception", "condition", "qualifier", "scope", "time", "magnitude", "definition",
    "weak_source",
]
BoxStatus = Literal["pinned", "located", "approximate", "unpinned"]
CheckName = Literal["agrees", "disagrees", "unavailable", "not_run"]
CheckAnswer = Literal["entails", "contradicts", "not_mentioned"]
PageKind = Literal["text_layer", "image_only", "image"]
BannerKind = Literal["injection", "unreadable", "cap", "checker_unavailable"]


def _check_box(box: list[int]) -> list[int]:
    x_min, y_min, x_max, y_max = box
    if x_min >= x_max or y_min >= y_max:
        raise ValueError("box must have x_min < x_max and y_min < y_max")
    return box


# [x_min, y_min, x_max, y_max] on a 0 to 1000 grid over the displayed page image.
Box = Annotated[
    list[Annotated[int, Field(ge=0, le=GRID)]],
    Field(min_length=4, max_length=4),
    AfterValidator(_check_box),
]


class Claim(BaseModel):
    text: str
    origin: str


class Run(BaseModel):
    mode: Literal["live", "replayed"]
    recorded_at: str
    models: dict[str, str]
    cost_usd: float
    flags: list[str] = Field(default_factory=list)


class Page(BaseModel):
    n: int
    kind: PageKind
    png: str
    w: int
    h: int
    readable: bool
    note: str | None = None


class Doc(BaseModel):
    id: str
    name: str
    pages: list[Page]
    note: str | None = None


class Passage(BaseModel):
    """A place in a document: a page, with a short snippet when it was matched by word search."""

    doc: str
    page: int
    text: str = ""


class Receipt(BaseModel):
    pages_read: int
    unread: list[int] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    uncited_hits: list[str] = Field(default_factory=list)
    # Display-only disclosure (PROOFGRAPH_EVIDENCE_LINES). None / empty on every older review.
    matched_passages: int | None = None
    matched_docs: int | None = None
    uncited_passages: list[Passage] = Field(default_factory=list)
    unsearched: list[Passage] = Field(default_factory=list)

    @model_serializer(mode="wrap")
    def _omit_unused_evidence(self, handler):
        """Keep saved JSON and the embedded page byte-identical when the disclosure is off."""
        data = handler(self)
        if self.matched_passages is None:
            for key in ("matched_passages", "matched_docs", "uncited_passages", "unsearched"):
                data.pop(key, None)
        return data


class MapItem(BaseModel):
    """One entry of the evidence map: a card, or a source the documents cite but do not supply."""

    kind: Literal["card", "referenced"]
    card_id: str | None = None
    date: str | None = None  # ISO, inferred from the text
    date_source: str | None = None
    ref_text: str | None = None
    ref_doc: str | None = None
    ref_page: int | None = None


class Part(BaseModel):
    id: str
    text: str
    span: tuple[int, int]
    status: PartStatus
    reason: str | None = None
    card_ids: list[str] = Field(default_factory=list)
    receipt: Receipt | None = None
    conflict: bool = False
    # Display-only (PROOFGRAPH_EVIDENCE_MAP). None on every older review.
    evidence_map: list[MapItem] | None = None
    map_counts: dict | None = None  # examined, relevant, unlabelled, matched, shown

    @model_serializer(mode="wrap")
    def _omit_unused_map(self, handler):
        data = handler(self)
        if self.evidence_map is None:
            data.pop("evidence_map", None)
        if self.map_counts is None:
            data.pop("map_counts", None)
        return data

    @model_validator(mode="after")
    def _conflict_is_contradicted(self) -> "Part":
        if self.conflict and self.status != "contradicted":
            raise ValueError("conflict is only valid on a contradicted part")
        return self


class Computed(BaseModel):
    ok: bool
    text: str


class Card(BaseModel):
    id: str
    part: str
    relation: Relation
    weakener_type: WeakenerType | None = None
    quote: str = Field(min_length=1)
    cue_words: list[str] = Field(default_factory=list)
    doc: str
    page: int
    boxes: list[Box] = Field(default_factory=list)
    box_status: BoxStatus
    why: str
    computed: Computed | None = None
    check: CheckName
    check_answer: CheckAnswer | None = None
    controls: bool = False
    superseded_by: str | None = None


class Banner(BaseModel):
    kind: BannerKind
    text: str
    card: str | None = None


class Review(BaseModel):
    version: Literal["review-1"]
    review_id: str
    claim: Claim
    status: PartStatus
    driver_part: str | None = None
    run: Run
    docs: list[Doc]
    parts: list[Part]
    cards: list[Card]
    banners: list[Banner] = Field(default_factory=list)
    # Display-only (PROOFGRAPH_GRAPH). None on every older review.
    graph: dict | None = None

    @model_serializer(mode="wrap")
    def _omit_unused_graph(self, handler):
        data = handler(self)
        if self.graph is None:
            data.pop("graph", None)
        return data

    @model_validator(mode="after")
    def _references_resolve(self) -> "Review":
        part_ids = {p.id for p in self.parts}
        card_ids = {c.id for c in self.cards}
        pages = {(d.id, p.n) for d in self.docs for p in d.pages}
        if self.driver_part is not None and self.driver_part not in part_ids:
            raise ValueError(f"driver_part {self.driver_part!r} is not a part")
        for part in self.parts:
            for card_id in part.card_ids:
                if card_id not in card_ids:
                    raise ValueError(f"part {part.id} lists unknown card {card_id!r}")
        for card in self.cards:
            if card.part not in part_ids:
                raise ValueError(f"card {card.id} points at unknown part {card.part!r}")
            if (card.doc, card.page) not in pages:
                raise ValueError(f"card {card.id} points at unknown page {card.doc} p{card.page}")
        for banner in self.banners:
            if banner.card is not None and banner.card not in card_ids:
                raise ValueError(f"banner points at unknown card {banner.card!r}")
        return self
