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


def test_flag_on_renders_grouped_map(review, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    html = render(_mapped(review))
    assert "Text pages only; 12 passages in 1 documents examined; scans/images not read; may be incomplete." in html
    assert "Dates are inferred from the text, not legal dates." in html
    assert "May 7, 2026 \u00b7 inferred from the signature block" in html
    assert "No date found in this passage" in html and ">Undated<" not in html
    assert html.count('class="gap-line"') == 1
    assert "Not uploaded: the &lt;b&gt;2019&lt;/b&gt; master agreement. Cited 1 time." in html
    assert "<b>2019</b>" not in html
    assert len(re.findall(r"<article ", html)) == 2  # unknown card id skipped
    assert not re.search(r"resolved|score", html.split('data-part-id="')[1].split("</section>")[0], re.I)


def test_saved_json_unchanged_when_none_and_old_json_validates(review):
    d = json.loads((FIX / "review_tc40.json").read_text())
    r = Review.model_validate(d)
    assert r.parts[0].evidence_map is None and r.parts[0].map_counts is None
    assert "evidence_map" not in r.model_dump_json() and "map_counts" not in r.model_dump_json()
    assert "evidence_map" in _mapped(review).model_dump_json()



# ---- Argument ledger: helpers, fixtures ----
from html.parser import HTMLParser  # noqa: E402

import html as _html_mod  # noqa: E402

from app.viewer.render import _map_items, _part_summary  # noqa: E402
from proofgraph.review.models import Card, Claim, Doc, Part, Review as _Review, Run  # noqa: E402

BANNED = ["disagree", "failed", "unverified", "wrong", "flagged"]
NAMES = {"d1": "Bylaws.pdf", "d2": "Minutes.pdf", "d3": "Letter.pdf"}
RULE = "One passage that goes against a claim is enough to count against it."
OLD_TERMS = ["Second read", "referenced, not supplied", "Undated", "Contradicts (", "weakens", "second read", "not settled",
             "Weakened", "Contradicted", "Supported", "box pinned", "labelling step", "not to scale"]


def _card(cid, rel="supports", doc="d1", page=1, check="agrees", answer=None):
    return Card(
        id=cid, part="p1", relation=rel, quote=f"SECRETQUOTE {cid}", doc=doc, page=page,
        box_status="pinned", why=f"SECRETWHY {cid}", check=check, check_answer=answer,
    )


def _ui_review() -> Review:
    """TC17-shaped: 3 parts, 3 documents, unsettled sole contradiction in p2, repeated references in p1 and p2."""
    base = json.loads((FIX / "review_tc40.json").read_text())
    page = base["docs"][0]["pages"][0]
    docs = [Doc(id=i, name=n, pages=[page]) for i, n in (("d1", "0-Bylaws.pdf"), ("d2", "2-Minutes.pdf"), ("d3", "Letter.pdf"))]
    cs, parts = [], []

    def add(pid, cid, rel, doc="d1", pg=1, check="agrees", date=None, src="in passage", answer=None):
        c = _card(cid, rel, doc, pg, check, answer)
        c.part = pid
        c.page = 1
        cs.append(c)
        return MapItem(kind="card", card_id=cid, date=date, date_source=src if date else None)

    def refs():
        return [MapItem(kind="referenced", ref_text=t, ref_doc="d1", ref_page=p)
                for t, p in (("The Master Agreement.", 1), ("the master agreement", 2))]

    m1 = [add("p1", "w1", "weakens", date="2024-03-01"), add("p1", "w2", "weakens", "d2", date="2024-03-02"),
          add("p1", "w3", "weakens", "d2", pg=1, date="2024-03-09"), add("p1", "w4", "weakens", "d1", check="disagrees", answer="not_mentioned"),
          add("p1", "s1", "supports", date="2024-03-12"), add("p1", "s2", "supports", "d2"),
          add("p1", "s3", "supports", "d1", check="disagrees", answer="not_mentioned"), *refs()]
    m2 = [add("p2", "c1", "contradicts", "d2", check="disagrees", answer="not_mentioned"),
          add("p2", "t1", "supports", date="2024-04-04"), *refs()]
    m3 = [add("p3", f"k{i}", "contradicts", ("d1", "d2", "d3", "d1")[i], date=f"2024-05-0{i + 1}") for i in range(4)]
    for pid, text, status, ms, conflict in (("p1", "Part one.", "weakened", m1, False), ("p2", "Part two.", "contradicted", m2, True),
                                            ("p3", "Part three.", "contradicted", m3, False)):
        parts.append(Part(id=pid, text=text, span=(0, 1), status=status, card_ids=[m.card_id for m in ms if m.card_id],
                          evidence_map=ms, map_counts={"examined": 12, "relevant": len(ms), "shown": len(ms)}, conflict=conflict))
    return _Review(version="review-1", review_id="r", claim=Claim(text="A claim.", origin="typed"), status="contradicted",
                   driver_part="p3", run=Run(mode="live", recorded_at="2026-11-03", models={}, cost_usd=0), docs=docs,
                   parts=parts, cards=cs)


def _tc17_review(ref_text="the letter dated May 7, 2026", claim="Connors was continuously authorized from May 7, 2026."):
    """Two parts: p1 casts doubt, p2 has one undated, not-sure contradiction (driver); one document cited, not supplied."""
    r = _ui_review()
    r.claim.text = claim
    r.driver_part = "p2"
    r.parts = r.parts[:2]
    keep = {i for p in r.parts for i in p.card_ids}
    r.cards = [c for c in r.cards if c.id in keep]
    for p in r.parts:
        for it in p.evidence_map:
            if it.kind == "referenced":
                it.ref_text = ref_text
    return r


def _html(r, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    return render(r)


def _ui_html(monkeypatch):
    return _html(_ui_review(), monkeypatch)


def _visible(h):
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    attrs = re.findall(r'(?:aria-label|title)="([^"]*)"', body)
    return _html_mod.unescape(re.sub(r"<[^>]+>", " ", body) + " " + " ".join(attrs))


def _sections(h):
    """part id -> (class, html), in page order."""
    return {m.group(2): (m.group(1), m.group(3)) for m in re.finditer(r'<section class="part ([^"]*)" data-part-id="(\w+)"(.*?)</section>', h, re.S)}


def _rows(chunk):
    """[(classes, card id, aria-expanded, controls, row html)] in order."""
    out = []
    for m in re.finditer(r'<li class="row ([^"]*)">(.*?)</li>', chunk, re.S):
        body = m.group(2)
        btn = re.search(r'<button type="button" class="rowbtn" aria-expanded="(\w+)" aria-controls="([^"]+)"', body)
        out.append((m.group(1), re.search(r'data-card-id="(\w+)"', body).group(1), btn.group(1), btn.group(2), body))
    return out


def _txt(x):
    return _html_mod.unescape(re.sub(r"<[^>]+>", " ", x))


# ---- Structure: regions in order, nothing from the old page ----
def test_regions_in_order_and_nothing_from_the_old_page(monkeypatch):
    h = _html(_tc17_review(), monkeypatch)
    order = ['class="claim"', 'class="verdict', "<h1", f'class="rule"', 'class="why-line"', 'class="gap-line"',
             'data-part-id="p2"', 'data-part-id="p1"', "<footer", 'id="review"']
    at = [h.index(x) for x in order]
    assert at == sorted(at)
    for gone in ("stance", "st-mark", "st-key", "<figure", "legend", "class=\"map", "map-group", "<details", "not to scale",
                 "<nav"):
        assert gone.lower() not in re.sub(r"<style.*?</style>", "", h, flags=re.S).lower(), gone
    assert "We split your claim into parts" not in h


def test_verdict_word_once_outside_part_headers_and_old_vocabulary_gone(monkeypatch):
    h = _html(_tc17_review(), monkeypatch)
    vis = _visible(h)
    assert vis.count("Goes against the claim") == 1
    assert "Casts doubt on the claim" not in vis  # that verdict is not this review's verdict
    for t in OLD_TERMS:
        assert t.lower() not in vis.lower(), t
    assert h.split("<h1")[1].split(">", 1)[1].lstrip().startswith('<span class="gl" aria-hidden="true">')


def test_claim_is_above_the_verdict_and_in_the_users_words(monkeypatch):
    h = _html(_tc17_review(), monkeypatch)
    claim = re.search(r'<p class="claim">(.*?)</p>', h, re.S).group(1)
    assert "Your claim" in claim and "Connors was continuously authorized from May 7, 2026." in claim


def test_rule_line_only_for_goes_against_and_names_the_part(monkeypatch):
    r = _tc17_review()
    h = _html(r, monkeypatch)
    rule = re.search(r'<p class="rule">(.*?)</p>', h, re.S).group(1)
    assert rule.startswith(RULE) and rule.endswith("It is in Part 2.") and h.count(RULE) == 1
    r.status = "weakened"
    assert RULE not in _html(r, monkeypatch)
    one = _tc17_review()
    one.parts = [one.parts[1]]
    one.cards = [c for c in one.cards if c.part == "p2"]
    assert re.search(r'<p class="rule">(.*?)</p>', _html(one, monkeypatch), re.S).group(1) == RULE


# ---- Parts: worst first, numbers kept ----
def test_parts_sorted_worst_first_keep_claim_numbers_and_driver_first(monkeypatch):
    h = _ui_html(monkeypatch)
    s = _sections(h)
    assert list(s) == ["p3", "p2", "p1"]  # driver p3 first among two contradicted, then p2, then weakened p1
    heads = {pid: _txt(re.search(r"<h2.*?</h2>", c, re.S).group(0)) for pid, (_, c) in s.items()}
    assert "Part 3 of 3" in heads["p3"] and "Part 2 of 3" in heads["p2"] and "Part 1 of 3" in heads["p1"]
    assert "Goes against" in heads["p3"] and "Casts doubt" in heads["p1"]
    assert "Part three." in heads["p3"]


def test_single_part_hides_the_part_counter(monkeypatch):
    r = _tc17_review()
    r.parts, r.cards, r.driver_part = [r.parts[1]], [c for c in r.cards if c.part == "p2"], "p2"
    h = _html(r, monkeypatch)
    assert "Part 1 of 1" not in h and 'class="pn"' not in h and "The whole claim" in h


def test_part_headers_are_h2_with_word_and_glyph(monkeypatch):
    s = _sections(_ui_html(monkeypatch))
    for pid, (cls, c) in s.items():
        h2 = re.search(r"<h2.*?</h2>", c, re.S).group(0)
        assert re.search(r'<span class="pv[^"]*"><span class="gl" aria-hidden="true">.</span> [A-Z]', h2)


# ---- Columns ----
def test_every_card_is_one_row_once_in_its_own_part(monkeypatch):
    h = _ui_html(monkeypatch)
    rv = _ui_review()
    s = _sections(h)
    seen = []
    for pid, (_, c) in s.items():
        ids = [r[1] for r in _rows(c)]
        assert set(ids) == {x.id for x in rv.cards if x.part == pid}
        seen += ids
    assert sorted(seen) == sorted(c.id for c in rv.cards)
    assert len(re.findall(r"<article ", h)) == len(rv.cards)


def test_against_and_doubt_are_open_and_uncapped_backs_it_up_is_capped_per_document(monkeypatch):
    r = _ui_review()
    p = next(p for p in r.parts if p.id == "p1")
    for i in range(7):
        c = _card(f"b{i}", "supports", "d1")
        c.part = "p1"
        r.cards.append(c)
        p.evidence_map.append(MapItem(kind="card", card_id=c.id, date="2024-02-01"))
        p.card_ids.append(c.id)
    h = _html(r, monkeypatch)
    c1 = _sections(h)["p1"][1]
    left, right = c1.split('class="col back"')
    assert len(_rows(left)) == 4  # the four casts-doubt cards, none behind a button
    assert 'class="more"' not in left and " hidden>" not in re.sub(r'<div class="panel"[^>]*hidden>', "", left)
    grp = re.search(r'<div class="grp">.*?<ul class="rest"', right, re.S).group(0)
    assert len(_rows(grp)) == 4  # the cap
    assert re.search(r'<button type="button" class="more" aria-expanded="false" aria-controls="[^"]+"[^>]*>Show all 9</button>', right)
    assert right.count("<li ") == 10  # d1: 7 new + s1 + s3, d2: s2 (nothing lost)


def test_first_backs_group_open_others_collapsed_with_aria(monkeypatch):
    c1 = _sections(_ui_html(monkeypatch))["p1"][1].split('class="col back"')[1]
    btns = re.findall(r'<button type="button" class="gbtn" aria-expanded="(\w+)" aria-controls="([^"]+)">', c1)
    assert [b[0] for b in btns] == ["true", "false"]
    for _, cid in btns:
        assert f'id="{cid}"' in c1
    assert re.search(r'id="%s"[^>]*hidden' % btns[1][1], c1) and not re.search(r'id="%s"[^>]*hidden' % btns[0][1], c1)


def test_empty_side_collapses_to_one_line(monkeypatch):
    s = _sections(_ui_html(monkeypatch))
    p3 = s["p3"][1]
    assert "Nothing in the documents backs it up." in p3 and 'class="col back"' not in p3
    r = _ui_review()
    r.parts[0].evidence_map = []
    h = _html(r, monkeypatch)
    assert "No passages to show for this part." in _sections(h)["p1"][1]


# ---- Rows ----
def test_row_shows_real_quote_name_page_date_and_second_check_in_words(monkeypatch):
    c = _sections(_ui_html(monkeypatch))["p2"][1]
    rows = {r[1]: r for r in _rows(c)}
    first = rows["c1"][4]
    vis = re.sub(r'<div class="panel".*', "", first, flags=re.S)
    t = _txt(vis)
    assert "SECRETQUOTE c1" in t and "Minutes" in t and "p1" in t and "No date" in t and "Second check: not sure" in t
    assert 'title="2-Minutes.pdf"' in vis and "SECRETWHY" not in _visible(_ui_html(monkeypatch))
    dated = _txt(re.sub(r'<div class="panel".*', "", rows["t1"][4], flags=re.S))
    assert "4 April 2024" in dated and "Second check: confirmed" in dated and "Bylaws" in dated


def test_second_check_words_for_every_check_value_and_row_class(monkeypatch):
    words = {"agrees": "confirmed", "disagrees": "not sure", "unavailable": "not available", "not_run": "not done"}
    for check, w in words.items():
        r = _ui_review()
        for c in r.cards:
            c.check, c.check_answer = check, ("not_mentioned" if check == "disagrees" else None)
        h = _html(r, monkeypatch)
        rows = [x for _, (_, c) in _sections(h).items() for x in _rows(c)]
        assert rows and all(f"Second check: {w}" in _txt(re.sub(r'<div class="panel".*', "", x[4], flags=re.S)) for x in rows)
        assert all(("nc" in x[0].split()) == (check != "agrees") for x in rows)


def test_row_button_is_keyboard_ready_and_points_at_its_hidden_panel(monkeypatch):
    h = _ui_html(monkeypatch)
    for _, (_, c) in _sections(h).items():
        for cls, cid, exp, ctl, body in _rows(c):
            assert exp == "false" and ctl == f"p-{cid}"
            assert re.search(rf'<div class="panel" id="p-{cid}" hidden>', body)
            art = re.search(r"<article [^>]*>", body).group(0)
            assert f'data-card-id="{cid}"' in art and "data-doc=" in art and "data-page=" in art and "tabindex" in art
            assert "<blockquote>SECRETQUOTE" in body and 'class="close"' in body and 'class="slot"' in body


def test_confirmed_and_dated_rows_come_first_in_a_list(monkeypatch):
    c = _sections(_ui_html(monkeypatch))["p1"][1].split('class="col back"')[0]
    ids = [r[1] for r in _rows(c)]
    assert ids == ["w1", "w2", "w3", "w4"]  # w4 is not sure: last
    r = _ui_review()
    for x in r.cards:
        if x.id == "w1":
            x.check = "disagrees"
    ids = [r_[1] for r_ in _rows(_sections(_html(r, monkeypatch))["p1"][1].split('class="col back"')[0])]
    assert ids[-2:] == ["w1", "w4"] or ids[-1] == "w4"


def test_deciding_passage_leads_its_list(monkeypatch):
    r = _ui_review()
    r.driver_part = "p3"
    ids = [x[1] for x in _rows(_sections(_html(r, monkeypatch))["p3"][1])]
    from app.viewer.render import _decider
    assert ids[0] == _decider(r, {c.id: c for c in r.cards}).id


def test_why_line_is_the_code_chosen_deciding_passage(monkeypatch):
    r = _tc17_review()
    h = _html(r, monkeypatch)
    why = re.search(r'<p class="why-line">(.*?)</p>', h, re.S).group(1)
    c1 = next(c for c in r.cards if c.id == "c1")
    assert 'data-reveal="c1"' in why and c1.quote in why
    assert "Minutes" in why and "p1" in why and "no date found" in why and "second check: not sure" in why and "Part 2" in why
    assert 'title="2-Minutes.pdf"' in why
    assert "Only one passage goes against it, and the second check was not sure." in h.split("<main>")[0]


def test_why_line_for_backs_up_takes_first_confirmed_passage(monkeypatch):
    r = _tc17_review()
    r.status, r.driver_part = "supported", "p1"
    for p in r.parts:
        p.status = "supported"
    for c in r.cards:
        c.relation = "supports"
        c.check = "disagrees" if c.id in ("w1", "w2") else "agrees"
    why = re.search(r'<p class="why-line">(.*?)</p>', _html(r, monkeypatch), re.S).group(1)
    assert 'data-reveal="w3"' in why


def test_gap_line_in_the_verdict_names_the_document_and_settle_clause_needs_a_match(monkeypatch):
    h = _html(_tc17_review(), monkeypatch)
    gap = re.search(r'<p class="gap-line">(.*?)</p>', h, re.S).group(1)
    assert gap.startswith("Not uploaded: the letter dated May 7, 2026.") and "Cited 2 times." in gap
    assert gap.endswith("It is the document that would settle this.")
    assert h.index('class="verdict') < h.index('class="gap-line"') < h.index('class="part ')
    h2 = _html(_tc17_review(ref_text="the Master Agreement", claim="Connors was authorized."), monkeypatch)
    assert "would settle this" not in h2 and "Not uploaded: the Master Agreement" in h2
    r = _tc17_review()
    for p in r.parts:
        p.evidence_map = [m for m in p.evidence_map if m.kind == "card"]
    assert 'class="gap-line"' not in _html(r, monkeypatch)


def test_map_items_dedupes_refs_and_keeps_every_known_card_in_order():
    items = [MapItem(kind="card", card_id="a", date="2024-01-01"), MapItem(kind="card", card_id="zz"),
             MapItem(kind="card", card_id="b")]
    for t, pg in [("The Master  Agreement.", 1), ("the master agreement", 2), ("THE MASTER AGREEMENT", 3)]:
        items.append(MapItem(kind="referenced", ref_text=t, ref_doc="d1", ref_page=pg))
    part = Part(id="p1", text="t", span=(0, 1), status="supported", evidence_map=items)
    v = _map_items(part, {"a": _card("a"), "b": _card("b")})
    assert len(v.refs) == 1 and v.refs[0].count == 3
    assert [(e.card.id, e.date) for e in v.entries] == [("a", "2024-01-01"), ("b", None)]


def test_part_summary_worked_example_and_clause_drop():
    cards = [_card("s1"), _card("s2"), _card("s3", doc="d2"), _card("s4", doc="d2"), _card("c1", "contradicts"),
             _card("c2", "contradicts", "d2"), _card("w1", "weakens", "d2")]
    items = [MapItem(kind="card", card_id=c.id) for c in cards]
    items.append(MapItem(kind="referenced", ref_text="the master agreement", ref_doc="d1", ref_page=1))
    part = Part(id="p1", text="t", span=(0, 1), status="contradicted", evidence_map=items,
                map_counts={"examined": 13, "relevant": 7, "shown": 7})
    cd = {c.id: c for c in cards}
    assert _part_summary(part, cd, NAMES) == (
        "4 back it up, 2 go against it, 1 casts doubt. 6 passages not about this part are hidden. "
        "From 2 of 3 uploaded documents. Mentioned but not uploaded: 1 document."
    )
    part.evidence_map = [m for m in part.evidence_map if m.kind == "card"]
    assert _part_summary(part, cd, NAMES).endswith("From 2 of 3 uploaded documents.")


# ---- Footer, names, copy ----
def test_footer_holds_counts_caveats_second_check_and_nothing_numeric_is_above(monkeypatch):
    h = _html(_tc17_review(), monkeypatch)
    foot = h.split("<footer")[1].split("</footer>")[0]
    assert "documents read" in foot and "not about this part" in foot and "Text pages only" in foot
    assert "Dates are inferred from the text, not legal dates." in foot
    assert "Not sure means it did not reach the same label; the finding still counts." in foot
    assert "not about this part" not in h.split("<footer")[0]
    assert not re.search(r"\d+ (passages|documents)", _txt(h.split("<main>")[0]))


def test_display_names_are_short_and_full_names_are_on_hover(monkeypatch):
    from app.viewer.render import _short_names
    docs = [Doc(id="a", name="IHP_Bylaws_Excerpt_Article_V_Officers.pdf", pages=[]),
            Doc(id="b", name="IHP_Board_Resolution_2026-14.pdf", pages=[]),
            Doc(id="c", name="01_Bosch-Automotive-Service-Solutions-Mutual-Non-Disclosure-Agreement-7-12-17.pdf", pages=[])]
    n = _short_names(docs)
    assert ".pdf" not in "".join(n.values()) and "IHP" not in n["a"] and len(set(n.values())) == 3
    assert all(len(v) <= 30 for v in n.values()) and n["c"].endswith("7-12-17")
    on = re.sub(r"<script.*?</script>", "", _ui_html(monkeypatch), flags=re.S)
    assert "0-Bylaws" not in re.sub(r'title="[^"]*"', "", on) and 'title="0-Bylaws.pdf"' in on
    monkeypatch.delenv(FLAG)
    assert "0-Bylaws.pdf" in re.sub(r"<script.*?</script>", "", render(_ui_review()), flags=re.S)


@pytest.mark.parametrize("check", ["agrees", "disagrees", "unavailable", "not_run"])
@pytest.mark.parametrize("answer", [None, "entails", "contradicts", "not_mentioned"])
def test_no_banned_word_or_old_term_anywhere_visible(monkeypatch, check, answer):
    r = _tc17_review()
    for c in r.cards:
        c.check, c.check_answer = check, answer
    low = _visible(_html(r, monkeypatch)).lower().replace("claim part", "")
    for t in OLD_TERMS + BANNED:
        assert t.lower() not in low, t


def test_no_model_written_text_only_quotes_and_fixed_labels(monkeypatch):
    h = re.sub(r"<script.*?</script>", "", _ui_html(monkeypatch), flags=re.S)
    assert "SECRETWHY" not in h
    assert "SECRETQUOTE" in h


# ---- Boxes and the page image ----
def test_one_click_one_box_per_card_even_for_a_many_line_passage(monkeypatch):
    r = _tc17_review()
    c = next(c for c in r.cards if c.id == "s1")
    c.boxes = [[100, 100 + i * 20, 900, 115 + i * 20] for i in range(20)]
    h = _html(r, monkeypatch)
    assert len(re.findall(r'class="box [^"]*" data-box-for="s1"', h)) == 1
    box = re.search(r'data-box-for="s1" style="([^"]*)"', h).group(1)
    assert "left:10%" in box and "top:10%" in box and "width:80%" in box
    assert all(len(re.findall(rf'data-box-for="{c.id}"', h)) <= 1 for c in r.cards)


def test_flag_off_pages_keep_one_box_per_line(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    c = review.cards[0]
    assert len(re.findall(rf'data-box-for="{c.id}"', render(review))) == len(c.boxes)


def test_pages_wait_in_a_store_and_each_page_exists_once(monkeypatch):
    h = _ui_html(monkeypatch)
    store = h.split('<section class="store"')[1].split("</section>")[0]
    assert store.count('class="page"') == store.count("<div class=\"page\"") >= 1
    assert h.count('class="page"') == store.count('class="page"')


# ---- JS and CSS contracts ----
def test_viewer_js_only_in_map_mode_and_has_no_stance_code(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert "function reveal(" not in render(review) and "MAP_JS" not in render(review)
    monkeypatch.setenv(FLAG, "1")
    h = render(_ui_review())
    assert "function reveal(" in h and "[data-reveal]" in h and "MAP_JS" not in h
    assert "st-list" not in h and "data-opens" not in h
    js = (Path(__file__).parents[1] / "app" / "viewer" / "map.js").read_text()
    assert "aria-expanded" in js and "Escape" in js and "stopImmediatePropagation" in js


def test_ledger_css_contract():
    from app.viewer.render import LEDGER_CSS
    css = LEDGER_CSS
    assert "max-width:1100px" in css and "focus-visible" in css and "prefers-color-scheme:dark" in css
    assert "max-width:720px" in css and "overflow-wrap:anywhere" in css
    assert not [s for s in re.findall(r"font-size:(\d+)px", css) if int(s) < 14]
    assert "legend" not in css.lower() and ".disagrees" not in css and ".agrees" not in css
    dark = css.split("prefers-color-scheme:dark")[1].split("}")[0]
    assert "--l-ink" in dark and "--l-against" in dark
