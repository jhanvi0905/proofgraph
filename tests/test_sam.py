"""SAM count. No network and no image file."""

import base64
import json
from typing import Any, Mapping, get_type_hints

import pytest

from proofgraph.clients.sam import SamClient, sam_count
from proofgraph.config import DEFAULT_SAM_MODEL, load_settings

STILL = b"drawn-still"
NOUN = "cardboard box"
SAMPLE = "<|box;x1=261;y1=463;x2=419;y2=611;w=960;h=720|>"
DECOY = "<|mask;x=0;y=0;data=46,101,~MASK<|box;not-counted|>"


def _settings(cache):
    return load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(cache)})


def _record(index: int) -> str:
    if index == 0:
        box = SAMPLE
        mask = DECOY
    else:
        box = f"<|box;x1={261 + index};y1=463;x2=419;y2=611;w=960;h=720|>"
        mask = f"<|mask;x=0;y=0;data=12,8,~PAYLOAD{index}|>"
    return f"{index}{box}{mask}"


def _segmentation(count: int) -> str:
    return "<0f>" + ",".join(_record(index) for index in range(count))


def _events(output_text: str) -> list[dict[str, Any]]:
    return [
        {"type": "response.output_text.delta", "delta": SAMPLE},
        {
            "type": "response.completed",
            "response": {"status": "completed", "output_text": output_text},
        },
    ]


class FakeTransport:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = list(events)
        self.bodies: list[dict[str, Any]] = []

    def stream(self, body: Mapping[str, Any]):
        self.bodies.append(json.loads(json.dumps(body)))
        yield from self._events

    @property
    def calls(self) -> int:
        return len(self.bodies)


def _use(monkeypatch: pytest.MonkeyPatch, client: SamClient) -> None:
    monkeypatch.setattr(
        "proofgraph.clients.sam.SamClient",
        lambda *args, **kwargs: client,
    )


def _part(content: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next(part for part in content if part["type"] == kind)


def _assert_still_request(body: dict[str, Any], data_url: str) -> None:
    assert set(body) == {"model", "input", "stream"}
    assert body["model"] == DEFAULT_SAM_MODEL
    assert body["model"] == "sam-3.1"
    assert body["stream"] is True
    message = body["input"][0]
    assert message["role"] == "user"
    content = message["content"]
    assert [part["type"] for part in content] == ["input_text", "input_image"]
    assert _part(content, "input_text") == {"type": "input_text", "text": NOUN}
    assert _part(content, "input_image") == {
        "type": "input_image",
        "image_url": data_url,
    }
    wire = json.dumps(body)
    assert "file_id" not in wire
    assert "test-key" not in wire
    assert "<|" not in wire


def test_sam_count_reads_completed_box_records(tmp_path, monkeypatch):
    hints = get_type_hints(sam_count)
    assert list(hints) == ["still", "noun", "return"]
    assert hints["still"] is bytes
    assert hints["noun"] is str
    assert hints["return"] is int
    parameters = sam_count.__code__.co_varnames[: sam_count.__code__.co_argcount]
    assert parameters == ("still", "noun")
    with pytest.raises(TypeError):
        sam_count(STILL, NOUN, "file-abc")  # type: ignore[misc]

    segmented = _segmentation(12)
    assert segmented.count("<|box;") == 13
    assert segmented.count("<|mask;") == 12
    data_url = "data:image/png;base64," + base64.b64encode(STILL).decode("ascii")

    boxes = FakeTransport(_events(segmented))
    _use(monkeypatch, SamClient(_settings(tmp_path / "boxes"), transport=boxes))

    assert sam_count(STILL, NOUN) == 12
    assert boxes.calls == 1
    _assert_still_request(boxes.bodies[0], data_url)

    empty = FakeTransport(_events(""))
    _use(monkeypatch, SamClient(_settings(tmp_path / "empty"), transport=empty))

    assert sam_count(STILL, NOUN) == 0
    assert empty.calls == 1
    _assert_still_request(empty.bodies[0], data_url)
