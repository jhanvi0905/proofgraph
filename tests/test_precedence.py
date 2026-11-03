import networkx as nx

from proofgraph.review.precedence import amendments, apply_effects, precedence, resolve_dates


def _g(res_date="May 13, 2026", role="resolution"):
    g = nx.MultiDiGraph()
    g.graph["docs"] = {"res": {"role": role, "date": res_date}, "byl": {"role": "bylaws", "date": "March 12, 2025"},
                       "amd": {"role": "amendment", "date": "June 1, 2026"}, "m": {"role": "other", "date": None}}
    g.add_node("e:byl:section 5.2", kind="entity", type="section", docs=["byl"])
    g.add_node("e:res:section 5.2", kind="entity", type="section", docs=["res"])
    g.add_node("e:byl:section 9", kind="entity", type="section", docs=["byl"])
    g.add_node("res-r1", kind="rule", doc="res", page=1, quote="x", tier="page", effective_from="effective as of May 7")
    g.add_node("res-r2", kind="rule", doc="res", page=1, quote="x", tier="page", effective_from="upon adoption")
    g.add_node("byl-r1", kind="rule", doc="byl", page=1, quote="x", tier="page", effective_from=None)
    g.add_node("amd-r1", kind="rule", doc="amd", page=1, tier="page", effective_from="July 1, 2026",
               quote="Section 9 of the Bylaws is hereby amended to read as follows.")
    g.add_node("amd-r2", kind="rule", doc="amd", page=1, tier="page", effective_from=None,
               quote="Section 5.2 is hereby deleted.")
    return g


def test_resolve_dates_upon_adoption_and_year_borrowing():
    d = resolve_dates(_g())
    assert d == {"res-r1": "2026-05-07", "res-r2": "2026-05-13", "byl-r1": None, "amd-r1": "2026-07-01", "amd-r2": None}


def test_upon_adoption_without_doc_date_stays_unresolved():
    assert resolve_dates(_g(res_date=None))["res-r2"] is None


def test_precedence_bylaws_over_resolution_only():
    g = _g()
    assert precedence(g) == [("amd", "res"), ("byl", "res")]
    assert not any(g.has_edge(f"doc:{a}", f"doc:{b}") for a, b in (("m", "res"), ("res", "m"), ("byl", "amd")))


def test_amendment_links_only_unambiguous_section_and_effect_comes_later():
    g = _g()
    found = {a.rule: a for a in amendments(g)}
    assert found["amd-r1"].target == "e:byl:section 9" and found["amd-r1"].linked
    assert found["amd-r2"].target is None and not found["amd-r2"].linked  # section 5.2 exists in two other documents
    edge = next(iter(g.get_edge_data("amd-r1", "e:byl:section 9").values()))
    assert edge["effect"] is None and edge["tier"] == "page"
    assert apply_effects(g, {"amd-r1": "replaces", "x": "bogus"}) == 1
    assert next(iter(g.get_edge_data("amd-r1", "e:byl:section 9").values()))["effect"] == "replaces"


def test_missing_date_makes_supersedes_unclear():
    g = _g()
    g.graph["docs"]["amd"]["date"] = None
    amendments(g)
    assert next(iter(g.get_edge_data("amd-r1", "e:byl:section 9").values()))["tier"] == "unclear"
