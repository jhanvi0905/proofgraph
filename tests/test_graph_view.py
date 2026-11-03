"""F4: the proof-path review page. Flag off stays byte-identical; flag on draws the graph page."""

import json
import re
from pathlib import Path

import pytest

from app.viewer.render import render
from proofgraph.review.models import Review

FIX = Path(__file__).parent / "fixtures"
FLAG = "PROOFGRAPH_GRAPH"


@pytest.fixture
def review() -> Review:
    return Review.model_validate_json((FIX / "review_tc40.json").read_text())


def _graphed(review: Review, **info) -> Review:
    r = review.model_copy(deep=True)
    doc = r.docs[0].id
    r.graph = {"stats": {"pages": 3, "rules": 38, "entities": 14}, "docs": {doc: {"role": "contract", "date": None}},
               "parts": {p.id: {"scenario": "S1", "tier": "page", "agreement": "partial", "read_only": ["x-r7"],
                                "path": ["e:consultants", f"{doc}-r2"], "extra_key": 1, **info} for p in r.parts}}
    return r


def test_flag_off_is_byte_identical_even_with_a_graph(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    golden = (FIX / "review_tc40_render_golden.html").read_text()
    assert render(review) == golden
    assert "class=\"grid\"" not in render(_graphed(review))


def test_flag_on_without_graph_is_the_old_page(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    assert render(review) == (FIX / "review_tc40_render_golden.html").read_text()


def test_flag_on_draws_the_proof_path_page(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review)
    html = render(r, ask=True)
    assert 'class="u ' in html and r.claim.text.split()[0] in html
    assert '<ol class="crumbs"' in html and "consultants" in html
    assert html.count('<button type="button" class="cell') == len(r.cards)
    assert "The full read also cites 1 passage the walk did not reach." in html
    assert "read from the page" in html and 'id="ask"' in html and 'id="download"' in html
    assert "Read 3 pages: 38 rules about 14 things." in html
    if any(c.relation == "contradicts" and c.controls for c in r.cards):
        assert 'class="circle"' in html
    assert 'id="ask"' not in render(r)
    assert not re.search(r"<script[^>]*src=", html)


def test_path_labels_and_cited_are_used_when_present(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review, path_labels=["Connors", "CMO <b>", "Bylaws p2"])
    r.graph["cited"] = [{"phrase": "the CEO letter of May 7"}, "the CEO letter of May 7 "]
    html = render(r)
    assert "CMO &lt;b&gt;" in html and "<b>" not in html.split("<main>")[0].replace("<br>", "")
    assert html.count("the CEO letter of May 7") == 1 and "Cited, not supplied" in html


def test_missing_or_odd_graph_keys_do_not_break(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = review.model_copy(deep=True)
    r.graph = {"parts": {"nope": {}}}
    assert 'class="grid"' in render(r)
    r.graph = {"stats": {}, "parts": {p.id: {"read_only": None, "path": None} for p in r.parts}}
    assert 'class="grid"' in render(r)
