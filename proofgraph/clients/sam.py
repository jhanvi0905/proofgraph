"""SAM 3.1 count for one still.

A still goes up as an ``input_image`` data URL on a streamed ``sam-3.1``
response. The count is the number of ``<|box;`` records in the completed
``output_text``. Mask payloads are discarded. The request text is the noun.
A signature prompt is not sent. A still does not need a ``file_id``.

HTTP 429 and 5xx are retried at most four times with backoff, and Retry-After
is honored. A timeout is not retried. Each call checks the total spend cap
first and adds its cost after. A cache hit costs nothing.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any, Protocol

from proofgraph.cache import CachedCall, DiskCache, cache_key
from proofgraph.config import Settings, load_settings
from proofgraph.spend import (
    REQUEST_TIMEOUT_S,
    SpendGuard,
    SpendLedger,
    call_with_retries,
    image_fallback_cost_usd,
    responses_cost_usd,
    retry_after_seconds,
)

RESPONSES_ENDPOINT = "POST /v1/responses"
_BOX = "<|box;"
_MASK = "<|mask;"
_MASK_END = "|>"


class SamError(Exception):
    """A SAM call failed before a count exists."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class StreamTransport(Protocol):
    """One streamed POST /v1/responses. Tests pass a fake. Production uses the OpenAI SDK."""

    def stream(self, body: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
        """Yield response events through response.completed. Do not retry."""


class OpenAIStreamTransport:
    """Official OpenAI SDK pointed at https://api.meta.ai/v1. No retries."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        # The SDK retries 429/5xx twice unless this is 0. SamClient retries
        # 429/5xx itself, so every attempt is visible and counted.
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            max_retries=0,
            timeout=REQUEST_TIMEOUT_S,
        )

    def stream(self, body: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
        from openai import APIError, APITimeoutError

        try:
            with self._client.responses.stream(
                model=body["model"],
                input=body["input"],
            ) as stream:
                for event in stream:
                    yield _dumped_event(event)
        except APITimeoutError as exc:
            raise SamError("SAM response timed out") from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            if status == 504 or code == "gateway_timeout":
                raise SamError("SAM gateway timeout") from exc
            raise SamError(
                "SAM request failed",
                status_code=status if isinstance(status, int) else None,
                retry_after=retry_after_seconds(exc),
            ) from exc
        except TimeoutError as exc:
            raise SamError("SAM response timed out") from exc


class SamClient:
    """Cached SAM count. The request carries the still and the noun, and no key."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: StreamTransport | None = None,
        cache: DiskCache | None = None,
        ledger: SpendLedger | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self._api_key = _blank_to_none(self.settings.model_api_key)
        self._transport = transport
        self.cache = cache if cache is not None else DiskCache(self.settings.cache_dir)
        self._sleep = sleep
        self._spend = SpendGuard(
            ledger if ledger is not None else SpendLedger(self.cache.directory),
            self.settings.spend_limit_usd,
            offline=transport is not None,
        )

    def count(self, still: bytes, noun: str) -> int:
        """Return how many times the noun is segmented in the still."""

        self._require_key()
        _require_still(still)
        text = _require_noun(noun)
        body = _request_body(self.settings.sam_model, text, still)
        digest = hashlib.sha256(still).hexdigest()
        key = cache_key(
            model=body["model"],
            endpoint=RESPONSES_ENDPOINT,
            prompt=text,
            schema=None,
            inputs={"image_sha256": digest, "part": "input_image"},
            sample_idx=0,
        )
        cached = self._read(key)
        if cached is not None:
            return cached
        response = self._completed(body)
        count = _count_box_records(_completed_output_text(response))
        self.cache.put(
            CachedCall(
                key=key,
                endpoint=RESPONSES_ENDPOINT,
                request=body,
                response=response,
            )
        )
        return count

    def _read(self, key: str) -> int | None:
        cached = self.cache.get(key)
        if cached is None:
            return None
        try:
            return _count_box_records(_completed_output_text(cached.response))
        except SamError:
            self.cache.delete(key)
            return None

    def _require_key(self) -> None:
        if self._api_key is None:
            raise SamError("MODEL_API_KEY is not set. SAM was not called.")

    def _completed(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self._spend.check()
        transport = self._transport
        if transport is None:
            if self._api_key is None:
                raise SamError("MODEL_API_KEY is not set. SAM was not called.")
            transport = OpenAIStreamTransport(
                api_key=self._api_key,
                base_url=self.settings.muse_base_url,
            )
        def attempt() -> dict[str, Any] | None:
            completed: dict[str, Any] | None = None
            try:
                for event in transport.stream(body):
                    parsed = _event(event)
                    kind = parsed.get("type")
                    if kind in {"error", "response.failed", "response.incomplete"}:
                        raise SamError(_event_message(parsed))
                    if kind != "response.completed":
                        continue
                    response = parsed.get("response")
                    if not isinstance(response, dict):
                        raise SamError("SAM stream did not include a completed response")
                    completed = response
            except SamError:
                raise
            except TimeoutError as exc:
                raise SamError("SAM response timed out") from exc
            return completed

        completed = call_with_retries(attempt, sleep=self._sleep)
        if completed is None:
            raise SamError("SAM stream did not complete")
        try:
            dumped = json.loads(json.dumps(completed))
        except (TypeError, ValueError) as exc:
            raise SamError("SAM response was not JSON") from exc
        if not isinstance(dumped, dict):
            raise SamError("SAM response was not a JSON object")
        if isinstance(dumped.get("usage"), Mapping):
            self._spend.charge(responses_cost_usd(dumped))
        else:
            self._spend.charge(image_fallback_cost_usd())
        return dumped


def sam_count(still: bytes, noun: str) -> int:
    """Count the noun in one still. The still is an input_image data URL."""

    _require_still(still)
    text = _require_noun(noun)
    return SamClient().count(still, text)


def _count_box_records(output_text: str) -> int:
    """Count ``<|box;`` records. Mask payloads are not counted."""

    return _without_masks(output_text).count(_BOX)


def _without_masks(output_text: str) -> str:
    parts: list[str] = []
    index = 0
    while index < len(output_text):
        start = output_text.find(_MASK, index)
        if start < 0:
            parts.append(output_text[index:])
            break
        parts.append(output_text[index:start])
        end = output_text.find(_MASK_END, start + len(_MASK))
        if end < 0:
            break
        index = end + len(_MASK_END)
    return "".join(parts)


def _request_body(model: str, noun: str, still: bytes) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": noun},
                    {"type": "input_image", "image_url": _png_data_url(still)},
                ],
            }
        ],
        "stream": True,
    }


def _png_data_url(still: bytes) -> str:
    encoded = base64.b64encode(still).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _completed_output_text(response: Mapping[str, Any]) -> str:
    status = response.get("status")
    if status in {"failed", "cancelled", "incomplete"}:
        raise SamError(f"SAM response status is {status}")
    error = response.get("error")
    if error not in (None, {}):
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise SamError(message or "SAM response failed")
    if "output_text" in response:
        direct = response["output_text"]
        if not isinstance(direct, str):
            raise SamError("SAM output_text was not a string")
        return direct
    output = response.get("output")
    parts: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if (
                    isinstance(part, dict)
                    and part.get("type") == "output_text"
                    and isinstance(part.get("text"), str)
                ):
                    parts.append(part["text"])
    return "".join(parts)


def _dumped_event(event: Any) -> dict[str, Any]:
    if isinstance(event, Mapping):
        dumped: Any = json.loads(json.dumps(event))
    else:
        dump = getattr(event, "model_dump", None)
        if not callable(dump):
            raise SamError("SAM stream event was not a JSON object")
        dumped = dump(mode="json")
    if not isinstance(dumped, dict):
        raise SamError("SAM stream event was not a JSON object")
    if dumped.get("type") != "response.completed":
        return dumped
    response = dumped.get("response")
    text = _sdk_output_text(event)
    if isinstance(response, dict) and isinstance(text, str):
        response["output_text"] = text
    return dumped


def _sdk_output_text(event: Any) -> str | None:
    if isinstance(event, Mapping):
        response = event.get("response")
    else:
        response = getattr(event, "response", None)
    if isinstance(response, Mapping):
        direct = response.get("output_text")
        return direct if isinstance(direct, str) else None
    text = getattr(response, "output_text", None)
    return text if isinstance(text, str) else None


def _event(event: Mapping[str, Any]) -> dict[str, Any]:
    try:
        parsed = json.loads(json.dumps(event))
    except (TypeError, ValueError) as exc:
        raise SamError("SAM stream event was not JSON") from exc
    if not isinstance(parsed, dict):
        raise SamError("SAM stream event was not a JSON object")
    return parsed


def _event_message(event: Mapping[str, Any]) -> str:
    error = event.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message:
            return message
    response = event.get("response")
    if isinstance(response, dict):
        error = response.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
    kind = event.get("type")
    return kind if isinstance(kind, str) and kind else "SAM stream failed"


def _require_still(still: object) -> None:
    if not isinstance(still, bytes) or still == b"":
        raise SamError("still must be non-empty bytes")


def _require_noun(noun: object) -> str:
    if not isinstance(noun, str) or noun.strip() == "":
        raise SamError("noun must be a non-empty string")
    text = noun.strip()
    if "<|" in text:
        raise SamError("a signature prompt is not used")
    return text


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
