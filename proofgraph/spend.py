"""Total spend across every session and process, and the HTTP retry rule.

The ledger is one JSON file under CACHE_DIR, ``spend.ledger``. It is not named
``*.json`` so it never looks like a cache entry. An update takes an exclusive
file lock, writes a temp file, and renames it over the ledger with
``os.replace``, so two Streamlit sessions cannot lose each other's update.

Every paid call checks the cap first and adds its real cost after. A call that
would put spent plus ``RESERVE_USD`` over the cap raises ``SpendCapReached``
before any HTTP request. A cache hit never reaches this module.

``SPEND_LIMIT_USD=0`` with an injected fake transport is the offline replay:
nothing is checked and nothing is written. Zero with a real transport is a cap
of nothing, so every call is refused.

The ledger lives on local disk. A host that wipes its disk resets the total.

``MuseError`` is defined here, not in ``clients/muse.py``, because
``clients/checker.py`` and ``clients/sam.py`` share these rules and the checker
must not import the Muse client. ``clients.muse`` re-exports it.
"""

from __future__ import annotations

import fcntl
import json
import os
import random
import tempfile
import time
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, TypeVar

T = TypeVar("T")

# Published Spark rates, docs/04-meta-models.md. USD per 1M tokens.
INPUT_USD_PER_M = Decimal("1.25")
OUTPUT_USD_PER_M = Decimal("4.25")
CACHED_USD_PER_M = Decimal("0.15")
# Held back from the cap so one call cannot overshoot it by much.
RESERVE_USD = Decimal("0.05")
# Charged for a SAM still whose response carries no usage: ~1,500 image tokens.
IMAGE_FALLBACK_TOKENS = 1_500

LEDGER_NAME = "spend.ledger"
_LOCK_NAME = "spend.lock"

MAX_RETRIES = 4
REQUEST_TIMEOUT_S = 180.0
_BACKOFF_BASE_S = 1.0
_RETRY_AFTER_MAX_S = 120.0
_MILLION = Decimal(1_000_000)


class MuseError(Exception):
    """A Muse call failed before any verdict exists."""


class SpendCapReached(MuseError):
    """The total spend cap is reached. No request was sent."""

    reason_code = "SPEND_CAP"


class SpendLedgerError(Exception):
    """The ledger file exists but cannot be read."""


class SpendLedger:
    """Total USD spent. Every instance on one directory sees the same total."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    @property
    def path(self) -> Path:
        return self.directory / LEDGER_NAME

    def total(self) -> Decimal:
        """Return the total spent. A missing ledger is zero. An unreadable one raises."""

        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Decimal("0")
        except OSError as exc:
            raise SpendLedgerError("the spend ledger cannot be read") from exc
        try:
            total = Decimal(str(json.loads(raw)["total_usd"]))
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            raise SpendLedgerError("the spend ledger is not valid") from exc
        if not total.is_finite() or total < 0:
            raise SpendLedgerError("the spend ledger is not valid")
        return total

    def add(self, amount: Decimal) -> Decimal:
        """Add ``amount`` atomically and return the new total."""

        if amount < 0:
            raise ValueError("spend cannot be negative")
        self.directory.mkdir(parents=True, exist_ok=True)
        with open(self.directory / _LOCK_NAME, "a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                total = self.total() + amount
                self._write(total)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
        return total

    def _write(self, total: Decimal) -> None:
        fd, temp = tempfile.mkstemp(dir=self.directory, prefix="spend-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"total_usd": str(total)}, handle)
            os.replace(temp, self.path)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise


class SpendGuard:
    """The check before a paid call and the charge after it."""

    def __init__(self, ledger: SpendLedger, limit_usd: Decimal, *, offline: bool) -> None:
        self.ledger = ledger
        self.limit_usd = limit_usd
        self._offline = offline and limit_usd <= 0

    def check(self) -> None:
        """Raise SpendCapReached when spent plus the reserve would pass the cap."""

        if self._offline:
            return
        try:
            spent = self.ledger.total()
        except SpendLedgerError as exc:
            raise SpendCapReached(f"{exc}; spending is stopped") from exc
        if spent + RESERVE_USD > self.limit_usd:
            raise SpendCapReached(
                f"The ${self.limit_usd} spend cap is reached (${spent} spent). "
                "No request was sent."
            )

    def charge(self, cost: Decimal) -> None:
        if self._offline or cost <= 0:
            return
        self.ledger.add(cost)


def _tokens(container: object, key: str) -> int:
    if not isinstance(container, Mapping):
        return 0
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value


def _cost(usage: object, input_key: str, output_key: str, details_key: str) -> Decimal:
    if not isinstance(usage, Mapping):
        return Decimal("0")
    prompt = _tokens(usage, input_key)
    cached = min(_tokens(usage.get(details_key), "cached_tokens"), prompt)
    return (
        (prompt - cached) * INPUT_USD_PER_M
        + cached * CACHED_USD_PER_M
        + _tokens(usage, output_key) * OUTPUT_USD_PER_M
    ) / _MILLION


def responses_cost_usd(response: Mapping[str, Any]) -> Decimal:
    """Cost of a Responses API reply from its ``usage``. No usage costs zero."""

    return _cost(
        response.get("usage"), "input_tokens", "output_tokens", "input_tokens_details"
    )


def chat_cost_usd(response: Mapping[str, Any]) -> Decimal:
    """Cost of a Chat Completions reply from its ``usage``. No usage costs zero."""

    return _cost(
        response.get("usage"),
        "prompt_tokens",
        "completion_tokens",
        "prompt_tokens_details",
    )


def image_fallback_cost_usd() -> Decimal:
    return IMAGE_FALLBACK_TOKENS * INPUT_USD_PER_M / _MILLION


def retry_after_seconds(exc: object) -> float | None:
    """The Retry-After header of an SDK status error, in seconds, when it is a number."""

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("retry-after")
        seconds = float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
    if seconds is None or seconds != seconds or seconds < 0:
        return None
    return seconds


def _retryable(status: object) -> bool:
    # 504 is a gateway timeout. Timeouts are not retried.
    if isinstance(status, bool) or not isinstance(status, int):
        return False
    return status == 429 or (500 <= status < 600 and status != 504)


def call_with_retries(
    send: Callable[[], T],
    *,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> T:
    """Run ``send``. Retry 429 and 5xx at most ``MAX_RETRIES`` times, then re-raise.

    The delay is 1s, 2s, 4s, 8s plus up to 1s of jitter. A ``retry_after`` on
    the error replaces it, capped at two minutes. An error with no
    ``status_code`` (a timeout, a bad body) is never retried.
    """

    attempt = 0
    while True:
        try:
            return send()
        except Exception as exc:
            if attempt >= MAX_RETRIES or not _retryable(getattr(exc, "status_code", None)):
                raise
            hinted = getattr(exc, "retry_after", None)
            if isinstance(hinted, (int, float)) and not isinstance(hinted, bool) and hinted >= 0:
                delay = min(float(hinted), _RETRY_AFTER_MAX_S)
            else:
                delay = _BACKOFF_BASE_S * (2**attempt) + jitter() * _BACKOFF_BASE_S
            sleep(delay)
            attempt += 1
