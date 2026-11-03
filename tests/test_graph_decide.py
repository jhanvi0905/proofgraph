import pytest
from graph_fixtures import _graph

from proofgraph.review.compare import Item
from proofgraph.review.full_read import Agreement
from proofgraph.review.graph_decide import graph_status, overridden
from proofgraph.review.precedence import precedence, resolve_dates
from proofgraph.review.query import Linked, paths, rank_paths


def _setup():
    g = _graph()
    precedence(g)
    resolve_dates(g)
    ranked = rank_paths(g, paths(g, ["e:connors"]).paths, "Connors authorized from May 7, 2026")
    return g, ranked, Linked("p1", {"e:connors": "exact"})


def _ask(labels, checks=None, agree="agree", **kw):
    g, ranked, linked = _setup()
    items = {i: Item(id=i, label=l, why="why " + i) for i, l in labels.items()}
    return graph_status("Connors authorized from May 7, 2026", g, ranked, items, checks or {}, Agreement(agree), linked, **kw)


def test_tc17_bylaws_outrank_resolution_so_contradicted_scenario_s5():
    d = _ask({"res-r1": "agrees", "byl-r2": "conflicts"})
    assert (d.status, d.scenario, d.deciding) == ("contradicted", "S5", ("byl-r2",))


def test_same_rank_clash_is_documents_disagree_cannot_tell():
    d = _ask({"byl-r1": "agrees", "byl-r2": "conflicts"})  # same document: conflict wins
    assert d.status == "contradicted"
    g, ranked, linked = _setup()
    g.graph["docs"]["res"]["role"] = "memo"
    g.graph["docs"]["byl"]["role"] = "memo"
    items = {"res-r1": Item(id="res-r1", label="agrees"), "byl-r2": Item(id="byl-r2", label="conflicts")}
    d = graph_status("p", g, ranked, items, {}, Agreement("agree"), linked)
    assert (d.status, d.scenario) == ("cannot_tell", "S5") and "nothing decides" in d.reason


def test_precedence_off_ablation_lets_conflict_win_without_ranking():
    d = _ask({"res-r1": "agrees", "byl-r2": "conflicts"}, precedence_on=False)
    assert d.status == "contradicted"


def test_qualifies_weakened_and_supported_and_disagreed_support():
    assert _ask({"res-r1": "qualifies"}).status == "weakened"
    assert _ask({"res-r1": "agrees"}, {"res-r1": ("agrees", "entails")}).status == "supported"
    d = _ask({"res-r1": "agrees"}, {"res-r1": ("disagrees", "not_mentioned")})
    assert d.status == "cannot_tell" and "second read" in d.reason


def test_unclear_statement_never_decides():
    g, ranked, linked = _setup()
    g.nodes["byl-r2"]["tier"] = "unclear"
    d = graph_status("p", g, ranked, {"byl-r2": Item(id="byl-r2", label="conflicts")}, {}, Agreement("agree"), linked)
    assert d.status != "contradicted"


def test_not_found_needs_both_routes_empty_and_a_complete_receipt():
    g, ranked, linked = _setup()
    irrelevant = {"res-r2": Item(id="res-r2", label="irrelevant")}
    ok = graph_status("p", g, ranked, irrelevant, {}, Agreement("both_empty"), linked)
    assert ok.status == "not_found" and ok.scenario == "S7"
    assert graph_status("p", g, ranked, irrelevant, {}, Agreement("disagree", (), ("byl-r2",)), linked).status == "cannot_tell"
    assert graph_status("p", g, ranked, irrelevant, {}, Agreement("both_empty"), linked, receipt_complete=False).status == "cannot_tell"


def test_unknown_when_nothing_is_linked_and_both_routes_empty():
    g, _, _ = _setup()
    d = graph_status("p", g, [], {}, {}, Agreement("both_empty"), Linked("p1", {}))
    assert (d.status, d.scenario) == ("cannot_tell", "S7") and "No document mentions" in d.reason


def test_date_rule_effective_after_claimed_date_contradicts_s6():
    g, ranked, linked = _setup()
    g.nodes["res-r1"]["effective"] = "2026-05-13"
    d = graph_status("Connors was authorized from May 7, 2026", g, ranked, {"res-r1": Item(id="res-r1", label="agrees")},
                     {}, Agreement("agree"), linked)
    assert (d.status, d.scenario) == ("contradicted", "S6")


def test_amendment_override_removes_statement_only_with_known_effect_and_dates():
    g, _, _ = _setup()
    g.graph["docs"]["amd"] = {"role": "amendment", "date": "June 1, 2026"}
    g.add_node("amd-r1", kind="rule", doc="amd", tier="page")
    g.add_edge("amd-r1", "e:byl:section 5.2", "supersedes", kind="supersedes", effect=None, tier="page", evidence=[])
    assert not overridden(g, "byl-r2")
    next(iter(g.get_edge_data("amd-r1", "e:byl:section 5.2").values()))["effect"] = "replaces"
    assert overridden(g, "byl-r2")
