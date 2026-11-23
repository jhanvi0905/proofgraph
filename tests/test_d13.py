"""D13: effective dates are read from the page; a person picks the figure in a multi-amount line.

Each test names the old behaviour it rules out. PDFs are written by tests/pdfgen.py at test time; the proposer
is a fake model, so no key and no recording is needed.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from pdfgen import write_pdf
from proofgraph.model import ModelReply
from proofgraph.propose import printed_date

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
NONE = {"quote": "", "page": 0}


# ---------------------------------------------------------------- item 1: effective dates from printed text


@pytest.mark.parametrize("text, date", [
    ("effective June 1, 1996", dt.date(1996, 6, 1)),
    ("6/1/96", dt.date(1996, 6, 1)),
    ("Effective 12/31/96", dt.date(1996, 12, 31)),
    ("2025-12-31", dt.date(2025, 12, 31)),
    ("Effective Date: 08/11/20 12:01 a.m.", dt.date(2020, 8, 11)),
    ("for taxable years beginning after December 31, 2025", dt.date(2025, 12, 31)),  # "after" is kept, not interpreted
    ("Dec. 31, 2025", dt.date(2025, 12, 31)),
    ("1 June 1996", dt.date(1996, 6, 1)),
])
def test_code_reads_the_one_date_in_a_printed_line(text, date):
    assert printed_date(text) == date


@pytest.mark.parametrize("text", [
    "HO 00 03 04 91",  # an edition is not a date
    "04 91",
    "2/30/96",  # impossible
    "Policy period 6/1/96 to 6/1/99",  # two dates: which one is not decided by code
    "effective upon issue",
    "",
])
def test_no_date_or_more_than_one_reads_as_none(text):
    assert printed_date(text) is None


TITLE = "EXTENDED REPORTING ENDORSEMENT"
FORM = "XX 12 34 05 95"
EFFECTIVE = "Effective 12/31/96 12:01 a.m."
FILLER = ["This endorsement changes the policy. Please read it carefully and keep it",
          "with the policy. All other terms and conditions of the policy remain unchanged."]


@pytest.fixture()
def endorsement(tmp_path) -> Path:
    lines = [(72, 60, FORM), (72, 80, TITLE), (72, 100, EFFECTIVE)] + [(72, 130 + 14 * i, t) for i, t in enumerate(FILLER)]
    (tmp_path / "src").mkdir()
    return write_pdf(tmp_path / "src" / "endorsement.pdf", [lines])


def _wire(effective=None, edition=None):
    return {"form_number": {"quote": FORM, "page": 1}, "edition": edition or NONE, "title": {"quote": TITLE, "page": 1},
            "kind": {"kind": "endorsement", "quote": TITLE, "page": 1}, "amends": NONE, "policy_number": NONE,
            "effective_date": effective or NONE}


class Fake:
    def __init__(self, wire):
        self.wire, self.prompts = wire, []

    def __call__(self, prompt, schema, *, system, template, effort="low"):
        self.prompts.append(prompt)
        w = self.wire(prompt) if callable(self.wire) else self.wire
        return ModelReply(json.dumps(w), "fake", "h", 0, 0, 0, False)


def _client(tmp_path, fake):
    from fastapi.testclient import TestClient

    from app.limit import LiveRunLimit
    from app.server import create_app

    off = LiveRunLimit(runs=0)
    return TestClient(create_app(complete=fake, uploads_dir=tmp_path / "uploads", limit=off, upload_limit=off))


def _upload(c, *paths):
    r = c.post("/api/upload", files=[("files", (p.name, p.read_bytes(), "application/pdf")) for p in paths])
    assert r.status_code == 200, r.text
    return r.json()


def _body(view, **row):
    return {"confirmed_by": "A. Reviewer", "rows": [{"row_id": r["row_id"], "kind": r["kind"], "policy": "P1", "how": "judgment",
                                                     "reason": "specimen", **row} for r in view["rows"]]}


def _label(tmp_path, view):
    from proofgraph.schema import SourceManifest

    folder = tmp_path / "uploads" / view["upload_id"]
    m = SourceManifest.model_validate_json((folder / "instruments.json").read_text())
    return m.sources[0].instruments[0], json.loads((folder / "confirmed.json").read_text())["rows"][0]


def test_the_proposer_quotes_the_effective_line_and_code_parses_it(tmp_path, endorsement):
    fake = Fake(_wire(effective={"quote": EFFECTIVE, "page": 1}))
    c = _client(tmp_path, fake)
    v = _upload(c, endorsement)
    row = v["rows"][0]
    assert "effective_date:" in fake.prompts[0]  # the proposer is asked for the line
    assert (row["effective_date"], row["effective_phrase"]) == ("1996-12-31", EFFECTIVE)
    q = next(q for q in row["quotes"] if q["field"] == "effective_date")
    assert (q["page"], q["occurrence"], q["count"]) == (1, 1, 1)  # verified on its page, the occurrence recorded
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v)).status_code == 200
    inst, rec = _label(tmp_path, v)
    assert inst.effective_date == dt.date(1996, 12, 31)
    assert (rec["effective_source"], rec["effective_phrase"], rec["effective_quote"]["page"]) == ("printed", EFFECTIVE, 1)


def test_an_effective_line_that_is_not_on_the_page_gives_no_date(tmp_path, endorsement):
    c = _client(tmp_path, Fake(_wire(effective={"quote": "Effective 01/01/2001", "page": 1})))
    v = _upload(c, endorsement)
    assert v["rows"][0]["effective_date"] == "" and any("effective_date" in e for e in v["rows"][0]["rejected"])
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v)).status_code == 200
    inst, rec = _label(tmp_path, v)
    assert inst.effective_date is None and rec["effective_source"] == "none"


@pytest.mark.skipif(not (RAW / "ho_00_03_04_91.pdf").exists(), reason="sources absent")
def test_the_edition_is_never_an_effective_date(tmp_path):
    """Counterfactual: before D13 the edition "04 91" became an effective date of 1991-04-01 (upload.py, edition_date),
    so two endorsements on different editions could let rule 2 pick a winner for the wrong reason."""
    wire = {"form_number": {"quote": "HO 00 03 04 91", "page": 1}, "edition": {"quote": "04 91", "page": 1},
            "title": {"quote": "SPECIAL FORM", "page": 1}, "kind": {"kind": "policy_form", "quote": "SPECIAL FORM", "page": 1},
            "amends": NONE, "policy_number": NONE, "effective_date": NONE}
    c = _client(tmp_path, Fake(wire))
    v = _upload(c, RAW / "ho_00_03_04_91.pdf")
    assert v["rows"][0]["edition"] == "04 91"  # the edition is verified and kept as the version
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v)).status_code == 200
    inst, rec = _label(tmp_path, v)
    assert inst.effective_date is None and inst.version == "04 91"
    assert rec["effective_source"] == "none"
    import proofgraph.propose as propose
    assert not hasattr(propose, "edition_date")


def test_a_typed_effective_date_with_no_printed_line_is_a_judgment_and_needs_a_reason(tmp_path, endorsement):
    c = _client(tmp_path, Fake(_wire()))
    v = _upload(c, endorsement)
    assert v["rows"][0]["effective_date"] == ""
    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v, effective_date="6/1/96"))
    assert r.status_code == 400 and any("needs a written reason" in e for e in r.json()["errors"])
    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v, effective_date="sometime in 1996", effective_reason="x"))
    assert r.status_code == 400 and any("not one date code can read" in e for e in r.json()["errors"])
    ok = c.post(f"/api/upload/{v['upload_id']}/confirm",
                json=_body(v, effective_date="6/1/96", effective_reason="the binder's cover letter dates it"))
    assert ok.status_code == 200
    inst, rec = _label(tmp_path, v)
    assert inst.effective_date == dt.date(1996, 6, 1)
    assert (rec["effective_source"], rec["effective_reason"], rec["effective_phrase"]) == \
        ("typed_at_confirmation", "the binder's cover letter dates it", None)


def test_a_corrected_or_cleared_printed_date_is_recorded_as_the_person_s(tmp_path, endorsement):
    fake = Fake(_wire(effective={"quote": EFFECTIVE, "page": 1}))
    c = _client(tmp_path, fake)
    v = _upload(c, endorsement)
    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v, effective_date="1997-01-01"))
    assert r.status_code == 400  # a correction away from the printed line is a judgment: it needs a reason
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v, effective_date="12/31/1996")).status_code == 200
    assert _label(tmp_path, v)[1]["effective_source"] == "printed"  # the same date written another way
    v = _upload(c, endorsement)
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_body(v, effective_date="")).status_code == 200
    inst, rec = _label(tmp_path, v)
    assert inst.effective_date is None and rec["effective_source"] == "cleared_at_confirmation"


# ---------------------------------------------------------------- item 2: a person picks the figure

TWO = "fees up to USD 5,000 or USD 10,000 per coverage period"
ONE = "fees up to USD 5,000 per coverage period"


@pytest.fixture()
def lines_pdf(tmp_path) -> Path:
    return write_pdf(tmp_path / "lines.pdf", [[(42.5, 100, TWO), (42.5, 130, ONE)]])


def _evidence(path: Path, text: str, pointer: str | None = None):
    from proofgraph.checker import open_source
    from proofgraph.schema import Citation, DocumentRoute, Evidence, Excerpt, MappingMethod, RouteStrength, Side

    cit = Citation.model_validate({"source_file": path.name, "sha256_of_file": open_source(path).sha256,
                                   "locator": {"kind": "page_quote", "page": 1}, "text": text})
    value = None
    if pointer:
        i = text.index(pointer)
        value = Excerpt(start=i, end=i + len(pointer), text=pointer)
    route = DocumentRoute(policy="P1", strength=RouteStrength.READ, method=MappingMethod.LABEL, reasoning=None, citation=cit)
    span = ("a" if text == TWO else "b") * 16
    return Evidence(side=Side.SUPPORT, span_id=span, doc_id="doc", identification=route, reading="r",
                    quote=Excerpt(start=0, end=len(text), text=text), citation=cit, value=value)


def _inst():
    from proofgraph.schema import Instrument

    return Instrument.model_validate_json(json.dumps({
        "doc_id": "doc", "version": "1", "instrument_type": "policy_form", "issuer": "x", "policy_numbers": ["P1"],
        "effective_date": None, "source_id": "s", "source_start": 0, "source_end": 1, "first_page": 1, "last_page": 1,
        "file_start": None, "file_end": None, "spans": [], "definitions": []}))


def _gathered(monkeypatch, path: Path, text: str, claim="Under P1, fees are covered up to USD 5,000 per coverage period.",
              pointer: str | None = None):
    """gather_typed over a fake gather: the line goes through the real assertion step, so a quote with several
    amounts and no pointer comes back value_ambiguous exactly as a live read would."""
    import proofgraph.grouping as grouping
    from proofgraph.assertions import assert_from_evidence
    from proofgraph.pipeline import PacketRun
    from proofgraph.trace import Trace

    ev = _evidence(path, text, pointer)

    def fake_gather(packet_id, c, doc_ids, mappings, data, trace):
        run = PacketRun(claim=c, atom_text="x", documents=[("doc", 1)], evidence=[ev], instruments={"doc": _inst()})
        a = assert_from_evidence(ev, _inst(), c.slot, Trace(None))
        (run.assertions if hasattr(a, "amount") else run.invalid).append(a)
        return run, ()

    monkeypatch.setattr(grouping, "gather", fake_gather)
    return grouping.gather_typed(grouping.read_claim(claim, ("P1",)), "P1", "t", ["doc"], None, path.parent, None)


def test_gather_lists_the_amounts_code_found_in_a_multi_amount_line(monkeypatch, lines_pdf):
    g = _gathered(monkeypatch, lines_pdf, TWO)
    [c] = g.candidates
    assert c.value is None and c.no_value.startswith("value_ambiguous")
    assert c.figures == ("USD 5,000", "USD 10,000")  # found by code in the verified quote, in order


def test_without_a_pick_the_line_still_refuses_value_ambiguous(monkeypatch, lines_pdf):
    """Counterfactual: nothing is compared until a person picks; code never matches the claim's "5,000" to a figure."""
    from proofgraph.grouping import decide_typed

    g = _gathered(monkeypatch, lines_pdf, TWO)
    c = g.candidates[0]
    d = decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen")
    assert d.refusal == "value_ambiguous" and d.run.verdict is None
    for bad in ({c.line_id: 2}, {c.line_id: -1}, {"other": 0}):  # outside the list, or a line that is not this one
        assert decide_typed(_gathered(monkeypatch, lines_pdf, TWO), {c.line_id}, {}, confirmed_by="t", policy_source="chosen",
                            figures_set=bad).refusal == "value_ambiguous"


def test_the_figure_picked_at_confirmation_is_compared_and_recorded(monkeypatch, lines_pdf):
    from app.result import _how_set, _record_line
    from proofgraph.grouping import decide_typed

    for index, answer in ((0, "supported"), (1, "contradicted")):
        g = _gathered(monkeypatch, lines_pdf, TWO)
        c = g.candidates[0]
        d = decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen", figures_set={c.line_id: index})
        assert d.refusal is None and d.run.verdict.verdict.value == answer
        [a] = d.run.assertions
        assert a.value.text == c.figures[index] and a.slot == d.record["question"]
        assert a.routes[1].mapping_id.startswith("set_at_confirmation:") and a.routes[1].strength.value == "judgment"
        assert d.run.invalid == []
        assert d.record["value_source"] == "set_at_confirmation"
        assert d.record["value_set"] == [{"line_id": c.line_id, "doc_id": "doc", "line": TWO, "figure": c.figures[index],
                                          "index": index, "figures": ["USD 5,000", "USD 10,000"]}]
    rec = {**d.record, "confirmed_on": None, "dropped": [], "nothing_found": []}
    assert "Figure: picked at confirmation by a person, not read by code (USD 10,000 in" in _record_line(rec)
    assert "The figure USD 10,000 was picked at confirmation" in _how_set(rec)


def test_a_one_amount_line_whose_pointer_disagrees_is_not_offered_a_pick(monkeypatch, lines_pdf):
    """D13 covers several amounts with no valid pointer. One amount and a disagreeing pointer stays value_ambiguous."""
    from proofgraph.grouping import decide_typed

    g = _gathered(monkeypatch, lines_pdf, ONE, pointer="fees")
    c = g.candidates[0]
    assert c.no_value.startswith("value_ambiguous") and c.figures == ()
    assert decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen",
                        figures_set={c.line_id: 0}).refusal == "value_ambiguous"


def test_a_line_code_reads_records_its_value_as_read_from_the_verified_quote(monkeypatch, lines_pdf):
    from proofgraph.grouping import decide_typed

    g = _gathered(monkeypatch, lines_pdf, ONE)
    c = g.candidates[0]
    d = decide_typed(g, {c.line_id}, {}, confirmed_by="t", policy_source="chosen", figures_set={c.line_id: 0})
    assert d.run.verdict.verdict.value == "supported"
    assert (d.record["value_source"], d.record["value_set"]) == ("verified_quote", [])  # the pick is ignored: nothing to pick


def test_the_decide_endpoint_takes_a_pick_by_position_only(monkeypatch, lines_pdf):
    from fastapi.testclient import TestClient

    import app.server as server
    from app.limit import LiveRunLimit

    g = _gathered(monkeypatch, lines_pdf, TWO)
    seen = {}
    monkeypatch.setattr(server, "gather_typed", lambda *a, **k: g)

    def fake_decide(gg, confirmed, dropped, **kw):
        seen.update(kw)
        from proofgraph.grouping import Decided
        return Decided(gg.run, {}, "value_ambiguous")

    monkeypatch.setattr(server, "decide_typed", fake_decide)
    c = TestClient(server.create_app(limit=LiveRunLimit(runs=5)))
    text = "Under FD960228, fees are covered up to USD 5,000 per coverage period."
    out = c.post("/api/claim/gather", json={"packet": "gillette", "text": text, "policy": "FD960228"}).json()
    assert out["lines"][0]["figures"] == ["USD 5,000", "USD 10,000"]
    url = f"/api/claim/{out['gather_id']}/decide"
    assert c.post(url, json={"confirmed": [], "confirmed_by": "t", "figures": {"x": "USD 5,000"}}).status_code == 400
    r = c.post(url, json={"confirmed": [g.candidates[0].line_id], "confirmed_by": "t", "figures": {g.candidates[0].line_id: 1}})
    assert seen["figures_set"] == {g.candidates[0].line_id: 1} and "Pick the figure" in r.json()["refusal"]
