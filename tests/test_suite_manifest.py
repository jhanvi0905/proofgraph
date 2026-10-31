"""R-30: the suite manifest and the local-copy fetch script. Nothing is downloaded."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "download_data.sh"
MANIFEST = ROOT / "examples" / "suite" / "manifest.json"

CASE_FIELDS = {"id", "claim", "source_dataset", "citation", "split", "licence_status", "files"}
FILE_FIELDS = {"name", "path", "sha256"}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fake_dataset(tmp_path: Path, content: bytes = b"evidence bytes"):
    dataset = tmp_path / "Dataset"
    (dataset / "sub").mkdir(parents=True)
    (dataset / "sub" / " lead space.pdf").write_bytes(content)
    manifest = {
        "cases": [
            {
                "id": "TC99",
                "files": [
                    {"name": " lead space.pdf", "path": "sub/ lead space.pdf", "sha256": _sha(b"evidence bytes")}
                ],
            }
        ]
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    return dataset, manifest_path


def _run(dataset: Path, manifest: Path, dest: Path):
    env = {**os.environ, "SUITE_MANIFEST": str(manifest), "SUITE_DEST": str(dest)}
    return subprocess.run(
        ["bash", str(SCRIPT), "--suite", str(dataset)],
        env=env,
        capture_output=True,
        text=True,
    )


def test_hash_mismatch_aborts(tmp_path):
    dataset, manifest = _fake_dataset(tmp_path, content=b"tampered bytes")
    dest = tmp_path / "out"
    result = _run(dataset, manifest, dest)
    assert result.returncode != 0
    assert "sha256 mismatch" in result.stderr
    assert not (dest / "TC99" / " lead space.pdf").exists()


def test_matching_hash_copies_file(tmp_path):
    dataset, manifest = _fake_dataset(tmp_path)
    dest = tmp_path / "out"
    result = _run(dataset, manifest, dest)
    assert result.returncode == 0, result.stderr
    assert (dest / "TC99" / " lead space.pdf").read_bytes() == b"evidence bytes"


def test_missing_source_file_aborts(tmp_path):
    dataset, manifest = _fake_dataset(tmp_path)
    (dataset / "sub" / " lead space.pdf").unlink()
    result = _run(dataset, manifest, tmp_path / "out")
    assert result.returncode != 0
    assert "missing" in result.stderr


def test_missing_dataset_dir_aborts(tmp_path):
    _, manifest = _fake_dataset(tmp_path)
    result = _run(tmp_path / "nope", manifest, tmp_path / "out")
    assert result.returncode != 0


def test_committed_manifest_shape():
    cases = json.loads(MANIFEST.read_text())["cases"]
    assert len(cases) == 21
    assert len({c["id"] for c in cases}) == 21
    for case in cases:
        assert CASE_FIELDS <= case.keys(), case["id"]
        assert case["claim"] and case["citation"]
        assert case["split"] in {"dev", "heldout"}
        assert case["files"], case["id"]
        for f in case["files"]:
            assert FILE_FIELDS <= f.keys()
            assert len(f["sha256"]) == 64 and int(f["sha256"], 16) >= 0


def test_committed_manifest_split_and_groups():
    cases = {c["id"]: c for c in json.loads(MANIFEST.read_text())["cases"]}
    dev = {i for i, c in cases.items() if c["split"] == "dev"}
    assert dev == {"TC17", "TC18", "TC20", "TC22", "TC25", "TC37", "TC40"}
    # Source-overlap groups stay inside one split.
    by_group: dict[str, set[str]] = {}
    for c in cases.values():
        by_group.setdefault(c["source_group"], set()).add(c["split"])
    assert all(len(splits) == 1 for splits in by_group.values())


def test_pointer_sources_are_not_committed():
    committed = {p.name for p in (ROOT / "examples" / "suite").rglob("*") if p.is_file()}
    assert committed == {"manifest.json"}
    pointer = {"ContractNLI", "Tobacco800 (YACCLAB-packaged version)", "Company Documents (Kaggle archive (3).zip)"}
    for case in json.loads(MANIFEST.read_text())["cases"]:
        if case["source_dataset"] in pointer:
            assert case["licence_status"].startswith("pointer only")
