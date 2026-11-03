import networkx as nx

from graph_fixtures import LETTER_Q, P52_Q, RES_Q, _graph, _reads
from proofgraph.review.graph import load, make_locator, packet_hash, pair_key, save
from proofgraph.review.graph_extract import Relation
from proofgraph.review.relate import PageText

def _kinds(g, u, v):
    return {d["kind"] for _, _, d in g.edges(u, data=True)} if v is None else {
        d["kind"] for d in (g.get_edge_data(u, v) or {}).values()}


def test_tc17_chain_is_connors_cmo_principal_officer_section():
    g = _graph()
    assert _kinds(g, "e:connors", "e:chief medical officer") == {"holds_office"}
    assert _kinds(g, "e:chief medical officer", "e:byl:principal officer") == {"is_a"}
    edge = next(iter(g.get_edge_data("e:connors", "e:chief medical officer").values()))
    assert edge["interim"] is True and edge["tier"] == "page" and edge["evidence"][0]["quote"] == RES_Q
    assert {"refers_to_section"} <= _kinds(g, "byl-r1", "e:byl:section 5.1")
    assert nx.has_path(g.to_undirected(), "e:connors", "byl-r2")


def test_every_edge_has_tier_and_evidence_list():
    for _, _, d in _graph().edges(data=True):
        assert d["tier"] in {"page", "model", "unclear"} and isinstance(d["evidence"], list)
        assert d["kind"] != "unclear" or d["evidence"] == []


def test_exception_links_and_dangling_exception_is_counted():
    g = _graph()
    assert _kinds(g, "byl-r3", "byl-r2") == {"excepts"}
    assert g.graph["rejected"]["dangling_exception"] == 1


def test_relation_not_in_quote_is_unclear_and_counted():
    reads = _reads()
    reads[1].rules[0].rule.relations[0] = Relation(kind="is_a", subject="Chief Medical Officer", object="chief executive")
    g = _graph(reads)
    assert g.graph["rejected"]["relation_not_in_quote"] == 1


def test_fuzzy_statement_lowers_edge_tier():
    g = _graph(_reads("fuzzy"))
    edge = next(iter(g.get_edge_data("e:connors", "e:chief medical officer").values()))
    assert edge["tier"] == "model"


def test_cites_and_defined_by():
    g = _graph()
    ext = [n for n, d in g.nodes(data=True) if d["kind"] == "external"]
    assert len(ext) == 1 and g.nodes[ext[0]]["status"] == "not supplied"
    assert _kinds(g, "e:byl:principal officer", None) >= {"defined_by"}


def test_locator_adds_boxes():
    from proofgraph.review.ingest import Word
    words = {("res", 1): [Word("The", (0, 0, 10, 10)), Word("Board", (11, 0, 50, 10))]}
    reads = _reads()
    reads[0].rules[0].rule.quote = "The Board"
    g = _graph(reads, locator=make_locator(words, {}))
    ev = next(iter(g.get_edge_data("res-r1", "e:connors").values()))["evidence"][0]
    assert ev["box_status"] == "pinned" and ev["box"]


def test_save_load_roundtrip_and_shrink_guard(tmp_path):
    g = _graph()
    key = packet_hash([PageText("a", 1, "x")])
    assert save(g, key, tmp_path)
    back = load(key, tmp_path)
    assert back.number_of_nodes() == g.number_of_nodes() and back.number_of_edges() == g.number_of_edges()
    small = nx.MultiDiGraph()
    small.add_node("e:x", kind="entity")
    assert save(small, key, tmp_path) is False
    assert load(key, tmp_path).number_of_nodes() == g.number_of_nodes()
    assert load("missing", tmp_path) is None


def test_hash_and_pair_key_are_stable_and_order_sensitive():
    a, b = PageText("a", 1, "x"), PageText("b", 1, "y")
    assert packet_hash([a, b]) == packet_hash([b, a]) != packet_hash([a])
    assert pair_key("s1", "s2", "p") != pair_key("s2", "s1", "p")


def test_plural_in_the_quote_still_checks_the_relation():
    from proofgraph.review.graph import _in_quote
    assert _in_quote("principal officer", "The principal officers shall be the CEO and the CMO.")
    assert not _in_quote("principal officer", "The principally minded officer")
