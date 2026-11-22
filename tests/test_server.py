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
    assert "Supported, decided by a rule" in page and "Rule applied: endorsement over base form" in page
    assert "HO 00 15 (endorsement)" in page and "Governs" in page
    assert page.count("data:image/png;base64,") == 2  # both pages, cited lines boxed
    assert "state no basis" in page  # the pair's reason in plain words


def test_disagreement_page_says_neither_rule_fired_and_why(client):
    stream, page = _run(client, "documents-disagree")
    assert '"status": "unresolved"' in stream
    assert "Can’t be settled from these documents: they disagree" in page and "Neither precedence rule fired" in page
    assert "Only Underwriters at Lloyd" in page and "<mark>" in page  # raw-text pane marks the cited characters
    assert "in scope: [" not in page and "support:" not in page  # no internal ids on the screen


def test_uploads_are_refused_with_a_reason(client):
    r = client.post("/api/review")
    assert r.status_code == 400 and "not built yet" in r.json()["refusal"]


def test_form_lists_each_packet_with_its_mapping_and_registry_questions(client):
    packs = {p["id"]: p for p in client.get("/api/packets").json()}
    assert set(packs) == {"homeowners", "gillette"}
    home = packs["homeowners"]
    assert [d["kind"] for d in home["docs"]] == ["Base form", "Endorsement"]
    assert all(q["claim"] for q in home["questions"]) and len(home["questions"]) == 4
    gil = packs["gillette"]
    runnable = [q["slot"] for q in gil["questions"] if q["claim"]]
    assert runnable == ["FD960228.corp_reimbursement.retention"]
    assert {d["strength"] for d in gil["docs"]} == {"read", "derived", "judgment"}


def test_every_question_with_a_claim_replays_to_its_label(client):
    for slot in ("SPECIMEN-HO3.money.special_limit", "SPECIMEN-HO3.firearms_theft.special_limit",
                 "SPECIMEN-HO3.silverware_theft.special_limit"):
        assert '"status": "supported"' in client.post(f"/api/run/homeowners/{slot}").text


def test_questions_outside_the_registry_or_without_a_claim_are_refused_before_running(client):
    r = client.post("/api/run/gillette/not.a.slot")
    assert r.status_code == 400 and "not in the registry" in r.json()["refusal"]
    r = client.post("/api/run/gillette/81385411.d_and_o.limit")
    assert r.status_code == 400 and "No claim has been written" in r.json()["refusal"]
