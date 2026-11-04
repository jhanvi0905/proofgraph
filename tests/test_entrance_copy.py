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


def test_the_offer_runs_the_example_and_stays_hidden_when_there_is_none():
    js = (Path(__file__).resolve().parents[1] / "app" / "web" / "app.js").read_text(encoding="utf-8")
    assert "function runSample" in js and js.count("runSample(") >= 2  # defined, used by the offer; there is no separate examples section
    assert '$("try").hidden = false' in js and 'id="try" class="try" hidden' in PAGE


def _ids(html: str) -> set[str]:
    return set(re.findall(r'\bid="([^"]+)"', html))


ENTRANCE = PAGE.split('<section id="entrance"')[1].split('<header id="runbar"')[0]


def test_the_entrance_has_a_top_bar_before_the_hero_and_every_link_in_it_lands_on_a_section():
    assert PAGE.index('class="topnav"') < PAGE.index('class="hero"')
    bar = re.search(r'<header class="topnav" id="top">.*?</header>', PAGE, re.S).group(0)
    links = re.search(r"<nav[^>]*>.*?</nav>", bar, re.S).group(0)
    assert re.findall(r"<a [^>]*>(.*?)</a>", links) == ["Check a claim", "How it works", "What the answers mean", "Questions"]
    for target in re.findall(r'href="#([^"]+)"', bar):
        assert target in _ids(PAGE), target
    assert PAGE.count('class="wordmark"') == 1  # the name lives in the bar, once


def test_sections_have_plain_titles_in_the_order_a_visitor_asks_their_questions():
    assert '<span class="wp">' not in PAGE  # no reference numbers: nothing says what N-3 means
    assert re.findall(r"<h2>(.*?)</h2>", ENTRANCE) == ["How it works", "What the answers mean", "Beyond a citation", "Questions"]


def test_all_five_answers_are_explained_in_one_place():
    block = re.search(r'<section class="band states" id="answers">.*?</section>', PAGE, re.S).group(0)
    for word in ("Supported", "Contradicted", "Qualified", "Not in these documents", "Can't tell"):
        assert word in block, word


def test_the_journey_bar_has_three_steps_that_each_lead_to_a_titled_section():
    bar = re.search(r'<header id="runbar".*?</header>', PAGE, re.S).group(0)
    steps = re.findall(r'<button type="button" class="step" id="st\d" data-go="([^"]+)"', bar)
    assert steps == ["sec-read", "sec-parts", "result"]
    for target in steps:
        assert target in _ids(PAGE), target
    for title in ("Your claim, part by part", "The answer"):
        assert title in PAGE, title
    assert PAGE.count('class="sec-lede"') == 3  # each section says in a sentence what it is


def test_notices_the_review_already_shows_are_not_repeated_above_it_but_errors_stay():
    css = (Path(__file__).resolve().parents[1] / "app" / "web" / "app.css").read_text(encoding="utf-8")
    assert ".live.done .notes li:not(.error) { display: none; }" in css
