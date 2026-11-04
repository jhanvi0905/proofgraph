"""The entrance sells the value in the visitor's words. It never describes how the code works."""

import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parents[1] / "app" / "web" / "index.html").read_text(encoding="utf-8")


def _text(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_the_headline_and_lede_say_what_the_visitor_gets():
    h1 = re.search(r"<h1>(.*?)</h1>", PAGE, re.S).group(1)
    lede = re.search(r'<p class="lede">(.*?)</p>', PAGE, re.S).group(1)
    assert h1 == "Check any claim against the documents behind it."
    for must in ("support it, contradict it or say nothing", "exact words on the page", "the clause that disagrees"):
        assert must in lede
    assert "opens the clause that decides" not in PAGE


def test_the_page_never_describes_how_the_code_works():
    text = _text(PAGE)
    for banned in ("Code decides", "from the structure", "statements about who must", "span-grounded", "evidence graph",
                   "Read once", "followed from the things it names"):
        assert banned not in text, banned


def test_how_it_works_is_three_plain_steps_and_the_title_and_description_match_the_headline():
    steps = re.findall(r"<h3>(.*?)</h3>", re.search(r'<div class="frames">(.*?)</div>\s*</section>', PAGE, re.S).group(1))
    assert steps == ["Add the claim and the documents", "Every part is checked against every page", "Each answer comes with its proof"]
    assert "<title>ProofGraph: check any claim against the documents</title>" in PAGE
    assert re.search(r'<meta name="description" content="[^"]*support it, contradict it or say nothing', PAGE)


def test_the_example_is_offered_in_the_first_screen_between_the_lede_and_the_form():
    lede, offer, form = (PAGE.index(s) for s in ('<p class="lede">', 'id="try"', '<form id="start"'))
    assert lede < offer < form  # a visitor with no documents sees it before an empty form
    text = _text(PAGE[offer - 40 : form])
    assert "No documents to hand?" in text and 'id="try-btn"' in PAGE


def test_the_offer_runs_the_same_example_as_the_card_below_and_stays_hidden_when_there_is_none():
    js = (Path(__file__).resolve().parents[1] / "app" / "web" / "app.js").read_text(encoding="utf-8")
    assert "function runSample" in js and js.count("runSample(") >= 3  # defined, used by the card, used by the offer
    assert '$("try").hidden = false' in js and 'id="try" class="try" hidden' in PAGE
