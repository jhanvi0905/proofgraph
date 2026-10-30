"""Muse Spark calls on the Meta Responses API.

The request body follows the official create-response schema
(https://dev.meta.ai/docs/api-reference/responses/schemas) and the quickstart
(https://dev.meta.ai/docs/quickstart):

    POST /v1/responses
    model, input, reasoning.effort, text.format = json_schema

Structured output on this endpoint is ``text.format``. ``response_format`` is
the Chat Completions parameter and does not configure Responses.

This client returns a validated pydantic object. It does not choose a verdict.
A cached request and response are the provenance of a call that validated.
Failed and invalid responses are not stored. ``bypass_cache`` skips the read
and the write for an experiment. One repair call is made when the output is
not valid JSON for the schema; the next failure raises ExtractionFailed.
Timeouts and malformed responses are not repaired.

A local PDF or image is uploaded with files.create and purpose "user_data".
The file id is cached under the SHA-256 of those bytes, so the same bytes
are not uploaded again. A call that attaches files sends input as a user
message: input_text, then one input_file part per file with detail high.
Text-only calls still send input as a string.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Mapping, Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from proofgraph.cache import CachedCall, DiskCache, cache_key
from proofgraph.config import Settings, load_settings

T = TypeVar("T", bound=BaseModel)

RESPONSES_ENDPOINT = "POST /v1/responses"
FILES_ENDPOINT = "POST /v1/files"
FILE_PURPOSE = "user_data"
FILE_DETAIL = "high"
# docs/04 starts propose at medium. The Responses schema also allows max.
DEFAULT_REASONING_EFFORT = "medium"
# docs/04 allows minimal…xhigh. The Responses schema also lists max; this client does not send it.
_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


class MuseError(Exception):
    """A Muse call failed before any verdict exists."""


class MissingApiKeyError(MuseError):
    """MODEL_API_KEY is absent, so the API was not called."""


class MuseTimeoutError(MuseError):
    """The Responses call timed out."""


class MuseResponseError(MuseError):
    """The API answered with a body this client cannot read as text."""


class ExtractionFailed(MuseError):
    """The output was still invalid JSON after one repair attempt."""

    reason_code = "EXTRACTION_FAILED"


class _InvalidJson(MuseError):
    def __init__(self, raw: str, detail: str) -> None:
        super().__init__(detail)
        self.raw = raw
        self.detail = detail


class ResponsesTransport(Protocol):
    """One POST /v1/responses. Tests pass a fake. Production uses the OpenAI SDK."""

    def create(self, body: Mapping[str, Any]) -> Mapping[str, Any]:
        """Return the response JSON object. Do not retry."""


class FilesTransport(Protocol):
    """One POST /v1/files. Tests pass a fake. Production uses the OpenAI SDK."""

    def create(self, *, filename: str, content: bytes, purpose: str) -> Mapping[str, Any]:
        """Return the file object JSON. Do not retry."""


class JsonSchemaFormat(BaseModel):
    """text.format when type is json_schema. ``strict`` is omitted (server default false)."""

    model_config = ConfigDict(populate_by_name=True)

    type: str = "json_schema"
    name: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    schema_document: dict[str, Any] = Field(alias="schema")


class TextParam(BaseModel):
    format: JsonSchemaFormat


class ReasoningParam(BaseModel):
    effort: str


class ResponsesRequest(BaseModel):
    """The four fields this client sends. No other request parameters."""

    model: str
    input: str | list[dict[str, Any]]
    reasoning: ReasoningParam
    text: TextParam

    def wire(self) -> dict[str, Any]:
        body = self.model_dump(mode="json", by_alias=True)
        format_ = body["text"]["format"]
        if set(format_) != {"type", "name", "schema"}:
            raise MuseError("refusing to send a structured-output format that is not json_schema")
        if format_["type"] != "json_schema":
            raise MuseError("refusing to send a structured-output format that is not json_schema")
        return body


class OpenAIResponsesTransport:
    """Official OpenAI SDK pointed at https://api.meta.ai/v1. No retries."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        # The SDK retries 429/5xx twice unless this is 0. This slice repairs
        # malformed JSON once and does not retry HTTP failures.
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
            raise MuseTimeoutError("Muse response timed out") from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            if status == 504 or code == "gateway_timeout":
                raise MuseTimeoutError("Muse gateway timeout") from exc
            raise MuseResponseError(f"Muse request failed: {exc}") from exc
        except TimeoutError as exc:
            raise MuseTimeoutError("Muse response timed out") from exc
        dumped = response.model_dump(mode="json")
        if not isinstance(dumped, dict):
            raise MuseResponseError("Muse response was not a JSON object")
        return dumped


class OpenAIFilesTransport:
    """Official OpenAI SDK files.create against https://api.meta.ai/v1. No retries."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url, max_retries=0)

    def create(self, *, filename: str, content: bytes, purpose: str) -> Mapping[str, Any]:
        from openai import APIError, APITimeoutError

        if purpose != FILE_PURPOSE:
            raise MuseError('files are uploaded with purpose "user_data"')
        try:
            uploaded = self._client.files.create(
                file=(filename, content),
                purpose="user_data",
            )
        except APITimeoutError as exc:
            raise MuseTimeoutError("Muse file upload timed out") from exc
        except APIError as exc:
            status = getattr(exc, "status_code", None)
            code = getattr(exc, "code", None)
            if status == 504 or code == "gateway_timeout":
                raise MuseTimeoutError("Muse gateway timeout") from exc
            raise MuseResponseError(f"Muse request failed: {exc}") from exc
        except TimeoutError as exc:
            raise MuseTimeoutError("Muse file upload timed out") from exc
        dumped = uploaded.model_dump(mode="json")
        if not isinstance(dumped, dict):
            raise MuseResponseError("Files API response was not a JSON object")
        return dumped


class MuseClient:
    """Cached, validated structured calls to Muse Spark."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        transport: ResponsesTransport | None = None,
        files_transport: FilesTransport | None = None,
        cache: DiskCache | None = None,
    ) -> None:
        self.settings = settings if settings is not None else load_settings()
        self.spend_limit_usd = self.settings.spend_limit_usd
        self._api_key = _blank_to_none(self.settings.model_api_key)
        self._transport = transport
        self._files_transport = files_transport
        self.cache = cache if cache is not None else DiskCache(self.settings.cache_dir)
        self._file_cache = DiskCache(self.cache.directory / "files")

    def upload_user_data(self, path: str | Path) -> str:
        """Upload a local file once. Return the cached file id for these bytes.

        The Files API can return a new id for the same bytes. This method
        keeps the first id and does not call the API again.
        """

        self._require_key()
        file_path = Path(path)
        if not file_path.is_file():
            raise FileNotFoundError(f"cannot upload {file_path.name or 'file'}")
        content = file_path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        cached = self._cached_file_id(digest)
        if cached is not None:
            return cached
        response = self._read_json(
            lambda: self._files().create(
                filename=file_path.name,
                content=content,
                purpose=FILE_PURPOSE,
            )
        )
        file_id = _require_upload_id(response)
        self._file_cache.put(
            CachedCall(
                key=digest,
                endpoint=FILES_ENDPOINT,
                request={"purpose": FILE_PURPOSE, "sha256": digest},
                response={"id": file_id},
            )
        )
        return file_id

    def structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        sample_idx: int = 0,
        bypass_cache: bool = False,
        file_ids: Sequence[str] | None = None,
    ) -> T:
        """Return one validated object. The caller's prompt text is sent unchanged.

        ``bypass_cache`` is for a prompt experiment. It does not read or write
        the response cache. Eval loops keep the default and stay cached.
        ``file_ids`` become ``input_file`` parts. Omit them for a text case:
        ``input`` stays a string. This method does not upload.
        """

        return self._structured(
            prompt,
            response_model,
            reasoning_effort=reasoning_effort,
            sample_idx=sample_idx,
            repairing=False,
            bypass_cache=bypass_cache,
            file_ids=_require_file_ids(file_ids),
        )

    def _structured(
        self,
        prompt: str,
        response_model: type[T],
        *,
        reasoning_effort: str,
        sample_idx: int,
        repairing: bool,
        bypass_cache: bool,
        file_ids: tuple[str, ...],
    ) -> T:
        self._require_key()
        _require_prompt(prompt)
        _require_model(response_model)
        effort = _require_effort(reasoning_effort)
        _require_sample(sample_idx)
        body = _request_body(
            model=self.settings.muse_model,
            prompt=prompt,
            response_model=response_model,
            effort=effort,
            file_ids=file_ids,
        )
        # Text calls hash the string input. File calls hash that same text
        # plus the input_file parts, so a different file does not reuse it.
        inputs: dict[str, Any] = {"reasoning": body["reasoning"]}
        if file_ids:
            inputs["files"] = [
                {"type": "input_file", "file_id": file_id, "detail": FILE_DETAIL}
                for file_id in file_ids
            ]
        key = cache_key(
            model=body["model"],
            endpoint=RESPONSES_ENDPOINT,
            prompt=prompt if file_ids else body["input"],
            schema=body["text"]["format"],
            inputs=inputs,
            sample_idx=sample_idx,
        )
        if not bypass_cache:
            cached = self._read_cached(key, response_model)
            if cached is not None:
                return cached
        response = self._create(body)
        timeout = _gateway_timeout(response)
        if timeout is not None:
            raise MuseTimeoutError(timeout)
        try:
            parsed = _parse(response, response_model)
        except _InvalidJson as exc:
            if repairing:
                raise ExtractionFailed(
                    "EXTRACTION_FAILED: model output was not valid JSON for "
                    f"{response_model.__name__} after one repair attempt: {exc.detail}"
                ) from exc
            return self._structured(
                _repair_prompt(prompt, exc.raw, exc.detail),
                response_model,
                reasoning_effort=effort,
                sample_idx=sample_idx,
                repairing=True,
                bypass_cache=bypass_cache,
                file_ids=file_ids,
            )
        if not bypass_cache:
            self.cache.put(
                CachedCall(
                    key=key,
                    endpoint=RESPONSES_ENDPOINT,
                    request=body,
                    response=response,
                )
            )
        return parsed

    def _read_cached(self, key: str, response_model: type[T]) -> T | None:
        """Return a stored object only when it still validates.

        A poisoned or invalid entry is deleted so it cannot replay a failure.
        """

        cached = self.cache.get(key)
        if cached is None:
            return None
        try:
            return _parse(cached.response, response_model)
        except MuseError:
            self.cache.delete(key)
            return None

    def _require_key(self) -> None:
        if self._api_key is None:
            raise MissingApiKeyError(
                "MODEL_API_KEY is not set. The Meta Model API was not called."
            )

    def _create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        transport = self._transport
        if transport is None:
            if self._api_key is None:
                raise MissingApiKeyError(
                    "MODEL_API_KEY is not set. The Meta Model API was not called."
                )
            transport = OpenAIResponsesTransport(
                api_key=self._api_key,
                base_url=self.settings.muse_base_url,
            )
        return self._read_json(lambda: transport.create(body))

    def _cached_file_id(self, digest: str) -> str | None:
        cached = self._file_cache.get(digest)
        if cached is None:
            return None
        file_id = _cached_upload_id(cached, digest)
        if file_id is None:
            self._file_cache.delete(digest)
            return None
        return file_id

    def _files(self) -> FilesTransport:
        transport = self._files_transport
        if transport is not None:
            return transport
        if self._api_key is None:
            raise MissingApiKeyError(
                "MODEL_API_KEY is not set. The Meta Model API was not called."
            )
        return OpenAIFilesTransport(
            api_key=self._api_key,
            base_url=self.settings.muse_base_url,
        )

    def _read_json(self, send: Callable[[], Mapping[str, Any]]) -> dict[str, Any]:
        try:
            raw = send()
        except MuseTimeoutError:
            raise
        except TimeoutError as exc:
            raise MuseTimeoutError("Muse response timed out") from exc
        try:
            response = json.loads(json.dumps(raw))
        except (TypeError, ValueError) as exc:
            raise MuseResponseError("Muse response was not JSON") from exc
        if not isinstance(response, dict):
            raise MuseResponseError("Muse response was not a JSON object")
        return response


def _request_body(
    *,
    model: str,
    prompt: str,
    response_model: type[BaseModel],
    effort: str,
    file_ids: Sequence[str] = (),
) -> dict[str, Any]:
    try:
        request = ResponsesRequest(
            model=model,
            input=_responses_input(prompt, file_ids),
            reasoning=ReasoningParam(effort=effort),
            text=TextParam(
                format=JsonSchemaFormat(
                    name=response_model.__name__,
                    schema_document=response_model.model_json_schema(),
                )
            ),
        )
    except ValidationError as exc:
        raise ValueError(
            f"{response_model.__name__} is not a valid json_schema format name"
        ) from exc
    return request.wire()


def _parse(response: Mapping[str, Any], response_model: type[T]) -> T:
    timeout = _gateway_timeout(response)
    if timeout is not None:
        raise MuseTimeoutError(timeout)
    error = response.get("error")
    if error not in (None, {}):
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise MuseResponseError(message or "Muse response failed")
    status = response.get("status")
    if status in {"failed", "cancelled"}:
        raise MuseResponseError(f"Muse response status is {status}")
    raw = _output_text(response)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _InvalidJson(raw, exc.msg) from exc
    try:
        return response_model.model_validate(data)
    except ValidationError as exc:
        raise _InvalidJson(raw, str(exc)) from exc


def _output_text(response: Mapping[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip() != "":
        return direct
    output = response.get("output")
    texts: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "refusal":
                    refusal = part.get("refusal")
                    raise MuseResponseError(
                        refusal if isinstance(refusal, str) and refusal else "Muse refused the request"
                    )
                if part.get("type") == "output_text" and isinstance(part.get("text"), str):
                    texts.append(part["text"])
    if texts:
        joined = "".join(texts)
        if joined.strip() != "":
            return joined
    raise MuseResponseError("Muse response did not include output_text")


def _gateway_timeout(response: Mapping[str, Any]) -> str | None:
    error = response.get("error")
    if not isinstance(error, dict) or error.get("code") != "gateway_timeout":
        return None
    message = error.get("message")
    return message if isinstance(message, str) and message else "Muse gateway timeout"


def _repair_prompt(prompt: str, raw: str, detail: str) -> str:
    return (
        f"{prompt}\n\n"
        "The previous response was not valid JSON for the required schema. "
        "Return only a JSON object that matches the schema.\n"
        f"Previous response:\n{raw}\n"
        f"Error:\n{detail}\n"
    )


def _responses_input(prompt: str, file_ids: Sequence[str]) -> str | list[dict[str, Any]]:
    if not file_ids:
        return prompt
    content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt}]
    for file_id in file_ids:
        content.append({"type": "input_file", "file_id": file_id, "detail": FILE_DETAIL})
    return [{"type": "message", "role": "user", "content": content}]


def _require_file_ids(file_ids: Sequence[str] | None) -> tuple[str, ...]:
    if file_ids is None:
        return ()
    if isinstance(file_ids, (str, bytes)):
        raise TypeError("file_ids must be a sequence of file ids")
    cleaned: list[str] = []
    for file_id in file_ids:
        if not isinstance(file_id, str) or file_id.strip() == "":
            raise ValueError("file_ids must be non-empty strings")
        cleaned.append(file_id.strip())
    return tuple(cleaned)


def _require_upload_id(response: Mapping[str, Any]) -> str:
    file_id = response.get("id")
    if not isinstance(file_id, str) or file_id.strip() == "":
        raise MuseResponseError("Files API response did not include a file id")
    return file_id.strip()


def _cached_upload_id(record: CachedCall, digest: str) -> str | None:
    if record.endpoint != FILES_ENDPOINT:
        return None
    if record.request.get("purpose") != FILE_PURPOSE or record.request.get("sha256") != digest:
        return None
    file_id = record.response.get("id")
    if not isinstance(file_id, str) or file_id.strip() == "":
        return None
    return file_id.strip()


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _require_prompt(prompt: str) -> None:
    if not isinstance(prompt, str) or prompt == "":
        raise ValueError("prompt must be a non-empty string")


def _require_model(response_model: type[BaseModel]) -> None:
    if not isinstance(response_model, type) or not issubclass(response_model, BaseModel):
        raise TypeError("response_model must be a pydantic model")


def _require_effort(effort: str) -> str:
    if effort == "none":
        raise ValueError("reasoning effort 'none' is not supported by Muse Spark")
    if effort not in _EFFORTS:
        raise ValueError(f"reasoning effort must be one of {', '.join(_EFFORTS)}")
    return effort


def _require_sample(sample_idx: int) -> None:
    if type(sample_idx) is not int or sample_idx < 0:
        raise ValueError("sample_idx must be a non-negative integer")
