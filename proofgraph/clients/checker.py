"""Blind checks. Wording is one quote and one statement. Re-read is one crop.

Wording uses ``prompts/blind_wording.md``. Re-read uses ``prompts/blind_reread.md``.
Both call Chat Completions at ``https://inference.baseten.co/v1`` for
``meta-models/muse-spark-open-1026``. This module does not call
``MuseClient``. A re-read whose image Baseten rejects is sent again as a Muse
``input_image`` data URL. Any other failure raises ``CheckerError``. Wording
attempts one JSON repair. HTTP failures are not retried.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol

from pydantic import BaseModel, ValidationError

from proofgraph.cache import CachedCall, DiskCache, cache_key
from proofgraph.config import Settings, load_settings

WordingLabel = Literal["entails", "contradicts", "not_mentioned"]
_PASSAGE = "<<one quote or one clause>>"
_SENTENCE = "<<one plain sentence>>"
_PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "blind_wording.md"
_REREAD_PROMPT = Path(__file__).resolve().parents[2] / "prompts" / "blind_reread.md"
CHAT_COMPLETIONS_ENDPOINT = "POST /v1/chat/completions"
_RESPONSES_ENDPOINT = "POST /v1/responses"
_IMAGE_DETAIL = "high"
_IMAGE_REJECTED = frozenset({400, 415, 422})
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_LABELS = ("entails", "contradicts", "not_mentioned")
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "enum": list(_LABELS)},
    },
    "required": ["answer"],
    "additionalProperties": False,
}
_REREAD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"value": {"type": "string"}},
    "required": ["value"],
    "additionalProperties": False,
}


class CheckerError(Exception):
    """The blind checker failed before it could return a label."""

    def __init__(
        self,
        message: str,
        *,
        reason_code: str = "CHECKER_UNAVAILABLE",
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.reason_code = reason_code
        self.status_code = status_code


class ImageRejected(CheckerError):
    """Baseten refused the image. The Muse input_image fallback may run."""


class WordingAnswer(BaseModel):
    answer: WordingLabel


class RereadValue(BaseModel):
    value: str


class _InvalidJson(CheckerError):
    def __init__(self, raw: str, detail: str) -> None:
        super().__init__(detail, reason_code="EXTRACTION_FAILED")
        self.raw = raw
        self.detail = detail


class ChatTransport(Protocol):
    """One chat.completions.create. Tests pass a fake. Production uses the OpenAI SDK."""

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return the completion JSON object. Do not retry."""


class OpenAIChatTransport:
    """Official OpenAI SDK pointed at Baseten Chat Completions. No retries."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        # The SDK retries 429/5xx twice unless this is 0. HTTP retries stay
        # off until a call actually returns 429.
        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        from openai import APIError, APITimeoutError

        try:
            response = self._client.chat.completions.create(
                model=body["model"],
                messages=body["messages"],
                response_format=body["response_format"],
            )
        except APITimeoutError as exc:
            raise CheckerError("blind checker timed out") from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            code = status if isinstance(status, int) else None
            if code in _IMAGE_REJECTED and _request_has_image(body):
                raise ImageRejected(
                    "Baseten rejected the image",
                    status_code=code,
                ) from exc
            raise CheckerError(
                "blind checker request failed",
                status_code=code,
            ) from exc
        except TimeoutError as exc:
            raise CheckerError("blind checker timed out") from exc
        dumped = response.model_dump(mode="json")
        if not isinstance(dumped, dict):
            raise CheckerError("blind checker response was not a JSON object")
        return dumped


class ImageTransport(Protocol):
    """One Responses create for an input_image. Tests pass a fake."""

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return the response JSON object. Do not retry."""


class OpenAIImageTransport:
    """Muse Responses input_image fallback. No retries."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        from openai import APIError, APITimeoutError

        try:
            response = self._client.responses.create(
                model=body["model"],
                input=body["input"],
                reasoning=body["reasoning"],
                text=body["text"],
            )
        except APITimeoutError as exc:
            raise CheckerError("blind re-read fallback timed out") from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            code = status if isinstance(status, int) else None
            raise CheckerError(
                "blind re-read fallback failed",
                status_code=code,
            ) from exc
        except TimeoutError as exc:
            raise CheckerError("blind re-read fallback timed out") from exc
        dumped = response.model_dump(mode="json")
        if not isinstance(dumped, dict):
            raise CheckerError("blind re-read fallback response was not a JSON object")
        return dumped


class CheckerClient:
    """Cached blind checks. The request carries the crop or the prompt, and no key."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: ChatTransport | None = None,
        image_transport: ImageTransport | None = None,
        cache: DiskCache | None = None,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self._api_key = _blank_to_none(self.settings.baseten_api_key)
        self._transport = transport
        self._image_transport = image_transport
        self.cache = cache if cache is not None else DiskCache(self.settings.cache_dir)

    def answer(self, prompt: str) -> WordingLabel:
        """Return one wording label. The caller's prompt is sent unchanged."""

        self._require_key()
        return self._answer(prompt, repairing=False)

    def reread(self, crop: bytes) -> str:
        """Return the value written in the crop. The crop is the only input."""

        self._require_key()
        _require_crop(crop)
        prompt = _load_reread_prompt()
        body = _image_url_body(self.settings.checker_model, prompt, crop)
        digest = hashlib.sha256(crop).hexdigest()
        key = cache_key(
            model=body["model"],
            endpoint=CHAT_COMPLETIONS_ENDPOINT,
            prompt=prompt,
            schema=body["response_format"],
            inputs={"image_sha256": digest},
            sample_idx=0,
        )
        cached = self._read_reread(key)
        if cached is not None:
            return cached
        try:
            response = self._create(body)
        except ImageRejected:
            return self._reread_fallback(prompt, crop, digest)
        return self._remember(key, CHAT_COMPLETIONS_ENDPOINT, body, response)

    def _answer(self, prompt: str, *, repairing: bool) -> WordingLabel:
        _require_prompt(prompt)
        body = _request_body(self.settings.checker_model, prompt)
        key = cache_key(
            model=body["model"],
            endpoint=CHAT_COMPLETIONS_ENDPOINT,
            prompt=prompt,
            schema=body["response_format"],
            inputs={},
            sample_idx=0,
        )
        if not repairing:
            cached = self._read_cached(key)
            if cached is not None:
                return cached
        response = self._create(body)
        try:
            parsed = _parse_completion(response)
        except _InvalidJson as exc:
            if repairing:
                raise CheckerError(
                    "EXTRACTION_FAILED: model output was not valid JSON for "
                    f"WordingAnswer after one repair attempt: {exc.detail}",
                    reason_code="EXTRACTION_FAILED",
                ) from exc
            return self._answer(
                _repair_prompt(prompt, exc.raw, exc.detail),
                repairing=True,
            )
        self.cache.put(
            CachedCall(
                key=key,
                endpoint=CHAT_COMPLETIONS_ENDPOINT,
                request=body,
                response=response,
            )
        )
        return parsed.answer

    def _reread_fallback(self, prompt: str, crop: bytes, digest: str) -> str:
        body = _input_image_body(self.settings.muse_model, prompt, crop)
        key = cache_key(
            model=body["model"],
            endpoint=_RESPONSES_ENDPOINT,
            prompt=prompt,
            schema=body["text"]["format"],
            inputs={"image_sha256": digest, "part": "input_image"},
            sample_idx=0,
        )
        cached = self._read_reread(key)
        if cached is not None:
            return cached
        response = self._create_image(body)
        return self._remember(key, _RESPONSES_ENDPOINT, body, response)

    def _remember(
        self,
        key: str,
        endpoint: str,
        body: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> str:
        value = _reading(response)
        self.cache.put(
            CachedCall(
                key=key,
                endpoint=endpoint,
                request=dict(body),
                response=dict(response),
            )
        )
        return value

    def _read_reread(self, key: str) -> str | None:
        cached = self.cache.get(key)
        if cached is None:
            return None
        try:
            return _reading(cached.response)
        except CheckerError:
            self.cache.delete(key)
            return None

    def _create_image(self, body: Mapping[str, Any]) -> dict[str, Any]:
        transport = self._image_transport
        if transport is None:
            api_key = _blank_to_none(self.settings.model_api_key)
            if api_key is None:
                raise CheckerError(
                    "Baseten rejected the image and MODEL_API_KEY is not set. "
                    "The Muse fallback was not called."
                )
            transport = OpenAIImageTransport(
                api_key=api_key,
                base_url=self.settings.muse_base_url,
            )
        try:
            raw = transport.create(body)
        except CheckerError:
            raise
        except TimeoutError as exc:
            raise CheckerError("blind re-read fallback timed out") from exc
        try:
            response = json.loads(json.dumps(raw))
        except (TypeError, ValueError) as exc:
            raise CheckerError("blind re-read fallback response was not JSON") from exc
        if not isinstance(response, dict):
            raise CheckerError("blind re-read fallback response was not a JSON object")
        return response

    def _read_cached(self, key: str) -> WordingLabel | None:
        cached = self.cache.get(key)
        if cached is None:
            return None
        try:
            return _parse_completion(cached.response).answer
        except CheckerError:
            self.cache.delete(key)
            return None

    def _require_key(self) -> None:
        if self._api_key is None:
            raise CheckerError(
                "BASETEN_API_KEY is not set. The blind checker was not called."
            )

    def _create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        transport = self._transport
        if transport is None:
            if self._api_key is None:
                raise CheckerError(
                    "BASETEN_API_KEY is not set. The blind checker was not called."
                )
            transport = OpenAIChatTransport(
                api_key=self._api_key,
                base_url=self.settings.baseten_base_url,
            )
        try:
            raw = transport.create(body)
        except CheckerError:
            raise
        except TimeoutError as exc:
            raise CheckerError("blind checker timed out") from exc
        try:
            response = json.loads(json.dumps(raw))
        except (TypeError, ValueError) as exc:
            raise CheckerError("blind checker response was not JSON") from exc
        if not isinstance(response, dict):
            raise CheckerError("blind checker response was not a JSON object")
        return response


def blind_wording(quote: str, statement: str) -> WordingLabel:
    """Ask the blind checker whether the quote entails, contradicts, or omits the statement."""

    _require_text("quote", quote)
    _require_text("statement", statement)
    client = CheckerClient()
    return client.answer(_render(quote, statement))


def blind_reread(crop: bytes) -> str:
    """Read the value written in the crop. The crop is the only input."""

    _require_crop(crop)
    client = CheckerClient()
    return client.reread(crop)


def clocks_agree(left: str, right: str) -> bool:
    """True when both strings name the same time of day. 7:40 and 07:40 agree."""

    left_s = _clock_seconds(left)
    right_s = _clock_seconds(right)
    if left_s is None or right_s is None:
        return False
    return left_s == right_s


def _require_text(name: str, value: object) -> None:
    if not isinstance(value, str) or value.strip() == "":
        raise CheckerError(f"{name} must be a non-empty string")


def _require_prompt(prompt: str) -> None:
    if not isinstance(prompt, str) or prompt.strip() == "":
        raise CheckerError("prompt must be a non-empty string")


def _require_crop(crop: object) -> None:
    if not isinstance(crop, bytes) or crop == b"":
        raise CheckerError("crop must be non-empty bytes")


def _clock_seconds(value: object) -> int | None:
    if not isinstance(value, str):
        return None
    match = _CLOCK.fullmatch(value.strip())
    if match is None:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2))
    second = int(match.group(3) or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return None
    return hour * 3600 + minute * 60 + second


def _png_data_url(crop: bytes) -> str:
    encoded = base64.b64encode(crop).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _load_reread_prompt() -> str:
    try:
        template = _REREAD_PROMPT.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CheckerError("could not read prompts/blind_reread.md") from exc
    if template == "":
        raise CheckerError("prompts/blind_reread.md is empty")
    return template


def _image_url_body(model: str, prompt: str, crop: bytes) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": _png_data_url(crop), "detail": _IMAGE_DETAIL},
                    },
                ],
            }
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "RereadValue",
                "strict": True,
                "schema": _REREAD_SCHEMA,
            },
        },
    }


def _input_image_body(model: str, prompt: str, crop: bytes) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": _png_data_url(crop),
                        "detail": _IMAGE_DETAIL,
                    },
                ],
            }
        ],
        "reasoning": {"effort": "medium"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "RereadValue",
                "schema": _REREAD_SCHEMA,
            },
        },
    }


def _request_has_image(body: Mapping[str, Any]) -> bool:
    messages = body.get("messages")
    if not isinstance(messages, list):
        return False
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if isinstance(part, dict) and part.get("type") == "image_url":
                return True
    return False


def _reading(response: Mapping[str, Any]) -> str:
    return _parse_reading(_reading_text(response))


def _reading_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip() != "":
        return direct
    output = response.get("output")
    if isinstance(output, list):
        parts: list[str] = []
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
        joined = "".join(parts)
        if joined.strip() != "":
            return joined
    if "choices" in response:
        return _message_text(response)
    raise CheckerError(
        "blind re-read response did not include a value",
        reason_code="EXTRACTION_FAILED",
    )


def _parse_reading(raw: str) -> str:
    stripped = raw.strip()
    if stripped == "":
        raise CheckerError(
            "blind re-read returned an empty value",
            reason_code="EXTRACTION_FAILED",
        )
    candidate = _unwrap_fence(stripped)
    if candidate.startswith("{") or candidate.startswith("["):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise CheckerError(
                f"EXTRACTION_FAILED: model output was not valid JSON: {exc.msg}",
                reason_code="EXTRACTION_FAILED",
            ) from exc
        try:
            parsed = RereadValue.model_validate(data)
        except ValidationError as exc:
            raise CheckerError(
                "EXTRACTION_FAILED: model output was not a re-read value",
                reason_code="EXTRACTION_FAILED",
            ) from exc
        value = parsed.value.strip()
        if value == "":
            raise CheckerError(
                "blind re-read returned an empty value",
                reason_code="EXTRACTION_FAILED",
            )
        return value
    if "\n" in candidate:
        raise CheckerError(
            "EXTRACTION_FAILED: model output was not a single value",
            reason_code="EXTRACTION_FAILED",
        )
    return candidate


def _request_body(model: str, prompt: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "WordingAnswer",
                "strict": True,
                "schema": _SCHEMA,
            },
        },
    }


def _parse_completion(response: Mapping[str, Any]) -> WordingAnswer:
    raw = _message_text(response)
    stripped = raw.strip()
    if stripped in _LABELS:
        return WordingAnswer(answer=stripped)  # type: ignore[arg-type]
    candidate = _unwrap_fence(stripped)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise _InvalidJson(raw, exc.msg) from exc
    try:
        return WordingAnswer.model_validate(data)
    except ValidationError as exc:
        raise _InvalidJson(raw, str(exc)) from exc


def _message_text(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise _InvalidJson("", "completion did not include a choice")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise _InvalidJson("", "completion did not include a message")
    content = message.get("content")
    if isinstance(content, str) and content.strip() != "":
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        joined = "".join(parts)
        if joined.strip() != "":
            return joined
    raise _InvalidJson(content if isinstance(content, str) else "", "empty content")


def _unwrap_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    body = text.strip("`").strip()
    if body.lower().startswith("json"):
        body = body[4:].strip()
    return body


def _repair_prompt(prompt: str, raw: str, detail: str) -> str:
    return (
        f"{prompt}\n\n"
        "The previous response was not valid JSON for the required schema. "
        "Return only a JSON object that matches the schema.\n"
        f"Previous response:\n{raw}\n"
        f"Error:\n{detail}\n"
    )


def _render(quote: str, statement: str) -> str:
    try:
        template = _PROMPT.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CheckerError("could not read prompts/blind_wording.md") from exc
    if template == "":
        raise CheckerError("prompts/blind_wording.md is empty")
    passage_at = template.find(_PASSAGE)
    sentence_at = template.find(_SENTENCE)
    if passage_at < 0 or sentence_at < passage_at or template.count(_PASSAGE) != 1:
        raise CheckerError("prompts/blind_wording.md is missing the passage slot")
    if template.count(_SENTENCE) != 1:
        raise CheckerError("prompts/blind_wording.md is missing the statement slot")
    return (
        template[:passage_at]
        + quote
        + template[passage_at + len(_PASSAGE) : sentence_at]
        + statement
        + template[sentence_at + len(_SENTENCE) :]
    )


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
