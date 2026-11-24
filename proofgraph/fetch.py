"""Fetch: download each source from its pinned URL and refuse it unless its sha256 matches.

Sources are never copied into the repository. A file already present with the
right hash is kept. A download with the wrong hash is deleted and reported, so a
changed upstream file can never pass silently as the one the labels describe.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from proofgraph.schema import SourceManifest


@dataclass(frozen=True)
class Fetched:
    source_id: str
    path: Path
    status: str  # "present", "downloaded", "missing", "hash_mismatch", "error"
    detail: str


def fetch_sources(manifest: SourceManifest, raw_dir: Path) -> list[Fetched]:
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for src in manifest.sources:
        path = raw_dir / src.file
        if path.exists() and _sha(path.read_bytes()) == src.sha256_of_file:
            out.append(Fetched(src.source_id, path, "present", "hash matches"))
            continue
        if path.exists():
            out.append(Fetched(src.source_id, path, "hash_mismatch", f"existing file hashes {_sha(path.read_bytes())[:12]}, expected {src.sha256_of_file[:12]}"))
            continue
        if src.url is None:
            out.append(Fetched(src.source_id, path, "missing", src.fetch_note))
            continue
        try:
            data = _download(src.url)
        except Exception as exc:  # network, HTTP or missing user agent: report, never guess
            out.append(Fetched(src.source_id, path, "error", f"{type(exc).__name__}: {exc}. {src.fetch_note}"))
            continue
        digest = _sha(data)
        if digest != src.sha256_of_file:
            out.append(Fetched(src.source_id, path, "hash_mismatch", f"downloaded file hashes {digest[:12]}, expected {src.sha256_of_file[:12]}; not saved"))
            continue
        path.write_bytes(data)
        out.append(Fetched(src.source_id, path, "downloaded", f"{len(data):,} bytes, hash matches"))
    return out


def _download(url: str) -> bytes:
    agent = "proofgraph-fetch/2.0"
    if "sec.gov" in url:
        agent = os.environ.get("SEC_USER_AGENT", "")
        if not agent:
            raise RuntimeError("SEC_USER_AGENT is not set")
    req = urllib.request.Request(url, headers={"User-Agent": agent})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
