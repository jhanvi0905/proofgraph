"""Runs on a visitor's own API key: used when given, outside the cap and limit, and never leaked. Offline, mocked."""

import json
import logging
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.keyed as keyed_mod
from app.server import create_app
from proofgraph.clients.muse import MuseHTTPError
from tests.test_review_run import CLAIM, GOOD, PDF, SPLIT1, FakeTransport, _muse
from tests.test_server import events

KEY = "mk-live-SECRETSECRET1234567890"
BKEY = "bt-live-SECRETSECRET0987654321"


class FakeResponses:
    """Stands in for the OpenAI-SDK transport; records the key it was built with."""

    built: list[str] = []
    script: FakeTransport | None = None
    fail: Exception | None = None

    def __init__(self, *, api_key, base_url):
        FakeResponses.built.append(api_key)

    def create(self, body):
        if FakeResponses.fail is not None:
            raise FakeResponses.fail
        return FakeResponses.script.create(body)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_PASSCODE", raising=False)
    monkeypatch.delenv("PROOFGRAPH_GRAPH", raising=False)
    monkeypatch.delenv("BASETEN_API_KEY", raising=False)
    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("SPEND_LIMIT_USD", "1")
    monkeypatch.setenv("LIVE_RUNS_PER_HOUR", "1")
    monkeypatch.setattr(keyed_mod, "OpenAIResponsesTransport", FakeResponses)
    FakeResponses.built, FakeResponses.fail = [], None
    FakeResponses.script = FakeTransport(SPLIT1, GOOD, SPLIT1, GOOD, SPLIT1, GOOD)
    return tmp_path


def post(c, path="/api/review", **extra):
    data = {"claim": CLAIM, **extra}
    return c.post(path, data=data, files={"files": ("rate.pdf", PDF.read_bytes(), "application/pdf")})


def everything_on_disk(root: Path) -> str:
    return "".join(f.read_bytes().decode("latin-1") for f in root.rglob("*") if f.is_file())


def plain_client(tmp_path):
    return TestClient(create_app(lambda: _muse(tmp_path, FakeTransport(SPLIT1, GOOD, SPLIT1, GOOD), limit="1")))


def test_supplied_key_builds_the_clients_and_the_server_client_is_not_used(env):
    seen, plain = [], []

    def make_keyed(meta, baseten):
        seen.append((meta, baseten))
        return _muse(env, FakeTransport(SPLIT1, GOOD)), (lambda q, s: "entails"), keyed_mod.KeyedRun(meta, baseten)

    c = TestClient(create_app(lambda: plain.append(1), make_keyed))
    r = post(c, meta_api_key=f"  {KEY}  ", baseten_api_key=BKEY)
    assert events(r.text)[-1][0] == "done"
    assert seen == [(KEY, BKEY)] and plain == []


def test_real_builder_uses_the_key_for_the_meta_call_and_no_baseten_key_means_no_second_reader(env, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "server-baseten")  # the host's own key must not be borrowed
    c = TestClient(create_app(lambda: pytest.fail("the server client must not run")))
    evs = events(post(c, meta_api_key=KEY).text)
    assert evs[-1][0] == "done" and FakeResponses.built == [KEY]
    muse, checker, run = keyed_mod.keyed_clients(KEY)
    assert muse.settings.baseten_api_key is None
    with pytest.raises(Exception, match="BASETEN_API_KEY is not set"):
        checker("a quote", "a statement")


def test_limiter_and_spend_cap_bypassed_only_with_a_key(env):
    (env / "spend.ledger").write_text(json.dumps({"total_usd": "1000"}))  # the demo's cap is long gone
    c = TestClient(create_app(lambda: _muse(env, FakeTransport(SPLIT1, GOOD), limit="1")))
    first = events(post(c).text)[-1]
    assert first[0] == "done" and "spend cap" in " ".join(first[1]["banners"])  # no key: capped
    assert post(c).status_code == 429  # no key: the per-visitor limit
    for _ in range(3):  # a key: neither applies
        last = events(post(c, meta_api_key=KEY).text)[-1]
        assert last[0] == "done" and last[1]["status"] == "contradicted" and last[1]["banners"] == []
    assert json.loads((env / "spend.ledger").read_text())["total_usd"] == "1000"  # their spend is not ours
    assert Decimal(json.loads((env / "spend.ledger").read_text())["total_usd"]) == 1000


def test_key_never_appears_in_bodies_logs_or_files(env, caplog):
    caplog.set_level(logging.DEBUG)
    c = TestClient(create_app())
    ok = post(c, meta_api_key=KEY, baseten_api_key=BKEY)
    FakeResponses.fail = RuntimeError(f"upstream said: bad token {KEY} / {BKEY}")
    broken = post(c, meta_api_key=KEY, baseten_api_key=BKEY, claim="Detention is a different claim entirely.")
    rid = events(ok.text)[-1][1]["review_id"]
    seen = [ok.text, broken.text, c.get(f"/api/review/{rid}").text, c.get(f"/r/{rid}").text, caplog.text,
            everything_on_disk(env)]
    for chunk in seen:
        assert KEY not in chunk and BKEY not in chunk
    assert "[your key]" in broken.text  # the failure was reported, with the key struck out


def test_key_is_not_part_of_the_cache_keys(env):
    """A cache entry is named by model, prompt, schema, inputs: the same packet under two keys hits the same entries."""
    c = TestClient(create_app())
    post(c, meta_api_key=KEY)
    first = sorted(p.name for p in env.glob("*.json"))
    FakeResponses.script = FakeTransport(SPLIT1, GOOD)
    post(c, meta_api_key="mk-another-key-9876543210")
    assert first and sorted(p.name for p in env.glob("*.json")) == first
    assert all(len(n) == 64 + len(".json") for n in first)


def test_invalid_key_is_a_friendly_refusal_not_a_trace(env):
    FakeResponses.fail = MuseHTTPError(401, f"Muse request failed: Error code: 401 - Incorrect API key provided: {KEY}")
    c = TestClient(create_app())
    r = post(c, meta_api_key=KEY)
    evs = events(r.text)
    assert [n for n, _ in evs][-1] == "failed" and "done" not in [n for n, _ in evs]
    text = evs[-1][1]["text"]
    assert "did not accept the API key" in text and KEY not in r.text and "Traceback" not in r.text
    assert not list((env / "reviews").glob("*.json")) if (env / "reviews").exists() else True


@pytest.mark.parametrize("fields,msg", [({"meta_api_key": "has space and \"quote\""}, "does not look like an API key"),
                                        ({"meta_api_key": "short"}, "does not look like an API key"),
                                        ({"baseten_api_key": BKEY}, "Meta key too")])
def test_malformed_or_orphan_keys_are_refused_before_any_client(env, fields, msg):
    built = []
    c = TestClient(create_app(lambda: built.append(1), lambda *a: built.append(a)))
    r = post(c, **fields)
    assert r.status_code == 400 and msg in r.json()["refusal"] and built == []
    for v in fields.values():
        assert v not in r.text


def test_a_key_does_not_weaken_the_passcode(env, monkeypatch):
    monkeypatch.setenv("APP_PASSCODE", "open-sesame")
    built = []
    c = TestClient(create_app(lambda: built.append(1), lambda *a: built.append(a)))
    assert post(c, meta_api_key=KEY).status_code == 401
    assert post(c, passcode="wrong", meta_api_key=KEY).status_code == 401
    assert built == []
    ok = TestClient(create_app())
    assert events(post(ok, passcode="open-sesame", meta_api_key=KEY).text)[-1][0] == "done"


def test_ask_and_sample_routes_take_the_key_too(env, monkeypatch):
    c = TestClient(create_app())
    first = events(post(c, meta_api_key=KEY).text)[-1][1]["review_id"]
    ask = c.post(f"/api/review/{first}/ask", data={"claim": CLAIM, "meta_api_key": KEY})
    assert events(ask.text)[-1][0] == "done"
    (env / "rate.pdf").write_bytes(PDF.read_bytes())
    manifest = env / "samples.json"
    manifest.write_text(json.dumps({"samples": [{"id": "a", "title": "Rate", "claim": CLAIM, "files": ["rate.pdf"]}]}))
    monkeypatch.setenv("PROOFGRAPH_SAMPLES", str(manifest))
    sample = c.post("/api/sample/a", data={"meta_api_key": KEY})
    assert events(sample.text)[-1][0] == "done"
    assert FakeResponses.built.count(KEY) == 3
    assert KEY not in ask.text + sample.text + everything_on_disk(env)


def test_no_key_means_the_existing_path_exactly(env):
    built = []
    c = TestClient(create_app(lambda: _muse(env, FakeTransport(SPLIT1, GOOD), limit="0"), lambda *a: built.append(a)))
    assert events(post(c).text)[-1][0] == "done" and built == []
