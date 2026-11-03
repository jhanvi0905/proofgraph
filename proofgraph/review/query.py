"""Query side of the evidence graph: link a claim's parts, walk typed paths, rank them.

``link_parts`` attaches each part to entities that exist in the graph (exact name match, then one
Muse Spark call restricted to ids from the packet). ``paths`` walks typed paths with networkx; a third
hop is allowed only along class links, and an entity named in over 25% of the statements is ranked,
not walked through. ``rank_paths`` scores a path by its weakest hop and 0.7 per hop, BM25 on ties.
Deterministic: same graph, same order, every run. Unclear edges are never walked.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path as FilePath

import networkx as nx
from pydantic import BaseModel, Field

from proofgraph.clients.muse import MuseClient
from proofgraph.review.bm25 import bm25_scores
from proofgraph.review.graph import canon_name

CLASS_KINDS = frozenset({"is_a", "holds_office", "defined_by"})
WALK_KINDS = CLASS_KINDS | {"mentions", "refers_to_section", "excepts", "conditions", "supersedes"}
MAX_HOPS = 3
HUB_SHARE = 0.25
HUB_MIN_STATEMENTS = 8  # below this a share of 25% means nothing
HOP_DECAY = 0.7
TOP_PATHS = 8
MAX_STATEMENTS = 30
_TIER_WEIGHT = {"page": 1.0, "model": 0.7}
_TIER_RANK = {"page": 0, "model": 1, "unclear": 2}
_PROMPT = FilePath(__file__).resolve().parents[2] / "prompts" / "link.md"


class _PartLink(BaseModel):
    part: str
    entities: list[str] = Field(default_factory=list)
    rule_types: list[str] = Field(default_factory=list)


class _Linking(BaseModel):
    parts: list[_PartLink] = Field(default_factory=list)


@dataclass(frozen=True)
class Linked:
    part: str
    entities: dict[str, str]  # entity id -> "exact" or "model"
    rule_types: tuple[str, ...] = ()
    rejected: int = 0  # ids or types the model returned that are not in the packet


def _entities(g: nx.MultiDiGraph) -> dict[str, dict]:
    return {n: d for n, d in g.nodes(data=True) if d.get("kind") == "entity"}


def link_parts(parts: Sequence[tuple[str, str]], g: nx.MultiDiGraph, muse: MuseClient) -> dict[str, Linked]:
    """``parts`` is ``(part id, part text)``. No id or term outside the packet survives."""
    ents = _entities(g)
    types = sorted({d["deontic"] for _, d in g.nodes(data=True) if d.get("kind") == "rule"})
    exact = {pid: {e: "exact" for e, d in sorted(ents.items())
                   if re.search(rf"\b{re.escape(canon_name(d['name']))}\b", canon_name(text))}
             for pid, text in parts}
    answer = muse.structured(_link_prompt(parts, ents, types), _Linking, reasoning_effort="low")
    out = {}
    for pid, _ in parts:
        found, bad = dict(exact[pid]), 0
        rules: set[str] = set()
        for item in (i for i in answer.parts if i.part == pid):
            for e in item.entities:
                if e in ents:
                    found.setdefault(e, "model")
                else:
                    bad += 1
            for t in item.rule_types:
                if t in types:
                    rules.add(t)
                else:
                    bad += 1
        out[pid] = Linked(pid, found, tuple(sorted(rules)), bad)
    return out


def _link_prompt(parts, ents: dict[str, dict], types: list[str]) -> str:
    text = _PROMPT.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("prompts/link.md is empty")
    listing = "\n".join(f"{e} | {d['name']} | {d['type']}" for e, d in sorted(ents.items()))
    claim = "\n".join(f"[{pid}] {t}" for pid, t in parts)
    return (f"{text}\n\nRULE TYPES: {', '.join(types) or 'none'}\n\nENTITIES (id | name | type):\n{listing}\n\n"
            f"CLAIM PARTS (data):\n{claim}\n")


@dataclass(frozen=True)
class Path:
    nodes: tuple[str, ...]
    kinds: tuple[str, ...]
    tier: str  # the weakest hop

    @property
    def hops(self) -> int:
        return len(self.kinds)

    @property
    def end(self) -> str:
        return self.nodes[-1]


@dataclass(frozen=True)
class Walk:
    paths: list[Path] = field(default_factory=list)
    hubs: frozenset[str] = frozenset()


def hubs(g: nx.MultiDiGraph) -> frozenset[str]:
    rules = [n for n, d in g.nodes(data=True) if d.get("kind") == "rule"]
    if len(rules) < HUB_MIN_STATEMENTS:
        return frozenset()
    seen: dict[str, set[str]] = {}
    for u, v, d in g.edges(data=True):
        if d["kind"] == "mentions":
            seen.setdefault(v, set()).add(u)
    return frozenset(e for e, rs in seen.items() if len(rs) / len(rules) > HUB_SHARE)


def _view(g: nx.MultiDiGraph) -> tuple[nx.Graph, dict[frozenset, list[tuple[str, str]]]]:
    h, hops = nx.Graph(), {}
    for u, v, d in sorted(g.edges(data=True), key=lambda e: (e[0], e[1], e[2]["kind"])):
        if d["kind"] in WALK_KINDS and d["tier"] != "unclear":
            h.add_edge(u, v)
            hops.setdefault(frozenset((u, v)), []).append((d["tier"], d["kind"]))
    for k in hops:
        hops[k].sort(key=lambda tk: (_TIER_RANK[tk[0]], tk[1]))
    return h, hops


def paths(g: nx.MultiDiGraph, sources: Sequence[str], *, max_hops: int = MAX_HOPS,
          hub_brake: bool = True) -> Walk:
    """Typed paths from entity ids to the rules and definitions that govern them."""
    h, hop = _view(g)
    brake = hubs(g) if hub_brake else frozenset()
    targets = {n for n, d in g.nodes(data=True) if d.get("kind") in ("rule", "definition") and n in h}
    found: dict[tuple[str, ...], Path] = {}
    for src in sorted(set(sources)):
        if src not in h:
            continue
        near = nx.ego_graph(h, src, radius=max_hops)
        for t in sorted(targets & set(near)):
            for nodes in nx.all_simple_paths(near, src, t, cutoff=max_hops):
                chosen = [hop[frozenset(p)][0] for p in zip(nodes, nodes[1:])]
                kinds = tuple(k for _, k in chosen)
                if len(kinds) == 3 and not all(k in CLASS_KINDS for k in kinds[:2]):
                    continue
                if any(n in brake for n in nodes[1:-1]):
                    continue
                tier = max((t_ for t_, _ in chosen), key=_TIER_RANK.__getitem__)
                found[tuple(nodes)] = Path(tuple(nodes), kinds, tier)
    return Walk(sorted(found.values(), key=lambda p: (p.hops, p.nodes)), brake)


def statements(ps: Sequence[Path], g: nx.MultiDiGraph) -> list[str]:
    seen: dict[str, None] = {}
    for p in ps:
        for n in p.nodes:
            if g.nodes[n].get("kind") in ("rule", "definition"):
                seen.setdefault(n)
    return list(seen)


def rank_paths(g: nx.MultiDiGraph, ps: Sequence[Path], part_text: str, *, top: int = TOP_PATHS,
               max_statements: int = MAX_STATEMENTS, decay: float = HOP_DECAY) -> list[Path]:
    """Top paths by weakest hop times ``decay`` per hop, BM25 breaking ties; strongest last."""
    ps = [p for p in ps if p.tier != "unclear"]
    if not ps:
        return []
    bm = bm25_scores(part_text, [g.nodes[p.end].get("quote", "") + " " + g.nodes[p.end].get("action", "") for p in ps])
    keyed = sorted(zip(ps, bm), key=lambda pb: (-_TIER_WEIGHT[pb[0].tier] * decay ** pb[0].hops, -pb[1], pb[0].nodes))
    chosen: list[Path] = []
    for p, _ in keyed:
        if len(chosen) == top:
            break
        if len(statements([*chosen, p], g)) <= max_statements:
            chosen.append(p)
    return chosen[::-1]
