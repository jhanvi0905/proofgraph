"""Decide one claim part from the graph (A5). Pure code: no model, no network.

The model's labels (comparator, second read) are inputs; code combines them with the structure,
which document overrides which (C3), amendments and dates. Outcomes map onto today's part statuses:
supported, contradicted, weakened (qualified), not_found, cannot_tell (unknown, documents disagree,
or the two routes disagree). Unclear statements never decide, a second read that disagrees with
support never makes a part supported (as D38), and "not found" needs the walk and the read both empty.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import networkx as nx

from proofgraph.review.compare import Item, attached_exceptions
from proofgraph.review.full_read import Agreement
from proofgraph.review.models import PartStatus
from proofgraph.review.precedence import governance_rank
from proofgraph.review.query import Linked, Path
from proofgraph.review.graph import canon_name
from proofgraph.review.timeline import _first_date

_TIER_RANK = {"page": 0, "model": 1, "unclear": 2}
_DECIDING = ("conflicts", "qualifies", "agrees")


@dataclass(frozen=True)
class Decision:
    status: PartStatus
    conflict: bool
    reason: str
    tier: str  # the weakest tier on the deciding statements and paths: page, model or unclear
    scenario: str  # S1..S8, read off the shape of the deciding path
    agreement: str
    deciding: tuple[str, ...] = ()
    path: tuple[str, ...] = ()


def _doc(g: nx.MultiDiGraph, rule: str) -> dict:
    return g.graph["docs"].get(g.nodes[rule]["doc"], {})


def _mentions(g: nx.MultiDiGraph, rule: str) -> set[str]:
    return {v for _, v, d in g.out_edges(rule, data=True) if d["kind"] == "mentions"}


def _overrides(g: nx.MultiDiGraph, a: str, b: str) -> bool:
    """A statement of a document says, in its own words, that it overrides something the other statement is about."""
    return any(d["kind"] == "overrides" and d["tier"] != "unclear" and g.has_edge(b, v) and v in _mentions(g, b)
               for _, v, d in g.out_edges(a, data=True))


def _beats(g: nx.MultiDiGraph, a: str, b: str) -> bool | None:
    """C3: does statement ``a`` win over ``b`` (different documents)? Order: an extracted overrides edge; the later
    document of the same role on the same subject; the declared governance order; otherwise nobody (None)."""
    if _overrides(g, a, b) or _overrides(g, b, a):
        return _overrides(g, a, b)
    da, db = _doc(g, a), _doc(g, b)
    if da.get("role") and da.get("role") == db.get("role") and _mentions(g, a) & _mentions(g, b):
        ta, tb = _first_date(da.get("date") or ""), _first_date(db.get("date") or "")
        if ta and tb and ta != tb:
            return ta > tb
    ra, rb = governance_rank(da.get("role", "")), governance_rank(db.get("role", ""))
    if ra is not None and rb is not None and ra != rb:
        return ra < rb
    return None


def overridden(g: nx.MultiDiGraph, rule: str) -> bool:
    """True when a later amendment, with a known effect, replaces or deletes a section this statement is about."""
    about = {v for _, v, d in g.out_edges(rule, data=True) if d["kind"] in ("mentions", "refers_to_section")}
    mine = g.graph["docs"].get(g.nodes[rule]["doc"], {}).get("date")
    for u, v, d in g.edges(data=True):
        if d["kind"] == "supersedes" and v in about and d.get("effect") in ("replaces", "deletes") and d["tier"] != "unclear":
            theirs = g.graph["docs"].get(g.nodes[u]["doc"], {}).get("date")
            if mine and theirs and _first_date(theirs) and _first_date(mine) and _first_date(theirs) >= _first_date(mine):
                return True
    return False


def graph_status(part_text: str, g: nx.MultiDiGraph, ranked: Sequence[Path], labels: Mapping[str, Item],
                 checks: Mapping[str, tuple], agree: Agreement, linked: Linked, *, receipt_complete: bool = True,
                 precedence_on: bool = True) -> Decision:
    path_of = {p.end: p for p in ranked}
    live = {i: it for i, it in labels.items()
            if it.label in _DECIDING and g.nodes[i]["tier"] != "unclear" and not overridden(g, i)}
    notes_overridden = len([i for i in labels if i not in live and labels[i].label in _DECIDING
                            and g.nodes[i]["tier"] != "unclear"])
    flag = agree.flag

    def done(status, reason, deciding=(), conflict=False, scenario=None):
        paths_ = [path_of[i] for i in deciding if i in path_of]
        tiers = [g.nodes[i]["tier"] for i in deciding] + [p.tier for p in paths_]
        tier = max(tiers, key=_TIER_RANK.__getitem__) if tiers else "page"
        shape = scenario or _scenario(g, paths_, deciding)
        best = min(paths_, key=lambda p: (p.hops, p.nodes), default=None)
        return Decision(status, conflict, reason, tier, shape, flag, tuple(deciding), best.nodes if best else ())

    if not live:
        if not linked.entities and flag == "both_empty":
            return done("cannot_tell", "No document mentions the thing the claim is about.", scenario="S7")
        if flag in ("partial", "disagree") and agree.read_only:
            return done("cannot_tell", "The full read cites statements the walk did not reach; open them.")
        unsure = [i for i, it in labels.items() if it.label == "unsure"]
        if unsure or not receipt_complete or flag != "both_empty":
            return done("cannot_tell", "The documents discuss it, but no statement could be read against the claim.")
        return done("not_found", "The documents discuss the thing but never say this, and the full read found nothing.",
                    scenario="S7")

    if precedence_on:
        pro = [i for i, it in live.items() if it.label == "agrees"]
        con = [i for i, it in live.items() if it.label != "agrees"]
        cross = [(p, c) for p in pro for c in con if g.nodes[p]["doc"] != g.nodes[c]["doc"]]
        if pro and con and cross:
            wins = {_beats(g, p, c) for p, c in cross}
            if wins == {True}:
                live = {i: it for i, it in live.items() if i not in {c for _, c in cross}}
            elif wins == {False}:
                live = {i: it for i, it in live.items() if i not in {p for p, _ in cross}}
            else:
                return done("cannot_tell", "Two documents clash and nothing decides which one wins.", tuple(live), scenario="S5")
            return _decide(g, live, checks, done, "S5", part_text, notes_overridden)
    return _decide(g, live, checks, done, None, part_text, notes_overridden)


def _decide(g, live, checks, done, scenario, part_text, overridden_n):
    by = lambda label: [i for i, it in live.items() if it.label == label]  # noqa: E731
    asked = _first_date(part_text)
    late = [i for i in by("agrees") if asked and g.nodes[i].get("effective") and g.nodes[i]["effective"] > asked]
    if by("conflicts"):
        ids = by("conflicts")
        both = bool(by("agrees")) and all(g.nodes[i]["tier"] == "page" for i in ids + by("agrees"))
        return done("contradicted", live[ids[0]].why or "A statement conflicts with the claim.", ids, both, scenario)
    if late:
        return done("contradicted", f"The statement takes effect {g.nodes[late[0]]['effective']}, after the date the claim gives.",
                    late, False, "S6")
    waiting = [(i, d) for i in by("qualifies") if asked and (d := _anchor_date(g, i)) and d > asked]
    if waiting:  # C4: the condition the statement waits on is only met after the date the claim gives
        i, d = waiting[0]
        return done("contradicted", f"{g.nodes[i]['action']} from {d}, not {asked}", [i], False, "S6")
    if by("qualifies"):
        ids = by("qualifies")
        return done("weakened", live[ids[0]].why or "An exception or condition qualifies the claim.", ids, False, scenario)
    ids = by("agrees")
    standing = [i for i in ids if checks.get(i, ("not_run", None))[0] != "disagrees"]
    if standing:
        return done("supported", live[standing[0]].why or "A statement supports the claim.", standing, False, scenario)
    return done("cannot_tell", "The second read did not confirm the supporting statement.", ids, False, scenario)


def _anchor_date(g: nx.MultiDiGraph, rule: str) -> str | None:
    """C4: the date of the event an attached condition or exception waits on, or None when it cannot be resolved.

    The event is a statement the model typed as an event of the same type (and the same actor, when the anchor
    names one) whose quote aligned and whose date was written in full. The earliest such date is the one that
    satisfies the condition."""
    found = []
    for e in attached_exceptions(g, rule):
        anchor, actor = g.nodes[e].get("awaits"), g.nodes[e].get("awaits_actor")
        if not anchor:
            continue
        for i, d in g.nodes(data=True):
            if d.get("kind") == "rule" and d.get("stype") == "event" and d.get("event_type") == anchor and d["tier"] != "unclear":
                if actor and canon_name(actor) not in canon_name(d.get("actor") or ""):
                    continue
                if date := _first_date(d.get("event_date") or ""):
                    found.append(date)
    return min(found) if found else None


def _scenario(g: nx.MultiDiGraph, paths: Sequence[Path], deciding: Sequence[str]) -> str:
    kinds = {k for p in paths for k in p.kinds}
    if any(d["kind"] in ("supersedes", "outranks", "overrides") for i in deciding for _, _, d in g.edges(i, data=True)):
        return "S5"
    if kinds & {"is_a", "holds_office"}:
        return "S4"
    if "defined_by" in kinds:
        return "S3"
    if kinds & {"defeats", "conditions"} or any(g.in_edges(i) and any(d["kind"] in ("defeats", "conditions")
                                                                          for _, _, d in g.in_edges(i, data=True)) for i in deciding):
        return "S2"
    if any(g.nodes[i].get("value_status") == "blank" for i in deciding):
        return "S8"
    return "S1"
