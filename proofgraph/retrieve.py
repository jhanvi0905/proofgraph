"""Retrieve: one atom + a packet's spans -> the top ten candidate spans, for the passes to judge.

There are up to three rankings, fused by reciprocal rank fusion (k = 60).
Ranks are comparable across rankings; raw scores are not.
- sparse: BM25 over a tokeniser that keeps digits, money, policy numbers and
  section references whole;
- dense: cosine over local embeddings, when an embedder is given (cached on
  disk by the model module);
- defined terms: spans holding a defined term that the query names.
Before ranking, spans whose text is a duplicate of another span are dropped.
After fusion, a cap keeps at most six of the ten from one document. No
cross-encoder, no vector database, no model query expansion, and no
hand-written synonyms: a synonym list written after reading the packets tunes
retrieval to answers already known. The query is the atom's own fields.
Meaning-level matches ("retention" ~ "deductible") are the dense ranking's job.
A synonym is added only for a measured miss, with that miss recorded beside it.
"""

from __future__ import annotations

import re
from typing import Callable

from rank_bm25 import BM25Okapi

from proofgraph.schema import Atom, DocumentMappingFile, DocumentRoute, Instrument, RetrievalHit, RetrievalResult, Span, TraceRecord
from proofgraph.trace import Trace

Embed = Callable[[list[str]], "object"]  # returns an (n, d) numpy array, rows L2-normalised

TOP_K = 10
PER_DOC_CAP = 6
RRF_K = 60

_TAG_RE = re.compile(r"</?[A-Z]+>")
_TOKEN_RE = re.compile(
    r"\$?\d[\d,]*(?:\.\d+)?[mk]?"  # money and numbers, kept whole: 1,000,000  $500,000  $10m
    r"|[a-z]{1,3}\d[\w-]*"  # policy-like ids: fd960228, ho-00, gs-212c
    r"|\b[ivx]+\.[a-z]\b|\b\d+\.[a-z]\b"  # section refs: i.b  4.a
    r"|[a-z][a-z'-]+"  # words
)
_STOP = {"the", "of", "and", "or", "a", "an", "to", "in", "on", "for", "is", "are", "be", "by", "this", "that",
         "with", "as", "at", "any", "each", "all", "under", "its", "it", "not", "no"}


def tokenize(text: str) -> list[str]:
    low = _TAG_RE.sub(" ", text).lower()
    out: list[str] = []
    for tok in _TOKEN_RE.findall(low):
        tok = tok.strip(",.")
        if not tok or tok in _STOP:
            continue
        out.append(_fold(tok))
        if "/" in tok or "-" in tok:  # 757/fd960228 also yields fd960228
            out += [_fold(p) for p in re.split(r"[/-]", tok) if p and p not in _STOP]
    return out


def _fold(tok: str) -> str:
    """Light plural folding for words: retentions -> retention, claims -> claim.

    Same rule for query and documents. Words only (numbers and ids untouched),
    longer than four letters, and never -ss (loss, gross) or -us/-is (bonus, basis).
    """
    if tok.isalpha() and len(tok) > 4 and tok.endswith("s") and not tok.endswith(("ss", "us", "is")):
        return tok[:-1]
    return tok


def retrieve(
    atom: Atom,
    instruments: tuple[Instrument, ...],
    trace: Trace,
    embed: Embed | None = None,
) -> RetrievalResult:
    query = _query_terms(atom)
    spans, deduped = _dedupe([sp for inst in instruments for sp in inst.spans])
    by_doc = {sp.span_id: sp.doc_id for sp in spans}

    if not spans:
        result = RetrievalResult(atom_id=atom.atom_id, query_terms=tuple(query), hits=(), candidates=0,
                                 deduped=deduped, capped=0, dense=embed is not None)
        trace.write(TraceRecord(stage="retrieve", packet_id=None, atom_id=atom.atom_id, span_ids=(), model=None,
                                prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
                                verdict=None, rejects=("no candidate spans",), repairs=0, detail=f"query={' '.join(query)}"))
        return result
    docs = [_indexed_text(sp) for sp in spans]
    tokens = [tokenize(d) or ["_"] for d in docs]
    bm25 = BM25Okapi(tokens)
    sparse_scores = bm25.get_scores(query)
    # Rank every span sharing a query term. Not "score > 0": with one or two candidates BM25's
    # IDF is zero or negative, so a positive-score filter would drop an admitted schedule row.
    q = set(query)
    overlap = [i for i in range(len(spans)) if q & set(tokens[i])]
    sparse = _ranks(sorted(overlap, key=lambda i: -sparse_scores[i]))

    dense: dict[int, int] = {}
    if embed is not None:
        import numpy as np

        vecs = embed(docs)
        qv = embed([" ".join(query)])[0]
        sims = np.asarray(vecs) @ np.asarray(qv)
        dense = _ranks(list(np.argsort(-sims)))

    terms = {d.term for inst in instruments for d in inst.definitions}
    named = {t for t in terms if t in " ".join(query)}
    term_list = [i for i, sp in enumerate(spans) if any(t in sp.text.lower() for t in named)]
    term = _ranks(term_list)

    fused = sorted(
        range(len(spans)),
        key=lambda i: -sum(1.0 / (RRF_K + r[i]) for r in (sparse, dense, term) if i in r),
    )
    fused = [i for i in fused if i in sparse or i in dense or i in term]

    hits: list[RetrievalHit] = []
    per_doc: dict[str, int] = {}
    capped = 0
    for i in fused:
        if len(hits) == TOP_K:
            break
        doc = by_doc[spans[i].span_id]
        if per_doc.get(doc, 0) >= PER_DOC_CAP:
            capped += 1
            continue
        per_doc[doc] = per_doc.get(doc, 0) + 1
        sp = spans[i]
        hits.append(RetrievalHit(
            rank=len(hits) + 1, span_id=sp.span_id, doc_id=sp.doc_id, page=sp.page, section_path=sp.section_path,
            bm25_rank=sparse.get(i), dense_rank=dense.get(i), term_rank=term.get(i),
            rrf=round(sum(1.0 / (RRF_K + r[i]) for r in (sparse, dense, term) if i in r), 6),
        ))

    result = RetrievalResult(atom_id=atom.atom_id, query_terms=tuple(query), hits=tuple(hits),
                             candidates=len(spans), deduped=deduped, capped=capped, dense=embed is not None)
    trace.write(TraceRecord(
        stage="retrieve", packet_id=None, atom_id=atom.atom_id, span_ids=tuple(h.span_id for h in hits),
        model=None, prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
        verdict=None, rejects=(), repairs=0,
        detail=f"query={' '.join(query)} candidates={len(spans)} deduped={deduped} capped={capped} dense={embed is not None}",
    ))
    return result


def _query_terms(atom: Atom) -> list[str]:
    parts = [atom.subject, atom.quantity_raw, atom.value, atom.period, atom.conditions]
    if atom.slot:
        parts.append(atom.slot.replace(".", " ").replace("_", " "))
    terms: list[str] = []
    for tok in tokenize(" ".join(p for p in parts if p)):
        if tok not in terms:
            terms.append(tok)
    return terms


def _indexed_text(sp: Span) -> str:
    """What is searched: the span's headings and field label, then its text.

    The label context is searched but never cited. Citations still point at
    the span's own characters.
    """
    context = " ".join(sp.section_path[1:])
    return f"{context}\n{sp.text}" if context else sp.text


def _dedupe(spans: list[Span]) -> tuple[list[Span], int]:
    seen: set[str] = set()
    kept: list[Span] = []
    for sp in spans:
        key = " ".join(sp.text.split()).lower()
        if key in seen:
            continue
        seen.add(key)
        kept.append(sp)
    return kept, len(spans) - len(kept)


def _ranks(order: list[int]) -> dict[int, int]:
    return {int(i): r for r, i in enumerate(order, 1)}


def admit(instruments: tuple[Instrument, ...], mappings: DocumentMappingFile, policy: str,
          src, trace: Trace, extractor: str) -> tuple[tuple[Instrument, ...], tuple[tuple[str, DocumentRoute], ...]]:
    """Passage selection, decided in code: only text inside a scope mapped to `policy` reaches retrieval and the passes.

    A route's citation is its scope: the narrowest range that supports the attribution (a schedule
    row, a "primary carrier" section, or the whole document). Admission tests containment, not
    document membership. A chunk that straddles a scope is clipped to the part inside it, so the
    FD960229 row of a schedule never arrives labelled as FD960228. Each scope is verified against
    the file first; a broken one excludes its document. The model never decides identification.

    On a PDF the scope is a page plus a block of lines, with no offsets. It is found in the
    extracted text, and the passage is clipped to the whole block, never to a phrase inside
    it. The extractor and version that produced the text go in the trace, so the passage can
    be re-derived.
    """
    from proofgraph.checker import verify_citation
    from proofgraph.schema import PageQuote, RawOffsets, span_id_for

    by_doc = {i.doc_id: i for i in instruments}
    admitted: list[Instrument] = []
    routes: list[tuple[str, DocumentRoute]] = []
    excluded: list[str] = []
    for m in mappings.documents:
        route = next((r for r in m.describes if r.policy == policy), None)
        inst = by_doc.get(m.doc_id)
        if route is None or inst is None or verify_citation(route.citation, src, within=inst) is not None:
            continue
        loc = route.citation.locator
        if isinstance(loc, PageQuote):
            block = _clip_to_block(inst, loc.page, route.citation.text)
            if block is None:
                excluded.append(f"{m.doc_id}: scope block not found within one extracted passage on page {loc.page}")
                continue
            admitted.append(inst.model_copy(update={"spans": (block,)}))
            routes.append((m.doc_id, route))
            continue
        assert isinstance(loc, RawOffsets)
        shift = inst.file_start - inst.source_start
        clipped = []
        for sp in inst.spans:
            a = max(sp.start, loc.start - shift)
            b = min(sp.end, loc.end - shift)
            while a < b and sp.text[a - sp.start].isspace():
                a += 1
            while b > a and sp.text[b - 1 - sp.start].isspace():
                b -= 1
            if a >= b:
                continue
            if (a, b) == (sp.start, sp.end):
                clipped.append(sp)
                continue
            text = sp.text[a - sp.start:b - sp.start]
            clipped.append(sp.model_copy(update={
                "start": a, "end": b, "text": text,
                "span_id": span_id_for(sp.doc_id, sp.version, text, a, b), "bbox": None,
            }))
        admitted.append(inst.model_copy(update={"spans": tuple(clipped)}))
        routes.append((m.doc_id, route))
    trace.write(TraceRecord(
        stage="admit", packet_id=None, atom_id=policy, span_ids=tuple(sp.span_id for i in admitted for sp in i.spans),
        model=None, prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False, verdict=None,
        rejects=tuple(excluded), repairs=0,
        detail=f"extractor={extractor} admitted={[i.doc_id for i in admitted]}",
    ))
    return tuple(admitted), tuple(routes)


def _clip_to_block(inst: Instrument, page: int, block: str):
    """The extracted passage on `page` cut to exactly the scope block (whitespace may differ, words may not)."""
    from proofgraph.schema import span_id_for

    words = block.split()
    pat = re.compile(r"\s+".join(re.escape(w) for w in words))
    found = [(sp, m) for sp in inst.spans if sp.page == page for m in pat.finditer(sp.text)]
    if len(found) != 1:
        return None
    sp, m = found[0]
    a, b = sp.start + m.start(), sp.start + m.end()
    text = sp.text[m.start():m.end()]
    return sp.model_copy(update={"start": a, "end": b, "text": text,
                                 "span_id": span_id_for(sp.doc_id, sp.version, text, a, b), "bbox": None})
