"""The only file that imports a model SDK.

complete_json(prompt, schema) is used for generation: Anthropic, with structured
output enforced by a JSON schema. embed(texts) is local: a sentence-transformers
model, every vector cached on disk keyed by (model name, text hash). No hosted
embedding API and no second key. The weights are downloaded once from Hugging
Face, and after that everything runs locally.

Sampling: current Claude models reject `temperature` (HTTP 400), so "temperature
zero" is not available. Reproducibility comes from two things instead. The
prompt template is frozen (its hash goes in the trace). Every response is cached
on disk, keyed by (model, system, prompt, schema), so a rerun replays the exact
output. The trace marks cache hits, so cost per packet counts only real calls.

Refusal fallback: server-side fallbacks are on ("default"). The served model goes
in the trace, so a fallback-served answer is visible and never silent.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

MODEL = os.environ.get("PROOFGRAPH_MODEL", "claude-opus-5-5")
CACHE_DIR = Path(os.environ.get("PROOFGRAPH_CACHE", Path(__file__).resolve().parent.parent / "cache" / "model"))
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
EMBED_MODEL = os.environ.get("PROOFGRAPH_EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_CACHE = CACHE_DIR.parent / "embed"
_encoder = None


@dataclass(frozen=True)
class ModelReply:
    text: str  # the JSON text the model returned; caller validates it
    model: str  # model that actually served the call
    prompt_hash: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cache_hit: bool


class ModelRefused(RuntimeError):
    pass


def prompt_hash(template: str, model: str = MODEL) -> str:
    """Hash of the exact prompt template plus model name: tells you whether the prompt changed."""
    return hashlib.sha256(f"{model}\x1f{template}".encode()).hexdigest()[:16]


def complete_json(prompt: str, schema: dict, *, system: str, template: str, effort: str = "low") -> ModelReply:
    key_src = json.dumps([MODEL, system, prompt, schema, effort], sort_keys=True)
    key = hashlib.sha256(key_src.encode()).hexdigest()
    path = CACHE_DIR / f"{key}.json"
    ph = prompt_hash(template)
    if path.exists():
        c = json.loads(path.read_text(encoding="utf-8"))
        return ModelReply(c["text"], c["model"], ph, c["input_tokens"], c["output_tokens"], 0, True)

    import anthropic

    client = anthropic.Anthropic()
    t0 = time.monotonic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        betas=[_FALLBACK_BETA],
        fallbacks="default",
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    latency = int((time.monotonic() - t0) * 1000)
    if response.stop_reason == "refusal":
        raise ModelRefused(f"refused: {getattr(response.stop_details, 'category', None)}")
    text = next(b.text for b in response.content if b.type == "text")
    reply = ModelReply(
        text=text,
        model=response.model,
        prompt_hash=ph,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency,
        cache_hit=False,
    )
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"text": text, "model": reply.model, "input_tokens": reply.input_tokens,
                                "output_tokens": reply.output_tokens}, sort_keys=True), encoding="utf-8")
    return reply


def embed(texts: list[str]):
    """L2-normalised vectors, one row per text, as an (n, d) float32 numpy array.

    Each vector is cached at cache/embed/<model>/<sha256(text)[:24]>.npy, so the
    same text under the same model is never recomputed.
    """
    import numpy as np

    folder = EMBED_CACHE / EMBED_MODEL.replace("/", "__")
    folder.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha256(t.encode("utf-8")).hexdigest()[:24] for t in texts]
    out: list = [None] * len(texts)
    missing = []
    for i, k in enumerate(keys):
        f = folder / f"{k}.npy"
        if f.exists():
            out[i] = np.load(f)
        else:
            missing.append(i)
    if missing:
        global _encoder
        if _encoder is None:
            from sentence_transformers import SentenceTransformer

            # CPU, not Apple MPS: torch 2.15's MPS backend crashes on macOS 14.4
            # (MPSNDArray arrayViewWithShape:strides: unrecognized selector). CPU is
            # also deterministic, which the embedding cache relies on.
            _encoder = SentenceTransformer(EMBED_MODEL, device="cpu")
        vecs = _encoder.encode([texts[i] for i in missing], normalize_embeddings=True, convert_to_numpy=True)
        for i, v in zip(missing, vecs):
            v = v.astype("float32")
            np.save(folder / f"{keys[i]}.npy", v)
            out[i] = v
    return np.stack(out)
