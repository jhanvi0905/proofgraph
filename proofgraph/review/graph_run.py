"""Wiring for the evidence graph behind PROOFGRAPH_GRAPH=1 (A7, A8).

``build_packet_graph`` reads the packet once (one Muse Spark call per document, in parallel) and yields
progress events; the graph is cached by the packet's content hash, so a second claim reuses it.
``run_part_graph`` answers one claim part: link, walk and rank typed paths, compare, second-read the
deciding statements, with the full read running beside it, then decide in code. Second reads are capped
per claim. Never imported when the flag is off.
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from collections.abc import Generator, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import networkx as nx

from proofgraph.clients.muse import MuseClient
from pathlib import Path

from proofgraph.review import graph as G
from proofgraph.review import precedence as precedence_mod
from proofgraph.review.check import Checker
from proofgraph.review.compare import attached_exceptions, compare
from proofgraph.review.full_read import agreement, full_read
from proofgraph.review.graph_check import MAX_SECOND_READS, second_reads
from proofgraph.review.graph_decide import Decision, graph_status
from proofgraph.review.graph_extract import _PROMPT as _EXTRACT_PROMPT, Extraction, extract_document
from proofgraph.review.models import Banner, Card, Part
from proofgraph.review.precedence import amendments, apply_effects, precedence, resolve_dates
from proofgraph.review.query import MAX_STATEMENTS, link_parts, paths, rank_paths, statements
from proofgraph.review.relate import PageText

CLAIM_SECOND_READS = 12  # second reads allowed across one whole claim
_CARD = {"agrees": "supports", "conflicts": "contradicts", "qualifies": "weakens"}


@dataclass(frozen=True)
class DocRead:
    doc: str
    name: str
    role: str
    date: str | None


@dataclass(frozen=True)
class PageRead:
    doc: str
    name: str
    page: int
    of: int


@dataclass(frozen=True)
class EntityFound:
    name: str
    type: str
    docs: int


@dataclass(frozen=True)
class GraphReady:
    pages: int
    rules: int
    entities: int
    cached: bool = False


@dataclass(frozen=True)
class PartLinked:
    part_id: str
    entities: list[str]


@dataclass(frozen=True)
class PathFound:
    part_id: str
    labels: list[str]
    scenario: str


@dataclass
class Built:
    g: nx.MultiDiGraph
    banners: list[Banner] = field(default_factory=list)


def build_packet_graph(texts: Sequence[PageText], names: dict[str, str], words: dict, transcripts: dict, muse: MuseClient,
                       workers: int = 4) -> Generator[object, None, Built]:
    key = G.packet_hash(texts, extraction_version())
    cached = G.load(key, muse.settings.cache_dir)
    if cached is not None:
        yield from _ready(cached, cached=True)
        return Built(cached, _injections(cached))
    by_doc: dict[str, list[PageText]] = {}
    for t in texts:
        by_doc.setdefault(t.doc, []).append(t)
    reads = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(extract_document, doc, pages, muse): doc for doc, pages in sorted(by_doc.items())}
        for fut in as_completed(futures):
            read = fut.result()
            reads.append(read)
            name = names.get(read.doc, read.doc)
            yield DocRead(read.doc, name, read.header.role, read.header.date)
            for p in sorted(by_doc[read.doc], key=lambda p: p.page):
                yield PageRead(read.doc, name, p.page, len(by_doc[read.doc]))
    reads.sort(key=lambda r: r.doc)
    ents = G.build_entities(reads)
    g = G.edges(reads, ents, G.merge(ents, reads), G.make_locator(words, transcripts))
    amendments(g)
    precedence(g)
    resolve_dates(g)
    g.graph["stats"] = {"pages": len(texts), "rules": sum(len(r.rules) for r in reads),
                        "entities": sum(1 for _, d in g.nodes(data=True) if d["kind"] == "entity"),
                        "alignment": {r.doc: dict(r.counts) for r in reads}}
    g.graph["injections"] = [{"doc": r.doc, "quote": r.injection_quote} for r in reads if r.injection_quote]
    if not G.save(g, key, muse.settings.cache_dir):  # never serve a smaller graph than the last good one
        g = G.load(key, muse.settings.cache_dir) or g
    yield from _ready(g)
    return Built(g, _injections(g))


def extraction_version() -> str:
    """Changes whenever the extraction prompt, its schema or the graph-building code does."""
    code = "".join(Path(m.__file__).read_text(encoding="utf-8") for m in (G, precedence_mod))
    return _EXTRACT_PROMPT.read_text(encoding="utf-8") + json.dumps(Extraction.model_json_schema(), sort_keys=True) + code


def _ready(g: nx.MultiDiGraph, cached: bool = False):
    ents = sorted(((n, d) for n, d in g.nodes(data=True) if d["kind"] == "entity"),
                  key=lambda nd: (-len(nd[1]["docs"]), nd[1]["name"]))
    for _, d in ents[:12]:
        yield EntityFound(d["name"], d["type"], len(d["docs"]))
    s = g.graph["stats"]
    yield GraphReady(s["pages"], s["rules"], s["entities"], cached)


def _injections(g: nx.MultiDiGraph) -> list[Banner]:
    return [Banner(kind="injection", text=f"A page contains an instruction aimed at the reviewer: {i['quote']}")
            for i in g.graph.get("injections", [])]


class SecondReadBudget:
    """Second reads allowed across one claim; thread-safe."""

    def __init__(self, total: int = CLAIM_SECOND_READS) -> None:
        self.left, self._lock = total, threading.Lock()

    def take(self, wanted: int) -> int:
        with self._lock:
            n = min(wanted, self.left)
            self.left -= n
            return n


@dataclass
class GraphOutcome:
    part: Part
    cards: list[Card]
    banners: list[Banner]
    info: dict
    events: list[object] = field(default_factory=list)


def run_part_graph(part: Part, built: Built, texts: list[PageText], muse: MuseClient, checker: Checker,
                   names: dict[str, str], budget: SecondReadBudget, receipt_complete: bool = True,
                   *, typed_walk: bool = True, hub_brake: bool = True, precedence_on: bool = True) -> GraphOutcome:
    g = built.g.copy()
    banners: list[Banner] = []
    with ThreadPoolExecutor(max_workers=1) as side:  # the full read runs beside the walk
        read_future = side.submit(full_read, part.text, texts, g, muse)
        linked = link_parts([(part.id, part.text)], g, muse)[part.id]
        walk = paths(g, list(linked.entities), max_hops=3 if typed_walk else 1, hub_brake=hub_brake)
        ranked = rank_paths(g, walk.paths, part.text, top=MAX_STATEMENTS)  # the comparator judges relevance
        ids = [i for i in statements(ranked, g) if g.nodes[i]["kind"] == "rule"]
        result = compare(part.text, ids, g, muse)
        apply_effects(g, result.effects)
        read = read_future.result()
    if result.injection_quote:
        banners.append(Banner(kind="injection", text=f"A page contains an instruction aimed at the reviewer: {result.injection_quote}"))
    items = list(result.labels.values())
    checks = {}
    if items:
        take = budget.take(MAX_SECOND_READS)
        checks = second_reads(part.text, items, g, checker=checker, cap=take)
    agree = agreement(set(ids), read)
    decision = graph_status(part.text, g, ranked, result.labels, checks, agree, linked,
                            receipt_complete=receipt_complete, precedence_on=precedence_on)
    cards = _cards(part, g, result.labels, checks, decision)
    done = part.model_copy()
    done.status, done.conflict, done.reason = decision.status, decision.conflict, decision.reason
    done.card_ids = [c.id for c in cards]
    info = _info(g, linked, ranked, decision, agree, read, result, checks)
    events = [PartLinked(part.id, [g.nodes[e]["name"] for e in linked.entities]),
              PathFound(part.id, _labels(g, decision.path, names), decision.scenario)]
    return GraphOutcome(done, cards, banners, info, events)


def _cards(part: Part, g: nx.MultiDiGraph, labels: dict, checks: dict, decision: Decision) -> list[Card]:
    cards = []
    for rid, item in sorted(labels.items()):
        if item.label not in _CARD:
            continue
        d = g.nodes[rid]
        check, answer = checks.get(rid, ("not_run", None))
        cards.append(Card(
            id=f"{part.id}-c{len(cards) + 1}", part=part.id, relation=_CARD[item.label],
            weakener_type="exception" if item.label != "agrees" and attached_exceptions(g, rid) else None,
            quote=d["quote"], doc=d["doc"], page=d["page"], boxes=d["box"], box_status=d["box_status"],
            why=item.why or item.label, check=check, check_answer=answer, controls=rid in decision.deciding))
    return cards


def _labels(g: nx.MultiDiGraph, nodes: Sequence[str], names: dict[str, str]) -> list[str]:
    out = []
    for n in nodes:
        d = g.nodes[n]
        out.append(d["name"] if d["kind"] == "entity" else f"{names.get(d['doc'], d['doc'])} p{d['page']}")
    return out


def _info(g, linked, ranked, decision: Decision, agree, read, result, checks) -> dict:
    return {
        "scenario": decision.scenario, "tier": decision.tier, "agreement": agree.flag,
        "walk_only": list(agree.walk_only), "read_only": list(agree.read_only),
        "deciding": list(decision.deciding), "path": list(decision.path),
        "linked": dict(linked.entities), "rejected": {"link": linked.rejected, "compare": result.dropped,
                                                      **dict(read.rejected)},
        "paths": [list(p.nodes) for p in ranked], "second_reads": dict(Counter(c for c, _ in checks.values())),
        "checks": {k: {"check": c, "answer": a} for k, (c, a) in checks.items()},
    }
