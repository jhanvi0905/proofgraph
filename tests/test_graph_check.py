from graph_fixtures import _graph

from proofgraph.review.compare import Item
from proofgraph.review.graph_check import checker_text, second_reads


def test_checker_gets_exactly_statement_with_exception_and_part():
    g, calls = _graph(), []

    def checker(*args, **kw):
        calls.append((args, kw))
        return "contradicts"

    out = second_reads("PART TEXT", [Item(id="byl-r2", label="conflicts")], g, checker=checker)
    (args, kw), = calls
    assert kw == {} and len(args) == 2 and args[1] == "PART TEXT"
    assert args[0] == checker_text(g, "byl-r2") and "Exception or condition: The Board may waive" in args[0]
    for word in ("conflicts", "contradicts", "supports", "relation", "byl-r2"):
        assert word not in args[0]
    assert out["byl-r2"] == ("agrees", "contradicts")


def test_disagreement_unavailable_and_not_run():
    g = _graph()
    labels = [Item(id="byl-r1", label="agrees"), Item(id="byl-r2", label="qualifies"), Item(id="res-r2", label="irrelevant")]

    def checker(quote, part):
        if "principal officer is" in quote or "Exception" in quote:
            raise RuntimeError("down")
        return "not_mentioned"

    out = second_reads("p", labels, g, checker=checker)
    assert out["byl-r2"][0] == "unavailable" and out["res-r2"] == ("not_run", None)
    assert out["byl-r1"] == ("disagrees", "not_mentioned")


def test_cap_prefers_conflicts_and_skips_the_rest():
    g = _graph()
    labels = [Item(id="byl-r1", label="agrees"), Item(id="byl-r2", label="conflicts"), Item(id="res-r1", label="agrees")]
    out = second_reads("p", labels, g, checker=lambda q, p: "entails", cap=1)
    assert out["byl-r2"][0] == "disagrees" and out["byl-r1"] == ("not_run", None) == out["res-r1"]


def test_c2_supported_deciding_statements_are_always_second_read_even_past_the_cap():
    from proofgraph.review.graph_check import confirm_support

    g = _graph()
    labels = {"byl-r1": Item(id="byl-r1", label="agrees"), "res-r1": Item(id="res-r1", label="agrees")}
    checks = {"byl-r1": ("agrees", "entails"), "res-r1": ("not_run", None)}
    asked = []
    out = confirm_support(["byl-r1", "res-r1"], labels, checks, "p", g,
                          checker=lambda q, p: asked.append(q) or "not_mentioned")
    assert len(asked) == 1 and out["res-r1"] == ("disagrees", "not_mentioned") and out["byl-r1"] == ("agrees", "entails")
