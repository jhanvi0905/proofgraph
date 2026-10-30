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


# ---- retries and spend ----

from decimal import Decimal  # noqa: E402

from proofgraph.clients.muse import MuseError, SpendCapReached  # noqa: E402
from proofgraph.clients.sam import SamError  # noqa: E402
from proofgraph.spend import SpendLedger  # noqa: E402


def _with_usage(output_text: str, **usage: int) -> list[dict[str, Any]]:
    events = _events(output_text)
    events[-1]["response"]["usage"] = usage
    return events


class ScriptedStream:
    """Each item is an event list to stream or an exception to raise."""

    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self.calls = 0

    def stream(self, body: Mapping[str, Any]):
        self.calls += 1
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        yield from item


def _sam(tmp_path, transport, sleeps=None, **env):
    settings = load_settings(
        {"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path), **env}
    )
    return SamClient(
        settings,
        transport=transport,
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
    )


def test_sam_adds_the_cost_of_a_call_and_a_cache_hit_adds_nothing(tmp_path):
    events = _with_usage(_segmentation(2), input_tokens=1_000_000, output_tokens=0)
    transport = ScriptedStream([events])
    client = _sam(tmp_path, transport)

    assert client.count(STILL, NOUN) == 2
    assert SpendLedger(tmp_path).total() == Decimal("1.25")
    assert client.count(STILL, NOUN) == 2
    assert SpendLedger(tmp_path).total() == Decimal("1.25")
    assert transport.calls == 1


def test_sam_stops_at_the_cap_before_any_stream(tmp_path):
    SpendLedger(tmp_path).add(Decimal("5"))
    transport = ScriptedStream([_events(_segmentation(1))])
    client = _sam(tmp_path, transport, SPEND_LIMIT_USD="5")

    with pytest.raises(SpendCapReached) as caught:
        client.count(STILL, NOUN)
    assert isinstance(caught.value, MuseError)
    assert caught.value.reason_code == "SPEND_CAP"
    assert transport.calls == 0


def test_sam_retries_429_then_succeeds(tmp_path):
    transport = ScriptedStream(
        [
            SamError("busy", status_code=429, retry_after=5.0),
            SamError("busy", status_code=502),
            _events(_segmentation(3)),
        ]
    )
    sleeps: list[float] = []
    client = _sam(tmp_path, transport, sleeps)

    assert client.count(STILL, NOUN) == 3
    assert transport.calls == 3
    assert sleeps[0] == 5.0
    assert 2.0 <= sleeps[1] < 3.0


def test_sam_gives_up_after_four_retries_and_caches_nothing(tmp_path):
    transport = ScriptedStream([SamError("busy", status_code=429) for _ in range(5)])
    sleeps: list[float] = []
    client = _sam(tmp_path, transport, sleeps)

    with pytest.raises(SamError):
        client.count(STILL, NOUN)
    assert transport.calls == 5
    assert len(sleeps) == 4
    assert list(tmp_path.glob("*.json")) == []


def test_sam_does_not_retry_a_400_or_a_timeout(tmp_path):
    for error in (SamError("bad", status_code=400), TimeoutError("slow")):
        transport = ScriptedStream([error])
        sleeps: list[float] = []
        client = _sam(tmp_path, transport, sleeps)
        with pytest.raises(SamError):
            client.count(STILL, NOUN)
        assert transport.calls == 1
        assert sleeps == []
