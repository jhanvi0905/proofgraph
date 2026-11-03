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
            kind, out = "compare", {"items": [{"id": RULE, "label": self.label, "why": "The rate is $75, not $100."}]}
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
    assert kinds[:2] == ["DocRead", "PageRead"] and "GraphReady" in kinds
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
