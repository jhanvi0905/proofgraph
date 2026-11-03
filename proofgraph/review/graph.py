"""The evidence graph: entities from rule statements, merged by rule, never by guess.

``build_entities`` turns each statement's bearer and concepts into typed entities, one
primary subject per statement. ``merge`` joins entities that are the same thing through a
definition, a parties clause or a section number, and across documents only on "as defined
in". Near misses become ``unclear`` links, never merges, and a differing number vetoes any link
(section 3.2 is not section 3.3). Pure and deterministic: no model, no network.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

import networkx as nx
from rapidfuzz.distance import JaroWinkler

from proofgraph.review.graph_extract import DocRead

EntityType = Literal["person", "organisation", "office", "section", "concept", "event"]

NEAR_MISS = 0.92  # Jaro-Winkler at or above this, below an exact match: an unclear link
_SECTION = re.compile(r"^(?:(?:section|sec\.?|article|art\.?|clause|§+)\s*)?(\d+(?:\.\d+)*[a-z]?)(?:\s*\(\w+\))*$")
_ORG = re.compile(r"\b(inc|llc|ltd|corp|corporation|company|co|gmbh|plc|lp|llp|ag|association|university|bank)\b\.?")
_OFFICE = re.compile(r"\b(officer|director|chair\w*|president|secretary|treasurer|board|committee|ceo|cfo|cmo|coo"
                     r"|counsel|trustee|member)\b")
_EVENT = re.compile(r"\b(adoption|ratification|meeting|resolution|amendment|appointment|approval|effective date)\b"
                    r"|\b\d{4}\b")
_PARTY_CLAUSE = re.compile(r"(?P<name>[^()\"“”]+?)\s*\(\s*(?:the\s+|a\s+|an\s+)?[\"“](?P<term>[^\"”]+)[\"”]\s*\)")
_MEANS = re.compile(r"[\"“](?P<term>[^\"”]+)[\"”]\s+(?:shall\s+)?(?:means?|refers?\s+to)\s+(?:the\s+|a\s+|an\s+)?"
                    r"(?P<name>[^,.;:]+)")
_AS_DEFINED = re.compile(r"as\s+defined\s+in", re.I)
_DIGITS = re.compile(r"\d+")


@dataclass
class Entity:
    id: str
    name: str
    type: EntityType
    scope: str | None = None  # the document, for a defined term or a section number
    docs: set[str] = field(default_factory=set)
    rule_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SameAs:
    a: str
    b: str
    kind: Literal["same_as", "unclear"]
    rule: str  # definition, parties_clause, as_defined_in, near_miss
    doc: str
    quote: str = ""


@dataclass
class Entities:
    by_id: dict[str, Entity] = field(default_factory=dict)
    subject: dict[str, str] = field(default_factory=dict)  # rule id -> its one primary entity
    mentions: dict[str, list[str]] = field(default_factory=dict)  # rule id -> concept entities


@dataclass(frozen=True)
class Merged:
    canon: dict[str, str]  # entity id -> the id its same-as group is known by
    links: list[SameAs]


def canon_name(name: str) -> str:
    folded = unicodedata.normalize("NFKC", name).casefold()
    folded = re.sub(r"^(the|a|an)\s+", "", re.sub(r"[^\w§.\s]", " ", folded).strip())
    return re.sub(r"\s+", " ", folded).strip(" .")


def section_key(name: str) -> str | None:
    m = _SECTION.match(canon_name(name))
    return f"section {m.group(1)}" if m and (m.group(0)[0] in "sacp§" or "." in m.group(1)) else None


def entity_type(name: str, parties: set[str]) -> EntityType:
    key = canon_name(name)
    if section_key(name):
        return "section"
    if _OFFICE.search(key):
        return "office" if not _EVENT.search(key) else "event"
    if _EVENT.search(key):
        return "event"
    if _ORG.search(key):
        return "organisation"
    if key in parties and len(key.split()) <= 4:
        return "person"
    return "concept"


def build_entities(reads: list[DocRead]) -> Entities:
    out = Entities()
    for read in reads:
        parties = {canon_name(p) for p in read.header.parties}
        defined = {canon_name(t.term) for t in read.header.defined_terms}

        def entity(name: str) -> Entity:
            key = section_key(name) or canon_name(name)
            scope = read.doc if key in defined or key.startswith("section ") else None
            eid = f"e:{scope}:{key}" if scope else f"e:{key}"
            ent = out.by_id.get(eid)
            if ent is None:
                ent = out.by_id[eid] = Entity(eid, name.strip(), entity_type(name, parties), scope)
            ent.docs.add(read.doc)
            return ent

        for term in read.header.defined_terms:
            entity(term.term)
        for g in read.rules:
            rule = g.rule
            subject = entity(rule.bearer or "unspecified")
            subject.rule_ids.append(rule.id)
            out.subject[rule.id] = subject.id
            seen = []
            for c in rule.concepts:
                if canon_name(c):
                    ent = entity(c)
                    if ent.id != subject.id and ent.id not in seen:
                        ent.rule_ids.append(rule.id)
                        seen.append(ent.id)
            out.mentions[rule.id] = seen
    return out


def _numbers_differ(a: str, b: str) -> bool:
    # Adapted from graphify dedup._numeric_tokens_differ (Graphify-Labs/graphify, MIT):
    # digit runs compared as multisets with leading zeros stripped.
    if a == b:
        return False
    norm = lambda s: sorted(t.lstrip("0") or "0" for t in _DIGITS.findall(s))  # noqa: E731
    return norm(a) != norm(b)


def merge(ents: Entities, reads: list[DocRead]) -> Merged:
    by_name: dict[str, list[Entity]] = {}
    for e in ents.by_id.values():
        by_name.setdefault(canon_name(e.name), []).append(e)

    links: list[SameAs] = []
    seen: set[tuple[str, str, str]] = set()

    def link(a: Entity, b: Entity, kind: str, rule: str, doc: str, quote: str = "") -> None:
        pair = tuple(sorted((a.id, b.id)))
        if a.id != b.id and (pair[0], pair[1], kind) not in seen and not _numbers_differ(a.name, b.name):
            seen.add((pair[0], pair[1], kind))
            links.append(SameAs(pair[0], pair[1], kind, rule, doc, quote))

    for read in reads:
        local = {e.name: e for e in ents.by_id.values() if read.doc in e.docs}
        for t in read.header.defined_terms:
            term = next((e for e in local.values() if canon_name(e.name) == canon_name(t.term)), None)
            if term is None:
                continue
            for pattern, rule in ((_PARTY_CLAUSE, "parties_clause"), (_MEANS, "definition")):
                for m in pattern.finditer(t.quote):
                    if canon_name(m.group("term")) != canon_name(t.term):
                        continue
                    for other in by_name.get(canon_name(m.group("name")), []):
                        if other.type != "section":
                            link(term, other, "same_as", rule, read.doc, t.quote)
        for g in read.rules:
            if not _AS_DEFINED.search(g.rule.quote):
                continue
            for eid in [ents.subject[g.rule.id], *ents.mentions.get(g.rule.id, [])]:
                src = ents.by_id[eid]
                if src.scope == read.doc and src.type != "section":
                    for other in by_name.get(canon_name(src.name), []):
                        if other.scope and other.scope != read.doc:
                            link(src, other, "same_as", "as_defined_in", read.doc, g.rule.quote)

    named = sorted((e for e in ents.by_id.values() if e.type != "section"), key=lambda e: e.id)
    for i, a in enumerate(named):
        for b in named[i + 1 :]:
            ka, kb = canon_name(a.name), canon_name(b.name)
            if a.type == b.type and ka != kb and JaroWinkler.normalized_similarity(ka, kb) >= NEAR_MISS:
                link(a, b, "unclear", "near_miss", "")

    graph = nx.Graph()
    graph.add_nodes_from(ents.by_id)
    graph.add_edges_from((l.a, l.b) for l in links if l.kind == "same_as")
    canon: dict[str, str] = {}
    for comp in nx.connected_components(graph):
        head = min(comp, key=lambda i: (ents.by_id[i].scope is not None, i))
        canon.update({i: head for i in comp})
    return Merged(canon, links)
