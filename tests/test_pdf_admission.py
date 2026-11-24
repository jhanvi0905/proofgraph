"""PDF scopes: page + block, no offsets. Admission clips to the whole block; evidence cites whole lines."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofgraph.checker import open_source, verify_citation
from proofgraph.ingest import ingest
from proofgraph.model import ModelReply
from proofgraph.passes import support
from proofgraph.retrieve import admit, retrieve
from proofgraph.schema import Atom, DocumentMappingFile, SourceManifest
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
HO = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
          if s.source_id == "iso_ho0003_0491")
BLOCK = "$200 on money, bank notes, bullion, gold other\nthan goldware, silver other than silverware, plati-\nnum, coins and medals."
ATOM = Atom(atom_id="m.a0", predicate="states", kind=None, negated=False, subject="special limit on money",
            slot=None, quantity_raw="$200", quantity=None, value=None, period=None, territory=None, basis=None, conditions=None)

pytestmark = pytest.mark.skipif(not (RAW / HO.file).exists(), reason="ISO file absent")


def _mappings(block=BLOCK, page=2):
    # a test fixture, not family B data: one scope on the special-limits block
    return DocumentMappingFile.model_validate_json(json.dumps({"note": "test", "documents": [{"doc_id": "ho_00_03", "describes": [{
        "policy": "HO-00-03", "method": "label", "strength": "read", "reasoning": None,
        "citation": {"source_file": HO.file, "sha256_of_file": HO.sha256_of_file,
                     "locator": {"kind": "page_quote", "page": page}, "text": block}}]}]}))


@pytest.fixture(scope="module")
def env():
    res = ingest(HO, RAW)
    return res, open_source(RAW / HO.file)


def test_the_scope_block_verifies_on_the_page_with_no_offsets(env):
    res, src = env
    c = _mappings().documents[0].describes[0].citation
    assert c.locator.kind == "page_quote" and not hasattr(c.locator, "start")
    assert verify_citation(c, src, within=res.instruments[0]) is None


def test_admission_clips_to_the_whole_block_not_a_phrase(env):
    res, src = env
    trace = memory_trace()
    insts, routes = admit(res.instruments, _mappings(), "HO-00-03", src, trace, res.source.extractor)
    [inst] = insts
    [passage] = inst.spans
    assert " ".join(passage.text.split()) == " ".join(BLOCK.split())  # the modifiers survive
    assert "coins and medals" in passage.text


def test_the_trace_records_the_extractor_that_produced_the_text(env):
    res, src = env
    trace = memory_trace()
    admit(res.instruments, _mappings(), "HO-00-03", src, trace, res.source.extractor)
    rec = next(r for r in trace.records if r.stage == "admit")
    assert f"extractor={res.source.extractor}" in rec.detail and "pdf_columns/v1" in rec.detail


def test_a_block_not_on_its_page_is_excluded_loudly(env):
    res, src = env
    trace = memory_trace()
    insts, _ = admit(res.instruments, _mappings(page=3), "HO-00-03", src, trace, res.source.extractor)
    assert insts == ()


def test_pdf_evidence_cites_whole_lines_and_verifies(env):
    res, src = env
    insts, routes = admit(res.instruments, _mappings(), "HO-00-03", src, memory_trace(), res.source.extractor)
    r = retrieve(ATOM, insts, memory_trace())
    [hit] = r.hits

    def fake(prompt, schema, *, system, template, effort="low"):
        return ModelReply(json.dumps({"evidence": [{"span_id": hit.span_id, "reading": "r", "quote": "$200", "value": "$200"}]}),
                          "fake", "ph", 1, 1, 1, False)

    out = support(ATOM, r, insts, routes, src, memory_trace(), fake)
    assert not out.failed, out.errors
    [ev] = out.evidence
    assert ev.quote.text == "$200"  # what the model pointed at
    assert ev.citation.text.split("\n")[0] == "$200 on money, bank notes, bullion, gold other"  # what is cited: the whole line
    assert verify_citation(ev.citation, src) is None


def test_retrieval_over_a_single_admitted_passage_finds_it(env):
    """BM25 IDF is <= 0 with one candidate; a positive-score filter used to drop it."""
    res, src = env
    insts, _ = admit(res.instruments, _mappings(), "HO-00-03", src, memory_trace(), res.source.extractor)
    r = retrieve(ATOM, insts, memory_trace())
    assert len(r.hits) == 1 and r.hits[0].bm25_rank == 1


def test_retrieval_over_no_passages_is_empty_not_an_error():
    r = retrieve(ATOM, (), memory_trace())
    assert r.hits == () and r.candidates == 0


def test_a_multi_item_block_admits_each_item_inside_it_and_nothing_else():
    """Ingest splits a numbered list at each item; a block scope must be matched across those chunks."""
    fb = DocumentMappingFile.model_validate_json((ROOT / "data" / "family_b" / "document_mappings.json").read_text())
    for src_id, doc, first_items in (("iso_ho0003_0491", "ho_00_03", ["1.", "2.", "3.", "4.", "5.", "6.", "7."]),
                                     ("iso_ho0015_0491", "ho_00_15", ["5.", "6.", "7."])):
        label = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
                     if s.source_id == src_id)
        if not (RAW / label.file).exists():
            pytest.skip(f"{label.file} absent")
        res = ingest(label, RAW)
        insts, _ = admit(res.instruments, fb, "SPECIMEN-HO3", open_source(RAW / label.file), memory_trace(), res.source.extractor)
        [inst] = insts
        assert [sp.text.split()[0] for sp in inst.spans] == first_items, doc
        assert all(sp.page == 2 for sp in inst.spans)
