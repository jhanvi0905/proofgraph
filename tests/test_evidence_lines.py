"""PROOFGRAPH_EVIDENCE_LINES: display-only disclosure. Off by default and byte-identical."""

import json
import re
from pathlib import Path

import pytest

from app.viewer.render import LIMIT_TEXT, ONE_SHOWN_TEXT, render
from proofgraph.review.absence import AbsencePage, build_receipt
from proofgraph.review.evidence import ONLY_ONE_LISTED, SNIPPET_CHARS, receipt_with_evidence
from proofgraph.review.models import Passage, Receipt, Review
from proofgraph.review.status import part_status

FIX = Path(__file__).parent / "fixtures"
FLAG = "PROOFGRAPH_EVIDENCE_LINES"


@pytest.fixture
def review() -> Review:
    return Review.model_validate_json((FIX / "review_tc40.json").read_text())


def _with_receipt(review, **kw):
    r = review.model_copy(deep=True)
    r.parts[0].receipt = Receipt(pages_read=4, **kw)
    return r


def _full(review, **kw):
    base = dict(matched_passages=3, matched_docs=1, unsearched=[Passage(doc="d1", page=2)],
                uncited_passages=[Passage(doc="d1", page=3, text="Consultants may be <b>authorized</b> in writing"),
                                  Passage(doc="d1", page=4, text="second hit")])
    base.update(kw)
    return _with_receipt(review, **base)


def test_flag_off_is_byte_identical_to_golden(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert render(review) == (FIX / "review_tc40_render_golden.html").read_text()
    monkeypatch.setenv(FLAG, "0")
    assert render(review) == (FIX / "review_tc40_render_golden.html").read_text()


def test_flag_off_ignores_evidence_fields(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert "Word search" not in render(_full(review))
    assert "matched, not assessed" not in render(_full(review))


def test_old_json_without_new_fields_validates(review):
    d = json.loads((FIX / "review_tc40.json").read_text())
    rec = Review.model_validate(d).parts[0].receipt
    assert rec.matched_passages is None and rec.uncited_passages == [] and rec.unsearched == []


def test_flag_on_renders_every_element(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(_full(review))
    assert "Word search matched 3 passages in 1 document. 2 matched passages were not assessed." in html
    assert '<details class="ev ev-matched"><summary>Matched by word search, not assessed</summary>' in html
    assert html.count("matched, not assessed</span>") == 2
    assert "Bosch_NDA.pdf p3:" in html and "Bosch_NDA.pdf p4:" in html
    assert LIMIT_TEXT in html
    assert "Bosch_NDA.pdf p2 are images and were not searched." in html
    assert "no contrary evidence" not in html.lower()


def test_flag_on_qualifier_phrase_in_meta_not_in_chip(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(review)
    assert "· condition · Depends on a condition ·" in html
    chips = re.findall(r'<span class="chip[^>]*>.*?</span>', html)
    assert chips and not any("Depends on" in c for c in chips)
    monkeypatch.delenv(FLAG)
    assert "Depends on a condition" not in render(review)


def test_single_card_note_only_for_single_card_parts(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    assert ONE_SHOWN_TEXT not in render(review)  # P1 has two cards
    one = review.model_copy(deep=True)
    one.parts[0].card_ids = ["c1"]
    one.cards = [c for c in one.cards if c.id == "c1"]
    assert ONE_SHOWN_TEXT in render(one)
    assert ONLY_ONE_LISTED == "Only one passage listed"


def test_no_counts_without_data_but_limit_line_still_shown(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(_with_receipt(review, unread=[2]))
    assert "Word search matched" not in html and "<details" not in html
    assert LIMIT_TEXT in html and "Pages 2 are images and were not searched." in html


def test_one_match_uses_singular_wording(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(_full(review, matched_passages=1, uncited_passages=[Passage(doc="d1", page=3, text="x")]))
    assert "matched 1 passage in 1 document. 1 matched passage was not assessed." in html


def test_everything_is_escaped(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _full(review)
    r.docs[0].name = "<i>n</i>.pdf"
    html = render(r)
    assert "<b>authorized</b>" not in html and "&lt;b&gt;authorized&lt;/b&gt;" in html
    assert "<i>n</i>" not in html and "&lt;i&gt;n&lt;/i&gt;.pdf p3" in html


def test_render_is_deterministic(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _full(review)
    assert render(r) == render(r)


def test_built_receipt_carries_passages_and_never_changes_status(monkeypatch):
    text = "The consultants must be authorized in writing before access. " + "filler words here. " * 30 + \
           "Elsewhere consultants appear again."
    pages = [AbsencePage("d1", 1, text), AbsencePage("d1", 2, None)]
    absence = build_receipt("Consultants are authorized in writing.", pages, [])
    base = Receipt(pages_read=1, unread=[2])
    out = receipt_with_evidence(base, absence, pages)
    assert out.matched_passages == 2 and out.matched_docs == 1
    assert len(out.uncited_passages) == 2
    assert all(len(p.text) <= SNIPPET_CHARS + 3 for p in out.uncited_passages)
    assert out.unsearched == [Passage(doc="d1", page=2)]
    assert part_status([], receipt_complete=absence.complete) == part_status([], receipt_complete=absence.complete)
    assert out.pages_read == base.pages_read and out.unread == base.unread


def test_long_snippet_is_cut(monkeypatch):
    long = "consultants " + "authorized in writing " * 40
    absence = build_receipt("consultants", [AbsencePage("d1", 1, long)], [])
    out = receipt_with_evidence(Receipt(pages_read=1), absence, [AbsencePage("d1", 1, long)])
    assert all(len(p.text) <= SNIPPET_CHARS + 3 for p in out.uncited_passages)
