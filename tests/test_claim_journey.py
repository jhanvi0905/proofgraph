"""Text-packet screen. The stamp comes from run_program, not from the wrapper."""

import json

from proofgraph.adapters.base import for_engine
from proofgraph.engine.route import run_program
from proofgraph.schema import Case, ClaimProgram

from app.streamlit_app import (
    PACKET_DIR,
    ReplayError,
    packet_catalog,
    render_review,
    review_packet,
)


def _load(name: str) -> dict:
    return json.loads((PACKET_DIR / name).read_text(encoding="utf-8"))


def _section(html: str, section_id: str) -> str:
    marker = f"id='links-{section_id}'"
    start = html.index(marker)
    nxt = html.find("id='links-", start + len(marker))
    return html[start:] if nxt < 0 else html[start:nxt]


def test_catalog_leads_with_the_shared_file_and_other_worlds():
    keys = [item.key for item in packet_catalog()]
    assert keys[0] == "ship-export-this-week.json"
    assert "late-fee-overcharge.json" in keys
    assert "numeric-val-0.json" in keys
    lead = packet_catalog()[0].payload
    assert "expected" not in lead
    assert "answer" not in lead["case"]
    assert "gold_evidence" not in lead["case"]
    assert [source["id"] for source in lead["case"]["sources"]] == [
        "usage_note",
        "support_note",
        "release_note",
    ]


def test_lead_screen_matches_run_program():
    raw = _load("ship-export-this-week.json")
    review = review_packet(raw)
    case = for_engine(Case.model_validate(raw["case"]))
    program = ClaimProgram.model_validate(raw["program"])
    verdict = run_program(case, program)

    assert review.packet.verdict == verdict.verdict == "CONTRADICTED"
    assert review.packet.label == verdict.label == "COMPUTED"
    assert review.role == "demo"
    assert review.world == "product decision"
    assert review.case.dataset == "freight"
    assert review.case.id == "ship-export-this-week"
    assert [row.status for row in review.packet.link_results] == ["pass", "fail", "pass"]
    assert [row.link_id for row in review.packet.link_results] == ["l_use", "l_cost", "l_should"]

    html = render_review(review)
    passed = _section(html, "pass")
    failed = _section(html, "fail")
    opened = _section(html, "unresolved")
    aside = _section(html, "aside").split("One verdict")[0]

    assert "l_use" in passed
    assert "pass" in passed
    assert "40%" in passed
    assert "usage_note" in passed
    assert "Export is used by 40% of weekly active accounts." in passed
    assert "l_should" not in passed
    assert "l_cost" not in passed

    assert "l_cost" in failed
    assert "fail" in failed
    assert "expression does not hold" in failed
    assert "$4,200" in failed
    assert "support_note" in failed
    assert "Export support costs $4,200 a month." in failed

    assert "UNVERIFIABLE_PART" in opened
    assert "The release note does not mention the export button or this week." in opened
    assert "release_note" in opened
    assert "The release this cycle covers search filters and the billing page." in opened

    assert "l_should" in aside
    assert "ASSUMED" in aside
    assert "did not decide the verdict" in aside
    assert "CONTRADICTED" not in aside
    assert "pass" not in aside

    assert verdict.verdict in html
    assert "gold_evidence" not in html
    assert "expected" not in html
    assert "which contradicts the claimed" not in html
    assert "Sample packet" not in html


def test_another_world_uses_the_same_function():
    raw = _load("late-fee-overcharge.json")
    review = review_packet(raw)
    verdict = run_program(
        for_engine(Case.model_validate(raw["case"])),
        ClaimProgram.model_validate(raw["program"]),
    )
    assert review.packet.verdict == verdict.verdict
    assert review.packet.label == verdict.label
    assert review.world == "contract late fee"
    html = render_review(review)
    assert verdict.verdict in html
    assert "gold_evidence" not in html
    assert "expected" not in html


def test_filing_packet_without_a_program_does_not_invent_a_stamp():
    raw = _load("numeric-val-0.json")
    try:
        review_packet(raw)
    except ReplayError as exc:
        assert "no program" in str(exc)
    else:
        raise AssertionError("a packet with no program must not produce a stamp")


def test_a_different_program_changes_the_lead_verdict():
    raw = _load("ship-export-this-week.json")
    raw["program"] = {"facts": [], "links": [], "required": [], "unverifiable_parts": []}
    review = review_packet(raw)
    assert review.packet.verdict == "UNRESOLVED"
    assert review.packet.verdict != "CONTRADICTED"


# --- Judge journey screen: AppTest, no network, check_claim stubbed. ---

import hmac  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

import app.streamlit_app as screen  # noqa: E402

_SCRIPT = "from app.streamlit_app import main\nmain()\n"
_LOAD = "Load the export-button packet"
_VERDICT_WORDS = ("SUPPORTED", "CONTRADICTED", "UNRESOLVED")


def _screen(passcode: str | None = None) -> "AppTest":
    # Imported here: test_app asserts streamlit is not loaded at collection.
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT, default_timeout=30)
    if passcode is not None:
        at.secrets["APP_PASSCODE"] = passcode
    return at.run()


def _button(at: 'AppTest', label: str):
    return next(item for item in at.button if item.label == label)


def _text(at: 'AppTest') -> str:
    parts: list[str] = []
    for kind in ("html", "markdown", "caption", "error", "warning", "info", "success"):
        parts.extend(str(getattr(item, "value", "")) for item in at.get(kind))
    for item in at.get("status"):
        parts.append(str(item.proto))
    return "\n".join(parts)


def _loaded(passcode: str | None = None) -> 'AppTest':
    at = _screen(passcode)
    _button(at, _LOAD).click().run()
    return at


def _lead_packet() -> screen.ReplayPacket:
    return review_packet(_load("ship-export-this-week.json")).packet


class _Stub:
    """Stands in for check_claim. Records calls; never touches a model."""

    def __init__(self, *, error: BaseException | None = None) -> None:
        self.calls = 0
        self.error = error

    def __call__(self, case, *, client=None, on_stage=None):
        self.calls += 1
        if on_stage is not None:
            on_stage("propose")
        if self.error is not None:
            raise self.error
        if on_stage is not None:
            on_stage("ground")
        return _lead_packet()


class _CapError(Exception):
    reason_code = "SPEND_CAP"


def test_empty_state_names_the_job_and_shows_no_result():
    at = _screen()
    assert not at.exception
    text = _text(at)
    assert any(item.label == _LOAD for item in at.button)
    assert "links-pass" not in text
    assert "links-fail" not in text
    for word in _VERDICT_WORDS:
        assert word not in text
    assert "usage_note" not in text


def test_the_lead_packet_loads_in_one_click():
    at = _loaded()
    assert not at.exception
    claims = [item.value for item in at.text_area if item.label == "Claim"]
    assert any("ship the export button this week" in value for value in claims)
    assert {item.label for item in at.text_area} >= {"usage_note", "support_note", "release_note"}
    for word in _VERDICT_WORDS:
        assert word not in _text(at)


def test_detention_packet_is_still_loadable_from_the_empty_state():
    at = _screen()
    _button(at, "Load the detention packet").click().run()
    assert not at.exception
    claims = [item.value for item in at.text_area if item.label == "Claim"]
    assert any("detention" in value.lower() for value in claims)


def test_verdict_renders_only_after_the_run_and_never_paints_expected():
    at = _loaded()
    assert "links-pass" not in _text(at)
    _button(at, "Run the check").click().run()
    assert not at.exception
    text = _text(at)
    assert "CONTRADICTED" in text
    assert "expected" not in text.lower()
    assert "gold_evidence" not in text
    lines = [child.value for child in at.get("status")[0].children.values()]
    assert [line.split("**")[1] for line in lines] == list(screen.STAGES)


def test_pass_fail_and_unresolved_rows_each_carry_their_quote_and_source():
    at = _loaded()
    _button(at, "Run the check").click().run()
    html = next(item.value for item in at.get("html") if "links-pass" in str(item.value))
    passed = _section(html, "pass")
    failed = _section(html, "fail")
    opened = _section(html, "unresolved")
    assert "<mark>Export is used by 40% of weekly active accounts.</mark>" in passed
    assert "<details" in passed and "usage_note" in passed
    assert "<mark>Export support costs $4,200 a month.</mark>" in failed
    assert "support_note" in failed
    assert "compute" in passed and "compute" in failed
    assert "release_note" in opened
    assert "The release this cycle covers search filters and the billing page." in opened
    assert "Need evidence for the part of the claim that could not be mapped." in opened
    assert "fetch" in opened


def test_a_failing_stage_shows_no_verdict_and_keeps_the_inputs():
    at = _loaded()
    edited = "We should ship the export button next week."
    at.text_area(key="lead_claim").set_value(edited)
    at.run()

    def boom(_case, _program, **_kw):
        raise RuntimeError("calc broke")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(screen, "run_program", boom)
        _button(at, "Run the check").click().run()
    assert not at.exception
    text = _text(at)
    assert "calc broke" in text
    assert "ground" in at.error[0].value
    for word in _VERDICT_WORDS:
        assert word not in text
    assert at.text_area(key="lead_claim").value == edited


def test_spend_cap_says_cost_limit_and_shows_no_verdict(monkeypatch):
    stub = _Stub(error=_CapError("cap"))
    monkeypatch.setattr(screen, "check_claim", stub)
    at = _loaded("open-sesame")
    at.text_input(key="passcode").set_value("open-sesame").run()
    _button(at, "Check live with Meta").click().run()
    assert not at.exception
    assert stub.calls == 1
    assert "cost limit" in at.error[0].value
    assert "not a finding" in at.error[0].value
    for word in _VERDICT_WORDS:
        assert word not in _text(at)
    assert at.text_area(key="lead_claim").value  # inputs kept


@pytest.mark.parametrize("entered", ["", "wrong"])
def test_wrong_or_blank_passcode_makes_zero_calls(monkeypatch, entered):
    stub = _Stub()
    monkeypatch.setattr(screen, "check_claim", stub)
    at = _loaded("open-sesame")
    at.text_input(key="passcode").set_value(entered).run()
    _button(at, "Check live with Meta").click().run()
    assert not at.exception
    assert stub.calls == 0
    assert "passcode" in at.error[0].value.lower()
    for word in _VERDICT_WORDS:
        assert word not in _text(at)


def test_no_configured_passcode_refuses_live_calls_but_offline_review_works(monkeypatch):
    stub = _Stub()
    monkeypatch.setattr(screen, "check_claim", stub)
    at = _loaded(None)
    at.text_input(key="passcode").set_value("anything").run()
    _button(at, "Check live with Meta").click().run()
    assert stub.calls == 0
    assert "no passcode" in at.error[0].value.lower()
    _button(at, "Run the check").click().run()
    assert "CONTRADICTED" in _text(at)


def test_correct_passcode_allows_the_call_and_shows_the_rows(monkeypatch):
    stub = _Stub()
    monkeypatch.setattr(screen, "check_claim", stub)
    at = _loaded("open-sesame")
    at.text_input(key="passcode").set_value("open-sesame").run()
    _button(at, "Check live with Meta").click().run()
    assert not at.exception
    assert stub.calls == 1
    html = next(item.value for item in at.get("html") if "links-pass" in str(item.value))
    assert "CONTRADICTED" in html
    assert "<mark>" in _section(html, "fail")


def test_passcode_compare_is_constant_time_and_fails_closed():
    assert screen.passcode_ok("a-b", "a-b") is True
    assert screen.passcode_ok("a-b", "a-c") is False
    assert screen.passcode_ok("", "") is False
    assert screen.passcode_ok("x", None) is False
    assert screen.passcode_ok("é", "e") is False
    source = (Path(screen.__file__)).read_text(encoding="utf-8")
    assert "hmac.compare_digest" in source
    assert hmac is not None


def test_staged_engine_matches_run_program_on_the_lead_packet():
    seen: list[str] = []
    raw = _load("ship-export-this-week.json")
    review = review_packet(raw, on_stage=seen.append)
    assert seen == ["ground"]
    plain = review_packet(raw)
    assert review.verdict == plain.verdict


def test_every_check_claim_call_site_sits_behind_the_passcode_check():
    import ast

    tree = ast.parse(Path(screen.__file__).read_text(encoding="utf-8"))
    for name in ("_show_upload", "_run_lead"):
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        calls = [
            c.func.id
            for c in ast.walk(fn)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        ]
        assert "live_refusal" in calls, name
    live = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_review_live")
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "check_claim" for c in ast.walk(live))
