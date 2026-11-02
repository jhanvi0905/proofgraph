"""PROOFGRAPH_EVIDENCE_MAP: display-only ordered map. Off by default and byte-identical."""

import json
import re
from pathlib import Path

import pytest

from app.viewer.render import render
from proofgraph.review.models import MapItem, Review

FIX = Path(__file__).parent / "fixtures"
FLAG = "PROOFGRAPH_EVIDENCE_MAP"


@pytest.fixture
def review() -> Review:
    return Review.model_validate_json((FIX / "review_tc40.json").read_text())


def _mapped(review) -> Review:
    r = review.model_copy(deep=True)
    ids = [c.id for c in r.cards]
    r.parts[0].map_counts = {"examined": 12, "relevant": 3, "unlabelled": 1, "matched": 4, "shown": 3}
    r.parts[0].evidence_map = [
        MapItem(kind="card", card_id=ids[0], date="2026-05-07", date_source="the signature block"),
        MapItem(kind="referenced", ref_text="the <b>2019</b> master agreement", ref_doc=r.docs[0].id, ref_page=2),
        MapItem(kind="card", card_id=ids[1]),
        MapItem(kind="card", card_id="nope", date="2026-01-01"),
    ]
    return r


def test_flag_off_is_byte_identical_to_golden(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    golden = (FIX / "review_tc40_render_golden.html").read_text()
    assert render(review) == golden
    assert "class=\"map\"" not in render(_mapped(review))


def test_flag_on_renders_ordered_map(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(_mapped(review))
    assert "Text pages only; 12 passages in 1 documents examined; scans/images not read; may be incomplete." in html
    assert "Dates are inferred from the text, not legal dates." in html
    assert "May 7, 2026 · inferred from the signature block" in html
    first, undated, ref = (html.index(s) for s in ("May 7, 2026", ">Undated<", "Referenced, not supplied"))
    assert first < ref < undated
    assert html.count('<li class="map-undated">Undated</li>') == 1
    assert "Referenced, not supplied: the &lt;b&gt;2019&lt;/b&gt; master agreement (cited in Bosch_NDA.pdf p2)" in html
    assert "<b>2019</b>" not in html
    assert len(re.findall(r'class="map-rel"', html)) == 2  # unknown card id skipped
    assert not re.search(r"resolved|score", html.split('<ol class="map">')[1].split("</ol>")[0], re.I)


def test_saved_json_unchanged_when_none_and_old_json_validates(review):
    d = json.loads((FIX / "review_tc40.json").read_text())
    r = Review.model_validate(d)
    assert r.parts[0].evidence_map is None and r.parts[0].map_counts is None
    assert "evidence_map" not in r.model_dump_json() and "map_counts" not in r.model_dump_json()
    assert "evidence_map" in _mapped(review).model_dump_json()


# ---- UI display helpers (tasks 1, 2, 9, 10) ----
from app.viewer.render import _class_header, _map_items, _part_summary, _summary  # noqa: E402
from proofgraph.review.models import Card, Part  # noqa: E402

BANNED = ["disagree", "failed", "unverified", "wrong", "flagged"]
NAMES = {"d1": "Bylaws.pdf", "d2": "Minutes.pdf", "d3": "Letter.pdf"}


def _card(cid, rel="supports", doc="d1", page=1, check="agrees", answer=None):
    return Card(
        id=cid, part="p1", relation=rel, quote=f"SECRETQUOTE {cid}", doc=doc, page=page,
        box_status="pinned", why=f"SECRETWHY {cid}", check=check, check_answer=answer,
    )


def _tc17():
    """4 supports, 2 contradicts, 1 weakens, 6 irrelevant, 2 of 3 docs, 4 repeated refs -> 1."""
    cards = [
        _card("s1", doc="d1", page=1), _card("s2", doc="d1", page=1), _card("s3", doc="d2", page=5),
        _card("s4", doc="d2", page=9, check="disagrees", answer="not_mentioned"),
        _card("c1", "contradicts", "d1", 3), _card("c2", "contradicts", "d2", 7, check="disagrees"),
        _card("w1", "weakens", "d2", 2, check="unavailable"),
    ]
    dates = {"s1": "2024-03-12", "s2": "2024-03-12", "s3": "2024-04-04", "c1": "2024-03-20"}
    items = [MapItem(kind="card", card_id=c.id, date=dates.get(c.id)) for c in cards]
    for t, page in [("The Master  Agreement.", 1), ("the master agreement", 2), ("THE MASTER AGREEMENT", 3), ("the master agreement,", 4)]:
        items.append(MapItem(kind="referenced", ref_text=t, ref_doc="d1", ref_page=page))
    part = Part(id="p1", text="t", span=(0, 1), status="contradicted", card_ids=[c.id for c in cards],
                evidence_map=items, map_counts={"examined": 13, "relevant": 7, "shown": 7})
    return part, {c.id: c for c in cards}


def test_map_items_dedupes_refs_merges_and_splits_disagreeing():
    part, cards = _tc17()
    v = _map_items(part, cards)
    assert len(v.refs) == 1 and v.refs[0].count == 4
    assert [e.card.id for e in v.entries] == ["s1", "s3", "c1", "w1"]
    assert [c.id for c in v.entries[0].also] == ["s2"]
    assert {e.card.id for e in v.disagreeing} == {"s4", "c2"}
    reachable = {c.id for e in v.entries + v.disagreeing for c in [e.card, *e.also]}
    assert reachable == set(cards)


def test_map_items_merge_stays_inside_one_relation_and_adjacent_needs_same_date():
    cs = [_card("a", "supports", page=1), _card("b", "contradicts", page=1),
          _card("c", "supports", page=2), _card("d", "supports", page=3)]
    dated = {"a": "2024-01-01", "c": "2024-01-01", "d": "2024-02-02"}
    part = Part(id="p1", text="t", span=(0, 1), status="supported",
                evidence_map=[MapItem(kind="card", card_id=c.id, date=dated.get(c.id)) for c in cs])
    v = _map_items(part, {c.id: c for c in cs})
    assert [(e.card.id, [x.id for x in e.also]) for e in v.entries] == [("a", ["c"]), ("b", []), ("d", [])]


def test_summary_only_numbers_names_dates():
    part, cards = _tc17()
    v = _map_items(part, cards)
    s = _summary(v.entries[:2], NAMES)
    assert s == "3 passages from Bylaws.pdf, Minutes.pdf, 12 Mar to 4 Apr 2024"
    assert "SECRET" not in s
    left = re.sub(r"Bylaws\.pdf|Minutes\.pdf|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d+", "", s)
    assert re.fullmatch(r"[ ,]*(passage|passages)? ?from ?,*[ ,]*(to)?[ ,]*", left), left


def test_summary_singular_and_single_date():
    c = _card("x", doc="d1")
    from app.viewer.render import MapEntry
    assert _summary([MapEntry(c, "2024-03-12", None, [])], NAMES) == "1 passage from Bylaws.pdf, 12 Mar 2024"


def test_class_header_template():
    cs = [_card("a", "contradicts"), _card("b", "contradicts", check="disagrees"), _card("c", "contradicts", check="disagrees")]
    assert _class_header("Contradicts", cs) == (
        "Contradicts (3): 1 confirmed by a second read of its quote alone, 2 need other passages to settle."
    )
    assert _class_header("Contradicts", [_card("a", "contradicts")] * 3) == (
        "Contradicts (3): 3 confirmed by a second read of its quote alone."
    )
    assert _class_header("Contradicts", [_card("a", "contradicts", check="disagrees"), _card("b", "contradicts", check="not_run")]) == (
        "Contradicts (2): 1 need other passages to settle, 1 without a second read."
    )


def test_second_read_badges_in_map_mode(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _mapped(review)
    ids = [c.id for c in r.cards]
    r.cards[0].check, r.cards[1].check = "agrees", "disagrees"
    html = render(r)
    assert html.count("Second read of this quote alone: not settled.") == 2  # text + aria-label
    assert html.count("Second read of this quote alone: confirmed.") == 2
    badges = re.findall(r'<span class="(mark[^"]*)" aria-label', html)
    assert len(badges) == 2 and len(set(badges)) == 1 and "disagrees" not in badges[0]


@pytest.mark.parametrize("check", ["agrees", "disagrees", "unavailable", "not_run"])
@pytest.mark.parametrize("answer", [None, "entails", "contradicts", "not_mentioned"])
def test_no_banned_word_in_visible_map_output(review, monkeypatch, check, answer):
    monkeypatch.setenv(FLAG, "1")
    r = _mapped(review)
    for c in r.cards[:2]:
        c.check, c.check_answer = check, answer
    h = render(r)
    h = h[h.index('class="ev ev-summary"'):h.index("</ol>")]  # the map; part.reason/conflict text is not ours
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    for t in BANNED:
        assert t not in h.lower(), t


def test_map_css_has_no_badge_colour_on_check_values():
    from app.viewer.render import EVIDENCE_CSS
    assert ".disagrees" not in EVIDENCE_CSS and ".agrees" not in EVIDENCE_CSS and "underline" not in EVIDENCE_CSS


def test_part_summary_worked_example_and_clause_drop():
    part, cards = _tc17()
    # make counts match the worked example: 4 supports, 2 contradicts, 1 weakens
    cards = dict(cards)
    assert _part_summary(part, cards, NAMES) == (
        "4 supports, 2 contradicts, 1 weakens, 6 irrelevant (hidden), from 2 of 3 documents; 1 document referenced, not supplied"
    )
    part.evidence_map = [m for m in part.evidence_map if m.kind == "card"]
    assert _part_summary(part, cards, NAMES).endswith("from 2 of 3 documents")


def test_part_summary_in_map_render_and_irrelevant_not_rendered(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _mapped(review)
    h = render(r)
    assert 'class="ev ev-summary"' in h and "irrelevant (hidden)" in h
    assert h.count("data-card-id=") >= 1
