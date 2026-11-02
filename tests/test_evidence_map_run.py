"""PROOFGRAPH_EVIDENCE_MAP run path: every candidate labelled by the model, status from all cards. No network."""

import re

import pytest

from app.viewer.render import render
from proofgraph.review import run as run_mod
from proofgraph.review.ingest import Word
from proofgraph.review.models import Doc, Page, Part, Review
from proofgraph.review.relate import PageText
from proofgraph.review.run import _assemble
from proofgraph.spend import SpendCapReached

FLAG = "PROOFGRAPH_EVIDENCE_MAP"
CLAIM = "The supplier delivers widgets within 30 days."
PAGES = {
    "dB": "Date: 2026-03-10\nThe supplier delivers widgets within 45 days of the order.",
    "dA": "Date: 2026-01-05\nThe supplier delivers widgets within 30 days of the order.",
    "dC": "Date: 2026-05-20\nPer the letter dated March 3, 2024, the supplier delivers widgets later.\n"
          "The supplier lists widgets in the catalogue.",
}
NAMES = {"dA": "A.pdf", "dB": "B.pdf", "dC": "C.pdf"}


def _words(text):
    out = []
    for y, line in enumerate(text.split("\n")):
        for x, w in enumerate(line.split()):
            out.append(Word(w, (x * 20, y * 20, x * 20 + 18, y * 20 + 18)))
    return out


TEXTS = [PageText(d, 1, t) for d, t in PAGES.items()]
WORDS = {(d, 1): _words(t) for d, t in PAGES.items()}


class Muse:
    def __init__(self, labels=None, exc=None):
        self.labels, self.exc = labels, exc

    def structured(self, prompt, model):
        if self.exc:
            raise self.exc
        return model.model_validate({"labels": self.labels(prompt)})


def _ids(prompt):
    return [(k, d, t) for k, d, t in re.findall(r"\[(k\d+) \| (\S+) p1\]\n((?:\| .*\n?)+)", prompt)]


def _label(rule):
    def make(prompt):
        out = []
        for kid, doc, text in _ids(prompt):
            rel = rule(doc, text)
            out.append({"id": kid, "relation": rel, "why": "w",
                        "weakener_type": "time" if rel in ("contradicts", "weakens") else None})
        return out
    return make


def _by_text(doc, text):
    if "45 days" in text:
        return "contradicts"
    if "30 days of" in text:
        return "supports"
    if "later" in text:
        return "weakens"
    return "irrelevant"


def _run(muse, checker=lambda q, p: "entails"):
    part = Part(id="p1", text=CLAIM, span=(0, len(CLAIM)), status="checking")
    return run_mod._run_part(part, TEXTS, WORDS, {}, [], muse, checker, NAMES)


@pytest.fixture(autouse=True)
def on(monkeypatch):
    monkeypatch.setenv(FLAG, "1")


def test_map_orders_cards_by_date_and_drops_irrelevant():
    out = _run(Muse(_label(_by_text)))
    items = out.part.evidence_map
    cards = {c.id: c for c in out.cards}
    assert [cards[i.card_id].doc for i in items if i.kind == "card"] == ["dA", "dB", "dC"]
    assert [i.date for i in items if i.kind == "card"] == ["2026-01-05", "2026-03-10", "2026-05-20"]
    assert len(out.cards) == 3 and all("catalogue" not in c.quote for c in out.cards)
    assert out.part.map_counts["examined"] - out.part.map_counts["relevant"] == 1


def test_referenced_not_supplied_node():
    items = _run(Muse(_label(_by_text))).part.evidence_map
    ref = [i for i in items if i.kind == "referenced"]
    assert len(ref) == 1 and ref[0].ref_doc == "dC" and ref[0].ref_page == 1


def test_status_from_all_cards_and_conflict():
    out = _run(Muse(_label(_by_text)))
    assert (out.part.status, out.part.conflict) == ("contradicted", True)
    only = _run(Muse(_label(lambda d, t: "contradicts" if "45 days" in t else "irrelevant")))
    assert (only.part.status, only.part.conflict) == ("contradicted", False)


def test_second_check_disagreement_does_not_change_contradicted():
    out = _run(Muse(_label(_by_text)), checker=lambda q, p: "entails" if "45 days" in q else "not_mentioned")
    assert out.part.status == "contradicted"
    assert any(c.check == "disagrees" and c.relation == "contradicts" for c in out.cards)


def test_bad_and_missing_ids_are_handled():
    def labels(prompt):
        good = _label(_by_text)(prompt)
        return [{"id": "zzz", "relation": "supports", "why": "x"}] + good[:1] + good[:1]

    out = _run(Muse(labels))
    assert len(out.cards) <= 1 and out.part.status != "error"
    assert out.part.map_counts["unlabelled"] >= 1


def test_failure_is_error_part():
    out = _run(Muse(exc=SpendCapReached("cap")))
    assert out.part.status == "error" and out.banners[0].kind == "cap"
    out = _run(Muse(exc=ValueError("bad")))
    assert out.part.status == "error" and "not the second check" in out.part.reason


def test_flag_off_uses_relate_path(monkeypatch):
    monkeypatch.delenv(FLAG)
    out = _run(Muse(exc=AssertionError("labeller must not run")))
    assert out.part.evidence_map is None and out.part.status == "error"  # relate path failed on fake


def test_render_no_duplicate_cards_and_irrelevant_never_shown():
    out = _run(Muse(_label(_by_text)))
    part = out.part
    docs = [Doc(id=d, name=NAMES[d], pages=[Page(n=1, kind="text_layer", png="x", w=10, h=10, readable=True)])
            for d in PAGES]
    review = _assemble("c", type("M", (), {"settings": type("S", (), {"muse_model": "m"})()})(),
                       docs, {}, [part], out.cards, [])
    review = Review.model_validate_json(review.review.model_dump_json())
    html = render(review)
    body = html.split('<script type="application/json"')[0]
    ids = re.findall(r'data-card-id="([^"]+)"', body)
    assert len(ids) == len(set(ids)) == 3
    assert "catalogue" not in body
    assert "1 matched passages were judged not to bear on this part by the labelling step." in html
    assert all(i.card_id in {c.id for c in review.cards} for i in review.parts[0].evidence_map if i.kind == "card")


# ---- semantic read: a passage that shares no claim word is added to the candidates and labelled like any other

HIDDEN = "Any carrier handover must complete inside 45 hours after dispatch."


class SuggestMuse(Muse):
    def __init__(self, labels, pick=None, exc=None):
        super().__init__(labels)
        self.pick, self.rexc = pick, exc

    def structured(self, prompt, model):
        if model.__name__ == "Relate":
            if self.rexc:
                raise self.rexc
            return model.model_validate(self.pick)
        return super().structured(prompt, model)


def _hidden_run(muse, monkeypatch=None):
    texts = TEXTS + [PageText("dD", 1, "Date: 2026-02-02\nUnrelated heading.\n" + HIDDEN)]
    words = dict(WORDS)
    words[("dD", 1)] = _words(texts[-1].text)
    part = Part(id="p1", text=CLAIM, span=(0, len(CLAIM)), status="checking")
    return run_mod._run_part(part, texts, words, {}, [], muse, lambda q, p: "entails", {**NAMES, "dD": "D.pdf"})


def _pick(quote=HIDDEN, rel="contradicts", doc="dD"):
    return {"relation": rel, "weakener_type": "time", "quote": quote, "doc": doc, "page": 1, "why": "w"}


def _rule(doc, text):
    return "contradicts" if "45 hours" in text else _by_text(doc, text)


def test_suggested_passage_joins_map_and_drives_status():
    out = _hidden_run(SuggestMuse(_label(_rule), _pick()))
    assert any(c.doc == "dD" and c.relation == "contradicts" for c in out.cards)
    assert out.part.map_counts["suggested"] == 1
    only = _hidden_run(SuggestMuse(_label(lambda d, t: "contradicts" if "45 hours" in t else "irrelevant"), _pick()))
    assert (only.part.status, len(only.cards)) == ("contradicted", 1)


def test_suggested_passage_can_be_labelled_irrelevant():
    out = _hidden_run(SuggestMuse(_label(_by_text), _pick()))
    assert all(c.doc != "dD" for c in out.cards) and out.part.map_counts["suggested"] == 1


def test_no_suggestion_behaves_as_before():
    base = _hidden_run(Muse(_label(_rule)))  # relate call fails validation and is ignored
    assert base.part.map_counts["suggested"] == 0 and all(c.doc != "dD" for c in base.cards)
    for pick in (_pick(rel="set_aside"), _pick(quote=""), _pick(quote="not on the page at all"), _pick(doc="zz")):
        out = _hidden_run(SuggestMuse(_label(_rule), pick))
        assert out.part.map_counts["suggested"] == 0 and [c.quote for c in out.cards] == [c.quote for c in base.cards]


def test_spend_cap_propagates_from_semantic_read():
    out = _hidden_run(SuggestMuse(_label(_rule), exc=SpendCapReached("cap")))
    assert out.part.status == "error"
