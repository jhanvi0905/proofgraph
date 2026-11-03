"""The deploy warms the sample packet once, on the machine it runs on, so the cache key matches that machine.

A seed built on another platform cannot be shipped: the cache key of a scanned page's transcription depends on
the rendered pixels, which differ between a Mac and Linux, and every legal pack has a scan. So the container
runs the sample itself on first start (`app/warm.py`) and leaves a marker on the persistent disk.
"""

import json
import shutil
from pathlib import Path

from test_review_run import CLAIM, GOOD, PDF, SPLIT1, FakeTransport, _muse

from app.warm import marker_for, warm

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples" / "samples"


def _manifest(tmp_path) -> Path:
    shutil.copy(PDF, tmp_path / "packet.pdf")
    path = tmp_path / "samples.json"
    path.write_text(json.dumps({"note": "SYNTHETIC test packet", "samples": [
        {"id": "t1", "title": "t", "claim": CLAIM, "files": ["packet.pdf"]}]}))
    return path


def test_the_shipped_manifest_names_only_synthetic_files_that_exist():
    manifest = json.loads((SAMPLES / "samples.json").read_text())
    assert "SYNTHETIC" in manifest["note"] and manifest["samples"]
    for sample in manifest["samples"]:
        assert sample["id"] and sample["title"] and sample["claim"] and sample["files"]
        assert all((SAMPLES / f).is_file() for f in sample["files"])


def test_warming_runs_each_sample_once_and_leaves_a_marker(tmp_path):
    manifest, cache = _manifest(tmp_path), tmp_path / "cache"
    transport = FakeTransport(SPLIT1, GOOD)
    assert warm(manifest, cache, _muse(tmp_path / "m", transport)) == 1
    assert len(transport.bodies) == 2 and marker_for(manifest, cache).is_file()


def test_an_existing_marker_means_no_model_call(tmp_path):
    manifest, cache = _manifest(tmp_path), tmp_path / "cache"
    warm(manifest, cache, _muse(tmp_path / "m", FakeTransport(SPLIT1, GOOD)))
    again = FakeTransport()  # any call would pop from an empty list
    assert warm(manifest, cache, _muse(tmp_path / "m2", again)) == 0 and again.bodies == []


def test_a_failed_warm_up_leaves_no_marker_so_the_next_start_tries_again(tmp_path):
    manifest, cache = _manifest(tmp_path), tmp_path / "cache"

    class Down:
        def create(self, body):
            raise RuntimeError("down")

    assert warm(manifest, cache, _muse(tmp_path / "m", Down())) == 0
    assert not marker_for(manifest, cache).exists()


def test_the_marker_changes_with_the_manifest_and_the_graph_flag(tmp_path, monkeypatch):
    manifest, cache = _manifest(tmp_path), tmp_path / "cache"
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    on = marker_for(manifest, cache)
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "0")
    assert marker_for(manifest, cache) != on
    monkeypatch.setenv("PROOFGRAPH_GRAPH", "1")
    manifest.write_text(manifest.read_text().replace("t1", "t2"))
    assert marker_for(manifest, cache) != on
