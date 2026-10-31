"""The boxed bundle: PDF text-in-box, blind re-read, and SAM count in one verdict.

No network. The two photos are generated stand-ins (a white PNG), not the
human's phone photos. They test the wiring, not the handwriting or the SAM
count on real goods.
"""

import base64
import importlib.util
import io
import json
from pathlib import Path
from typing import Any, Mapping

import pytest
from PIL import Image, ImageDraw

from proofgraph.clients.checker import CheckerClient
from proofgraph.clients.sam import SamClient
from proofgraph.config import DEFAULT_CHECKER_MODEL, load_settings
from proofgraph.engine.ground import ground
from proofgraph.engine.route import run_program
from proofgraph.pdf import map_text_span, read_page_words
from proofgraph.propose import propose
from proofgraph.schema import Case, ClaimProgram, Fact, Link, Source
from test_text_span import _pdf_pages

ROOT = Path(__file__).resolve().parents[1]
PACKET = ROOT / "examples" / "freight" / "demo-001"
NOUN = "carton"  # stand-in noun; the real one comes from the human's photo
HAND_COUNT = 6
INVOICE_COUNT = 4
DETENTION_LINE = "Detention: $75.00/hour after 2 hours free time"
CLAIM = (
    "The invoice detention charge of $450.00 is correct, and the invoice count "
    f"of {INVOICE_COUNT} {NOUN}s matches the photo."
)
POD_ARRIVED = [100, 200, 300, 300]
POD_DEPARTED = [100, 600, 300, 700]
SAM_BOX = "<|box;x1=1;y1=1;x2=9;y2=9;w=960;h=720|>"


def _script():
    spec = importlib.util.spec_from_file_location("make_demo_pdfs", ROOT / "scripts" / "make_demo_pdfs.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _png(path: Path, size: tuple[int, int] = (1000, 500)) -> Path:
    """White stand-in. A mark in the lower half keeps the two pod crops distinct for the cache."""
    image = Image.new("RGB", size, "white")
    ImageDraw.Draw(image).rectangle((size[0] // 5, size[1] * 6 // 10, size[0] // 4, size[1] * 65 // 100), fill="black")
    image.save(path, format="PNG")
    return path


def _chat(text: str) -> dict[str, Any]:
    return {
        "id": "chatcmpl_test",
        "object": "chat.completion",
        "model": DEFAULT_CHECKER_MODEL,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
    }


def _reading(value: str) -> dict[str, Any]:
    return _chat(json.dumps({"value": value}))


class ChatFake:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> Any:
        self.bodies.append(json.loads(json.dumps(body)))
        if not self._responses:
            raise AssertionError("checker called too many times")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class SamFake:
    def __init__(self, events: list[dict[str, Any]]) -> None:
        self._events = events
        self.bodies: list[dict[str, Any]] = []

    def stream(self, body: Mapping[str, Any]):
        self.bodies.append(json.loads(json.dumps(body)))
        yield from self._events


def _segmentation(count: int) -> list[dict[str, Any]]:
    text = "<0f>" + ",".join(f"{i}{SAM_BOX}<|mask;x=0;y=0;data=1,1,~P{i}|>" for i in range(count))
    return [{"type": "response.completed", "response": {"status": "completed", "output_text": text}}]


def _checker(monkeypatch, tmp_path: Path, responses: list[Any]) -> ChatFake:
    fake = ChatFake(responses)
    settings = load_settings({"BASETEN_API_KEY": "test-key", "CACHE_DIR": str(tmp_path / "checker")})
    client = CheckerClient(settings, transport=fake, sleep=lambda _s: None)
    monkeypatch.setattr("proofgraph.clients.checker.CheckerClient", lambda *a, **k: client)
    return fake


def _sam(monkeypatch, tmp_path: Path, events: list[dict[str, Any]]) -> SamFake:
    fake = SamFake(events)
    settings = load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path / "sam")})
    client = SamClient(settings, transport=fake, sleep=lambda _s: None)
    monkeypatch.setattr("proofgraph.clients.sam.SamClient", lambda *a, **k: client)
    return fake


def _image_from(body: dict[str, Any]) -> Image.Image:
    content = body["messages"][0]["content"]
    url = next(part for part in content if part["type"] == "image_url")["image_url"]["url"]
    return Image.open(io.BytesIO(base64.b64decode(url.split(",", 1)[1])))


def _case(*sources: Source, claim: str = CLAIM) -> Case:
    return Case(id="freight-demo-001", dataset="freight", mode="whole", claim=claim, sources=list(sources))


def _pdf_fact(fid: str, source: Source, quote: str, value: Any, *, page: int = 1) -> Fact:
    span = map_text_span(source.path, quote, page=page)
    return Fact(
        id=fid, label=fid, source_id=source.id, quote=quote, page=page,
        box=list(span.box), value=value, kind="number",
    )


# --- packet files ---------------------------------------------------------


def test_packet_has_the_key_and_two_courier_pdfs_with_one_timeline():
    key = json.loads((PACKET / "key.json").read_text())
    assert key["case_id"] == "freight-demo-001"
    assert (key["demonstration"], key["benchmark"]) == (True, False)
    truth = key["truth"]
    assert (truth["arrived"], truth["departed"]) == ("08:00", "12:30")
    assert truth["fair_detention_usd"] == 187.50 and truth["invoice_detention_usd"] == 450
    assert truth["goods_noun"] is None or truth["goods_noun"] != "cardboard box"
    raw = (PACKET / "key.json").read_text()
    assert "07:40" not in raw and "11:55" not in raw and "14:12" not in raw
    for name in ("rate_confirmation.pdf", "invoice.pdf"):
        assert b"/BaseFont /Courier" in (PACKET / name).read_bytes()
    rate_words = " ".join(w.text for w in read_page_words(PACKET / "rate_confirmation.pdf"))
    assert DETENTION_LINE in rate_words
    assert "Detention: $450.00" in " ".join(w.text for w in read_page_words(PACKET / "invoice.pdf"))


def test_script_writes_the_same_bytes_as_the_text_span_writer():
    script = _script()
    stream = script.page_stream(["A line", "Detention: $450.00"])
    assert script.pdf_pages([stream]) == _pdf_pages([stream])


def test_invoice_count_line_uses_the_noun_and_count_from_the_key():
    script = _script()
    key = json.loads((PACKET / "key.json").read_text())
    key["truth"].update(goods_noun=NOUN, invoice_count=INVOICE_COUNT)
    words = " ".join(w.text for w in read_page_words(script.invoice(key)))
    assert f"Delivered: {INVOICE_COUNT} {NOUN}s" in words


# --- text_in_box ----------------------------------------------------------


def test_text_in_box_grounds_a_pdf_fact_and_names_the_margin():
    source = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    fact = _pdf_fact("f_rate", source, DETENTION_LINE, 75)
    check = ground(fact, _case(source))
    assert (check.status, check.method) == ("grounded", "text_in_box")
    assert "2%" in check.detail


@pytest.mark.parametrize(("shift", "margin"), [(5, "2%"), (25, "3%"), (35, "4%")])
def test_margin_ladder_keeps_the_smallest_margin_that_contains_the_value(shift, margin):
    source = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    span = map_text_span(source.path, DETENTION_LINE)
    word = next(w for w in read_page_words(source.path) if "75.00" in w.text)
    centre = (word.x0 + word.x1) / 2 * 1000 / word.page_width
    box = [span.box[0], span.box[1], int(centre - shift), span.box[3]]
    fact = Fact(id="f", label="rate", source_id="rate_conf", quote=DETENTION_LINE, page=1,
                box=box, value=75, kind="number")
    check = ground(fact, _case(source))
    assert check.status == "grounded"
    assert margin in check.detail


def test_a_miss_at_every_margin_is_ungrounded():
    source = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    span = map_text_span(source.path, DETENTION_LINE)
    word = next(w for w in read_page_words(source.path) if "75.00" in w.text)
    centre = (word.x0 + word.x1) / 2 * 1000 / word.page_width
    box = [span.box[0], span.box[1], int(centre - 45), span.box[3]]
    fact = Fact(id="f", label="rate", source_id="rate_conf", quote=DETENTION_LINE, page=1,
                box=box, value=75, kind="number")
    check = ground(fact, _case(source))
    assert (check.status, check.method) == ("ungrounded", "text_in_box")


def test_a_wrong_value_in_the_right_box_is_ungrounded():
    source = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    fact = _pdf_fact("f_rate", source, DETENTION_LINE, 80)
    assert ground(fact, _case(source)).status == "ungrounded"


@pytest.mark.parametrize("path", ["missing.pdf", None])
def test_text_in_box_with_no_readable_file_is_ungrounded(tmp_path, path):
    source = Source(id="s", kind="pdf", path=None if path is None else str(tmp_path / path))
    fact = Fact(id="f", label="x", source_id="s", page=1, box=[0, 0, 1000, 1000], value=75, kind="number")
    check = ground(fact, _case(source))
    assert (check.status, check.method) == ("ungrounded", "text_in_box")


def test_text_in_box_with_a_page_outside_the_pdf_is_ungrounded():
    source = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    fact = Fact(id="f", label="x", source_id="rate_conf", page=9, box=[0, 0, 1000, 1000], value=75, kind="number")
    assert ground(fact, _case(source)).status == "ungrounded"


# --- blind_reread ---------------------------------------------------------


def _pod(tmp_path: Path) -> Source:
    return Source(id="pod", kind="image", path=str(_png(tmp_path / "pod.png")))


def _time_fact(box: list[int], value: str = "08:00") -> Fact:
    return Fact(id="f_arrived", label="arrived", source_id="pod", quote="Arrived", box=box, value=value, kind="time")


def test_blind_reread_sends_only_the_crop_and_matches_times_as_times(tmp_path, monkeypatch):
    fake = _checker(monkeypatch, tmp_path, [_reading("8:00")])
    check = ground(_time_fact(POD_ARRIVED), _case(_pod(tmp_path)))
    assert (check.status, check.method) == ("grounded", "blind_reread")
    assert len(fake.bodies) == 1
    body = fake.bodies[0]
    parts = body["messages"][0]["content"]
    assert [part["type"] for part in parts] == ["text", "image_url"]
    wire = json.dumps(body)
    for private in ("08:00", "Arrived", "450", "Northwind", "freight-demo-001", CLAIM):
        assert private not in wire
    assert _image_from(body).size == (240, 70)  # the box plus a 2% pad, nothing wider


def test_blind_reread_disagreement_is_ungrounded(tmp_path, monkeypatch):
    _checker(monkeypatch, tmp_path, [_reading("07:40")])
    check = ground(_time_fact(POD_ARRIVED), _case(_pod(tmp_path)))
    assert (check.status, check.method) == ("ungrounded", "blind_reread")


@pytest.mark.parametrize("reply", ["", "smudged", '{"value": ""}'])
def test_a_smudged_or_empty_reading_is_ungrounded(tmp_path, monkeypatch, reply):
    _checker(monkeypatch, tmp_path, [_chat(reply)])
    assert ground(_time_fact(POD_ARRIVED), _case(_pod(tmp_path))).status == "ungrounded"


def test_a_checker_error_is_ungrounded_with_a_reason(tmp_path, monkeypatch):
    from proofgraph.clients.checker import CheckerError

    _checker(monkeypatch, tmp_path, [CheckerError("boom", reason_code="CHECKER_UNAVAILABLE")] * 5)
    check = ground(_time_fact(POD_ARRIVED), _case(_pod(tmp_path)))
    assert check.status == "ungrounded" and check.detail


def test_blind_reread_without_a_box_or_a_readable_image_is_ungrounded(tmp_path, monkeypatch):
    fake = _checker(monkeypatch, tmp_path, [_reading("08:00")])
    assert ground(_time_fact([]), _case(_pod(tmp_path))).status == "ungrounded"
    no_box = _time_fact(POD_ARRIVED).model_copy(update={"box": None})
    assert ground(no_box, _case(_pod(tmp_path))).status == "ungrounded"
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"not an image")
    bad = Source(id="pod", kind="image", path=str(broken))
    assert ground(_time_fact(POD_ARRIVED), _case(bad)).status == "ungrounded"
    assert fake.bodies == []


# --- count_agreement ------------------------------------------------------


def _goods(tmp_path: Path) -> Source:
    return Source(id="goods", kind="image", path=str(_png(tmp_path / "goods.png", (960, 720))))


def _count_fact(value: Any = HAND_COUNT, entity: str | None = NOUN) -> Fact:
    return Fact(id="f_goods_count", label="goods count", source_id="goods", value=value, kind="count", entity=entity)


def test_count_agreement_grounds_when_sam_matches_the_stated_count(tmp_path, monkeypatch):
    fake = _sam(monkeypatch, tmp_path, _segmentation(HAND_COUNT))
    check = ground(_count_fact(), _case(_goods(tmp_path)))
    assert (check.status, check.method) == ("grounded", "count_agreement")
    parts = fake.bodies[0]["input"][0]["content"]
    assert parts[0] == {"type": "input_text", "text": NOUN}
    assert parts[1]["type"] == "input_image"


def test_count_disagreement_is_ungrounded(tmp_path, monkeypatch):
    _sam(monkeypatch, tmp_path, _segmentation(HAND_COUNT - 1))
    check = ground(_count_fact(), _case(_goods(tmp_path)))
    assert (check.status, check.method) == ("ungrounded", "count_agreement")
    assert str(HAND_COUNT - 1) in check.detail


def test_a_sam_error_is_ungrounded(tmp_path, monkeypatch):
    _sam(monkeypatch, tmp_path, [{"type": "error", "message": "boom"}])
    check = ground(_count_fact(), _case(_goods(tmp_path)))
    assert (check.status, check.method) == ("ungrounded", "count_agreement")


@pytest.mark.parametrize(("value", "entity"), [(5.5, NOUN), ("many", NOUN), (HAND_COUNT, None), (HAND_COUNT, " ")])
def test_a_count_with_no_whole_number_or_noun_never_calls_sam(tmp_path, monkeypatch, value, entity):
    fake = _sam(monkeypatch, tmp_path, _segmentation(HAND_COUNT))
    assert ground(_count_fact(value, entity), _case(_goods(tmp_path))).status == "ungrounded"
    assert fake.bodies == []


def test_sam_counts_zero_boxes_as_ungrounded_for_a_positive_claim(tmp_path, monkeypatch):
    _sam(monkeypatch, tmp_path, _segmentation(0))
    assert ground(_count_fact(), _case(_goods(tmp_path))).status == "ungrounded"


def test_a_spend_stop_is_not_swallowed_as_a_grounding_miss(tmp_path, monkeypatch):
    from proofgraph.spend import SpendCapReached

    def capped(*_args, **_kwargs):
        raise SpendCapReached("cap")

    monkeypatch.setattr("proofgraph.engine.ground.blind_reread", capped)
    monkeypatch.setattr("proofgraph.engine.ground.sam_count", capped)
    with pytest.raises(SpendCapReached):
        ground(_time_fact(POD_ARRIVED), _case(_pod(tmp_path)))
    with pytest.raises(SpendCapReached):
        ground(_count_fact(), _case(_goods(tmp_path)))


# --- the whole packet -----------------------------------------------------


def _bundle(tmp_path: Path) -> tuple[Case, ClaimProgram]:
    script = _script()
    key = json.loads((PACKET / "key.json").read_text())
    key["truth"].update(goods_noun=NOUN, invoice_count=INVOICE_COUNT)
    invoice = tmp_path / "invoice.pdf"
    invoice.write_bytes(script.invoice(key))
    rate = Source(id="rate_conf", kind="pdf", path=str(PACKET / "rate_confirmation.pdf"))
    inv = Source(id="invoice", kind="pdf", path=str(invoice))
    pod = Source(id="pod", kind="image", path=str(_png(tmp_path / "pod.png")))
    goods = _goods(tmp_path)
    facts = [
        _pdf_fact("f_rate", rate, DETENTION_LINE, 75),
        _pdf_fact("f_free", rate, DETENTION_LINE, 2),
        Fact(id="f_arrived", label="arrived", source_id="pod", box=POD_ARRIVED, value="08:00", kind="time"),
        Fact(id="f_departed", label="departed", source_id="pod", box=POD_DEPARTED, value="12:30", kind="time"),
        _pdf_fact("f_invoice", inv, "Detention: $450.00", 450),
        _count_fact(),
        _pdf_fact("f_invoice_count", inv, f"Delivered: {INVOICE_COUNT} {NOUN}s", INVOICE_COUNT),
    ]
    links = [
        Link(id="l_detention", kind="compute", statement="Billable hours times the rate equals the invoice",
             inputs=["f_arrived", "f_departed", "f_free", "f_rate", "f_invoice"],
             expr="(hours_between(f_arrived, f_departed) - f_free) * f_rate == f_invoice",
             claim_span="$450.00"),
        Link(id="l_same_day", kind="rule", statement="Arrival and departure are on the same calendar day.",
             inputs=["f_arrived", "f_departed"], rule_source="assumed", claim_span="$450.00"),
        Link(id="l_goods", kind="compute", statement="The photo count equals the invoice count",
             inputs=["f_goods_count", "f_invoice_count"], expr="f_goods_count == f_invoice_count",
             claim_span=f"{INVOICE_COUNT} {NOUN}s"),
    ]
    program = ClaimProgram(facts=facts, links=links, required=["l_detention", "l_goods"], unverifiable_parts=[])
    return _case(rate, pod, goods, inv), program


def test_the_whole_packet_is_contradicted_with_every_method_shown(tmp_path, monkeypatch):
    case, program = _bundle(tmp_path)
    checker = _checker(monkeypatch, tmp_path, [_reading("8:00"), _reading("12:30")])
    sam = _sam(monkeypatch, tmp_path, _segmentation(HAND_COUNT))
    verdict = run_program(case, program)
    assert verdict.verdict == "CONTRADICTED"
    methods = {c.fact_id: (c.status, c.method) for c in verdict.fact_checks}
    assert methods == {
        "f_rate": ("grounded", "text_in_box"),
        "f_free": ("grounded", "text_in_box"),
        "f_arrived": ("grounded", "blind_reread"),
        "f_departed": ("grounded", "blind_reread"),
        "f_invoice": ("grounded", "text_in_box"),
        "f_goods_count": ("grounded", "count_agreement"),
        "f_invoice_count": ("grounded", "text_in_box"),
    }
    links = {r.link_id: r for r in verdict.link_results}
    assert (links["l_detention"].status, links["l_detention"].strength) == ("fail", "COMPUTED")
    assert (links["l_goods"].status, links["l_goods"].strength) == ("fail", "COMPUTED")
    assert (links["l_same_day"].status, links["l_same_day"].strength) == ("pass", "ASSUMED")
    assert "l_same_day" not in program.required
    assert len(checker.bodies) == 2 and len(sam.bodies) == 1


def test_a_smudged_time_leaves_the_detention_line_unresolved(tmp_path, monkeypatch):
    case, program = _bundle(tmp_path)
    program = program.model_copy(update={"required": ["l_detention"]})
    _checker(monkeypatch, tmp_path, [_chat("smudged"), _reading("12:30")])
    _sam(monkeypatch, tmp_path, _segmentation(HAND_COUNT))
    verdict = run_program(case, program)
    links = {r.link_id: r for r in verdict.link_results}
    assert links["l_detention"].status == "blocked"
    assert verdict.verdict == "UNRESOLVED"


def test_a_sam_error_blocks_the_goods_line_without_touching_detention(tmp_path, monkeypatch):
    case, program = _bundle(tmp_path)
    _checker(monkeypatch, tmp_path, [_reading("8:00"), _reading("12:30")])
    _sam(monkeypatch, tmp_path, [{"type": "error", "message": "boom"}])
    verdict = run_program(case, program)
    links = {r.link_id: r for r in verdict.link_results}
    assert links["l_goods"].status == "blocked"
    assert links["l_detention"].status == "fail"
    assert verdict.verdict == "CONTRADICTED"


# --- key.json stays sealed ------------------------------------------------


class _Muse:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.prompt = ""

    def upload_user_data(self, path: str) -> str:
        self.uploaded.append(path)
        return f"file-{len(self.uploaded)}"

    def structured(self, prompt: str, model: type, *, bypass_cache: bool = False, file_ids: list[str] | None = None):
        self.prompt = prompt
        return ClaimProgram(facts=[], links=[], required=[], unverifiable_parts=[])


def test_key_json_never_reaches_propose(tmp_path):
    poison = "POISON-KEY-7731"
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "key.json").write_text(json.dumps({"truth": {"fair_detention_usd": poison}}))
    (packet / "rate_confirmation.pdf").write_bytes((PACKET / "rate_confirmation.pdf").read_bytes())
    case = _case(Source(id="rate_conf", kind="pdf", path=str(packet / "rate_confirmation.pdf")))
    muse = _Muse()
    propose(case, client=muse)  # type: ignore[arg-type]
    assert poison not in muse.prompt
    assert not any("key.json" in path for path in muse.uploaded)
    for module in ("propose.py", "engine/ground.py", "engine/route.py"):
        assert "key.json" not in (ROOT / "proofgraph" / module).read_text()
