"""Replay screen data. Importing the app does not start a server or a model."""

import ast
import sys
from pathlib import Path

import pytest

from app.streamlit_app import (
    FIXTURES,
    ReplayError,
    build_packet,
    failure_message,
    span_rows,
    value_text,
)

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


def test_app_does_not_import_a_model_client():
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            modules.append(node.module or "")
    for name in modules:
        parts = name.split(".")
        assert "muse" not in parts
        assert "openai" not in parts
        assert "dotenv" not in parts
        assert "checker" not in parts
        assert not name.startswith("proofgraph.clients")
        assert name != "proofgraph.propose"


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
