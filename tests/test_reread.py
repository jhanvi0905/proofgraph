"""Blind re-read. No network and no image file."""

import base64
import json
from pathlib import Path
from typing import Any, Mapping, get_type_hints

import pytest

from proofgraph.clients.checker import (
    CheckerClient,
    CheckerError,
    ImageRejected,
    blind_reread,
    clocks_agree,
)
from proofgraph.config import DEFAULT_CHECKER_MODEL, DEFAULT_MUSE_MODEL, load_settings

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts" / "blind_reread.md"
CROP = b"clock-crop"


def _settings(cache: Path):
    return load_settings({"BASETEN_API_KEY": "test-key", "CACHE_DIR": str(cache)})


def _chat(text: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "model": DEFAULT_CHECKER_MODEL,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


class FakeTransport:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> Any:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("transport called too many times")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    @property
    def calls(self) -> int:
        return len(self.bodies)


def _use(monkeypatch: pytest.MonkeyPatch, client: CheckerClient) -> None:
    monkeypatch.setattr(
        "proofgraph.clients.checker.CheckerClient",
        lambda *args, **kwargs: client,
    )


def _client(cache: Path, transport: FakeTransport, image_transport: FakeTransport) -> CheckerClient:
    return CheckerClient(
        _settings(cache),
        transport=transport,
        image_transport=image_transport,
    )


def _part(content: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next(part for part in content if part["type"] == kind)


def test_blind_reread_sends_image_url_matches_clocks_and_falls_back(tmp_path, monkeypatch):
    hints = get_type_hints(blind_reread)
    assert list(hints) == ["crop", "return"]
    assert hints["crop"] is bytes
    assert hints["return"] is str
    parameters = blind_reread.__code__.co_varnames[: blind_reread.__code__.co_argcount]
    assert parameters == ("crop",)
    with pytest.raises(TypeError):
        blind_reread(CROP, "07:40")  # type: ignore[misc]

    assert clocks_agree("7:40", "07:40")
    assert clocks_agree("07:40", "7:40")
    assert clocks_agree("7:40", "7:41") is False

    data_url = "data:image/png;base64," + base64.b64encode(CROP).decode("ascii")
    prompt = PROMPT.read_text(encoding="utf-8").strip()
    reading = json.dumps({"value": "7:40"})

    baseten = FakeTransport([_chat(reading)])
    muse = FakeTransport([])
    _use(monkeypatch, _client(tmp_path / "ok", baseten, muse))

    assert blind_reread(CROP) == "7:40"
    assert blind_reread(CROP) == "7:40"
    assert clocks_agree("7:40", "07:40")

    assert baseten.calls == 1
    assert muse.calls == 0
    body = baseten.bodies[0]
    assert body["model"] == DEFAULT_CHECKER_MODEL
    assert body["model"] == "meta-models/muse-spark-open-1026"
    content = body["messages"][0]["content"]
    assert _part(content, "text") == {"type": "text", "text": prompt}
    assert _part(content, "image_url") == {
        "type": "image_url",
        "image_url": {"url": data_url, "detail": "high"},
    }
    wire = json.dumps(body)
    assert "input_image" not in wire
    assert "07:40" not in wire
    assert "test-key" not in wire

    baseten = FakeTransport([ImageRejected("Baseten rejected the image")])
    muse = FakeTransport([{"output_text": reading, "status": "completed"}])
    _use(monkeypatch, _client(tmp_path / "fallback", baseten, muse))

    fallback_read = blind_reread(CROP)
    assert fallback_read == "7:40"
    assert clocks_agree(fallback_read, "07:40")

    assert baseten.calls == 1
    assert muse.calls == 1
    rejected = baseten.bodies[0]["messages"][0]["content"]
    assert _part(rejected, "image_url")["image_url"]["url"] == data_url
    fallback = muse.bodies[0]
    assert fallback["model"] == DEFAULT_MUSE_MODEL
    assert fallback["model"] == "muse-spark-1.3"
    parts = fallback["input"][0]["content"]
    assert [part["type"] for part in parts] == ["input_text", "input_image"]
    assert _part(parts, "input_image") == {
        "type": "input_image",
        "image_url": data_url,
        "detail": "high",
    }

    baseten = FakeTransport(
        [CheckerError("blind checker request failed", status_code=400)]
    )
    muse = FakeTransport([{"output_text": reading}])
    _use(monkeypatch, _client(tmp_path / "other", baseten, muse))

    with pytest.raises(CheckerError, match="request failed") as caught:
        blind_reread(CROP)

    assert caught.value.status_code == 500
    assert baseten.calls == 1
    assert muse.calls == 0
