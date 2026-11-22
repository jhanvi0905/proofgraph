"""Fetch: pinned URL, pinned hash; a wrong hash is never saved. Uses file:// URLs, no network."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from proofgraph.fetch import fetch_sources
from proofgraph.schema import SourceManifest


def _manifest(url, sha, file="doc.txt"):
    return SourceManifest.model_validate_json(json.dumps({"note": "t", "sources": [{
        "source_id": "s", "file": file, "url": url, "fetch_note": "get it by hand", "sha256_of_file": sha,
        "extractor": "edgar_sgml", "edgar_type": None, "edgar_sequence": None, "instruments": []}]}))


def test_download_with_matching_hash_is_saved(tmp_path: Path):
    src = tmp_path / "upstream.txt"
    src.write_bytes(b"the document")
    sha = hashlib.sha256(b"the document").hexdigest()
    [r] = fetch_sources(_manifest(src.as_uri(), sha), tmp_path / "raw")
    assert r.status == "downloaded" and (tmp_path / "raw" / "doc.txt").read_bytes() == b"the document"
    [again] = fetch_sources(_manifest(src.as_uri(), sha), tmp_path / "raw")
    assert again.status == "present"


def test_download_with_wrong_hash_is_not_saved(tmp_path: Path):
    src = tmp_path / "upstream.txt"
    src.write_bytes(b"a changed document")
    [r] = fetch_sources(_manifest(src.as_uri(), "0" * 64), tmp_path / "raw")
    assert r.status == "hash_mismatch" and not (tmp_path / "raw" / "doc.txt").exists()


def test_source_without_url_says_how_to_get_it(tmp_path: Path):
    [r] = fetch_sources(_manifest(None, "0" * 64), tmp_path / "raw")
    assert r.status == "missing" and r.detail == "get it by hand"


def test_sec_requires_a_user_agent(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SEC_USER_AGENT", raising=False)
    [r] = fetch_sources(_manifest("https://www.sec.gov/x.txt", "0" * 64), tmp_path / "raw")
    assert r.status == "error" and "SEC_USER_AGENT" in r.detail
