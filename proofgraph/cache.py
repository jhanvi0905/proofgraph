"""JSON disk cache for model calls.

The key is sha256(model, endpoint, prompt, schema, inputs, sample_idx), as
docs/03-architecture.md specifies. The hashed bytes are canonical JSON of those
six fields, with sorted keys and no extra whitespace.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

_KEY = re.compile(r"^[0-9a-f]{64}$")


class CacheError(Exception):
    """A cache entry exists but cannot be used."""


class CachedCall(BaseModel):
    """Provenance for one model call: the request that was sent and the response."""

    model_config = ConfigDict(extra="forbid")

    key: str
    endpoint: str
    request: dict[str, Any]
    response: dict[str, Any]


def cache_key(
    *,
    model: str,
    endpoint: str,
    prompt: str,
    schema: object,
    inputs: object,
    sample_idx: int,
) -> str:
    """Explicit cache key. Field order in ``schema`` or ``inputs`` does not change it."""

    payload = {
        "model": model,
        "endpoint": endpoint,
        "prompt": prompt,
        "schema": schema,
        "inputs": inputs,
        "sample_idx": sample_idx,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class DiskCache:
    """One JSON file per call under the cache directory."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, key: str) -> Path:
        _require_key(key)
        return self.directory / f"{key}.json"

    def get(self, key: str) -> CachedCall | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        try:
            record = CachedCall.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise CacheError(f"cache entry {key} is unreadable") from exc
        if record.key != key:
            raise CacheError(f"cache entry {key} does not match its filename")
        return record

    def put(self, record: CachedCall) -> None:
        path = self.path_for(record.key)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.directory / f".{record.key}.tmp"
        temporary.write_text(record.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)

    def delete(self, key: str) -> None:
        """Drop an entry. A failed or invalid response must not stay a hit."""

        self.path_for(key).unlink(missing_ok=True)


def _require_key(key: str) -> None:
    if _KEY.fullmatch(key) is None:
        raise CacheError(f"refusing cache key {key!r}")
