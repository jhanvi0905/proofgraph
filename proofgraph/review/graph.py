"""The evidence graph: entities from rule statements, merged by rule, never by guess.

``build_entities`` turns each statement's bearer and concepts into typed entities, one
primary subject per statement. ``merge`` joins entities that are the same thing through a
definition, a parties clause or a section number, and across documents only on "as defined
in". Near misses become ``unclear`` links, never merges, and a differing number vetoes any link
(section 3.2 is not section 3.3). Pure and deterministic: no model, no network.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

import networkx as nx
from rapidfuzz.distance import JaroWinkler

from proofgraph.config import DEFAULT_CACHE_DIR
from proofgraph.review.graph_extract import DocRead, GroundedRule
from proofgraph.review.relate import PageText
from proofgraph.review.scan import locate
from proofgraph.review.snap import snap
from proofgraph.review.timeline import referenced_documents

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
            for rel in rule.relations:
                entity(rel.subject), entity(rel.object)
            for m in rule.members:
                entity(m)
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


# ---- typed links with evidence (A3) -------------------------------------------------------

Locator = Callable[[str, int, str], tuple[str, list]]  # (doc, page, quote) -> (box status, boxes)
_TIER_RANK = {"page": 0, "model": 1, "unclear": 2}
_SECTION_REF = re.compile(r"(?:section|sec\.|§)\s*(\d+(?:\.\d+)*)", re.I)


def make_locator(words: dict, transcripts: dict) -> Locator:
    """Boxes for a quote: ``snap`` on a text page, ``locate`` on a transcribed scan, else none."""

    def locator(doc: str, page: int, quote: str) -> tuple[str, list]:
        if (doc, page) in words:
            found = snap(quote, words[(doc, page)])
        elif (doc, page) in transcripts:
            found = locate(quote, transcripts[(doc, page)])
        else:
            return "unpinned", []
        return found.status, found.boxes

    return locator


def _weakest(*tiers: str) -> str:
    return max(tiers, key=_TIER_RANK.__getitem__)


def _in_quote(name: str, quote: str) -> bool:
    return bool(canon_name(name)) and re.search(rf"\b{re.escape(canon_name(name))}\b", canon_name(quote)) is not None


def _evidence(g: GroundedRule, locator: Locator | None) -> dict:
    a = g.alignment
    ev = {"doc": g.doc, "page": a.page, "level": a.level, "start": a.start, "end": a.end, "quote": g.rule.quote}
    if locator and g.decides:
        ev["box_status"], ev["box"] = locator(g.doc, a.page, g.rule.quote)
    return ev


def edges(reads: list[DocRead], ents: Entities, merged: Merged, locator: Locator | None = None) -> nx.MultiDiGraph:
    """The typed graph. Nodes: entities (by merged id), rules, definitions, external documents.
    Every edge carries ``tier``, ``made_by`` and an ``evidence`` list. A link whose names are not in
    its quote is kept as ``unclear`` and never decides; a dangling exception is counted."""
    g = nx.MultiDiGraph()
    g.graph.update(same_as=[asdict(l) for l in merged.links], rejected=Counter(), docs={})
    ent = lambda eid: merged.canon.get(eid, eid)  # noqa: E731
    for e in ents.by_id.values():
        node = g.nodes.get(ent(e.id)) or {}
        g.add_node(ent(e.id), kind="entity", name=ents.by_id[ent(e.id)].name, type=ents.by_id[ent(e.id)].type,
                   docs=sorted(set(node.get("docs", [])) | e.docs))
    by_name = {(read.doc, canon_name(e.name)): e.id for read in reads for e in ents.by_id.values() if read.doc in e.docs}

    rule_doc = {gr.rule.id: gr for read in reads for gr in read.rules}
    dated = {read.doc: read.header.date for read in reads}
    for read in reads:
        g.graph["docs"][read.doc] = {"role": read.header.role, "date": read.header.date}
        for gr in read.rules:
            r = gr.rule
            g.add_node(r.id, kind="rule", doc=gr.doc, page=gr.alignment.page, quote=r.quote, deontic=r.deontic,
                       action=r.action, value=r.value, value_status=r.value_status, link_kind=r.link_kind,
                       effective_from=r.effective_from, tier=gr.tier, level=gr.alignment.level)
            ev = [_evidence(gr, locator)]
            g.add_edge(r.id, ent(ents.subject[r.id]), "mentions", kind="mentions", role="bearer", tier=gr.tier,
                       made_by="code", evidence=ev)
            for eid in ents.mentions.get(r.id, []):
                g.add_edge(r.id, ent(eid), "mentions", kind="mentions", role="concept", tier=gr.tier,
                           made_by="code", evidence=ev)
            for m in _SECTION_REF.finditer(r.quote):
                target = f"e:{read.doc}:section {m.group(1)}"
                if target in ents.by_id and ent(target) != ent(ents.subject[r.id]):
                    g.add_edge(r.id, ent(target), "refers_to_section", kind="refers_to_section", tier=gr.tier,
                               made_by="code", evidence=ev)
            for rel in r.relations:
                a, b = by_name.get((read.doc, canon_name(rel.subject))), by_name.get((read.doc, canon_name(rel.object)))
                checked = _in_quote(rel.subject, r.quote) and _in_quote(rel.object, r.quote)
                if not checked:
                    g.graph["rejected"]["relation_not_in_quote"] += 1
                if a and b:
                    g.add_edge(ent(a), ent(b), rel.kind, kind=rel.kind, interim=rel.interim, source=r.id,
                               tier=gr.tier if checked else "unclear", made_by="model-checked", evidence=ev)
            for m in r.members:
                a, b = by_name.get((read.doc, canon_name(m))), ents.subject[r.id]
                checked = _in_quote(m, r.quote)
                if not checked:
                    g.graph["rejected"]["member_not_in_quote"] += 1
                if a:
                    g.add_edge(ent(a), ent(b), "is_a", kind="is_a", mode=r.member_mode, source=r.id,
                               tier=gr.tier if checked else "unclear", made_by="model-checked", evidence=ev)
            if r.link_kind != "rule" and r.excepts:
                if r.excepts in rule_doc:
                    g.add_edge(r.id, r.excepts, "excepts" if r.link_kind == "exception" else "conditions",
                               kind="excepts" if r.link_kind == "exception" else "conditions",
                               tier=_weakest(gr.tier, rule_doc[r.excepts].tier), made_by="model-extracted", evidence=ev)
                else:
                    g.graph["rejected"]["dangling_exception"] += 1
        for term, al in read.terms.items():
            node = f"d:{read.doc}:{canon_name(term)}"
            quote = next((t.quote for t in read.header.defined_terms if t.term == term), "")
            tier = "unclear" if al.level == "unmatched" else ("model" if al.level == "fuzzy" else "page")
            g.add_node(node, kind="definition", doc=read.doc, page=al.page, quote=quote, tier=tier)
            eid = by_name.get((read.doc, canon_name(term)))
            if eid:
                g.add_edge(ent(eid), node, "defined_by", kind="defined_by", tier=tier, made_by="code",
                           evidence=[{"doc": read.doc, "page": al.page, "level": al.level, "quote": quote}])
    for ref in referenced_documents([(gr.rule.id, gr.rule.quote) for gr in rule_doc.values()], dated):
        node = f"x:{ref.date}:{ref.phrase}"
        g.add_node(node, kind="external", phrase=ref.phrase, date=ref.date, status=ref.status)
        gr = rule_doc[ref.cited_in]
        g.add_edge(ref.cited_in, node, "cites", kind="cites", tier=gr.tier, made_by="code",
                   evidence=[_evidence(gr, locator)])
    for l in merged.links:
        if l.kind == "unclear":
            g.add_edge(ent(l.a), ent(l.b), "unclear", kind="unclear", tier="unclear", made_by="code", evidence=[])
    return g


# ---- store and cache (A6) -----------------------------------------------------------------


def packet_hash(texts: Iterable[PageText]) -> str:
    h = hashlib.sha256()
    for p in sorted(texts, key=lambda p: (p.doc, p.page)):
        h.update(f"{p.doc}\x00{p.page}\x00{p.text}\x01".encode())
    return h.hexdigest()


def pair_key(a: str, b: str, part: str = "") -> str:
    """Comparator cache key for one statement pair (order matters: part, then a, then b)."""
    return hashlib.sha256(json.dumps([part, a, b], ensure_ascii=False).encode()).hexdigest()


def _path(cache_dir: Path | str, key: str) -> Path:
    return Path(cache_dir) / "graphs" / f"{key}.json"


def save(g: nx.MultiDiGraph, key: str, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> bool:
    """Write the graph under ``key``. A rebuild smaller than the last good one is refused (False)."""
    path = _path(cache_dir, key)
    old = load(key, cache_dir)
    if old is not None and old.number_of_nodes() + old.number_of_edges() > g.number_of_nodes() + g.number_of_edges():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(g, edges="edges")
    data["graph"]["rejected"] = dict(g.graph.get("rejected", {}))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return True


def load(key: str, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> nx.MultiDiGraph | None:
    path = _path(cache_dir, key)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        g = nx.node_link_graph(data, edges="edges", multigraph=True, directed=True)
    except (OSError, ValueError, KeyError, TypeError):
        return None
    g.graph["rejected"] = Counter(g.graph.get("rejected", {}))
    return g
