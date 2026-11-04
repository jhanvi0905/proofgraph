"""Runs on a visitor's own Meta Model API key (and, optionally, their own Baseten key).

The key arrives with one request, is used by that request's clients only, and goes nowhere else: not the
environment, not the cache (a cache key is built from model, prompt, schema and inputs, never the key), not the
spend ledger, not a log line, not an event. The clients here are metered by nobody: the caller pays, so the
demo's spend cap and per-visitor limit do not apply. The server's own Baseten key is never used for them, so a
run on someone's Meta key cannot spend the host's second-reader money.

Anything a transport raises is scrubbed of the keys before it can reach a banner, an event or a saved review.
"""

from __future__ import annotations

import re
from decimal import Decimal

from proofgraph.clients.checker import CheckerClient, OpenAIChatTransport, OpenAIImageTransport, _render, _require_text
from proofgraph.clients.muse import MuseClient, MuseError, OpenAIFilesTransport, OpenAIResponsesTransport
from proofgraph.config import load_settings

# What an API key looks like (letters, digits and a few separators). Anything else is refused without being echoed.
_SHAPE = re.compile(r"^[A-Za-z0-9._~+/=:-]{8,300}$")
BAD_SHAPE = "That does not look like an API key. Paste the key as the provider gave it, with nothing around it."
META_REJECTED = ("Meta did not accept the API key you entered, so nothing was read. Check that it is a current "
                 "Meta Model API key and try again, or use the worked example, which needs no key.")
_UNMETERED_CAP = Decimal("1000000000")
REDACTED = "[your key]"


def clean_key(raw: str | None) -> str | None:
    """The key without surrounding space, or None when none was given. Raises ValueError on a malformed one."""
    key = (raw or "").strip()
    if not key:
        return None
    if not _SHAPE.match(key):
        raise ValueError(BAD_SHAPE)
    return key


class UnmeteredLedger:
    """Stands where the shared spend ledger stands: nothing is read from it and nothing is added to it."""

    def total(self) -> Decimal:
        return Decimal("0")

    def add(self, amount: Decimal) -> Decimal:
        return Decimal("0")


class KeyedRun:
    """The secrets of one request and what happened to them."""

    def __init__(self, meta_key: str, baseten_key: str | None) -> None:
        self.secrets = [k for k in (meta_key, baseten_key) if k]
        self.meta_rejected = False

    def scrub(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, REDACTED)
        return text

    def clean(self, exc: BaseException, *, meta: bool) -> BaseException:
        """The same exception (so retry rules still see its status), with the keys out of its text and chain."""
        status = getattr(exc, "status_code", None)
        if meta and status in (401, 403):
            self.meta_rejected = True
            exc.args = (META_REJECTED,)
        else:
            exc.args = tuple(self.scrub(a) if isinstance(a, str) else a for a in exc.args)
        exc.__cause__ = None
        exc.__context__ = None
        exc.__suppress_context__ = True
        return exc


class _Guarded:
    """A transport whose failures are cleaned before they leave."""

    def __init__(self, inner, run: KeyedRun, *, meta: bool) -> None:
        self._inner, self._run, self._meta = inner, run, meta

    def create(self, *args, **kwargs):
        try:
            return self._inner.create(*args, **kwargs)
        except Exception as exc:
            raise self._run.clean(exc, meta=self._meta)  # noqa: B904 - the chain is dropped on purpose


def keyed_clients(meta_key: str, baseten_key: str | None = None) -> tuple[MuseClient, object, KeyedRun]:
    """The Meta client, the blind-checker function and the run record for one request on the caller's keys.

    Without a Baseten key the second reader has no key at all (it answers "unavailable", exactly as on a server
    with none set); the server's own Baseten key is not borrowed.
    """
    run = KeyedRun(meta_key, baseten_key)
    base = load_settings()
    settings = base.model_copy(update={"model_api_key": meta_key, "baseten_api_key": baseten_key,
                                       "spend_limit_usd": _UNMETERED_CAP})
    ledger = UnmeteredLedger()
    muse = MuseClient(
        settings,
        transport=_Guarded(OpenAIResponsesTransport(api_key=meta_key, base_url=settings.muse_base_url), run, meta=True),
        files_transport=_Guarded(OpenAIFilesTransport(api_key=meta_key, base_url=settings.muse_base_url), run, meta=True),
        ledger=ledger,
    )
    checker_args: dict = {"ledger": ledger}
    if baseten_key:
        checker_args["transport"] = _Guarded(
            OpenAIChatTransport(api_key=baseten_key, base_url=settings.baseten_base_url), run, meta=False)
        checker_args["image_transport"] = _Guarded(
            OpenAIImageTransport(api_key=meta_key, base_url=settings.muse_base_url), run, meta=False)
    checker_client = CheckerClient(settings, **checker_args)

    def checker(quote: str, statement: str):
        _require_text("quote", quote)
        _require_text("statement", statement)
        return checker_client.answer(_render(quote, statement))

    return muse, checker, run

