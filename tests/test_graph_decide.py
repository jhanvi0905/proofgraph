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
    g.graph["docs"]["res"].update(role="memo", date=None)
    g.graph["docs"]["byl"].update(role="other", date=None)
    items = {"res-r1": Item(id="res-r1", label="agrees"), "byl-r2": Item(id="byl-r2", label="conflicts")}
    d = graph_status("p", g, ranked, items, {}, Agreement("agree"), linked)
    assert (d.status, d.scenario) == ("cannot_tell", "S5") and "nothing decides" in d.reason


def test_a_clash_records_the_statements_set_against_each_other_and_nothing_else_does():
    g, ranked, linked = _setup()
    g.graph["docs"]["res"].update(role="memo", date=None)
    g.graph["docs"]["byl"].update(role="other", date=None)
    items = {"res-r1": Item(id="res-r1", label="agrees"), "byl-r2": Item(id="byl-r2", label="conflicts")}
    d = graph_status("p", g, ranked, items, {}, Agreement("agree"), linked)
    assert d.status == "cannot_tell" and d.clash == (("res-r1", "byl-r2"),)
    assert _ask({"res-r1": "agrees", "byl-r2": "conflicts"}).clash == ()  # one document outranks: decided, no clash
    assert _ask({"res-r1": "agrees"}).clash == () and _ask({"byl-r1": "agrees", "byl-r2": "conflicts"}).clash == ()


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


def _clash(g, ranked, linked):
    items = {"res-r1": Item(id="res-r1", label="agrees"), "byl-r2": Item(id="byl-r2", label="conflicts")}
    return graph_status("Connors authorized from May 7, 2026", g, ranked, items, {"res-r1": ("agrees", "entails")},
                        Agreement("agree"), linked)


def test_c3_an_extracted_overrides_edge_wins_before_any_ranking():
    g, ranked, linked = _setup()
    g.graph["docs"]["res"].update(role="other", date=None)
    g.graph["docs"]["byl"].update(role="other", date=None)
    assert _clash(g, ranked, linked).status == "cannot_tell"
    g.add_edge("res-r1", "e:board", "overrides", kind="overrides", tier="page", made_by="model-checked", evidence=[])
    g.add_edge("byl-r2", "e:board", "mentions", kind="mentions", tier="page", made_by="code", evidence=[])
    d = _clash(g, ranked, linked)
    assert (d.status, d.scenario, d.deciding) == ("supported", "S5", ("res-r1",))
    next(iter(g.get_edge_data("res-r1", "e:board").values()))["tier"] = "unclear"  # an unclear edge never wins
    assert _clash(g, ranked, linked).status == "cannot_tell"


def test_c3_same_role_same_subject_the_later_document_wins():
    g, ranked, linked = _setup()
    g.graph["docs"]["res"].update(role="memo", date="May 13, 2026")
    g.graph["docs"]["byl"].update(role="memo", date="March 12, 2025")
    g.add_edge("byl-r2", "e:connors", "mentions", kind="mentions", tier="page", made_by="code", evidence=[])  # same subject
    assert _clash(g, ranked, linked).status == "supported"
    g.graph["docs"]["byl"]["date"] = "June 1, 2026"  # now the other document is later
    assert _clash(g, ranked, linked).status == "contradicted"
    g.graph["docs"]["byl"]["role"] = "other"  # different roles, none in the governance file: no winner
    assert _clash(g, ranked, linked).status == "cannot_tell"


def test_c3_no_role_name_is_special_cased_in_code():
    import inspect

    import proofgraph.review.graph_decide as mod

    src = inspect.getsource(mod)
    for word in ('"bylaws"', '"resolution"', '"memo"', '"contract"', '"amendment"'):
        assert word not in src


def _c4(*, event=True, event_date="May 13, 2026", tier="page", etype="approve_or_adopt", actor="Board",
        part="Connors was authorized from May 7, 2026"):
    """byl-r2 qualifies because byl-r3 (exception) waits on a Board approval; res-r1 may be that approval."""
    g, ranked, linked = _setup()
    g.nodes["byl-r3"].update(awaits="approve_or_adopt", awaits_actor="Board")
    g.nodes["res-r1"].update(stype="event" if event else "fact", event_type=etype, event_date=event_date, actor=actor, tier=tier)
    items = {"byl-r2": Item(id="byl-r2", label="qualifies", why="needs Board approval")}
    return graph_status(part, g, ranked, items, {}, Agreement("agree"), linked)


def test_c4_condition_met_after_the_claimed_date_turns_qualifies_into_contradicted():
    d = _c4()
    assert (d.status, d.scenario, d.deciding) == ("contradicted", "S6", ("byl-r2",))
    assert d.reason.endswith("from 2026-05-13, not 2026-05-07")


def test_c4_keeps_qualifies_when_the_anchor_cannot_be_resolved_or_is_not_later():
    assert _c4(event=False).status == "weakened"  # a fact, not an event
    assert _c4(event_date=None).status == "weakened"  # no date to compare
    assert _c4(etype="appoint").status == "weakened"  # not the event the condition waits on
    assert _c4(actor="the CEO").status == "weakened"  # not the actor it waits on
    assert _c4(tier="unclear").status == "weakened"  # an unaligned quote never decides
    assert _c4(event_date="May 5, 2026").status == "weakened"  # satisfied before the claimed date: no new rule
    assert _c4(part="Connors was authorized.").status == "weakened"  # the claim gives no date to compare
