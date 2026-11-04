"""app/server.py: gate, streamed events, review page, ask again. Offline, scripted model answers."""

import base64
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.auth import passcode_ok, passcode_refusal
from app.server import create_app, externalize
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


def test_config_says_whether_the_blind_second_reader_can_run(client, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "k")
    assert client.get("/api/config").json()["second_reader"] is True
    monkeypatch.setenv("BASETEN_API_KEY", "  ")
    assert client.get("/api/config").json()["second_reader"] is False
    monkeypatch.delenv("BASETEN_API_KEY")
    assert client.get("/api/config").json()["second_reader"] is False  # no key: support would pass with no second read


def test_no_configured_passcode_means_open_and_the_page_is_told(client, monkeypatch):
    assert client.get("/api/config").json()["passcode_required"] is True
    monkeypatch.delenv("APP_PASSCODE")
    assert client.get("/api/config").json()["passcode_required"] is False
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


def test_review_is_saved_and_shared_read_only(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "c"))
    rid = events(post(client).text)[-1][1]["review_id"]
    saved = tmp_path / "c" / "reviews"
    assert (saved / f"{rid}.json").is_file() and list(saved.glob(f"{rid}-*.png"))
    page = client.get(f"/r/{rid}")
    assert page.status_code == 200 and CLAIM in page.text  # flag off: the old page; the graph page adds the share footer
    # the shared link survives a restart: a fresh app reads the saved file
    fresh = TestClient(create_app(lambda: None))
    assert fresh.get(f"/r/{rid}").status_code == 200
    assert fresh.get(f"/api/review/{rid}").status_code == 200


@pytest.mark.parametrize("bad", ["nope", "..%2f..%2fetc", "0" * 12, "ABCDEF123456"])
def test_share_route_rejects_unknown_and_unsafe_ids(client, bad):
    assert client.get(f"/r/{bad}").status_code == 404


PNG = b"\x89PNG\r\n\x1a\nfake"


def test_externalize_swaps_inline_page_images_for_urls():
    html = f'<img alt="a" src="data:image/png;base64,{base64.b64encode(PNG).decode()}"><p>x</p>'
    out, pics = externalize(html, "abcdef012345")
    (name, data), = pics.items()
    assert "data:image" not in out and "<p>x</p>" in out and data == PNG
    assert f'src="/api/review/abcdef012345/img/{name}.png" loading="lazy"' in out  # a closed page does not load its images
    assert externalize("<p>none</p>", "abcdef012345") == ("<p>none</p>", {})


def _images(page: str, rid: str) -> list[str]:
    return re.findall(rf'src="(/api/review/{rid}/img/[0-9a-f]+\.png)"', page)


def test_review_pages_serve_page_images_as_cacheable_files_not_inline(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "c"))
    rid = events(post(client).text)[-1][1]["review_id"]
    for url in (f"/api/review/{rid}", f"/r/{rid}"):
        page = client.get(url).text
        assert "data:image/png;base64" not in page
        urls = _images(page, rid)
        assert urls
        img = client.get(urls[0])
        assert img.status_code == 200 and img.headers["content-type"] == "image/png"
        assert "immutable" in img.headers["cache-control"] and img.content.startswith(b"\x89PNG")


def test_a_restarted_server_still_serves_a_saved_reviews_images(client, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "c"))
    rid = events(post(client).text)[-1][1]["review_id"]
    fresh = TestClient(create_app(lambda: None))
    urls = _images(fresh.get(f"/r/{rid}").text, rid)
    assert urls and fresh.get(urls[0]).status_code == 200


@pytest.mark.parametrize("name", ["nope.png", "..%2fx.png", "0123456789abcdef.png", "ABCDEF0123456789.png"])
def test_image_route_rejects_unknown_and_unsafe_names(client, tmp_path, monkeypatch, name):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "c"))
    rid = events(post(client).text)[-1][1]["review_id"]
    assert client.get(f"/api/review/{rid}/img/{name}").status_code == 404
    assert client.get(f"/api/review/nothing/img/{name}").status_code == 404
