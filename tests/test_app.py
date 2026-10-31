"""Replay screen data. Importing the app does not start a server or a model."""

import ast
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

from app.streamlit_app import (
    FIXTURES,
    ReplayError,
    build_packet,
    check_claim,
    failure_message,
    live_case,
    live_refusal,
    span_rows,
    value_text,
)
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "streamlit_app.py"
DETENTION_REASON = (
    "Detention should be $165.00, not $450.00 (4.2 h on site, 2 h free, $75/h)"
)
SUM_REASON = (
    "The figures in the quotes (November cash collected was $18,450,000; "
    "August cash collected was $24,928,608) compute to $43,378,608, "
    "matching the claimed $43,378,608, so the check holds."
)


def test_app_imports_without_starting_a_server():
    import app.streamlit_app as replay

    assert "streamlit" not in sys.modules
    assert callable(replay.build_packet)
    assert callable(replay.main)


def test_app_imports_propose_and_not_a_model_client():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    assert "proofgraph.propose" in modules
    for name in modules:
        parts = name.split(".")
        assert "muse" not in parts
        assert "openai" not in parts
        assert "dotenv" not in parts
        assert "checker" not in parts
        assert not name.startswith("proofgraph.clients")


def test_selector_uses_the_offline_fixtures():
    assert FIXTURES["Detention"].name == "detention_program.json"
    assert FIXTURES["The sum"].name == "sum_program.json"


def test_detention_packet_is_the_engine_result():
    packet = build_packet(FIXTURES["Detention"])
    assert packet.verdict == "CONTRADICTED"
    assert packet.label == "COMPUTED"
    assert packet.reasons == (DETENTION_REASON,)
    assert packet.reason_codes == ()
    assert packet.fetch == ()
    assert [row.quote for row in packet.fact_checks] == [
        "Detention: $75.00/hour after 2 hours free time",
        "2 hours free time",
        "Arrived: 10:00",
        "Departed: 14:12",
        "Detention: $450.00",
    ]
    assert all(row.grounded for row in packet.fact_checks)
    assert packet.link_results[0].link_id == "l_detention"
    assert packet.link_results[0].status == "fail"
    assert packet.link_results[0].strength == "COMPUTED"


def test_sum_packet_is_supported():
    packet = build_packet(FIXTURES["The sum"])
    assert packet.claim.startswith("November and August")
    assert packet.verdict == "SUPPORTED"
    assert packet.label == "COMPUTED"
    assert packet.reasons == (SUM_REASON,)
    assert packet.reason_codes == ()
    assert packet.fetch == ()
    assert [row.quote for row in packet.fact_checks] == [
        "November cash collected was $18,450,000",
        "August cash collected was $24,928,608",
    ]
    assert all(row.grounded for row in packet.fact_checks)
    assert packet.link_results[0].status == "pass"
    assert packet.link_results[0].strength == "COMPUTED"


def test_span_rows_list_quote_value_scale_and_kind():
    rows = span_rows("Paid $75.00 at 10:00 on 2 January 2024.")
    assert [(row.quote, value_text(row.value), row.scale, row.kind) for row in rows] == [
        ("$75.00", "75", "units", "number"),
        ("10:00", "10:00", None, "time"),
        ("2 January 2024", "2024-01-02", None, "date"),
    ]
    assert span_rows("   ") == ()
    assert span_rows("no figures here") == ()


def test_missing_fixture_is_a_screen_error(tmp_path):
    with pytest.raises(ReplayError, match="could not read fixture"):
        build_packet(tmp_path / "missing.json")


def test_bad_fixture_is_a_screen_error(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    with pytest.raises(ReplayError, match="could not read fixture"):
        build_packet(path)
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ReplayError, match="fixture must contain case and program"):
        build_packet(path)


def test_engine_failure_stays_a_message(monkeypatch):
    def _boom(_case, _program):
        raise RuntimeError("calc broke")

    monkeypatch.setattr("app.streamlit_app.run_program", _boom)
    with pytest.raises(RuntimeError, match="calc broke"):
        build_packet(FIXTURES["Detention"])
    assert failure_message(RuntimeError("calc broke")) == "calc broke"
    noisy = RuntimeError("Traceback (most recent call last):\n  File \"x\"")
    assert failure_message(noisy) == "RuntimeError"


def _settings(tmp_path):
    return load_settings({"MODEL_API_KEY": "test-key", "CACHE_DIR": str(tmp_path)})


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


class _Transport:
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


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in tree.body:  # type: ignore[attr-defined]
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"missing {name}")


def _calls_named(node: ast.AST, name: str) -> list[ast.Call]:
    found: list[ast.Call] = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id == name:
                found.append(child)
    return found


def test_live_case_is_the_detention_claim():
    case = live_case()
    assert case.id == "detention-001"
    assert case.claim == "The invoice detention charge of $450.00 is correct."
    assert [source.text for source in case.sources] == [
        "Detention: $75.00/hour after 2 hours free time",
        "Arrived: 10:00 Departed: 14:12",
        "Detention: $450.00",
    ]


def test_live_detention_check_proposes_then_runs_the_engine(tmp_path):
    program = json.loads(FIXTURES["Detention"].read_text(encoding="utf-8"))["program"]
    transport = _Transport([_envelope(json.dumps(program))])
    client = MuseClient(_settings(tmp_path), transport=transport)

    packet = check_claim(live_case(), client=client)

    assert transport.calls == 1
    assert packet.verdict == "CONTRADICTED"
    assert packet.label == "COMPUTED"
    assert packet.reasons == (DETENTION_REASON,)
    assert packet.reason_codes == ()
    prompt = transport.bodies[0]["input"]
    assert "The invoice detention charge of $450.00 is correct." in prompt
    assert "l_detention" not in prompt
    assert "f_arrived" not in prompt


def test_live_check_uses_the_proposed_program(tmp_path):
    empty = json.dumps(
        {"facts": [], "links": [], "required": [], "unverifiable_parts": []}
    )
    transport = _Transport([_envelope(empty)])
    client = MuseClient(_settings(tmp_path), transport=transport)

    packet = check_claim(live_case(), client=client)

    assert transport.calls == 1
    assert packet.verdict == "UNRESOLVED"
    assert packet.label is None
    assert packet.fact_checks == ()
    assert "UNCOVERED_NUMBER" in packet.reason_codes
    assert packet.reasons != (DETENTION_REASON,)


def test_live_check_keeps_sealed_fields_out_of_the_prompt(tmp_path):
    case = live_case().model_copy(
        update={"answer": "SUPPORTED", "gold_evidence": ["secret-gold-span"]}
    )
    empty = json.dumps(
        {"facts": [], "links": [], "required": [], "unverifiable_parts": []}
    )
    transport = _Transport([_envelope(empty)])
    client = MuseClient(_settings(tmp_path), transport=transport)

    check_claim(case, client=client)

    prompt = transport.bodies[0]["input"]
    assert "secret-gold-span" not in prompt
    assert "gold_evidence" not in prompt


def test_check_claim_rejects_a_non_case():
    with pytest.raises(TypeError, match="Case"):
        check_claim({"claim": "x"})  # type: ignore[arg-type]


def test_propose_is_called_only_by_check_claim():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    callers = [
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and _calls_named(node, "propose")
    ]
    assert callers == ["check_claim"]
    check = _function(tree, "check_claim")
    assert _calls_named(check, "run_program")


def test_story_describes_the_detention_packet():
    from app.streamlit_app import PACKET_STORY, SAMPLE_NOTE, STORY_LEAD

    text = " ".join([STORY_LEAD, PACKET_STORY, SAMPLE_NOTE])
    assert "accept a detention charge" in STORY_LEAD
    assert "figure can still be wrong" in STORY_LEAD
    assert "mark on the page is the evidence" in STORY_LEAD
    assert "rate confirmation" in PACKET_STORY
    assert "proof of delivery" in PACKET_STORY
    assert "invoice" in PACKET_STORY
    assert "designed demonstration" in PACKET_STORY
    assert "No saved case is played." in SAMPLE_NOTE
    for banned in ("SAM", "scoreboard", "ContractNLI"):
        assert banned not in text
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    main = _function(tree, "main")
    calls: list[str] = []
    for node in ast.walk(main):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    assert calls.index("_story") < calls.index("text_area")
    assert calls.index("_story") < calls.index("file_uploader")
    assert "radio" not in calls


def test_verdict_and_label_glosses_match_the_three_outcomes():
    from app.streamlit_app import LABEL_GLOSS, VERDICT_GLOSS

    assert set(VERDICT_GLOSS) == {"SUPPORTED", "CONTRADICTED", "UNRESOLVED"}
    assert set(LABEL_GLOSS) == {"COMPUTED", "CHECKED", "ASSUMED"}
    assert "executed calculation" in LABEL_GLOSS["COMPUTED"]
    assert "independent wording" in LABEL_GLOSS["CHECKED"]
    assert "do not state" in LABEL_GLOSS["ASSUMED"]


def test_live_screen_starts_the_check_from_a_button():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    show = _function(tree, "_show_upload")
    started: list[ast.Call] = []
    for node in ast.walk(show):
        if not isinstance(node, ast.If) or not isinstance(node.test, ast.Call):
            continue
        func = node.test.func
        if isinstance(func, ast.Attribute) and func.attr == "button":
            assert isinstance(node.test.args[0], ast.Constant)
            assert node.test.args[0].value == "Check this claim"
            started.extend(_calls_named(node, "check_claim"))
    assert len(started) == 1
    main = _function(tree, "main")
    assert _calls_named(main, "check_claim") == []
    assert _calls_named(main, "propose") == []


def test_sample_packet_is_the_detention_verdict():
    from app.streamlit_app import sample_packet

    packet = sample_packet()
    assert packet.verdict == "CONTRADICTED"
    assert packet.label == "COMPUTED"
    assert packet.reasons == (DETENTION_REASON,)
    assert packet.claim == "The invoice detention charge of $450.00 is correct."


def test_overlay_marks_come_from_quotes_or_boxes():
    from io import BytesIO

    from PIL import Image

    from app.streamlit_app import (
        OverlayMark,
        box_pixels,
        courier_pdf,
        locate_overlay,
        mark_rects,
        marks_for_text,
        page_marks,
        render_marked_pdf,
        sample_packet,
    )
    from proofgraph.pdf import map_text_span

    pdf = (ROOT / "tests" / "fixtures" / "text_span_rate.pdf").read_bytes()
    quote = "Detention: $75.00/hour after 2 hours free time"
    assert locate_overlay(quote, pdf=pdf) == map_text_span(pdf, quote).box
    assert locate_overlay("a phone photo of the seal", pdf=pdf) is None
    assert locate_overlay("ignored", box=(4, 5, 6, 7)) == (4, 5, 6, 7)
    assert locate_overlay("ignored", box=(0, 0, 1001, 10)) is None
    assert locate_overlay("orphan quote") is None
    assert box_pixels((0, 0, 1000, 1000), 200, 100) == (0.0, 0.0, 200.0, 100.0)

    missing = (
        OverlayMark("gate photo", "gate photo", "in the source", None, 1),
        OverlayMark("$75.00", "$75.00", "in the source", (10, 20, 30, 40), 1),
    )
    assert mark_rects(missing, 1000, 500) == (
        ("in the source", (10.0, 10.0, 30.0, 20.0)),
    )

    text_marks = marks_for_text(
        "Detention: $450.00",
        [("Detention: $450.00", True), ("gate photo timestamp", False)],
        claimed="$450.00",
    )
    assert text_marks[0].role == "claimed"
    assert text_marks[0].box is not None
    assert text_marks[1].box is None
    assert text_marks[1].fact_quote == "gate photo timestamp"

    pages = page_marks(sample_packet())
    assert [page.title for page in pages] == [
        "Rate confirmation",
        "Proof of delivery",
        "Invoice",
    ]
    located = [mark for page in pages for mark in page.marks]
    assert {mark.quote for mark in located} >= {
        "$75.00",
        "2 hours free time",
        "10:00",
        "14:12",
        "$450.00",
    }
    for page in pages:
        assert page.pdf is not None
        for mark in page.marks:
            assert mark.box is not None
            assert mark.box == locate_overlay(mark.quote, pdf=page.pdf)
    claimed = [mark for mark in located if mark.role == "claimed"]
    assert [mark.quote for mark in claimed] == ["$450.00"]

    invoice = next(page for page in pages if page.title == "Invoice")
    png = render_marked_pdf(invoice.pdf, invoice.marks)
    assert png.startswith(b"\x89PNG")
    image = Image.open(BytesIO(png))
    mark = claimed[0]
    assert mark.box is not None
    x0, y0, x1, y1 = box_pixels(mark.box, image.width, image.height)
    crop = image.crop((int(x0), int(y0), int(x1) + 1, int(y1) + 1))
    colors = crop.getcolors(maxcolors=crop.width * crop.height)
    assert colors is not None
    assert any(color == (0x9F, 0x12, 0x39) for _count, color in colors)

    blank = render_marked_pdf(
        courier_pdf("Detention: $75.00/hour after 2 hours free time"),
        missing[:1],
    )
    blank_image = Image.open(BytesIO(blank))
    blank_colors = blank_image.getcolors(maxcolors=blank_image.width * blank_image.height)
    assert blank_colors is not None
    assert all(color != (0x9F, 0x12, 0x39) for _count, color in blank_colors)


# --- R-08b: the app opens on the new review screen; the packet app is the second page. ---

_ENTRY = "from app.streamlit_app import run_app\nrun_app()\n"
_BOOM_ENTRY = (
    "from app.streamlit_app import run_app\n"
    "def boom():\n"
    "    raise AssertionError('model client built before the passcode check')\n"
    "run_app(make_muse=boom)\n"
)


def _entry(script: str = _ENTRY, secret: str | None = None):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=30)
    if secret is not None:
        at.secrets["APP_PASSCODE"] = secret
    return at.run()


def test_the_default_page_is_the_new_review_screen():
    at = _entry()
    assert not at.exception
    assert [b.label for b in at.button] == ["Check the claim"]
    assert [t.label for t in at.text_area] == ["Claim"]


def test_the_default_page_has_exactly_one_passcode_box():
    at = _entry()
    assert [t.label for t in at.text_input].count("Passcode") == 1


def test_the_old_packet_page_has_exactly_one_passcode_box_and_its_content():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string("from app.streamlit_app import main\nmain()\n", default_timeout=30).run()
    assert [t.label for t in at.text_input].count("Passcode") == 1
    assert "Load the export-button packet" in [b.label for b in at.button]


def test_set_page_config_is_called_once_and_only_by_the_entry():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    owners = [
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef)
        and any(isinstance(n, ast.Attribute) and n.attr == "set_page_config" for n in ast.walk(fn))
    ]
    assert owners == ["run_app"]


def test_the_two_pages_are_the_new_review_then_the_packet_app():
    from app.streamlit_app import page_plan

    plan = page_plan()
    assert [(p.title, p.default) for p in plan] == [("New review", True), ("Packet app", False)]
    assert len({p.url_path for p in plan}) == 2


@pytest.mark.parametrize("secret,entered", [(None, "x"), ("right", ""), ("right", "wrong")])
def test_new_page_passcode_blocks_before_any_model_client_is_built(secret, entered):
    at = _entry(_BOOM_ENTRY, secret)
    at.text_input(key="passcode").set_value(entered)
    at.text_area[0].set_value("Detention is paid at $100.00 per hour.")
    at.get("form_submit_button")[0].click()
    at.run()
    assert not at.exception
    assert at.error and "passcode" in at.error[0].value.lower()


def test_old_page_passcode_check_comes_before_any_client_is_built():
    # The old page builds its client only inside check_claim or _review_live, after live_refusal.
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    for name in ("_show_upload", "_run_lead"):
        fn = _function(tree, name)
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        refusal = min(n.lineno for n in calls if n.func.id == "live_refusal")
        built = [n.lineno for n in calls if n.func.id in {"check_claim", "_review_live"}]
        assert built and refusal < min(built)


@pytest.mark.parametrize(
    "secret,state,refused",
    [
        (None, {"passcode": "x"}, True),  # unset passcode never passes
        ("right", {}, True),  # widget not yet committed: key absent
        ("right", {"passcode": ""}, True),
        ("right", {"passcode": "wrong"}, True),
        ("right", {"passcode": "right"}, False),
    ],
)
def test_live_refusal_gate_is_fail_closed(secret, state, refused):
    from types import SimpleNamespace

    st = SimpleNamespace(secrets={"APP_PASSCODE": secret} if secret else {}, session_state=state)
    assert (live_refusal(st) is not None) is refused
