"""The upload door: no-text-layer refusal, the proposer with a fake model on the real ISO PDFs, confirmation
and freezing, and the refusals before a run. No model is called and no key is needed."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from proofgraph.model import ModelReply

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
pytestmark = pytest.mark.skipif(not all((RAW / f).exists() for f in ("ho_00_03_04_91.pdf", "ho_00_15_04_91.pdf")), reason="sources absent")

NONE = {"quote": "", "page": 0}


def _reply(wire: dict) -> ModelReply:
    return ModelReply(json.dumps(wire), "fake", "h", 0, 0, 0, False)


def _good(prompt: str) -> dict:
    if "HO 00 15" in prompt:
        return {"form_number": {"quote": "HO 00 15 04 91", "page": 1}, "edition": NONE,
                "title": {"quote": "SPECIAL PERSONAL PROPERTY COVERAGE", "page": 1},
                "kind": {"kind": "endorsement", "quote": "THIS ENDORSEMENT CHANGES THE POLICY. PLEASE READ IT CAREFULLY.", "page": 1},
                "amends": {"quote": "Form HO 00 03 Only", "page": 1}, "policy_number": NONE}
    return {"form_number": {"quote": "HO 00 03 04 91", "page": 1}, "edition": NONE,
            "title": {"quote": "SPECIAL FORM", "page": 1},
            "kind": {"kind": "policy_form", "quote": "SPECIAL FORM", "page": 1}, "amends": NONE, "policy_number": NONE}


class Fake:
    def __init__(self, make=_good):
        self.make, self.prompts = make, []

    def __call__(self, prompt, schema, *, system, template, effort="low"):
        self.prompts.append(prompt)
        return _reply(self.make(prompt))


def _client(tmp_path, fake=None):
    from fastapi.testclient import TestClient

    from app.limit import LiveRunLimit
    from app.server import create_app

    off = LiveRunLimit(runs=0)
    return TestClient(create_app(complete=fake or Fake(), uploads_dir=tmp_path, limit=off, upload_limit=off))


def _pdf(name):
    return (name, (RAW / name).read_bytes(), "application/pdf")


def _upload(client, *names):
    r = client.post("/api/upload", files=[("files", _pdf(n)) for n in names])
    assert r.status_code == 200, r.text
    return r.json()


ISO = ("ho_00_03_04_91.pdf", "ho_00_15_04_91.pdf")


def _confirm_body(view, **extra):
    rows = [{"row_id": r["row_id"], "kind": r["kind"], "policy": "SPECIMEN-HO3", "how": "judgment",
             "reason": "ISO specimens carry no policy number; the packet assembles SPECIMEN-HO3 from these two forms."} for r in view["rows"]]
    return {"confirmed_by": "A. Reviewer", "rows": rows, **extra}


def test_a_file_with_no_text_layer_is_refused_as_a_result_not_an_error(tmp_path):
    from PIL import Image

    scan = io.BytesIO()
    Image.new("RGB", (300, 300), "white").save(scan, format="PDF")
    c = _client(tmp_path)
    r = c.post("/api/upload", files=[("files", ("scan.pdf", scan.getvalue(), "application/pdf")), ("files", _pdf(ISO[0]))])
    assert r.status_code == 200
    v = r.json()
    assert [x["refusal"] for x in v["refused"]] == ["no readable text layer"] and v["refused"][0]["file"] == "scan.pdf"
    assert len(v["rows"]) == 1 and v["rows"][0]["file"] == ISO[0]  # the readable file is still proposed
    assert not list((tmp_path / v["upload_id"] / "raw").glob("*scan*"))
    assert c.post("/api/upload", files=[("files", ("x.pdf", b"not a pdf", "application/pdf"))]).json()["refused"][0]["refusal"] == "not a PDF"


def test_the_proposer_quotes_and_code_verifies_each_quote(tmp_path):
    c = _client(tmp_path)
    v = _upload(c, *ISO)
    base, end = v["rows"]
    assert (base["kind"], base["form_number"], base["status"]) == ("policy_form", "HO 00 03 04 91", "proposed")
    assert (end["kind"], end["form_number"], end["amends"]) == ("endorsement", "HO 00 15 04 91", "Form HO 00 03 Only")
    assert len(base["sha256"]) == 64 and base["policy"] == "" and base["how"] == "judgment"  # no policy number is printed
    form = next(q for q in base["quotes"] if q["field"] == "form_number")
    assert form["page"] == 1 and form["occurrence"] == 1 and form["count"] == 2  # header and footer: both counted, first recorded
    assert base["anchor"]["field"] == "title" and base["anchor"]["count"] == 1  # the mapping cites a line that occurs once
    assert c.get(f"/api/upload/{v['upload_id']}").json()["rows"][0]["sha256"] == base["sha256"]
    assert c.get("/api/upload/not-an-id").status_code == 404


def test_a_fabricated_quote_is_rejected_and_one_repair_is_tried(tmp_path):
    calls = []

    def make(prompt):
        calls.append(prompt)
        wire = _good(prompt)
        if "failed validation" not in prompt:
            wire["amends"] = {"quote": "Form HO 99 99 Only", "page": 1}
        return wire

    v = _upload(_client(tmp_path, Fake(make)), ISO[1])
    assert len(calls) == 2 and "HO 99 99" in calls[1]  # the repair carried the error
    assert v["rows"][0]["amends"] == "Form HO 00 03 Only" and v["rows"][0]["rejected"] == []

    def always(prompt):
        wire = _good(prompt)
        wire["amends"] = {"quote": "Form HO 99 99 Only", "page": 1}
        return wire

    row = _upload(_client(tmp_path, Fake(always)), ISO[1])["rows"][0]
    assert row["amends"] == "" and any("HO 99 99" in e for e in row["rejected"]) and row["status"] == "proposed"


def test_an_unplaceable_file_says_what_it_would_need(tmp_path):
    blank = {f: NONE for f in ("form_number", "edition", "title", "amends", "policy_number")} | {"kind": {"kind": "", "quote": "", "page": 0}}
    v = _upload(_client(tmp_path, Fake(lambda p: blank)), ISO[1])
    row = v["rows"][0]
    assert row["status"] == "unplaceable" and v["unplaced"] == [row["row_id"]]
    assert ISO[1] in row["reason"] and "one line printed on it" in row["reason"]


def test_confirmation_is_one_submission_and_freezes_the_mapping(tmp_path):
    from proofgraph.checker import open_source, verify_citation
    from proofgraph.schema import DocumentMappingFile, SourceManifest

    c = _client(tmp_path)
    v = _upload(c, *ISO)
    bad = _confirm_body(v)
    bad["rows"][0]["reason"] = ""
    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=bad)
    assert r.status_code == 400 and any("written reason" in e for e in r.json()["errors"])
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json={**_confirm_body(v), "rows": _confirm_body(v)["rows"][:1]}).status_code == 400
    assert not (tmp_path / v["upload_id"] / "confirmed.json").exists()  # nothing froze on a refusal

    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v))
    assert r.status_code == 200 and r.json()["confirmed"] and r.json()["confirmed_by"] == "A. Reviewer"
    assert r.json()["confirmed_at"].endswith("Z")
    folder = tmp_path / v["upload_id"]
    frozen = json.loads((folder / "confirmed.json").read_text())
    assert frozen["confirmed_by"] == "A. Reviewer" and {x["kind"] for x in frozen["rows"]} == {"policy_form", "endorsement"}
    mapping = DocumentMappingFile.model_validate_json((folder / "document_mappings.json").read_text())
    manifest = SourceManifest.model_validate_json((folder / "instruments.json").read_text())
    assert [m.doc_id for m in mapping.documents] == ["ho_00_03_04_91", "ho_00_15_04_91"]
    assert {i.policy_numbers for s in manifest.sources for i in s.instruments} == {("SPECIMEN-HO3",)}
    for m, s in zip(mapping.documents, manifest.sources):
        route = m.describes[0]
        assert route.strength.value == "judgment" and route.reasoning and route.policy == "SPECIMEN-HO3"
        assert verify_citation(route.citation, open_source(folder / "raw" / s.file)) is None  # the same verifier the run uses
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v)).status_code == 409  # frozen


def test_read_needs_the_policy_to_be_printed_in_a_verified_quote(tmp_path):
    c = _client(tmp_path)
    v = _upload(c, ISO[0])
    body = _confirm_body(v)
    body["rows"][0]["how"] = "read"
    r = c.post(f"/api/upload/{v['upload_id']}/confirm", json=body)
    assert r.status_code == 400 and "'read' needs" in r.json()["errors"][0]


def test_nothing_runs_on_an_unconfirmed_proposal(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    c = _client(tmp_path)
    v = _upload(c, *ISO)
    r = c.post(f"/api/upload/{v['upload_id']}/run/SPECIMEN-HO3.jewelry_theft.special_limit")
    assert r.status_code == 400 and "No one has confirmed" in r.json()["refusal"]


def test_a_question_outside_the_registry_for_the_confirmed_policies_is_refused(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    c = _client(tmp_path)
    v = _upload(c, *ISO)
    c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v))
    for slot in ("not.a.slot", "FD960228.corp_reimbursement.retention"):  # unknown, and known but for a different policy
        r = c.post(f"/api/upload/{v['upload_id']}/run/{slot}")
        assert r.status_code == 400 and r.json()["refusal"] == "That question is not on the fixed list for these documents, so nothing ran."


def test_no_key_refuses_and_a_key_runs_the_packet_from_the_upload_folder(tmp_path, monkeypatch):
    import app.server as server

    c = _client(tmp_path)
    v = _upload(c, *ISO)
    c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v))
    slot = "SPECIMEN-HO3.jewelry_theft.special_limit"
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = c.post(f"/api/upload/{v['upload_id']}/run/{slot}")
    assert r.status_code == 400 and "not set up to call the model" in r.json()["refusal"]

    seen = {}

    def fake_run(packet_id, claim, doc_ids, mappings, data, trace):
        seen.update(claim=claim.slot, docs=doc_ids, data=data)
        raise RuntimeError("stop here: only the wiring is under test")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    monkeypatch.setattr(server, "run_packet", fake_run)
    body = c.post(f"/api/upload/{v['upload_id']}/run/{slot}").text
    assert "event: failed" in body
    assert seen == {"claim": slot, "docs": ["ho_00_03_04_91", "ho_00_15_04_91"], "data": tmp_path / v["upload_id"]}


def test_run_applies_the_live_limit(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.limit import LiveRunLimit
    from app.server import create_app

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-used")
    c = TestClient(create_app(complete=Fake(), uploads_dir=tmp_path, limit=LiveRunLimit(runs=1), upload_limit=LiveRunLimit(runs=0)))
    v = _upload(c, *ISO)
    c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v))
    slot = "SPECIMEN-HO3.jewelry_theft.special_limit"
    c.post(f"/api/upload/{v['upload_id']}/run/{slot}")
    assert c.post(f"/api/upload/{v['upload_id']}/run/{slot}").status_code == 429


def test_the_form_fallback_row_for_a_file_the_proposer_could_not_place(tmp_path):
    blank = {f: NONE for f in ("form_number", "edition", "title", "amends", "policy_number")} | {"kind": {"kind": "", "quote": "", "page": 0}}
    c = _client(tmp_path, Fake(lambda p: blank))
    v = _upload(c, ISO[1])
    rid = v["rows"][0]["row_id"]
    url = f"/api/upload/{v['upload_id']}/rows"
    typed = {"row_id": rid, "kind": "endorsement", "policy": "SPECIMEN-HO3", "how": "judgment",
             "reason": "It says it attaches to HO 00 03; the policy name is the packet author's.",
             "quote": "SPECIAL PERSONAL PROPERTY COVERAGE", "page": 1}
    assert c.post(url, json={**typed, "quote": "A LINE THAT IS NOT PRINTED"}).status_code == 400  # unverified line
    assert c.post(url, json={**typed, "reason": ""}).status_code == 400
    assert c.post(url, json={**typed, "row_id": "000000000000"}).status_code == 400
    r = c.post(url, json=typed)
    assert r.status_code == 200 and r.json()["rows"][0]["status"] == "typed"
    body = _confirm_body(r.json())
    body["rows"][0]["reason"] = ""  # the reason typed with the row stands
    done = c.post(f"/api/upload/{v['upload_id']}/confirm", json=body)
    assert done.status_code == 200 and done.json()["confirmed"]
    folder = tmp_path / v["upload_id"]
    route = json.loads((folder / "document_mappings.json").read_text())["documents"][0]["describes"][0]
    assert route["citation"]["text"] == "SPECIAL PERSONAL PROPERTY COVERAGE" and route["reasoning"].startswith("It says")


def test_review_stays_a_refusal_that_points_at_the_upload_flow(tmp_path):
    r = _client(tmp_path).post("/api/review")
    assert r.status_code == 400 and "guess which policy" in r.json()["refusal"] and "/api/upload" in r.json()["refusal"]


def test_a_confirmed_upload_is_admitted_whole_and_its_printed_amends_line_is_recorded(tmp_path):
    """D10. With no narrower block named, the whole document is admitted once its identifying line verifies,
    and an endorsement's printed 'Form HO 00 03 Only' points at the uploaded HO 00 03 when it is there."""
    from proofgraph.checker import open_source
    from proofgraph.ingest import ingest
    from proofgraph.retrieve import admit
    from proofgraph.schema import DocumentMappingFile, SourceManifest
    from proofgraph.trace import Trace

    c = _client(tmp_path)
    v = _upload(c, *ISO)
    assert c.post(f"/api/upload/{v['upload_id']}/confirm", json=_confirm_body(v)).status_code == 200
    folder = tmp_path / v["upload_id"]
    mapping = DocumentMappingFile.model_validate_json((folder / "document_mappings.json").read_text())
    by = {m.doc_id: m for m in mapping.documents}
    assert all(m.describes[0].scope == "document" for m in mapping.documents)
    assert by["ho_00_15_04_91"].amends.instrument_doc_id == "ho_00_03_04_91" and by["ho_00_03_04_91"].amends is None
    label = SourceManifest.model_validate_json((folder / "instruments.json").read_text()).sources[0]
    ing = ingest(label, folder / "raw")
    admitted, _ = admit(ing.instruments, mapping, "SPECIMEN-HO3", open_source(folder / "raw" / label.file), Trace(None), ing.source.extractor)
    assert sum(len(i.spans) for i in admitted) == sum(len(i.spans) for i in ing.instruments) > 1

    alone = _upload(c, "ho_00_15_04_91.pdf")
    assert c.post(f"/api/upload/{alone['upload_id']}/confirm", json=_confirm_body(alone)).status_code == 200
    m = DocumentMappingFile.model_validate_json((tmp_path / alone["upload_id"] / "document_mappings.json").read_text())
    assert m.documents[0].amends.instrument_doc_id is None  # its base form was not uploaded: the check will refuse
