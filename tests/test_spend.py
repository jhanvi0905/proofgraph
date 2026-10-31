"""Total spend ledger and the cap. Fakes only. No network."""

import json
import threading
from decimal import Decimal
from typing import Any, Mapping

import pytest
from pydantic import BaseModel

from proofgraph.clients.checker import CheckerClient, CheckerError
from proofgraph.clients.muse import MuseClient, MuseError, SpendCapReached
from proofgraph.config import load_settings
from proofgraph.spend import RESERVE_USD, SpendLedger, chat_cost_usd, responses_cost_usd


class Widget(BaseModel):
    name: str
    count: int


def _settings(tmp_path, **env: str):
    base = {"MODEL_API_KEY": "test-key", "BASETEN_API_KEY": "b-key", "CACHE_DIR": str(tmp_path)}
    base.update(env)
    return load_settings(base)


def _envelope(text: str, *, output_tokens: int = 0, input_tokens: int = 0) -> dict[str, Any]:
    return {
        "status": "completed",
        "output_text": text,
        "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
    }


class FakeTransport:
    def __init__(self, responses: list[dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return self._responses.pop(0)


WIDGET = '{"name": "crate", "count": 1}'


def test_cost_uses_the_published_rates():
    full = {"input_tokens": 1_000_000, "output_tokens": 1_000_000}
    assert responses_cost_usd({"usage": full}) == Decimal("5.50")
    cached = {
        "input_tokens": 1_000_000,
        "output_tokens": 0,
        "input_tokens_details": {"cached_tokens": 1_000_000},
    }
    assert responses_cost_usd({"usage": cached}) == Decimal("0.15")
    chat = {"prompt_tokens": 2_000_000, "completion_tokens": 1_000_000}
    assert chat_cost_usd({"usage": chat}) == Decimal("6.75")
    assert responses_cost_usd({}) == Decimal("0")
    assert responses_cost_usd({"usage": {"input_tokens": "x"}}) == Decimal("0")


def test_two_ledgers_on_one_file_see_the_same_total(tmp_path):
    first = SpendLedger(tmp_path)
    second = SpendLedger(tmp_path)

    first.add(Decimal("1.25"))
    assert second.total() == Decimal("1.25")
    second.add(Decimal("0.75"))
    assert first.total() == Decimal("2.00")
    assert list(tmp_path.glob("*.json")) == []
    assert not list(tmp_path.glob("*.tmp"))


def test_concurrent_updates_are_not_lost(tmp_path):
    def work() -> None:
        ledger = SpendLedger(tmp_path)
        for _ in range(10):
            ledger.add(Decimal("0.01"))

    threads = [threading.Thread(target=work) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert SpendLedger(tmp_path).total() == Decimal("0.80")


def test_unreadable_ledger_fails_closed(tmp_path):
    ledger = SpendLedger(tmp_path)
    ledger.add(Decimal("1"))
    next(tmp_path.glob("spend*.ledger")).write_text("not json")

    client = MuseClient(_settings(tmp_path), transport=FakeTransport([_envelope(WIDGET)]))
    with pytest.raises(SpendCapReached):
        client.structured("Count.", Widget)


def test_spend_cap_reached_is_a_muse_error_with_a_stable_code():
    assert issubclass(SpendCapReached, MuseError)
    assert SpendCapReached.reason_code == "SPEND_CAP"


def test_crossing_the_cap_blocks_the_next_call_before_any_http(tmp_path):
    transport = FakeTransport(
        [_envelope(WIDGET, output_tokens=400_000), _envelope(WIDGET)]
    )
    client = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="1"), transport=transport)

    client.structured("First.", Widget)
    assert SpendLedger(tmp_path).total() == Decimal("1.70")
    assert transport.calls == 1

    with pytest.raises(SpendCapReached) as caught:
        client.structured("Second.", Widget)
    assert caught.value.reason_code == "SPEND_CAP"
    assert transport.calls == 1


def test_the_reserve_counts_against_the_cap(tmp_path):
    SpendLedger(tmp_path).add(Decimal("1") - RESERVE_USD + Decimal("0.01"))
    transport = FakeTransport([_envelope(WIDGET)])
    client = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="1"), transport=transport)

    with pytest.raises(SpendCapReached):
        client.structured("Count.", Widget)
    assert transport.calls == 0


def test_a_cache_hit_costs_nothing_even_at_the_cap(tmp_path):
    transport = FakeTransport([_envelope(WIDGET, output_tokens=1_000_000)])
    client = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="5"), transport=transport)

    client.structured("Count.", Widget)
    spent = SpendLedger(tmp_path).total()
    assert spent == Decimal("4.25")

    assert client.structured("Count.", Widget) == Widget(name="crate", count=1)
    assert SpendLedger(tmp_path).total() == spent
    assert transport.calls == 1


def test_the_total_is_shared_between_clients(tmp_path):
    first = MuseClient(
        _settings(tmp_path, SPEND_LIMIT_USD="1"),
        transport=FakeTransport([_envelope(WIDGET, output_tokens=400_000)]),
    )
    second_transport = FakeTransport([_envelope(WIDGET)])
    second = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="1"), transport=second_transport)

    first.structured("First.", Widget)
    with pytest.raises(SpendCapReached):
        second.structured("Second.", Widget)
    assert second_transport.calls == 0


def test_offline_replay_with_a_zero_limit_makes_no_ledger_and_raises_nothing(tmp_path):
    transport = FakeTransport([_envelope(WIDGET, output_tokens=500)])
    client = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="0"), transport=transport)

    assert client.structured("Count.", Widget) == Widget(name="crate", count=1)
    assert list(tmp_path.glob("spend*")) == []


def test_a_zero_limit_without_a_fake_transport_never_builds_one(tmp_path, monkeypatch):
    import openai

    def boom(**kwargs: Any) -> None:
        raise AssertionError("an SDK client was built")

    monkeypatch.setattr(openai, "OpenAI", boom)
    client = MuseClient(_settings(tmp_path, SPEND_LIMIT_USD="0"))

    with pytest.raises(SpendCapReached):
        client.structured("Count.", Widget)


def test_a_repair_call_is_paid_for_too(tmp_path):
    transport = FakeTransport(
        [
            _envelope("not json", output_tokens=1_000_000),
            _envelope(WIDGET, output_tokens=1_000_000),
        ]
    )
    client = MuseClient(_settings(tmp_path), transport=transport)

    client.structured("Count.", Widget)
    assert SpendLedger(tmp_path).total() == Decimal("8.50")


# ---- checker (Baseten Chat Completions) ----


def _completion(label: str, *, prompt_tokens: int = 0, completion_tokens: int = 0):
    return {
        "choices": [{"message": {"content": json.dumps({"answer": label})}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


class ChatFake:
    def __init__(self, items: list[Any]) -> None:
        self._items = list(items)
        self.calls = 0

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls += 1
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _checker(tmp_path, transport, sleeps=None, **env):
    return CheckerClient(
        _settings(tmp_path, **env),
        transport=transport,
        sleep=(sleeps.append if sleeps is not None else (lambda _s: None)),
    )


def test_checker_adds_cost_and_stops_at_the_cap(tmp_path):
    transport = ChatFake(
        [_completion("entails", completion_tokens=400_000), _completion("entails")]
    )
    checker = _checker(tmp_path, transport, SPEND_LIMIT_USD="1")

    assert checker.answer("one") == "entails"
    assert SpendLedger(tmp_path).total() == Decimal("1.70")
    with pytest.raises(SpendCapReached):
        checker.answer("two")
    assert transport.calls == 1


def test_checker_retries_429_then_succeeds_and_honors_retry_after(tmp_path):
    transport = ChatFake(
        [
            CheckerError("busy", status_code=429, retry_after=7.0),
            CheckerError("busy", status_code=503),
            _completion("contradicts"),
        ]
    )
    sleeps: list[float] = []
    checker = _checker(tmp_path, transport, sleeps)

    assert checker.answer("one") == "contradicts"
    assert transport.calls == 3
    assert sleeps[0] == 7.0
    assert 2.0 <= sleeps[1] < 3.0


def test_checker_gives_up_after_four_retries(tmp_path):
    transport = ChatFake([CheckerError("busy", status_code=429) for _ in range(5)])
    sleeps: list[float] = []
    checker = _checker(tmp_path, transport, sleeps)

    with pytest.raises(CheckerError) as caught:
        checker.answer("one")
    assert caught.value.status_code == 429
    assert transport.calls == 5
    assert len(sleeps) == 4
    assert list(tmp_path.glob("*.json")) == []


def test_checker_does_not_retry_a_400(tmp_path):
    transport = ChatFake([CheckerError("bad", status_code=400)])
    checker = _checker(tmp_path, transport)

    with pytest.raises(CheckerError):
        checker.answer("one")
    assert transport.calls == 1


def test_checker_timeout_is_not_retried(tmp_path):
    transport = ChatFake([TimeoutError("slow")])
    sleeps: list[float] = []
    checker = _checker(tmp_path, transport, sleeps)

    with pytest.raises(CheckerError):
        checker.answer("one")
    assert transport.calls == 1
    assert sleeps == []
