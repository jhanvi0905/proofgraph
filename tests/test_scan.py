"""Scan path: transcribe an image page, fuzzy-match a quote, label the box approximate. No network."""

import io
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
from PIL import Image, ImageStat

from proofgraph.clients.muse import ExtractionFailed, MuseClient
from proofgraph.config import load_settings
from proofgraph.review.ingest import ingest
from proofgraph.review.relate import PageText
from proofgraph.review.scan import (
    Transcription,
    locate,
    page_text,
    transcribe,
)

ROOT = Path(__file__).resolve().parent.parent
PACKS = Path("/Users/jhanviarora/proofgraph/data/handoff-2026-10-31/packs")

# frt-03 POD upload, rendered 1224 x 1584 by ingest. Pixel boxes below were read by eye
# from that rendered page, not from gold text or pack.json.
W, H = 1224, 1584
# Muse boxes sit about one line low on scans (probe P1, +6 to +17 grid units). Recorded
# replies carry a +8 shift so the test uses the error the product will really see.
LOW = 8

POD_LINES_PX = [
    ("Orig. requested date 10/13/2025 (customer PO request; moved by DC scheduling)", (125, 335, 960, 375)),
    ("Guard check-in 10/14/2025 09:18", (125, 372, 632, 412)),
    ("Unload start 09:40", (125, 465, 500, 492)),
    ("Unload complete 10:51", (123, 498, 497, 533)),
    ("Late? N", (118, 660, 450, 695)),
    ("Received in good order except as noted: (no exceptions noted)", (108, 722, 672, 760)),
]
# Where the "Guard check-in ... 09:18" row really is, on the 0 to 1000 grid, from the pixels.
EXPECTED_ROW = (round(125 / W * 1000), round(372 / H * 1000), round(632 / W * 1000), round(412 / H * 1000))


def _grid(px: tuple[int, int, int, int], dy: int = 0) -> list[int]:
    x0, y0, x1, y1 = px
    return [round(x0 / W * 1000), round(y0 / H * 1000) + dy, round(x1 / W * 1000), round(y1 / H * 1000) + dy]


def _recorded() -> dict[str, Any]:
    return {"lines": [{"text": t, "box": _grid(px, LOW)} for t, px in POD_LINES_PX]}


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


class FakeFiles:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes, str]] = []

    def create(self, *, filename: str, content: bytes, purpose: str) -> dict[str, Any]:
        self.uploads.append((filename, content, purpose))
        return {"id": "file_scan_1"}


def _client(tmp_path, transport: FakeTransport, files: FakeFiles | None = None) -> MuseClient:
    settings = load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)})
    return MuseClient(settings, transport=transport, files_transport=files or FakeFiles())


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("L", (40, 60), 220).save(buf, format="PNG")
    return buf.getvalue()


def _centre(box: list[int]) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _transcription() -> Transcription:
    return Transcription.model_validate(_recorded())


def test_quote_09_18_maps_to_a_box_inside_the_pod_row(tmp_path):
    transport = FakeTransport([_envelope(json.dumps(_recorded()))])
    transcription = transcribe(_png(), _client(tmp_path, transport))
    hit = locate("09:18", transcription)
    assert len(hit.boxes) == 1
    cx, cy = _centre(hit.boxes[0])
    x0, y0, x1, y1 = EXPECTED_ROW
    assert x0 <= cx <= x1 and y0 <= cy <= y1


def test_quote_below_threshold_returns_no_box():
    hit = locate("Driver arrived two hours after the appointment window closed", _transcription())
    assert hit.status == "unpinned"
    assert hit.boxes == []


def test_near_miss_quote_returns_no_box():
    # same opening, different ending: real overlap but under 0.85
    hit = locate("Received in good order except as noted: (damage to three pallets)", _transcription())
    assert hit.boxes == []


def test_near_match_above_threshold_is_found_but_still_approximate():
    # one OCR-style slip in a long quote still clears 0.85
    hit = locate("Received in good order except as noted: (no exceptlons noted)", _transcription())
    assert hit.status == "approximate"
    assert len(hit.boxes) == 1


@pytest.mark.parametrize(
    "quote",
    ["09:18", "Late? N", "Orig. requested date 10/13/2025 (customer PO request; moved by DC scheduling)", "nothing like this"],
)
def test_scan_card_is_never_pinned(quote):
    assert locate(quote, _transcription()).status in {"approximate", "unpinned"}


def test_request_sends_the_image_and_no_gold_or_pack_text(tmp_path):
    transport = FakeTransport([_envelope(json.dumps(_recorded()))])
    files = FakeFiles()
    png = _png()
    transcribe(png, _client(tmp_path, transport, files))
    assert [u[1] for u in files.uploads] == [png]
    body = transport.bodies[0]
    parts = body["input"][0]["content"]
    assert {"type": "input_file", "file_id": "file_scan_1", "detail": "high"} in parts
    sent = json.dumps(body)
    for banned in ("Guard check-in", "09:18", "pack.json", "gold", "Solutions"):
        assert banned not in sent
    source = (ROOT / "proofgraph" / "review" / "scan.py").read_text(encoding="utf-8")
    prompt = (ROOT / "prompts" / "transcribe.md").read_text(encoding="utf-8")
    for text in (source, prompt):
        assert "load_gold" not in text
        assert "pack.json" not in text


def test_prompt_marks_page_content_as_data():
    prompt = (ROOT / "prompts" / "transcribe.md").read_text(encoding="utf-8")
    assert "DATA" in prompt
    assert "injection" in prompt.lower() or "instruction" in prompt.lower()


def test_bad_json_is_repaired_once_then_extraction_failed(tmp_path):
    transport = FakeTransport([_envelope("not json"), _envelope("still not json")])
    with pytest.raises(ExtractionFailed) as err:
        transcribe(_png(), _client(tmp_path, transport))
    assert err.value.reason_code == "EXTRACTION_FAILED"
    assert transport.calls == 2


def test_bad_json_then_valid_repair_succeeds(tmp_path):
    transport = FakeTransport([_envelope("not json"), _envelope(json.dumps(_recorded()))])
    result = transcribe(_png(), _client(tmp_path, transport))
    assert len(result.lines) == len(POD_LINES_PX)
    assert transport.calls == 2


def test_degenerate_and_out_of_range_boxes_are_dropped_not_drawn():
    t = Transcription.model_validate(
        {
            "lines": [
                {"text": "flat line", "box": [10, 50, 10, 60]},
                {"text": "off grid line", "box": [-20, 900, 1040, 960]},
                {"text": "fine line", "box": [100, 100, 400, 130]},
            ]
        }
    )
    assert locate("flat line", t).boxes == []
    assert locate("off grid line", t).boxes == [[0, 900, 1000, 960]]
    assert locate("fine line", t).boxes == [[100, 100, 400, 130]]


def test_transcribed_text_feeds_relate():
    pt = page_text("pod", 1, _transcription())
    assert isinstance(pt, PageText)
    assert (pt.doc, pt.page) == ("pod", 1)
    assert "Guard check-in 10/14/2025 09:18" in pt.text.splitlines()


def test_empty_transcription_is_empty_page_text_and_no_box():
    empty = Transcription(lines=[])
    assert page_text("d", 1, empty).text == ""
    assert locate("anything", empty).boxes == []


# Real files in the data folder -------------------------------------------------

def _mean(path: Path) -> float:
    return ImageStat.Stat(Image.open(path).convert("L")).mean[0]


def _images() -> list[Path]:
    if not PACKS.is_dir():
        return []
    return [
        p
        for p in PACKS.rglob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"} and "_debug" not in p.parts and "_preview" not in p.parts
    ]


def test_real_light_scan_is_not_inverted():
    path = PACKS / "freight" / "frt-02-lumper-buried-cap" / "upload" / "lumper_receipt_scan.jpg"
    if not path.is_file():
        pytest.skip(f"data folder file absent: {path}")
    doc = ingest([path])[0]
    assert doc.error is None
    out = Image.open(io.BytesIO(doc.pages[0].png))
    assert ImageStat.Stat(out).mean[0] > 150  # still light text on light page


def test_real_dark_scan_is_inverted_by_ingest():
    dark = [p for p in _images() if "photo" not in p.name.lower() and _mean(p) < 100]
    if not dark:
        pytest.skip("no real dark scan (mean brightness under 100) exists under data/handoff-2026-10-31/packs")
    out = Image.open(io.BytesIO(ingest([dark[0]])[0].pages[0].png))
    assert ImageStat.Stat(out).mean[0] > 100


def test_real_dark_background_photo_is_not_flipped():
    dark = [p for p in _images() if "photo" in p.name.lower() and _mean(p) < 100]
    if not dark:
        pytest.skip("no real dark-background photo (mean brightness under 100) exists under data/handoff-2026-10-31/packs")
    before = _mean(dark[0])
    out = Image.open(io.BytesIO(ingest([dark[0]])[0].pages[0].png))
    assert ImageStat.Stat(out).mean[0] == pytest.approx(before, abs=5)
