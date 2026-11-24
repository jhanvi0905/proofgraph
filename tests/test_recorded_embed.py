"""Recorded embedding vectors: a replay of the worked examples never loads the embedding model."""
import hashlib
import sys

import numpy as np

import proofgraph.model as M


def test_recorded_vector_is_used_without_loading_the_model(tmp_path, monkeypatch):
    name = f'{M.EMBED_MODEL.replace("/", "__")}@{M.EMBED_REVISION[:12]}'
    text = "a passage the worked examples retrieve"
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
    (tmp_path / "rec" / name).mkdir(parents=True)
    vec = np.arange(4, dtype="float32")
    np.save(tmp_path / "rec" / name / f"{key}.npy", vec)
    monkeypatch.setattr(M, "RECORDED_EMBED", tmp_path / "rec")
    monkeypatch.setattr(M, "EMBED_CACHE", tmp_path / "cache")
    monkeypatch.setattr(M, "_encoder", None)
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)  # any attempt to load the model fails
    assert np.array_equal(M.embed([text])[0], vec)


def test_every_recorded_vector_is_named_by_its_key():
    name = f'{M.EMBED_MODEL.replace("/", "__")}@{M.EMBED_REVISION[:12]}'
    files = list((M.RECORDED_EMBED / name).glob("*.npy"))
    assert files, "the worked examples' vectors are recorded"
    for f in files:
        v = np.load(f)
        assert len(f.stem) == 24 and v.dtype == np.float32 and abs(float(np.linalg.norm(v)) - 1) < 1e-4
