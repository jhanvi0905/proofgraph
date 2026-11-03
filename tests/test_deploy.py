"""The deploy ships a seed cache, so a fresh instance answers the sample packet with no model call."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from proofgraph.clients import checker as checker_mod
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.review.run import AllDone, run_review

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "examples" / "samples"


class NoNetwork:
    def __init__(self):
        self.calls = []

    def create(self, body):
        self.calls.append(body)
        text = json.dumps(body, default=str)
        raise AssertionError(f"a model call was made: {text[:160]!r} image={'image' in text} chars={len(text)}")


def _manifest():
    return json.loads((SAMPLES / "samples.json").read_text())


def test_the_manifest_names_only_synthetic_files_that_exist():
    manifest = _manifest()
    assert "SYNTHETIC" in manifest["note"] and manifest["samples"]
    for sample in manifest["samples"]:
        assert sample["id"] and sample["title"] and sample["claim"] and sample["files"]
        assert all((SAMPLES / f).is_file() for f in sample["files"])


@pytest.mark.parametrize("graph", ["1", "0"])
def test_a_cache_seeded_from_the_repo_answers_every_sample_without_a_model_call(tmp_path, monkeypatch, graph):
    cache = tmp_path / "cache"
    shutil.copytree(SAMPLES / "seed", cache)
    env = {"MODEL_API_KEY": "k", "CACHE_DIR": str(cache), "SPEND_LIMIT_USD": "5", "PROOFGRAPH_GRAPH": graph}  # a real cap, as on the deploy: at 0 the server refuses even cached answers
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    muse_net, chat_net, image_net = NoNetwork(), NoNetwork(), NoNetwork()  # the blind second reader has its own clients
    monkeypatch.setattr(checker_mod.OpenAIChatTransport, "create", lambda self, body: chat_net.create(body))
    monkeypatch.setattr(checker_mod.OpenAIImageTransport, "create", lambda self, body: image_net.create(body))
    muse = MuseClient(load_settings(env), transport=muse_net)
    for sample in _manifest()["samples"]:
        done = [e for e in run_review(sample["claim"], [SAMPLES / f for f in sample["files"]], muse) if isinstance(e, AllDone)]
        review = done[0].result.review
        banners = [b.text for b in review.banners]
        assert review.status not in ("error", "checking") and not [b for b in review.banners if b.kind == "checker_unavailable"], banners
    assert muse_net.calls == chat_net.calls == image_net.calls == []


def test_the_seed_script_copies_without_overwriting_what_the_disk_already_holds(tmp_path):
    src, dst = tmp_path / "seed", tmp_path / "disk" / "cache"
    (src / "graphs").mkdir(parents=True)
    (src / "a.json").write_text("seed a")
    (src / "graphs" / "g.json").write_text("seed g")
    dst.mkdir(parents=True)
    (dst / "a.json").write_text("kept")
    subprocess.run(["sh", str(ROOT / "docker" / "seed.sh"), str(src), str(dst)], check=True)
    assert (dst / "a.json").read_text() == "kept" and (dst / "graphs" / "g.json").read_text() == "seed g"
    subprocess.run(["sh", str(ROOT / "docker" / "seed.sh"), str(src), str(tmp_path / "new" / "cache")], check=True)
    assert (tmp_path / "new" / "cache" / "a.json").read_text() == "seed a"  # a missing destination is created
