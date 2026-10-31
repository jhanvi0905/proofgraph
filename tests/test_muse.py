"""Muse client: cached structured calls with a fake transport. No network."""

import json
from decimal import Decimal
from typing import Any, Mapping

import pytest
from pydantic import BaseModel

from proofgraph.cache import cache_key
from proofgraph.clients.muse import (
    RESPONSES_ENDPOINT,
    ExtractionFailed,
    MissingApiKeyError,
    MuseClient,
    MuseHTTPError,
    MuseResponseError,
    MuseTimeoutError,
    OpenAIResponsesTransport,
)
from proofgraph.config import MUSE_BASE_URL, ConfigError, load_settings


class Widget(BaseModel):
    name: str
    count: int


def _settings(tmp_path, **env: str):
    base = {"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)}
    base.update(env)
    return load_settings(base)


def _envelope(text: str) -> dict[str, Any]:
    return {
        "id": "resp_test",
        "object": "response",
        "status": "completed",
        "model": "muse-spark-1.3",
        "output": [
            {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}],
            }
        ],
    }


class FakeTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("transport called too many times")
        return self._responses.pop(0)

    @property
    def calls(self) -> int:
        return len(self.bodies)


def _client(tmp_path, transport: FakeTransport, **env: str) -> MuseClient:
    return MuseClient(_settings(tmp_path, **env), transport=transport)


def test_structured_call_matches_responses_schema(tmp_path):
    payload = json.dumps({"name": "carton", "count": 3})
    transport = FakeTransport([_envelope(payload)])
    client = _client(tmp_path, transport)

    result = client.structured("Count the cartons.", Widget)

    assert result == Widget(name="carton", count=3)
    assert transport.calls == 1
    body = transport.bodies[0]
    assert body["model"] == "muse-spark-1.3"
    assert body["input"] == "Count the cartons."
    assert body["reasoning"] == {"effort": "medium"}
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["name"] == "Widget"
    assert body["text"]["format"]["schema"] == Widget.model_json_schema()
    assert "strict" not in body["text"]["format"]
    assert "response_format" not in body
    assert set(body) == {"model", "input", "reasoning", "text"}
    assert "test-key" not in json.dumps(body)
    key = cache_key(
        model=body["model"],
        endpoint=RESPONSES_ENDPOINT,
        prompt=body["input"],
        schema=body["text"]["format"],
        inputs={"reasoning": body["reasoning"]},
        sample_idx=0,
    )
    stored = json.loads((tmp_path / f"{key}.json").read_text())
    assert stored["endpoint"] == RESPONSES_ENDPOINT
    assert stored["request"] == body
    assert stored["response"]["output"][0]["content"][0]["text"] == payload
    assert "test-key" not in json.dumps(stored)


def test_cache_hit_does_not_call_transport_twice(tmp_path):
    transport = FakeTransport([_envelope('{"name": "pallet", "count": 1}')])
    client = _client(tmp_path, transport)

    first = client.structured("Count the pallets.", Widget)
    second = client.structured("Count the pallets.", Widget)

    assert first == second == Widget(name="pallet", count=1)
    assert transport.calls == 1


def test_bad_json_gets_one_repair(tmp_path):
    valid = '{"name": "crate", "count": 4}'
    transport = FakeTransport(
        [
            _envelope("not json"),
            _envelope(valid),
            _envelope(valid),
        ]
    )
    client = _client(tmp_path, transport)

    result = client.structured("Count the crates.", Widget)

    assert result == Widget(name="crate", count=4)
    assert transport.calls == 2
    assert transport.bodies[0]["input"] == "Count the crates."
    assert "not json" in transport.bodies[1]["input"]
    assert "Count the crates." in transport.bodies[1]["input"]
    assert transport.bodies[1]["text"] == transport.bodies[0]["text"]
    assert transport.bodies[1]["reasoning"] == {"effort": "medium"}

    stored = list(tmp_path.glob("*.json"))
    assert len(stored) == 1
    record = json.loads(stored[0].read_text())
    assert "not json" in record["request"]["input"]
    assert record["response"]["output"][0]["content"][0]["text"] == valid

    again = client.structured("Count the crates.", Widget)
    assert again == result
    assert transport.calls == 3
    client.structured("Count the crates.", Widget)
    assert transport.calls == 3


def test_schema_mismatch_gets_one_repair(tmp_path):
    transport = FakeTransport(
        [
            _envelope('{"name": "crate"}'),
            _envelope('{"name": "crate", "count": 4}'),
        ]
    )
    client = _client(tmp_path, transport)

    result = client.structured("Count the crates.", Widget)

    assert result.count == 4
    assert transport.calls == 2
    stored = list(tmp_path.glob("*.json"))
    assert len(stored) == 1
    text = json.loads(stored[0].read_text())["response"]["output"][0]["content"][0]["text"]
    assert text == '{"name": "crate", "count": 4}'


def test_bad_json_twice_is_extraction_failed(tmp_path):
    transport = FakeTransport(
        [
            _envelope("nope"),
            _envelope("still nope"),
            _envelope("nope"),
            _envelope("still nope"),
        ]
    )
    client = _client(tmp_path, transport)

    with pytest.raises(ExtractionFailed, match="EXTRACTION_FAILED") as caught:
        client.structured("Count the crates.", Widget)

    assert caught.value.reason_code == "EXTRACTION_FAILED"
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []

    with pytest.raises(ExtractionFailed):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 4
    assert list(tmp_path.glob("*.json")) == []


def test_missing_key_does_not_call_transport(tmp_path):
    transport = FakeTransport([_envelope('{"name": "a", "count": 1}')])
    client = MuseClient(load_settings({"CACHE_DIR": str(tmp_path)}), transport=transport)

    with pytest.raises(MissingApiKeyError, match="MODEL_API_KEY"):
        client.structured("Count the crates.", Widget)

    assert transport.calls == 0
    assert list(tmp_path.glob("*.json")) == []


def test_blank_key_is_missing(tmp_path):
    transport = FakeTransport([])
    client = MuseClient(
        load_settings({"MODEL_API_KEY": "  ", "CACHE_DIR": str(tmp_path)}),
        transport=transport,
    )

    with pytest.raises(MissingApiKeyError):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 0


def test_timeout_is_explicit_and_does_not_repair(tmp_path):
    class TimeoutTransport:
        def __init__(self) -> None:
            self.calls = 0

        def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
            self.calls += 1
            raise TimeoutError("timed out")

    transport = TimeoutTransport()
    client = MuseClient(_settings(tmp_path), transport=transport)

    with pytest.raises(MuseTimeoutError):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 1
    assert list(tmp_path.glob("*.json")) == []

    with pytest.raises(MuseTimeoutError):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 2


def test_gateway_timeout_body_is_not_cached(tmp_path):
    body = {
        "error": {
            "message": "Request exceeded the non-streaming server time limit.",
            "type": "server_error",
            "param": None,
            "code": "gateway_timeout",
        }
    }
    transport = FakeTransport([body, body])
    client = _client(tmp_path, transport)

    with pytest.raises(MuseTimeoutError):
        client.structured("Count the crates.", Widget)
    with pytest.raises(MuseTimeoutError):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_malformed_response_is_explicit_and_does_not_repair(tmp_path):
    bad = {"status": "completed", "output": [{"type": "reasoning", "summary": []}]}
    transport = FakeTransport([bad, bad])
    client = _client(tmp_path, transport)

    with pytest.raises(MuseResponseError, match="output_text"):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 1
    assert list(tmp_path.glob("*.json")) == []

    with pytest.raises(MuseResponseError):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_failed_status_is_not_cached(tmp_path):
    fail = {"status": "failed"}
    transport = FakeTransport([fail, fail])
    client = _client(tmp_path, transport)

    with pytest.raises(MuseResponseError, match="failed"):
        client.structured("Count the crates.", Widget)
    with pytest.raises(MuseResponseError, match="failed"):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_refusal_is_not_repaired(tmp_path):
    refusal = {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [{"type": "refusal", "refusal": "cannot do that"}],
            }
        ],
    }
    transport = FakeTransport([refusal, refusal])
    client = _client(tmp_path, transport)

    with pytest.raises(MuseResponseError, match="cannot do that"):
        client.structured("Count the crates.", Widget)
    with pytest.raises(MuseResponseError, match="cannot do that"):
        client.structured("Count the crates.", Widget)
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_output_text_field_is_accepted(tmp_path):
    transport = FakeTransport([{"output_text": '{"name": "box", "count": 2}'}])
    client = _client(tmp_path, transport)

    assert client.structured("Count the boxes.", Widget) == Widget(name="box", count=2)


def test_none_reasoning_does_not_call_transport(tmp_path):
    transport = FakeTransport([])
    client = _client(tmp_path, transport)

    with pytest.raises(ValueError, match="none"):
        client.structured("Count the crates.", Widget, reasoning_effort="none")
    assert transport.calls == 0


def test_max_reasoning_is_not_sent(tmp_path):
    transport = FakeTransport([])
    client = _client(tmp_path, transport)

    with pytest.raises(ValueError, match="xhigh"):
        client.structured("Count the crates.", Widget, reasoning_effort="max")
    assert transport.calls == 0


def test_reasoning_effort_is_part_of_the_cache_key(tmp_path):
    transport = FakeTransport(
        [
            _envelope('{"name": "a", "count": 1}'),
            _envelope('{"name": "b", "count": 2}'),
        ]
    )
    client = _client(tmp_path, transport)

    medium = client.structured("Count.", Widget, reasoning_effort="medium")
    low = client.structured("Count.", Widget, reasoning_effort="low")

    assert medium.count == 1
    assert low.count == 2
    assert transport.calls == 2
    assert transport.bodies[1]["reasoning"] == {"effort": "low"}


def test_prompt_model_schema_and_sample_miss_the_cache(tmp_path):
    class Gadget(BaseModel):
        name: str
        count: int

    payload = _envelope('{"name": "a", "count": 1}')
    transport = FakeTransport([payload, payload, payload, payload, payload])
    client = _client(tmp_path, transport)

    assert client.structured("Count.", Widget).count == 1
    assert client.structured("Count.", Widget).count == 1
    assert transport.calls == 1

    client.structured("Count the other pile.", Widget)
    assert transport.calls == 2

    client.structured("Count.", Widget, sample_idx=1)
    assert transport.calls == 3

    shifted = MuseClient(
        _settings(tmp_path, MUSE_MODEL="muse-other"),
        transport=transport,
        cache=client.cache,
    )
    shifted.structured("Count.", Widget)
    assert transport.calls == 4
    assert transport.bodies[-1]["model"] == "muse-other"

    client.structured("Count.", Gadget)
    assert transport.calls == 5


def test_bypass_cache_skips_read_and_write(tmp_path):
    transport = FakeTransport(
        [
            _envelope('{"name": "a", "count": 1}'),
            _envelope('{"name": "b", "count": 2}'),
            _envelope("not json"),
            _envelope('{"name": "c", "count": 3}'),
        ]
    )
    client = _client(tmp_path, transport)

    first = client.structured("Count.", Widget)
    assert first.count == 1
    second = client.structured("Count.", Widget, bypass_cache=True)
    assert second.count == 2
    assert transport.calls == 2
    stored = list(tmp_path.glob("*.json"))
    assert len(stored) == 1
    record = json.loads(stored[0].read_text())
    assert record["response"]["output"][0]["content"][0]["text"] == '{"name": "a", "count": 1}'

    repaired = client.structured("Repair me.", Widget, bypass_cache=True)
    assert repaired.count == 3
    assert transport.calls == 4
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_invalid_cached_payload_is_not_replayed(tmp_path):
    transport = FakeTransport(
        [
            _envelope('{"name": "ok", "count": 1}'),
            _envelope('{"name": "ok", "count": 2}'),
        ]
    )
    client = _client(tmp_path, transport)

    assert client.structured("Count.", Widget).count == 1
    path = next(tmp_path.glob("*.json"))
    record = json.loads(path.read_text())
    record["response"] = {"output_text": "not json"}
    path.write_text(json.dumps(record), encoding="utf-8")

    assert client.structured("Count.", Widget).count == 2
    assert transport.calls == 2
    restored = json.loads(path.read_text())
    assert restored["response"]["output"][0]["content"][0]["text"] == '{"name": "ok", "count": 2}'


def test_cache_key_ignores_dict_order():
    left = cache_key(
        model="muse-spark-1.3",
        endpoint=RESPONSES_ENDPOINT,
        prompt="a",
        schema={"b": 1, "a": {"d": 2, "c": 3}},
        inputs={"reasoning": {"effort": "medium"}},
        sample_idx=0,
    )
    right = cache_key(
        model="muse-spark-1.3",
        endpoint=RESPONSES_ENDPOINT,
        prompt="a",
        schema={"a": {"c": 3, "d": 2}, "b": 1},
        inputs={"reasoning": {"effort": "medium"}},
        sample_idx=0,
    )
    assert left == right
    assert len(left) == 64
    assert left != cache_key(
        model="muse-spark-1.3",
        endpoint=RESPONSES_ENDPOINT,
        prompt="b",
        schema={"b": 1, "a": {"d": 2, "c": 3}},
        inputs={"reasoning": {"effort": "medium"}},
        sample_idx=0,
    )


def test_spend_limit_defaults_to_50_and_a_lower_setting_is_kept():
    defaults = load_settings({})
    assert defaults.spend_limit_usd == Decimal("50")
    assert defaults.model_api_key is None
    assert defaults.muse_model == "muse-spark-1.3"
    assert defaults.cache_dir.as_posix() == "cache"
    assert defaults.muse_base_url == MUSE_BASE_URL

    lowered = load_settings({"SPEND_LIMIT_USD": "4", "MUSE_MODEL": "muse-spark-1.3"})
    assert lowered.spend_limit_usd == Decimal("4")
    assert lowered.muse_model == "muse-spark-1.3"
    assert MuseClient(lowered, transport=FakeTransport([])).spend_limit_usd == Decimal("4")


def test_invalid_spend_limit_is_an_error():
    with pytest.raises(ConfigError, match="SPEND_LIMIT_USD"):
        load_settings({"SPEND_LIMIT_USD": "lots"})


def test_openai_transport_sends_the_documented_request(tmp_path, monkeypatch):
    captured: dict[str, Any] = {}

    class _Response:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            assert mode == "json"
            return _envelope('{"name": "drum", "count": 8}')

    class _Responses:
        def create(self, **kwargs: Any) -> _Response:
            captured["kwargs"] = kwargs
            return _Response()

    class _OpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["init"] = kwargs
            self.responses = _Responses()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _OpenAI)
    client = MuseClient(_settings(tmp_path))

    result = client.structured("Count the drums.", Widget)

    assert result == Widget(name="drum", count=8)
    assert captured["init"] == {
        "api_key": "test-key",
        "base_url": MUSE_BASE_URL,
        "max_retries": 0,
        "timeout": 180.0,
    }
    assert captured["kwargs"]["model"] == "muse-spark-1.3"
    assert captured["kwargs"]["input"] == "Count the drums."
    assert captured["kwargs"]["reasoning"] == {"effort": "medium"}
    assert captured["kwargs"]["text"]["format"]["type"] == "json_schema"
    assert set(captured["kwargs"]) == {"model", "input", "reasoning", "text"}


class RecordingFiles:
    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def create(self, *, filename: str, content: bytes, purpose: str) -> dict[str, Any]:
        self.calls.append({"filename": filename, "content": content, "purpose": purpose})
        if self._responses:
            return self._responses.pop(0)
        return {"id": f"file_{len(self.calls)}"}


def test_upload_caches_file_id_under_sha256_of_bytes(tmp_path):
    import hashlib

    content = b"%PDF-rate"
    first_path = tmp_path / "rate.pdf"
    renamed = tmp_path / "copy.pdf"
    other = tmp_path / "other.pdf"
    first_path.write_bytes(content)
    renamed.write_bytes(content)
    other.write_bytes(b"%PDF-other")
    files = RecordingFiles()
    client = MuseClient(_settings(tmp_path), transport=FakeTransport([]), files_transport=files)

    assert client.upload_user_data(first_path) == "file_1"
    assert client.upload_user_data(renamed) == "file_1"
    assert client.upload_user_data(other) == "file_2"
    assert [call["purpose"] for call in files.calls] == ["user_data", "user_data"]
    assert [call["filename"] for call in files.calls] == ["rate.pdf", "other.pdf"]
    assert files.calls[0]["content"] == content

    digest = hashlib.sha256(content).hexdigest()
    stored = json.loads((tmp_path / "files" / f"{digest}.json").read_text(encoding="utf-8"))
    assert stored["endpoint"] == "POST /v1/files"
    assert stored["request"] == {"purpose": "user_data", "sha256": digest}
    assert stored["response"] == {"id": "file_1"}
    assert content.decode() not in json.dumps(stored)

    fresh = RecordingFiles([{"id": "file_should_not_be_used"}])
    again = MuseClient(
        _settings(tmp_path),
        transport=FakeTransport([]),
        files_transport=fresh,
        cache=client.cache,
    )
    assert again.upload_user_data(first_path) == "file_1"
    assert fresh.calls == []


def test_poisoned_file_cache_is_uploaded_again(tmp_path):
    import hashlib

    from proofgraph.cache import CachedCall, DiskCache

    content = b"pdf-bytes"
    path = tmp_path / "rate.pdf"
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    DiskCache(tmp_path / "files").put(
        CachedCall(
            key=digest,
            endpoint="POST /v1/responses",
            request={"purpose": "user_data", "sha256": digest},
            response={"id": "stale"},
        )
    )
    files = RecordingFiles([{"id": "file_fresh"}])
    client = MuseClient(_settings(tmp_path), transport=FakeTransport([]), files_transport=files)

    assert client.upload_user_data(path) == "file_fresh"
    assert len(files.calls) == 1
    stored = json.loads((tmp_path / "files" / f"{digest}.json").read_text(encoding="utf-8"))
    assert stored["response"] == {"id": "file_fresh"}
    assert stored["endpoint"] == "POST /v1/files"


def test_upload_without_an_id_is_not_cached(tmp_path):
    path = tmp_path / "rate.pdf"
    path.write_bytes(b"pdf")
    files = RecordingFiles([{"object": "file"}])
    client = MuseClient(_settings(tmp_path), transport=FakeTransport([]), files_transport=files)

    with pytest.raises(MuseResponseError, match="file id"):
        client.upload_user_data(path)

    assert files.calls[0]["purpose"] == "user_data"
    assert list((tmp_path / "files").glob("*.json")) == []


def test_missing_key_does_not_upload(tmp_path):
    path = tmp_path / "rate.pdf"
    path.write_bytes(b"pdf")
    files = RecordingFiles()
    client = MuseClient(load_settings({"CACHE_DIR": str(tmp_path)}), files_transport=files)

    with pytest.raises(MissingApiKeyError, match="MODEL_API_KEY"):
        client.upload_user_data(path)

    assert files.calls == []
    assert list(tmp_path.glob("*.json")) == []


def test_file_parts_stay_on_the_repair_and_change_the_cache_key(tmp_path):
    transport = FakeTransport(
        [
            _envelope("not json"),
            _envelope('{"name": "crate", "count": 4}'),
            _envelope('{"name": "a", "count": 1}'),
            _envelope('{"name": "b", "count": 2}'),
        ]
    )
    client = _client(tmp_path, transport)

    result = client.structured("Count the crates.", Widget, file_ids=["file_abc"])

    assert result == Widget(name="crate", count=4)
    first = transport.bodies[0]["input"]
    second = transport.bodies[1]["input"]
    assert first[0]["content"][0]["type"] == "input_text"
    assert first[0]["content"][0]["text"] == "Count the crates."
    assert "File id:" not in first[0]["content"][0]["text"]
    assert first[0]["content"][1] == {
        "type": "input_file",
        "file_id": "file_abc",
        "detail": "high",
    }
    assert second[0]["content"][1] == first[0]["content"][1]
    assert "not json" in second[0]["content"][0]["text"]
    assert set(transport.bodies[0]) == {"model", "input", "reasoning", "text"}

    cached = client.structured("Count.", Widget, file_ids=["file_a"])
    assert cached.count == 1
    assert client.structured("Count.", Widget, file_ids=["file_a"]).count == 1
    assert transport.calls == 3
    other = client.structured("Count.", Widget, file_ids=["file_b"])
    assert other.count == 2
    assert transport.calls == 4
    assert transport.bodies[3]["input"][0]["content"][1]["file_id"] == "file_b"


def test_openai_files_transport_uploads_user_data(tmp_path, monkeypatch):
    content = b"%PDF-1.4\n"
    path = tmp_path / "nested" / "rate.pdf"
    path.parent.mkdir()
    path.write_bytes(content)
    captured: dict[str, Any] = {}

    class _File:
        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            assert mode == "json"
            return {
                "id": "file_uploaded",
                "object": "file",
                "bytes": len(content),
                "filename": "rate.pdf",
                "purpose": "user_data",
            }

    class _Files:
        def create(self, **kwargs: Any) -> _File:
            captured["kwargs"] = kwargs
            return _File()

    class _OpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["init"] = kwargs
            self.files = _Files()

    import openai

    monkeypatch.setattr(openai, "OpenAI", _OpenAI)
    client = MuseClient(_settings(tmp_path))

    assert client.upload_user_data(path) == "file_uploaded"
    assert captured["init"] == {
        "api_key": "test-key",
        "base_url": MUSE_BASE_URL,
        "max_retries": 0,
    }
    assert captured["kwargs"]["file"] == ("rate.pdf", content)
    assert captured["kwargs"]["purpose"] == "user_data"
    assert set(captured["kwargs"]) == {"file", "purpose"}
    assert "nested" not in json.dumps(captured["kwargs"]["file"][0])
    stored = json.loads(next((tmp_path / "files").glob("*.json")).read_text(encoding="utf-8"))
    assert stored["response"] == {"id": "file_uploaded"}
    assert "nested" not in json.dumps(stored)
    assert "filename" not in stored["response"]


# ---- HTTP retries ----


class ScriptedTransport:
    """Each item is a response to return or an exception to raise."""

    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self.calls = 0

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.calls += 1
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


_OK = _envelope('{"name": "crate", "count": 2}')


def _retrying(tmp_path, items: list[Any]):
    transport = ScriptedTransport(items)
    sleeps: list[float] = []
    client = MuseClient(_settings(tmp_path), transport=transport, sleep=sleeps.append)
    return client, transport, sleeps


def test_429_429_200_succeeds_after_two_retries(tmp_path):
    client, transport, sleeps = _retrying(
        tmp_path, [MuseHTTPError(429, "slow down"), MuseHTTPError(429, "slow down"), _OK]
    )

    assert client.structured("Count.", Widget) == Widget(name="crate", count=2)
    assert transport.calls == 3
    assert len(sleeps) == 2
    assert 1.0 <= sleeps[0] < 2.0
    assert 2.0 <= sleeps[1] < 3.0


def test_five_429s_raise_after_exactly_four_retries(tmp_path):
    client, transport, sleeps = _retrying(
        tmp_path, [MuseHTTPError(429, "slow down") for _ in range(5)]
    )

    with pytest.raises(MuseHTTPError) as caught:
        client.structured("Count.", Widget)
    assert caught.value.status_code == 429
    assert transport.calls == 5
    assert len(sleeps) == 4
    assert list(tmp_path.glob("*.json")) == []


def test_a_500_is_retried(tmp_path):
    client, transport, _ = _retrying(tmp_path, [MuseHTTPError(500, "oops"), _OK])

    assert client.structured("Count.", Widget).count == 2
    assert transport.calls == 2


def test_a_400_is_not_retried(tmp_path):
    client, transport, sleeps = _retrying(tmp_path, [MuseHTTPError(400, "bad request")])

    with pytest.raises(MuseResponseError):
        client.structured("Count.", Widget)
    assert transport.calls == 1
    assert sleeps == []


def test_retry_after_is_honored(tmp_path):
    client, transport, sleeps = _retrying(
        tmp_path, [MuseHTTPError(429, "slow down", retry_after=7.0), _OK]
    )

    client.structured("Count.", Widget)
    assert sleeps == [7.0]


def test_a_timeout_is_neither_retried_nor_repaired(tmp_path):
    client, transport, sleeps = _retrying(tmp_path, [TimeoutError("slow")])

    with pytest.raises(MuseTimeoutError):
        client.structured("Count.", Widget)
    assert transport.calls == 1
    assert sleeps == []


def test_a_retry_does_not_burn_the_one_repair(tmp_path):
    client, transport, _ = _retrying(
        tmp_path,
        [
            MuseHTTPError(503, "down"),
            _envelope("not json"),
            MuseHTTPError(429, "slow"),
            _OK,
        ],
    )

    assert client.structured("Count.", Widget).count == 2
    assert transport.calls == 4


def test_bad_json_after_the_repair_is_extraction_failed_with_a_code(tmp_path):
    client, transport, _ = _retrying(tmp_path, [_envelope("nope"), _envelope("still nope")])

    with pytest.raises(ExtractionFailed) as caught:
        client.structured("Count.", Widget)
    assert caught.value.reason_code == "EXTRACTION_FAILED"
    assert transport.calls == 2
    assert list(tmp_path.glob("*.json")) == []


def test_openai_transport_sets_the_timeout_and_reads_retry_after(tmp_path, monkeypatch):
    import httpx2 as httpx
    import openai

    captured: dict[str, Any] = {}

    class _Responses:
        def create(self, **kwargs: Any) -> Any:
            captured["kwargs"] = kwargs
            request = httpx.Request("POST", "https://api.meta.ai/v1/responses")
            response = httpx.Response(429, headers={"retry-after": "3"}, request=request)
            raise openai.RateLimitError("slow down", response=response, body=None)

    class _OpenAI:
        def __init__(self, **kwargs: Any) -> None:
            captured["init"] = kwargs
            self.responses = _Responses()

    monkeypatch.setattr(openai, "OpenAI", _OpenAI)
    transport = OpenAIResponsesTransport(api_key="k", base_url=MUSE_BASE_URL)

    with pytest.raises(MuseHTTPError) as caught:
        transport.create({"model": "m", "input": "x", "reasoning": {}, "text": {}})
    assert caught.value.status_code == 429
    assert caught.value.retry_after == 3.0
    assert captured["init"]["timeout"] == 180.0
    assert captured["init"]["max_retries"] == 0


def test_ensure_budget_raises_at_the_cap_and_sends_nothing(tmp_path):
    from proofgraph.spend import SpendCapReached

    transport = FakeTransport([])
    client = _client(tmp_path, transport, SPEND_LIMIT_USD="0.01")
    with pytest.raises(SpendCapReached):
        client.ensure_budget()
    assert transport.calls == 0


def test_ensure_budget_passes_under_the_cap(tmp_path):
    _client(tmp_path, FakeTransport([]), SPEND_LIMIT_USD="50").ensure_budget()
