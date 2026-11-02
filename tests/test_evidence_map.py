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
    assert html.count("Referenced, not supplied:") == 1
    assert "Referenced, not supplied: the &lt;b&gt;2019&lt;/b&gt; master agreement (cited in 1 place: Bosch_NDA.pdf p2)" in html
    assert "<b>2019</b>" not in html
    assert len(re.findall(r"<article ", html)) == 2  # unknown card id skipped
    assert not re.search(r"resolved|score", html.split('<div class="map">')[1].split("</nav>")[0], re.I)


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
    h = h[h.index('class="ev ev-summary"'):h.index("</nav>")]  # the map; part.reason/conflict text is not ours
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


# ---- UI wave 2: per-relation groups, verdict line, copy fixes ----
from html.parser import HTMLParser  # noqa: E402

from proofgraph.review.models import Claim, Doc, Review as _Review, Run  # noqa: E402


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


class _Walk(HTMLParser):
    """Collect cards with the number of closed <details> above them, plus group order."""

    def __init__(self):
        super().__init__()
        self.stack, self.cards, self.groups, self.in_script = [], {}, [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" or tag == "style":
            self.in_script += 1
        if tag == "details":
            self.stack.append("open" in a)
            if "map-group" in (a.get("class") or ""):
                self.groups.append((a.get("data-part"), a.get("data-rel"), "open" in a))
        elif tag == "article" and "data-card-id" in a:
            self.cards[a["data-card-id"]] = sum(not o for o in self.stack)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.in_script -= 1
        if tag == "details":
            self.stack.pop()


def _walk(html):
    w = _Walk()
    w.feed(html)
    return w


def _ui_html(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    return render(_ui_review())


def test_groups_order_defaults_and_two_clicks(monkeypatch):
    h = _ui_html(monkeypatch)
    w = _walk(h)
    p1 = [(r, o) for p, r, o in w.groups if p == "p1"]
    assert p1 == [("weakens", True), ("supports", False)]
    assert [(r, o) for p, r, o in w.groups if p == "p3"] == [("contradicts", True)]
    vis = lambda pid: sorted(c for c, n in w.cards.items() if n == 0 and c in {x.id for x in _ui_review().cards if x.part == pid})
    assert vis("p3") == ["k0", "k1", "k2"]  # Contradicts: first 3 open
    assert [c for c in vis("p1") if c.startswith("w")] == ["w1", "w2"]  # Weakens: first 2
    assert not [c for c in vis("p1") if c.startswith("s")]  # Supports collapsed
    assert set(w.cards) == {c.id for c in _ui_review().cards}  # nothing lost
    assert max(w.cards.values()) <= 2


def test_sole_unsettled_contradiction_is_not_hidden(monkeypatch):
    w = _walk(_ui_html(monkeypatch))
    assert w.cards["c1"] == 0


def test_group_header_counts_equal_cards(monkeypatch):
    h = _ui_html(monkeypatch)
    sec = h.split('data-rel="weakens"')[1].split('data-rel="supports"')[0]
    assert "Weakens (4): 3 confirmed by a second read of its quote alone, 1 need other passages to settle." in sec
    assert len(re.findall(r"<article ", sec)) == 4
    assert "Show all 3 supporting passages" in h and ">Show all 3<" in h


def test_one_class_note_and_short_badges_in_map_mode(monkeypatch):
    h = _ui_html(monkeypatch)
    assert 'class="reason-line check-answer"' not in h  # the long note is a tooltip, not a paragraph per card
    assert h.count('class="ev map-note"') == 3  # p1 weakens, p1 supports, p2 contradicts: one per class, not per card


def test_dates_and_labels(monkeypatch):
    h = _ui_html(monkeypatch)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    assert ">Undated<" not in body and "inferred from in passage" not in body
    assert "No date found in this passage" in body and "March 1, 2024 · inferred from the passage" in body
    assert "Dates are inferred from the text, not legal dates." in body


def test_verdict_line_facts_only_with_reveal_links(monkeypatch):
    h = _ui_html(monkeypatch)
    line = h.split('class="ev verdict-parts"')[1].split("</ul>")[0]
    assert 'data-reveal="c1"' in line and 'data-reveal="k0"' in line and 'data-reveal="w1"' in line
    assert "1 passage, second read not settled" in line
    assert "worst" not in line.lower() and "strongest" not in line.lower()
    assert "Bylaws.pdf, p1" in line and "0-Bylaws" not in line


def test_reference_marker_once_per_packet(monkeypatch):
    h = _ui_html(monkeypatch)
    assert h.count("Referenced, not supplied:") == 1
    assert "cited in 2 places" in h


def test_conflict_wording_and_no_banned_words_anywhere_visible(monkeypatch):
    h = _ui_html(monkeypatch)
    assert "Sources point different ways on this part." in h and "Sources disagree" not in h
    vis = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S).lower()
    for t in BANNED:
        assert t not in vis, t


def test_file_prefix_stripped_in_map_mode_only(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    on = re.sub(r"<script.*?</script>", "", render(_ui_review()), flags=re.S)
    assert "0-Bylaws" not in on and "Bylaws.pdf" in on and "Minutes.pdf" in on
    monkeypatch.delenv(FLAG)
    assert "0-Bylaws.pdf" in re.sub(r"<script.*?</script>", "", render(_ui_review()), flags=re.S)


def test_viewer_js_reveal_only_in_map_mode(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert "function reveal(" not in render(review) and "MAP_JS" not in render(review)
    monkeypatch.setenv(FLAG, "1")
    h = render(_ui_review())
    assert "function reveal(" in h and "[data-reveal]" in h and "MAP_JS" not in h


# ---- Wave 3A: stance map (lanes x dates, undated column, referenced row) ----
class _Stance(HTMLParser):
    """Collect, per part, the stance figure's lanes, cells and marks."""

    def __init__(self):
        super().__init__()
        self.figs, self.cur, self.lane, self.cell, self.order = {}, None, None, None, []
        self.articles, self.tag_order = {}, []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if tag == "article" and "data-card-id" in a:
            self.articles[a["data-card-id"]] = a["data-part"]
        if "map-group" in cls and self.cur is None:
            self.tag_order.append("group")
        if tag == "figure" and "stance" in cls:
            self.cur = self.figs.setdefault(a["data-part"], {"lanes": {}, "refs": [], "attrs": a})
            self.tag_order.append("figure")
        elif self.cur is not None:
            if "st-lane" in cls:
                self.lane = self.cur["lanes"].setdefault(a["data-lane"], {"marks": [], "none": False, "attrs": a})
            elif "st-cell" in cls:
                self.cell = {"undated": "undated" in cls, "date": a.get("data-day")}
            elif "st-none" in cls and self.lane is not None:
                self.lane["none"] = True
            elif "st-ref" in cls:
                self.cur["refs"].append(a)
            elif "st-mark" in cls:
                self.lane["marks"].append({**a, "cell": self.cell, "tag": tag})

    def handle_endtag(self, tag):
        if tag == "figure":
            self.cur = self.lane = self.cell = None


def _stance(h):
    s = _Stance()
    s.feed(h)
    return s


def _count(m):
    return int(m.get("data-count", "1"))


def test_stance_absent_when_flag_off(review, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    assert "stance" not in render(review) and "st-mark" not in render(review)


def test_one_stance_map_per_part_first_above_the_groups(monkeypatch):
    s = _stance(_ui_html(monkeypatch))
    assert set(s.figs) == {"p1", "p2", "p3"}
    h = _ui_html(monkeypatch)
    for pid in ("p1", "p2", "p3"):
        li = h.split(f'data-part-id="{pid}"')[1].split("</li>")[0]
        assert li.index('class="stance') < li.index('class="map-group')


def test_three_lanes_in_order_and_counts_equal_cards(monkeypatch):
    h = _ui_html(monkeypatch)
    s = _stance(h)
    rv = _ui_review()
    for part in rv.parts:
        fig = s.figs[part.id]
        assert list(fig["lanes"]) == ["contradicts", "weakens", "supports"]
        for rel, lane in fig["lanes"].items():
            n = sum(c.relation == rel and c.part == part.id for c in rv.cards)
            assert sum(map(_count, lane["marks"])) == n, (part.id, rel)
            assert (f"({n})" in lane["attrs"]["aria-label"]) and lane["none"] == (n == 0)
    assert "none found" in h


def test_marks_resolve_to_cards_of_their_own_part(monkeypatch):
    h = _ui_html(monkeypatch)
    s = _stance(h)
    seen = []
    for pid, fig in s.figs.items():
        for lane in fig["lanes"].values():
            for m in lane["marks"]:
                assert m["tag"] == "button" and m["type"] == "button"
                assert s.articles[m["data-reveal"]] == pid
                seen.append(m["data-reveal"])
    assert len(seen) == len(set(seen))


def test_shape_fill_and_relation_class(monkeypatch):
    h = _ui_html(monkeypatch)
    s = _stance(h)
    shape = {"contradicts": "diamond", "weakens": "triangle", "supports": "circle"}
    checks = {c.id: c.check for c in _ui_review().cards}
    for fig in s.figs.values():
        for rel, lane in fig["lanes"].items():
            for m in lane["marks"]:
                assert m["data-shape"] == shape[rel] and rel in m["class"].split()
                state = "filled" if checks[m["data-reveal"]] == "agrees" and _count(m) == 1 else "hollow"
                assert state in m["class"].split() or _count(m) > 1


def test_undated_column_and_dates_inferred(monkeypatch):
    s = _stance(_ui_html(monkeypatch))
    c1 = next(m for m in s.figs["p2"]["lanes"]["contradicts"]["marks"] if m["data-reveal"] == "c1")
    assert c1["cell"]["undated"] and "no date found" in c1["aria-label"].lower()
    t1 = next(m for m in s.figs["p2"]["lanes"]["supports"]["marks"] if m["data-reveal"] == "t1")
    assert not t1["cell"]["undated"] and t1["cell"]["date"] == "2024-04-04"
    assert "4 April 2024" in t1["aria-label"] and "inferred from the text" in t1["aria-label"]


def test_aria_label_has_relation_document_page_state_and_no_banned_words(monkeypatch):
    s = _stance(_ui_html(monkeypatch))
    labels = [m["aria-label"] for f in s.figs.values() for ln in f["lanes"].values() for m in ln["marks"]]
    assert labels
    for lab in labels:
        assert lab.split(",")[0] in {"Contradicts", "Weakens", "Supports"}
        assert re.search(r"\.pdf p\d", lab) and ("second read" in lab)
        assert not [b for b in BANNED if b in lab.lower()]
    assert any(lab.startswith("Contradicts, Minutes.pdf p1, no date found, second read not settled") for lab in labels)


def test_merged_cards_show_a_count(monkeypatch):
    s = _stance(_ui_html(monkeypatch))
    w = s.figs["p1"]["lanes"]["weakens"]["marks"]
    merged = [m for m in w if _count(m) > 1]
    assert [m["data-reveal"] for m in merged] == ["w2"] and _count(merged[0]) == 2
    assert "and 1 more" in merged[0]["aria-label"]


def test_many_same_day_marks_collapse_to_a_count(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _ui_review()
    p = r.parts[2]
    cs = []
    for i in range(6):
        c = _card(f"z{i}", "supports", "d1" if i % 2 else "d2", i + 1)
        c.part, c.page = "p3", i + 1
        cs.append(c)
    r.cards += cs
    p.evidence_map += [MapItem(kind="card", card_id=c.id, date="2024-06-01") for c in cs]
    p.card_ids += [c.id for c in cs]
    s = _stance(render(r))
    marks = s.figs["p3"]["lanes"]["supports"]["marks"]
    assert len(marks) == 1 and _count(marks[0]) == 6
    assert marks[0]["data-reveal"] == "z0"
    assert "z0" in s.articles and all(f"z{i}" in s.articles for i in range(6))  # all still reachable below


def test_referenced_row_one_per_distinct_reference(monkeypatch):
    h = _ui_html(monkeypatch)
    s = _stance(h)
    assert len(s.figs["p1"]["refs"]) == 1 and len(s.figs["p2"]["refs"]) == 1 and not s.figs["p3"]["refs"]
    assert "cited in 2 places" in h.split('class="stance')[1]
    assert h.count("Referenced, not supplied:") == 1  # the packet-level marker is untouched


def test_stance_css_is_themed_and_not_colour_only():
    from app.viewer.render import EVIDENCE_CSS
    rules = [r for r in EVIDENCE_CSS.split("}") if ".st-" in r or ".stance" in r]
    assert rules and not re.search(r"#[0-9a-fA-F]{3,6}", "".join(rules))
    assert "focus-visible" in EVIDENCE_CSS and "container-type" in EVIDENCE_CSS


def test_stance_map_survives_an_empty_part(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    r = _ui_review()
    r.parts[0].evidence_map = []
    h = render(r)
    fig = _stance(h).figs["p1"]
    assert all(ln["none"] for ln in fig["lanes"].values())
