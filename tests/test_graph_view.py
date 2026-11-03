"""F4: the audit tick-and-tie review page. Flag off stays byte-identical; flag on draws the workpaper."""

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
               "scenario_names": {"S1": "A rule on the thing the claim names"},
               "parts": {p.id: {"scenario": "S1", "tier": "page", "agreement": "partial", "read_only": ["x-r7"],
                                "path": ["e:consultants", f"{doc}-r2"], "extra_key": 1,
                                "second_reads": {"agrees": 3, "disagrees": 1, "not_run": 2},
                                "rejected": {"link": 1, "compare": 2}, **info} for p in r.parts}}
    return r


def test_flag_off_is_byte_identical_even_with_a_graph(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert render(review) == (FIX / "review_tc40_render_golden.html").read_text()
    assert 'class="grid"' not in render(_graphed(review))


def test_flag_on_without_graph_is_the_old_page(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    assert render(review) == (FIX / "review_tc40_render_golden.html").read_text()


def test_flag_on_draws_the_workpaper(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review)
    html = render(r, ask=True)
    assert '<ol class="trail"' in html and "consultants" in html
    assert html.count('<button type="button" class="cell') == len(r.cards)
    assert re.search(r'class="ref">A-\d+<', html)  # document letter and page
    assert "Reading every page also points at 1 passage that following the links did not reach." in html
    assert "Read 3 pages: 38 statements about who must, may or must not do what, naming 14 people, offices, sections and terms." in html
    assert "3 confirm, 1 do not confirm, 2 not re-checked" in html and "3 that could not be checked against the page" in html
    assert "A rule on the thing the claim names" in html
    for word in ("Quote found on the page", "Read by the model, box approximate", "Not placed on the page, never decides"):
        assert word in html
    assert 'id="ask"' in html and 'id="download"' in html and 'id="ask"' not in render(r)
    assert not re.search(r"<script[^>]*src=", html)


def test_every_answer_has_a_mark_and_a_word(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review)
    r.parts[0].status = "not_found"
    html = render(r)
    assert "Not in these documents" in html and 'data-mark="bracket"' in html
    r.parts[0].status = "cannot_tell"
    assert "Can't tell" in render(r) and 'data-mark="question"' in render(r)
    r.graph["parts"][r.parts[0].id]["documents_disagree"] = True
    html = render(r)
    assert "The documents disagree" in html and 'data-mark="clash"' in html


def test_date_strip_counts_the_days_between_deciding_dates(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review, deciding=["a-r1", "b-r2"])
    r.graph["dates"] = {"docs": {}, "statements": {"a-r1": {"effective": "2026-05-07", "event": None},
                                                    "b-r2": {"effective": None, "event": "2026-05-13"}}}
    html = render(r)
    assert "6 days" in html and "7 May 2026" in html and "13 May 2026" in html
    r.graph["dates"]["statements"]["b-r2"]["event"] = None
    assert 'class="strip"' not in render(r)


def test_path_labels_and_cited_are_used_when_present(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review, path_labels=["Connors", "CMO <b>", "Bylaws p2"])
    r.graph["cited"] = [{"phrase": "the CEO letter of May 7", "date": "2026-05-07", "status": "not supplied", "doc": "x", "page": 1},
                        {"phrase": "the CEO letter of May 7", "date": "2026-05-07", "status": "not supplied", "doc": "y", "page": 2},
                        {"phrase": "the bylaws", "date": "2025-03-12", "status": "supplied"}]
    html = render(r)
    assert "CMO &lt;b&gt;" in html and "<b>" not in html
    assert html.count("the CEO letter of May 7") == 1 and "Cited, not in your documents" in html
    assert "the bylaws" not in html.split("Cited, not in your documents")[1][:400]


def test_missing_or_odd_graph_keys_do_not_break(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = review.model_copy(deep=True)
    r.graph = {"parts": {"nope": {}}}
    assert 'class="grid"' in render(r)
    r.graph = {"stats": {}, "parts": {p.id: {"read_only": None, "path": None, "rejected": None, "second_reads": None} for p in r.parts},
               "cited": [None, 3, {"phrase": None}], "dates": {"statements": None}}
    assert 'class="grid"' in render(r)


def test_share_page_leads_with_the_answer_and_has_no_ask(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _graphed(review)
    html = render(r, share=True)
    assert html.index('class="answer') < html.index('class="claim')
    assert "Checked with ProofGraph against 1 document" in html and "Check your own claim" in html
    assert 'id="ask"' not in html
    assert "Copy review link" in render(r, ask=True, share_url="/r/abc123def456")
