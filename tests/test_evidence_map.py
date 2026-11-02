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
