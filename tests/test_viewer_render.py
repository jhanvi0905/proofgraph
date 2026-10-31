import json
import re
from pathlib import Path

import pytest

from app.viewer.render import render
from proofgraph.review.models import Review

FIXTURE = Path(__file__).parent / "fixtures" / "review_tc40.json"


@pytest.fixture
def review() -> Review:
    return Review.model_validate_json(FIXTURE.read_text())


def test_one_element_per_card(review):
    html = render(review)
    ids = re.findall(r'<[^>]*\bdata-card-id="([^"]+)"', html)
    assert sorted(ids) == sorted(c.id for c in review.cards)


def test_cards_grouped_by_relation(review):
    html = render(review)
    assert html.index("Contradicts") < html.index("Supports")
    assert html.index('data-card-id="c1"') < html.index('data-card-id="c2"')


def test_box_left_is_x_min_over_ten_percent(review):
    html = render(review)
    for card in review.cards:
        for x_min, y_min, x_max, y_max in card.boxes:
            assert f"left:{x_min / 10:g}%" in html
            assert f"top:{y_min / 10:g}%" in html
            assert f"width:{(x_max - x_min) / 10:g}%" in html


def test_no_external_url(review):
    html = render(review, page_images={("d1", 1): b"\x89PNG fake"})
    assert not re.search(r"https?://|//[a-z0-9.-]+\.[a-z]{2,}", html, re.I)
    assert not re.search(r'\b(?:src|href)="(?!#|data:)', html)


def test_conflict_and_doc_note_render(review):
    html = render(review)
    assert 'class="conflict"' in html
    assert "Sources disagree" in html
    assert review.docs[0].note in html


def test_page_image_embedded_as_data_uri(review):
    html = render(review, page_images={("d1", 1): b"abc"})
    assert "data:image/png;base64,YWJj" in html


def test_claim_text_is_escaped(review):
    review.claim.text = "<script>alert(1)</script>"
    assert "<script>alert(1)" not in render(review)


def test_viewer_template_is_valid_json_embedding(review):
    html = render(review)
    m = re.search(r'<script type="application/json" id="review">(.*?)</script>', html, re.S)
    assert json.loads(m.group(1))["review_id"] == review.review_id
