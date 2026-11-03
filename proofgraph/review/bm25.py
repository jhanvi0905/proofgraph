"""Plain-Python BM25 to break ties between equally strong paths. No library, no embeddings."""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence

K1, B = 1.5, 0.75
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset("the a an of to and or in on for by with is are be shall may must not any that this as at it".split())


def tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.casefold()) if t not in _STOP]


def bm25_scores(query: str, docs: Sequence[str]) -> list[float]:
    """Score each document against the query; the corpus is the documents given."""
    toks = [tokens(d) for d in docs]
    q = set(tokens(query))
    if not docs or not q:
        return [0.0] * len(docs)
    avg = sum(map(len, toks)) / len(toks) or 1.0
    df = Counter(t for ts in toks for t in set(ts) & q)
    out = []
    for ts in toks:
        tf = Counter(ts)
        score = 0.0
        for t in q & tf.keys():
            idf = math.log(1 + (len(docs) - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (K1 + 1) / (tf[t] + K1 * (1 - B + B * len(ts) / avg))
        out.append(score)
    return out
