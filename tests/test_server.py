"""The front end over the v2 pipeline: examples replay with no key; uploads are refused honestly."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    not all((ROOT / "data" / "raw" / f).exists() for f in ("gillette_10k405_1996.txt", "ho_00_03_04_91.pdf", "ho_00_15_04_91.pdf")),
    reason="sources absent")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    os.environ.pop("ANTHROPIC_API_KEY", None)  # must replay from data/recorded/model
    from app.server import create_app

    return TestClient(create_app())


def _run(client, sample):
    body = client.post(f"/api/sample/{sample}").text
    rid = re.search(r'"review_id": "([0-9a-f]+)"', body)
    assert rid, body[-400:]
    return body, client.get(f"/api/review/{rid.group(1)}").text


def test_config_needs_no_passcode(client):
    assert client.get("/api/config").json()["passcode_required"] is False


def test_the_first_example_is_the_decision(client):
    assert client.get("/api/samples").json()[0]["id"] == "endorsement-replaces-limit"


def test_rule_one_page_names_the_rule_the_governing_form_and_boxes_the_lines(client):
    stream, page = _run(client, "endorsement-replaces-limit")
    assert '"status": "supported"' in stream
    # D9: $1000 and $1,000 are now compared (neither states a basis) and equal, so the rule names the
    # governing form over agreeing values: no_conflict, not "decided by a rule".
    assert "Supported, decided by a rule" not in page and "Rule applied: endorsement over base form" in page
    assert "HO 00 15 (endorsement)" in page and "Governs" in page
    assert "The claim is right." in page and "<b>$1,000</b>" in page  # answer first, the claim's amount in bold
    assert page.count("data:image/png;base64,") == 3  # the governing page up front, then both pages in the chain
    assert page.index("The claim is right.") < page.index("How this was decided")  # conclusion before mechanism
    assert "Re-run this check" in page and "sha256" in page and "Commit" in page
    assert "compared: same amount; same currency; neither states a basis" in page  # the pair's reason in plain words
    # each document links out to its published original; the ISO PDFs are not served from here (NOTICE.md)
    assert 'href="https://www.independentagent.com/' in page and "Open the original" in page


def test_disagreement_page_says_neither_rule_fired_and_why(client):
    stream, page = _run(client, "documents-disagree")
    assert '"status": "unresolved"' in stream
    assert "This can’t be settled from these documents." in page and "no rule says which one controls" in page
    assert "Neither rule applied" in page
    assert "Only Underwriters at Lloyd" in page and "<mark>" in page  # raw-text pane marks the cited characters
    assert "in scope: [" not in page and "support:" not in page  # no internal ids on the screen


def test_uploads_are_refused_with_a_reason(client):
    r = client.post("/api/review")
    assert r.status_code == 400 and "guess which policy" in r.json()["refusal"]


def test_form_lists_each_packet_with_its_mapping_and_its_claims(client):
    packs = {p["id"]: p for p in client.get("/api/packets").json()}
    assert set(packs) == {"homeowners", "endorsement-alone", "gillette"}
    home = packs["homeowners"]
    assert [d["kind"] for d in home["docs"]] == ["Base form", "Endorsement"]
    ids = [q["id"] for q in home["questions"] if q["claim"]]
    assert ids[:3] == ["fb_jewelry", "fb_jewelry_wrong", "fb_jewelry_wording"] and len(ids) == 6
    assert [d["kind"] for d in packs["endorsement-alone"]["docs"]] == ["Endorsement"]
    gil = packs["gillette"]
    assert [q["slot"] for q in gil["questions"] if q["claim"]] == ["FD960228.corp_reimbursement.retention"]
    assert {d["strength"] for d in gil["docs"]} == {"read", "derived", "judgment"}
    # every worked document links to its published original (linked, not served: NOTICE.md)
    assert all(d["source"].startswith("https://") for p in packs.values() for d in p["docs"])
    assert {d["source"] for d in gil["docs"]} == {"https://www.sec.gov/Archives/edgar/data/0000041499/000095013597001269/0000950135-97-001269.txt"}


def test_each_hero_example_gives_its_answer_and_names_why(client):
    """The three answers, the missing-document refusal and the quoted wording claim, each with its plain reason."""
    want = {"endorsement-replaces-limit": ("supported", "HO 00 15 (endorsement) controls"),
            "claim-is-wrong": ("contradicted", "the claim says $1,500"),
            "documents-disagree": ("unresolved", "different amounts, and no rule says which one controls"),
            "base-form-missing": ("unresolved", "changes HO 00 03, and HO 00 03 is not among these documents"),
            "wording-quoted": ("quoted", "Quoted, not checked")}
    for sid, (status, words) in want.items():
        body = client.post(f"/api/sample/{sid}").text
        assert f'"status": "{status}"' in body and words in body, (sid, body[-600:])
        assert "support:" not in body and "attack:" not in body and "_mismatch" not in body  # no internal ids in the reason line


def test_every_question_with_a_claim_replays_to_its_label(client):
    for slot in ("SPECIMEN-HO3.money.special_limit", "SPECIMEN-HO3.firearms_theft.special_limit",
                 "SPECIMEN-HO3.silverware_theft.special_limit"):
        assert '"status": "supported"' in client.post(f"/api/run/homeowners/{slot}").text
    assert '"status": "contradicted"' in client.post("/api/run/homeowners/fb_jewelry_wrong").text


def test_questions_outside_the_registry_or_without_a_claim_are_refused_before_running(client):
    r = client.post("/api/run/gillette/not.a.slot")
    assert r.status_code == 400 and "not on the fixed list" in r.json()["refusal"]
    r = client.post("/api/run/gillette/81385411.d_and_o.limit")
    assert r.status_code == 400 and "No claim has been written" in r.json()["refusal"]


def test_the_run_shows_what_the_model_was_allowed_to_see(client):
    body = client.post("/api/sample/endorsement-replaces-limit").text
    assert "event: admitted" in body and "event: files" not in body
    assert '"name": "HO 00 15 (endorsement)"' in body and '"in_scope": true' in body
    # D9: the governing form is named on the page (see the rule-one test); the stream's one-line reason
    # names it only for resolved_by_rule, which this sample no longer is (app/server.py _reason)
    assert "ho_00_15 controls" not in body  # never an internal id


# ---- D11: a typed claim through the routes (replays the responses recorded on the regression run)

JEWELRY = "Under the specimen policy SPECIMEN-HO3, the special limit of liability for loss by theft of jewelry is $1,000."
RETENTION = "The primary corporate reimbursement retention under FD960228 is USD 1,000,000."


def test_reading_a_claim_shows_the_policy_match_and_does_not_apply_it(client):
    r = client.post("/api/claim/read", json={"packet": "gillette", "text": RETENTION}).json()
    assert r["kind"] == "amount" and r["value"] == "USD 1,000,000" and r["policy_matches"] == ["FD960228"]
    assert r["policies"] == ["FD960228"]  # the choices come from the packet's confirmed assignments
    bad = client.post("/api/claim/read", json={"packet": "gillette", "text": "limit $1 and deductible $2"}).json()
    assert "more than one amount" in bad["refusal"]


def test_a_typed_claim_is_confirmed_then_decided_and_the_result_says_how(client):
    g = client.post("/api/claim/gather", json={"packet": "homeowners", "text": JEWELRY, "policy": "SPECIMEN-HO3",
                                               "policy_source": "matched_in_claim"}).json()
    assert len(g["lines"]) == 2 and not g["ask_basis"]
    ids = [x["line_id"] for x in g["lines"]]
    assert client.post(f"/api/claim/{g['gather_id']}/decide", json={"confirmed": ids[:1], "confirmed_by": "t"}).status_code == 400
    d = client.post(f"/api/claim/{g['gather_id']}/decide", json={"confirmed": ids, "confirmed_by": "Test Person"}).json()
    assert d["status"] == "supported"
    page = client.get(f"/api/review/{d['review_id']}").text
    assert "How this question was set" in page and "confirmed by a person" in page and "Test Person" in page
    assert "found in the claim" in page and "Basis: written in the claim" not in page and "No line was set aside" in page


def test_a_basis_set_at_confirmation_is_shown_as_set_there(client):
    g = client.post("/api/claim/gather", json={"packet": "gillette", "text": RETENTION, "policy": "FD960228",
                                               "policy_source": "matched_in_claim"}).json()
    assert g["ask_basis"] and "each claim" in g["basis_in_lines"] and g["nothing_found"]
    ids = [x["line_id"] for x in g["lines"]]
    reliance = next(x["line_id"] for x in g["lines"] if x["doc"].startswith("Reliance"))
    keep = [i for i in ids if i != reliance]
    d = client.post(f"/api/claim/{g['gather_id']}/decide", json={"confirmed": keep, "dropped": {reliance: "different policy's binder"},
                                                                 "confirmed_by": "T", "basis": "each_claim"}).json()
    page = client.get(f"/api/review/{d['review_id']}").text
    assert "set at confirmation, not written by the claimant" in page
    assert "set aside by a person" in page and "different policy" in page and "nothing found" in page
