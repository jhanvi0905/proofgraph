"""The landing page and claim form: static checks on the shipped HTML, JS and CSS."""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "app" / "web"
HTML = (WEB / "index.html").read_text()
JS = (WEB / "app.js").read_text()
CSS = (WEB / "app.css").read_text()


def test_refusals_merged_into_the_three_answers():
    assert 'id="refuses"' not in HTML and 'href="#refuses"' not in HTML
    answers = HTML[HTML.index('id="answers"'):HTML.index('id="checked"')]
    assert "It also refuses before running:" in answers


def test_after_bar_has_one_primary_action():
    after = HTML[HTML.index('id="after"'):HTML.index("</nav>", HTML.index('id="after"'))]
    assert len(re.findall(r'class="btn primary"', after)) == 1
    assert "Check another claim" in after and "Copy link to this result" in after
    assert "Read the code" not in after
    assert 'navigator.clipboard.writeText(url)' in JS and '"/api/review/"' in JS
    assert "?review=" in JS


def test_clash_mark_is_a_not_equal_sign():
    assert 'clash: "M5 9h14M5 15h14M15 5L9 19"' in JS
    assert 'd="M5 9h14M5 15h14M15 5L9 19"' in HTML


def test_back_button_is_named():
    assert re.search(r'id="back"[^>]*aria-label="New check"', HTML)


def test_copy_lines():
    assert "answer questions about a date" in HTML and "check dates" not in HTML
    assert "the examples this page was tested on" in HTML and "regression test" not in HTML
    assert "Files stay on this server. Each check makes a few model calls (a few cents)." in HTML
    assert "<span>Can&rsquo;t settle</span>" in HTML
    assert "For example: The special limit for theft of jewelry is $1,000." in HTML
    assert 'placeholder="The special limit' not in HTML


def test_typed_claim_busy_state_and_errors():
    assert "Checking\\u2026" in JS and "didn\\u2019t answer. Nothing was decided; try again." in JS
    assert "aria-describedby" in JS


def test_mobile_nav_and_touch_targets():
    assert 'class="nav-menu"' in HTML and "<summary>Menu</summary>" in HTML
    assert "min-height: 44px" in CSS and ".c-note { margin: 0 0 .75rem !important; font-size: .875rem" in CSS
    assert len(re.findall(r"^\.result \{ margin-top", CSS, re.M)) == 1
