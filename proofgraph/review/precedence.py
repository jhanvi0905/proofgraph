"""Amendments, document precedence and resolved dates over the evidence graph (A4).

Code finds the candidates (regex on amendment quotes, a role-rank table, header dates); the
comparator only labels an amendment's effect later. Nothing is guessed: a missing role, a missing
date or an ambiguous section leaves the link ``unclear`` or absent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import networkx as nx

from proofgraph.review.timeline import _DATE_RE, _MONTHS, _first_date

RANK = {"bylaws": 3, "contract": 3, "amendment": 3, "resolution": 2, "memo": 1}  # equal rank: no edge
EFFECTS = ("replaces", "adds", "deletes", "restates")
_SEC = r"(?:section|§)\s*(\d+(?:\.\d+)*)"
_AMEND = re.compile(
    rf"(?:amend|replac|delet|restat|supersed)\w*[^.;]{{0,80}}?{_SEC}"
    rf"|{_SEC}[^.;]{{0,60}}?\b(?:is|are|shall\s+be)\s+(?:hereby\s+)?(?:amended|deleted|replaced|restated|superseded)",
    re.I)
_ON_EVENT = re.compile(r"\b(?:upon|on|at)\s+(?:its\s+|their\s+|the\s+)?(?:adoption|approval|ratification|execution|signing)\b", re.I)
_BARE = re.compile(rf"\b(?P<m>{'|'.join(sorted(_MONTHS, key=len, reverse=True))})\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?\b(?!,?\s+\d{{4}})", re.I)


@dataclass(frozen=True)
class Amendment:
    rule: str
    section: str
    target: str | None  # section entity id, when exactly one other document has that section
    linked: bool


def amendments(g: nx.MultiDiGraph) -> list[Amendment]:
    """Add ``supersedes`` edges from amendment statements to the section they change (effect unset)."""
    sections: dict[str, list[str]] = {}
    for n, d in g.nodes(data=True):
        if d.get("kind") == "entity" and d.get("type") == "section":
            sections.setdefault(n.rsplit("section ", 1)[1], []).append(n)
    found = []
    for rid, d in sorted(g.nodes(data=True)):
        if d.get("kind") != "rule" or g.graph["docs"].get(d["doc"], {}).get("role") != "amendment":
            continue
        for m in _AMEND.finditer(d["quote"]):
            num = next(x for x in m.groups() if x)
            options = [s for s in sections.get(num, []) if d["doc"] not in g.nodes[s]["docs"]]
            target = options[0] if len(options) == 1 else None
            if target is None:
                found.append(Amendment(rid, num, None, False))
                continue
            dates = [_doc_date(g, d["doc"]), _doc_date(g, g.nodes[target]["docs"][0])]
            tier = d["tier"] if all(dates) and dates[0] >= dates[1] else "unclear"
            g.add_edge(rid, target, "supersedes", kind="supersedes", effect=None, tier=tier, made_by="code",
                       evidence=[{"doc": d["doc"], "page": d["page"], "quote": d["quote"]}])
            found.append(Amendment(rid, num, target, True))
    return found


def apply_effects(g: nx.MultiDiGraph, effects: dict[str, str]) -> int:
    """Set the comparator's label on each supersedes edge; an unknown label leaves it unset. Returns edges set."""
    n = 0
    for u, v, k, d in g.edges(keys=True, data=True):
        if d["kind"] == "supersedes" and effects.get(u) in EFFECTS:
            g.edges[u, v, k]["effect"] = effects[u]
            n += 1
    return n


def precedence(g: nx.MultiDiGraph) -> list[tuple[str, str]]:
    """``outranks`` edges between document nodes whose role ranks differ. Unknown roles add nothing."""
    docs = g.graph["docs"]
    out = []
    for a in sorted(docs):
        g.add_node(f"doc:{a}", kind="doc", role=docs[a]["role"], date=_doc_date(g, a))
    for a in sorted(docs):
        for b in sorted(docs):
            ra, rb = RANK.get(docs[a]["role"]), RANK.get(docs[b]["role"])
            if ra and rb and ra > rb:
                g.add_edge(f"doc:{a}", f"doc:{b}", "outranks", kind="outranks", tier="model", made_by="code",
                           evidence=[{"doc": a, "role": docs[a]["role"]}, {"doc": b, "role": docs[b]["role"]}])
                out.append((a, b))
    return out


def resolve_dates(g: nx.MultiDiGraph) -> dict[str, str | None]:
    """ISO ``effective`` date per rule: a written date, else "upon adoption" = the document's own date."""
    out: dict[str, str | None] = {}
    for rid, d in g.nodes(data=True):
        if d.get("kind") != "rule":
            continue
        anchor = _doc_date(g, d["doc"])
        out[rid] = g.nodes[rid]["effective"] = _resolve(d.get("effective_from"), anchor)
    return out


def _doc_date(g: nx.MultiDiGraph, doc: str) -> str | None:
    raw = g.graph["docs"].get(doc, {}).get("date")
    return _first_date(raw) if raw else None


def _resolve(text: str | None, anchor: str | None) -> str | None:
    if not text:
        return None
    if iso := _first_date(text):
        return iso
    if anchor and _ON_EVENT.search(text):
        return anchor
    m = _BARE.search(text)
    if m and anchor:  # "May 7" with no year borrows the year of the document's own date
        try:
            return date(int(anchor[:4]), _MONTHS[next(k for k in _MONTHS if k.startswith(m["m"].lower()[:3]))],
                        int(m["d"])).isoformat()
        except ValueError:
            return None
    return None
