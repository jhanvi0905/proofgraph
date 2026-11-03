"""run_review with PROOFGRAPH_GRAPH=1: read once, link, walk, compare, second read, decide. No network."""

import json

import pytest
from test_review_run import CLAIM, DOC_ID, PDF, QUOTE, _envelope, _muse

from proofgraph.review.models import Review
from proofgraph.review.run import AllDone, run_review

EXTRACT = {"header": {"role": "contract", "date": None, "parties": [], "defined_terms": [], "vocabulary": ["detention"]},
           "rules": [{"id": "r1", "bearer": "Carrier", "deontic": "is", "action": "detention rate", "value": "$75.00/hour",
                      "value_status": "stated", "page": 1, "quote": QUOTE, "concepts": ["Detention"]}]}
RULE = f"{DOC_ID}-r1"


class RoutedTransport:
    def __init__(self, label="conflicts"):
        self.calls, self.label = [], label

    def create(self, body):
        p = body["input"]
        if "You read ONE document" in p:
            kind, out = "extract", EXTRACT
        elif "You link the parts" in p:
            kind, out = "link", {"parts": [{"part": "p1", "entities": ["e:detention"], "rule_types": ["is"]}]}
        elif "You read a whole packet" in p:
            kind, out = "read", {"cited": [RULE], "extra": []}
        elif "You compare ONE claim part" in p:
            kind, out = "compare", {"part_kind": "instance", "items": [{"id": RULE, "addresses": True, "relation": self.label,
                                                           "exceptions": [], "why": "The rate is $75, not $100."}]}
        else:
            kind, out = "split", {"parts": [{"text": CLAIM}]}
        self.calls.append(kind)
        return _envelope(out)


def _checker(quote, part):
    return "contradicts"


def _drain(events):
    seen = list(events)
    assert isinstance(seen[-1], AllDone)
    return seen[:-1], seen[-1].result


def test_graph_flow_decides_from_the_graph_and_emits_every_event(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    transport = RoutedTransport()
    events, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, transport), checker=_checker))
    kinds = [type(e).__name__ for e in events]
    assert kinds[:3] == ["DocStarted", "DocRead", "PageRead"] and "GraphReady" in kinds
    assert kinds[-3:] == ["PartLinked", "PathFound", "PartDone"]
    review = Review.model_validate_json(result.review.model_dump_json())
    part = review.parts[0]
    assert (part.status, review.status) == ("contradicted", "contradicted")
    card = review.cards[0]
    assert (card.relation, card.box_status, card.check, card.controls) == ("contradicts", "pinned", "agrees", True)
    info = review.graph["parts"]["p1"]
    assert info["scenario"] == "S1" and info["agreement"] == "agree" and info["tier"] == "page"
    assert transport.calls.count("extract") == 1


def test_second_claim_reuses_the_cached_graph(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    first = RoutedTransport()
    muse = _muse(tmp_path, first)
    _drain(run_review(CLAIM, [PDF], muse, checker=_checker))
    second = RoutedTransport()
    events, _ = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, second), checker=_checker))
    assert "extract" not in second.calls
    assert next(e for e in events if type(e).__name__ == "GraphReady").cached is True


def test_a_failed_extraction_is_a_banner_not_a_silent_fallback(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")

    class Down(RoutedTransport):
        def create(self, body):
            if "You read ONE document" in body["input"]:
                raise RuntimeError("upstream down")
            return super().create(body)

    _, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, Down()), checker=_checker))
    assert result.review.status == "error"
    assert any("upstream down" in b.text for b in result.review.banners)


def test_flag_off_has_no_graph_events_and_no_graph_key(monkeypatch, tmp_path):
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    from test_review_run import FakeTransport, GOOD, SPLIT1
    events, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, FakeTransport(SPLIT1, GOOD)), checker=_checker))
    assert {type(e).__name__ for e in events} == {"PartsReady", "PartDone"}
    assert "graph" not in json.loads(result.review.model_dump_json())


def test_a_part_that_times_out_resolves_to_unclear(monkeypatch, tmp_path):
    import time
    from proofgraph.review import run as run_mod
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    monkeypatch.setattr(run_mod, "PART_TIMEOUT_S", 0.2)

    class Slow(RoutedTransport):
        def create(self, body):
            if "You compare ONE claim part" in body["input"]:
                time.sleep(1.0)
            return super().create(body)

    _, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, Slow()), checker=_checker))
    part = result.review.parts[0]
    assert part.status == "cannot_tell" and "timed out" in part.reason


def test_second_reads_are_capped_per_claim():
    from proofgraph.review.graph_run import SecondReadBudget
    b = SecondReadBudget(7)
    assert [b.take(6), b.take(6), b.take(6)] == [6, 1, 0]


def test_graph_cache_key_changes_with_the_extraction_prompt(monkeypatch, tmp_path):
    from proofgraph.review import graph_extract, graph_run
    before = graph_run.extraction_version()
    other = tmp_path / "assert.md"
    other.write_text("a different prompt")
    monkeypatch.setattr(graph_run, "_EXTRACT_PROMPT", other)
    assert graph_run.extraction_version() != before


def test_c2_a_supported_part_is_second_read_even_when_the_claim_budget_is_spent(monkeypatch, tmp_path):
    from proofgraph.review import graph_run

    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    monkeypatch.setattr(graph_run, "MAX_SECOND_READS", 0)
    monkeypatch.setitem(EXTRACT["rules"][0], "stype", "fact")  # a rule cannot support an instance claim (C1)
    seen = []

    def checker(quote, part):
        seen.append(quote)
        return "not_mentioned"

    _, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, RoutedTransport("agrees")), checker=checker))
    assert seen and result.review.parts[0].status == "cannot_tell"


def test_d2_statements_the_full_read_cites_go_to_the_comparator_too():
    from proofgraph.review.full_read import ReadResult
    from proofgraph.review.graph_run import _judged

    ids = ["a", "b"]
    read = ReadResult(cited=("b", "c", "c", "d"))
    assert _judged(ids, read) == ["a", "b", "c", "d"]


def test_every_document_announces_its_start_and_entities_carry_their_document_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    events, _ = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, RoutedTransport()), checker=_checker))
    kinds = [type(e).__name__ for e in events]
    started = next(e for e in events if type(e).__name__ == "DocStarted")
    assert kinds.index("DocStarted") < kinds.index("DocRead") and started.pages == 1 and started.name
    read = next(e for e in events if type(e).__name__ == "DocRead")
    assert started.doc == read.doc
    entities = [e for e in events if type(e).__name__ == "EntityFound"]
    assert entities and all(e.doc_ids and len(e.doc_ids) == e.docs and read.doc in e.doc_ids for e in entities)
    # a cached graph has no reading to announce, but its entities still say which documents they are in
    again, _ = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, RoutedTransport()), checker=_checker))
    assert "DocStarted" not in [type(e).__name__ for e in again]
    assert all(e.doc_ids for e in again if type(e).__name__ == "EntityFound")


def _tiny_graph():
    import networkx as nx

    g = nx.MultiDiGraph()
    g.graph["docs"] = {"a": {"role": "memo", "date": "May 14, 2026"}, "b": {"role": "resolution", "date": "May 13, 2026"},
                       "c": {"role": "other", "date": None}}
    g.add_node("a-r1", kind="rule", doc="a", page=2, quote="Per the CEO letter dated May 7, 2026, she served.", tier="page",
               effective="2026-05-07", event_date="May 13, 2026", stype="event")
    g.add_node("x:2026-05-07:the CEO letter", kind="external", phrase="the CEO letter", date="2026-05-07", status="not supplied")
    g.add_edge("a-r1", "x:2026-05-07:the CEO letter", "cites", kind="cites", tier="page", made_by="code", evidence=[])
    return g


def test_graph_payload_lists_cited_but_not_supplied_documents():
    from proofgraph.review.graph_run import cited_payload

    assert cited_payload(_tiny_graph()) == [
        {"phrase": "the CEO letter", "date": "2026-05-07", "status": "not supplied", "doc": "a", "page": 2,
         "quote": "Per the CEO letter dated May 7, 2026, she served.", "rule": "a-r1"}]


def test_graph_payload_resolves_document_and_statement_dates_to_iso():
    from proofgraph.review.graph_run import dates_payload

    out = dates_payload(_tiny_graph(), ["a-r1"])
    assert out["docs"] == {"a": "2026-05-14", "b": "2026-05-13", "c": None}
    assert out["statements"] == {"a-r1": {"effective": "2026-05-07", "event": "2026-05-13"}}


def test_scenario_names_are_plain_words_for_every_code_the_decision_can_return():
    from proofgraph.review.graph_decide import SCENARIO_NAMES

    assert set(SCENARIO_NAMES) == {f"S{i}" for i in range(1, 9)}
    assert SCENARIO_NAMES["S5"] == "Override or precedence across documents" and SCENARIO_NAMES["S6"] == "Timing and sequence"


def test_flow_review_carries_the_new_display_fields_and_flags_a_documents_clash(monkeypatch, tmp_path):
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    _, result = _drain(run_review(CLAIM, [PDF], _muse(tmp_path, RoutedTransport()), checker=_checker))
    graph = result.review.graph
    assert graph["cited"] == [] and graph["scenario_names"]["S1"] == "Direct statement"
    assert set(graph["dates"]) == {"docs", "statements"} and graph["parts"]["p1"]["documents_disagree"] is False
