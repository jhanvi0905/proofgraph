"""The per-call log line: the model comes from the reply, nothing secret is printed, off by default."""

from __future__ import annotations

import time
from decimal import Decimal

from proofgraph.spend import SpendGuard, SpendLedger

REPLY = {
    "id": "resp_0123456789abcdef0123",
    "model": "muse-spark-1.3",
    "usage": {"input_tokens": 2310, "output_tokens": 214},
}


def _guard(tmp_path, *, offline: bool) -> SpendGuard:
    return SpendGuard(SpendLedger(tmp_path), Decimal("5"), offline=offline)


def test_prints_the_echoed_model_when_enabled(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_CALL_LOG", "1")
    _guard(tmp_path, offline=False).log_call("read-scan", REPLY, time.monotonic())
    err = capsys.readouterr().err
    assert "read-scan" in err
    assert "model=muse-spark-1.3" in err
    assert "id=resp_0123456789abc" in err
    assert "in=2310 out=214" in err


def test_silent_by_default(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("MODEL_CALL_LOG", raising=False)
    _guard(tmp_path, offline=False).log_call("read-scan", REPLY, time.monotonic())
    assert capsys.readouterr().err == ""


def test_silent_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_CALL_LOG", "1")
    SpendGuard(SpendLedger(tmp_path), Decimal("0"), offline=True).log_call(
        "read-scan", REPLY, time.monotonic()
    )
    assert capsys.readouterr().out == ""
    assert capsys.readouterr().err == ""


def test_missing_model_is_reported_as_unreported(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("MODEL_CALL_LOG", "1")
    _guard(tmp_path, offline=False).log_call("read-scan", {}, time.monotonic())
    assert "model=unreported" in capsys.readouterr().err
