"""app/server.py: gate, streamed events, review page, ask again. Offline, scripted model answers."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import passcode_ok, passcode_refusal
from app.server import create_app
from tests.test_review_run import CLAIM, DOC_ID, GOOD, PDF, SPLIT1, FakeTransport, _muse


def events(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        name, data = block.split("\n", 1)
        out.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSCODE", "open-sesame")
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    calls = []

    def make():
        calls.append(1)
        return _muse(tmp_path, FakeTransport(SPLIT1, GOOD, SPLIT1, GOOD))

    c = TestClient(create_app(make))
    c.calls = calls
    return c


def post(c, claim=CLAIM, passcode="open-sesame", files=True, path="/api/review"):
    data = {"claim": claim, "passcode": passcode}
    up = {"files": ("rate.pdf", PDF.read_bytes(), "application/pdf")} if files else None
    return c.post(path, data=data, files=up)


def test_passcode_helper():
    assert passcode_ok("a-b", "a-b") and not passcode_ok("a", None) and not passcode_ok("", "")
    assert passcode_refusal("x", None).startswith("Live checks are off")
    assert passcode_refusal("x", "y").startswith("Enter the passcode")
    assert passcode_refusal("y", "y") is None


@pytest.mark.parametrize("kw,code", [({"passcode": "nope"}, 401), ({"claim": " "}, 400), ({"files": False}, 400)])
def test_refusals_build_no_client(client, kw, code):
    r = post(client, **kw)
    assert r.status_code == code and r.json()["refusal"]
    assert client.calls == []


def test_no_configured_passcode_means_open_and_the_page_is_told(client, monkeypatch):
    assert client.get("/api/config").json() == {"passcode_required": True}
    monkeypatch.delenv("APP_PASSCODE")
    assert client.get("/api/config").json() == {"passcode_required": False}
    r = post(client, passcode="")
    assert r.status_code == 200 and events(r.text)[-1][0] == "done"
    assert post(client, claim=" ", passcode="").status_code == 400  # input checks still apply


def test_stream_ends_on_a_review_page(client):
    r = post(client)
    assert r.headers["content-type"].startswith("text/event-stream")
    evs = events(r.text)
    names = [n for n, _ in evs]
    assert names[0] == "files" and names[-1] == "done"
    assert names.index("parts") < names.index("partdone") < names.index("done")
    assert evs[0][1]["files"] == [{"name": "rate.pdf", "id": DOC_ID, "ok": True, "pages": 1, "note": None}]
    done = evs[-1][1]
    assert done["status"] == "contradicted"
    page = client.get(f"/api/review/{done['review_id']}")
    assert page.status_code == 200 and CLAIM in page.text and "<!doctype html>" in page.text.lower()


def test_ask_reuses_the_stored_files(client):
    first = events(post(client).text)[-1][1]["review_id"]
    r = post(client, path=f"/api/review/{first}/ask", files=False)
    evs = events(r.text)
    assert evs[-1][0] == "done" and evs[-1][1]["review_id"] != first
    assert post(client, path="/api/review/nope/ask", files=False).status_code == 404


def test_model_failure_is_one_plain_line(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_PASSCODE", "p")

    def boom():
        raise RuntimeError("secret detail")

    r = post(TestClient(create_app(boom)), passcode="p")
    name, data = events(r.text)[-1]
    assert name == "failed" and "secret" not in data["text"]


def test_bad_upload_type_and_page_served(client):
    r = client.post("/api/review", data={"claim": "x", "passcode": "open-sesame"},
                    files={"files": ("a.docx", b"PK", "application/octet-stream")})
    assert r.status_code == 400
    home = client.get("/")
    assert home.status_code == 200 and 'aria-live="polite"' in home.text
    assert client.get("/web/app.js").status_code == 200 and client.get("/web/app.css").status_code == 200
    assert client.get("/api/review/none").status_code == 404


def test_samples_listed_and_run_from_a_manifest(client, tmp_path, monkeypatch):
    (tmp_path / "rate.pdf").write_bytes(PDF.read_bytes())
    manifest = tmp_path / "samples.json"
    manifest.write_text(json.dumps({"samples": [{"id": "a", "title": "Rate", "claim": CLAIM, "files": ["rate.pdf"]},
                                                {"id": "b", "title": "Gone", "claim": CLAIM, "files": ["nope.pdf"]}]}))
    assert client.get("/api/samples").json() == []
    monkeypatch.setenv("PROOFGRAPH_SAMPLES", str(manifest))
    assert client.get("/api/samples").json() == [{"id": "a", "title": "Rate", "claim": CLAIM, "docs": ["rate"]}]
    r = client.post("/api/sample/a", data={"passcode": "open-sesame"})
    assert events(r.text)[-1][0] == "done"
    assert client.post("/api/sample/b", data={"passcode": "open-sesame"}).status_code == 404
    assert client.post("/api/sample/a", data={"passcode": "bad"}).status_code == 401


def test_graph_events_pass_through_with_doc_ids(client, monkeypatch):
    from proofgraph.review import graph_run
    from proofgraph.review.run import AllDone

    def fake(claim, paths, muse):
        yield graph_run.DocStarted("d1", "rate.pdf", 1)
        yield graph_run.EntityFound("Board", "office", 2, ("d1", "d2"))
        raise RuntimeError("stop")

    monkeypatch.setattr("app.server.run_review", fake)
    evs = events(post(client).text)
    assert ("docstarted", {"doc": "d1", "name": "rate.pdf", "pages": 1}) in evs
    assert ("entity", {"name": "Board", "type": "office", "docs": 2, "doc_ids": ["d1", "d2"]}) in evs
