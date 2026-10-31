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


def test_wrapped_quote_gets_one_box_div_per_rectangle(review):
    html = render(review)
    c1 = next(c for c in review.cards if c.id == "c1")
    assert len(c1.boxes) == 2
    divs = re.findall(r'<div class="box [^"]*" data-box-for="([^"]+)"', html)
    assert divs.count("c1") == 2
    assert len(divs) == sum(len(c.boxes) for c in review.cards)


def _script(review):
    html = render(review)
    return html, re.search(r"<script>(.*?)</script>", html, re.S).group(1)


def test_keyboard_uses_one_delegated_keydown_handler(review):
    _, js = _script(review)
    assert js.count('addEventListener("keydown"') == 1
    assert "document.addEventListener" in js


def test_aria_live_region_announces_focused_card(review):
    html, js = _script(review)
    assert re.search(r'aria-live="polite"', html)
    assert "live" in js


def test_card_navigation_keys_are_handled(review):
    _, js = _script(review)
    for key in ('"j"', '"k"', '"["', '"]"', '"Enter"'):
        assert key in js
    assert "scrollIntoView" in js


def test_keys_ignored_while_typing_in_form_fields(review):
    _, js = _script(review)
    for token in ("INPUT", "TEXTAREA", "isContentEditable", "ctrlKey", "metaKey", "altKey"):
        assert token in js


def test_reduced_motion_and_focus_styles(review):
    html, _ = _script(review)
    assert "prefers-reduced-motion: reduce" in html
    assert ".card:focus-visible" in html
    assert "@keyframes flash" in html


def test_hover_focus_and_box_click_link_card_box_and_part(review):
    _, js = _script(review)
    for token in ("mouseover", "focusin", "data-box-for", "data-part-id", "flash"):
        assert token in js
    assert "pointer-events:auto" in render(review).replace(" ", "")


# --- R-19 viewer S3: states, check mark, replay badge, export ---


def _with(review, *, status=None, receipt=None, reason=None, banners=(), readable=True, check=None):
    from proofgraph.review.models import Banner, Receipt

    r = review.model_copy(deep=True)
    part = r.parts[0]
    part.conflict = False
    if status:
        part.status = status
    if receipt is not None:
        part.receipt = Receipt(**receipt)
    part.reason = reason
    r.banners = [Banner(kind=k, text=t) for k, t in banners]
    if not readable:
        r.docs[0].pages[1].readable = False
        r.docs[0].pages[1].kind = "image_only"
        r.docs[0].pages[1].note = "Image only; not transcribed."
    if check:
        r.cards[0].check = check
    return r


@pytest.mark.parametrize(
    "kwargs,css,words",
    [
        (dict(status="checking"), 'class="state-help checking"', "Still being checked"),
        (dict(status="not_found", receipt=dict(pages_read=4)), 'class="state-help not_found"', "Pages read: 4"),
        (dict(status="cannot_tell"), 'class="state-help cannot_tell"', "not enough to decide"),
        (dict(status="error"), 'class="state-help error"', "could not be checked"),
        (dict(readable=False), 'class="pagenote unreadable"', "not transcribed"),
        (dict(banners=[("cap", "Limit hit.")]), 'class="banner cap"', "Spend cap reached"),
        (
            dict(banners=[("checker_unavailable", "Down.")]),
            'class="banner checker_unavailable"',
            "second check was unavailable",
        ),
    ],
)
def test_each_state_renders_distinct_class_and_plain_words(review, kwargs, css, words):
    html = render(_with(review, **kwargs))
    assert css in html
    assert words in html


def test_not_found_shows_why_the_receipt_is_incomplete(review):
    r = _with(review, status="not_found", receipt=dict(pages_read=2, unread=[3, 4]), reason="Pages 3 and 4 are scans.")
    html = render(r)
    assert "Pages read: 2" in html
    assert "Pages not read: 3, 4" in html
    assert "Pages 3 and 4 are scans." in html


@pytest.mark.parametrize(
    "check,words",
    [("agrees", "agrees"), ("disagrees", "disagrees"), ("unavailable", "unavailable"), ("not_run", "not run")],
)
def test_every_check_mark_is_visible_on_the_card(review, check, words):
    html = render(_with(review, check=check))
    assert f'class="mark {check}"' in html
    assert f"Second check {words}" in html


def test_disagrees_mark_is_never_hidden(review):
    html = render(_with(review, check="disagrees"))
    assert re.search(r"\.mark\.disagrees\s*\{[^}]*font-weight", html)
    assert not re.search(r"\.mark[^{]*\{[^}]*display:\s*none", html)


def test_replay_badge_only_when_replay_true(review):
    text = "Replayed from a saved run, not a live check"
    assert text not in render(review)
    assert text not in render(review, replay=False)
    html = render(review, replay=True)
    assert text in html
    assert html.index(text) < html.index("</header>")


def test_missing_page_image_shows_placeholder(review):
    assert "image not available" in render(review, page_images={})


def test_export_is_one_offline_file_with_keyboard_and_live_region(review):
    html = render(review, page_images={("d1", 1): b"\x89PNG fake"}, replay=True)
    assert not re.search(r"https?://", html, re.I)
    assert not re.search(r'\bsrc="(?!data:)', html)
    assert not re.search(r"fetch\(|XMLHttpRequest|import\(|<link|<iframe", html)
    assert 'addEventListener("keydown"' in html
    assert 'aria-live="polite"' in html
    assert "Replayed from a saved run" in html


# --- R-11c: reasons for qualified support, and text contrast ---

UNCONFIRMED = "The second check did not confirm the supporting quote."
NOT_DOUBLE_CHECKED = "Not double-checked"


def _supported_by(review, *checks):
    """P1 backed only by supporting cards with the given second-check marks."""
    r = review.model_copy(deep=True)
    part = r.parts[0]
    part.conflict = False
    part.reason = None
    base = r.cards[0]
    r.cards = [
        base.model_copy(update={"id": f"s{i}", "relation": "supports", "check": ch, "weakener_type": None})
        for i, ch in enumerate(checks)
    ]
    part.card_ids = [c.id for c in r.cards]
    part.status = "cannot_tell" if all(ch == "disagrees" for ch in checks) else "supported"
    return r


def test_disagreed_only_support_shows_reason_once_and_keeps_the_red_card(review):
    html = render(_supported_by(review, "disagrees"))
    assert html.count(UNCONFIRMED) == 1
    assert 'class="reason-line unconfirmed"' in html
    assert 'class="chip cannot_tell"' in html
    assert 'class="mark disagrees"' in html
    assert NOT_DOUBLE_CHECKED not in html


def test_unavailable_support_is_labelled_not_double_checked_and_stays_supported(review):
    html = render(_supported_by(review, "unavailable"))
    assert html.count(NOT_DOUBLE_CHECKED) == 1
    assert 'class="not-double-checked"' in html
    assert 'class="chip supported"' in html
    assert UNCONFIRMED not in html


def test_agreed_support_shows_neither_note(review):
    html = render(_supported_by(review, "agrees"))
    assert UNCONFIRMED not in html and NOT_DOUBLE_CHECKED not in html


def test_one_agree_among_disagrees_shows_neither_note(review):
    html = render(_supported_by(review, "disagrees", "agrees"))
    assert UNCONFIRMED not in html and NOT_DOUBLE_CHECKED not in html


def _luminance(hex_colour):
    h = hex_colour.lstrip("#")
    ch = [int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_disagrees_mark_text_meets_4_5_to_1_in_light_and_dark(review):
    html = render(review)
    css = html[: html.index("</style>")]
    light = re.search(r":root\s*\{([^}]*)\}", css).group(1)
    dark = re.search(r"prefers-color-scheme:\s*dark\)\s*\{\s*:root\s*\{([^}]*)\}", css).group(1)
    assert re.search(r"\.mark\.disagrees\s*\{[^}]*color:\s*var\(--red-text\)", css)
    assert re.search(r"\.mark\.disagrees\s*\{[^}]*font-weight:\s*700[^}]*text-decoration:\s*underline", css)

    def tok(block, name):
        value = re.search(rf"--{name}:\s*#([0-9a-fA-F]{{3,6}})\b", block).group(1)
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        return "#" + value

    assert _contrast(tok(light, "red-text"), tok(light, "bg")) >= 4.5
    assert _contrast(tok(dark, "red-text"), tok(dark, "bg")) >= 4.5
