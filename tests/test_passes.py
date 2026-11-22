"""Support and attack passes with a fake model: blindness, span checks, quote checks, one repair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.model import ModelReply
from proofgraph.passes import ATTACK_SYSTEM, ATTACK_TEMPLATE, SUPPORT_SYSTEM, SUPPORT_TEMPLATE, attack, locate, support
from proofgraph.retrieve import admit, retrieve
from proofgraph.schema import Atom, DocumentMappingFile, SourceManifest
from proofgraph.trace import memory_trace

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
LABEL = next(s for s in SourceManifest.model_validate_json((ROOT / "data" / "instruments.json").read_text()).sources
             if s.source_id == "gillette_ex10e")
ATOM = Atom(atom_id="t.a0", predicate="states", kind=None, negated=False,
            subject="primary corporate reimbursement retention", slot="FD960228.corp_reimbursement.retention",
            quantity_raw="1,000,000", quantity=None, value=None, period=None, territory=None, basis=None, conditions=None)

pytestmark = pytest.mark.skipif(not (RAW / LABEL.file).exists(), reason="gillette file absent")


@pytest.fixture(scope="module")
def env():
    src = open_source(RAW / LABEL.file)
    mappings = DocumentMappingFile.model_validate_json((ROOT / "data" / "document_mappings.json").read_text())
    insts, routes = admit(ingest(LABEL, RAW).instruments, mappings, "FD960228", src)
    r = retrieve(ATOM, insts, memory_trace())  # bm25 only: no embedding download in tests
    spans = {sp.span_id: sp for i in insts for sp in i.spans}
    return (insts, routes), r, src, spans


def _fake(*replies):
    calls = []

    def complete(prompt, schema, *, system, template, effort="low"):
        calls.append({"prompt": prompt, "system": system, "template": template, "schema": schema})
        return ModelReply(json.dumps(replies[len(calls) - 1]), "fake", "ph", 100, 20, 1, False)

    complete.calls = calls
    return complete


def _span_with(env, needle):
    (insts, routes), r, src, spans = env
    return next(spans[h.span_id] for h in r.hits if needle in spans[h.span_id].text)


def test_support_keeps_a_verbatim_quote_and_cites_it_exactly(env):
    (insts, routes), r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    quote = "$500,000                  Corporate Reimbursement, each loss"
    res = support(ATOM, r, insts, routes, src, memory_trace(), _fake({"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": quote}]}))
    assert not res.failed and len(res.evidence) == 1
    ev = res.evidence[0]
    assert ev.quote.text == quote and ev.citation.text == quote
    assert ev.citation.locator.kind == "raw_offsets"
    assert src.raw_text[ev.citation.locator.start:ev.citation.locator.end] == quote


def test_whitespace_may_differ_but_characters_may_not(env):
    sp = _span_with(env, "Corporate Reimbursement")
    assert locate("$500,000 Corporate Reimbursement, each loss", sp.text) is not None  # collapsed spaces: found
    assert locate("$500,000 Corporate Reimbursement each loss", sp.text) is None  # dropped comma: not found


def test_span_outside_the_input_is_a_hard_failure_with_no_repair(env):
    (insts, routes), r, src, spans = env
    outside = next(sid for sid in spans if sid not in {h.span_id for h in r.hits})
    fake = _fake({"evidence": [{"span_id": outside, "reading": "r", "quote": "x"}]})
    res = attack(ATOM, r, insts, routes, src, memory_trace(), fake)
    assert res.failed and res.evidence == () and len(fake.calls) == 1 and res.repairs == 0


def test_paraphrased_quote_gets_one_repair_then_succeeds(env):
    (insts, routes), r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    fake = _fake({"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "a half-million corporate retention"}]},
                 {"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "$500,000"}]})
    res = attack(ATOM, r, insts, routes, src, memory_trace(), fake)
    assert not res.failed and res.repairs == 1 and res.rejects == 1
    assert "does not occur exactly once" in fake.calls[1]["prompt"]


def test_two_bad_attempts_fail_the_pass(env):
    (insts, routes), r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    bad = {"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "not in the text"}]}
    res = support(ATOM, r, insts, routes, src, memory_trace(), _fake(bad, bad))
    assert res.failed and res.evidence == () and res.repairs == 1


def test_attack_is_blind_to_support(env):
    (insts, routes), r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    marker = "SUPPORT-READING-7f3a"
    sup_fake = _fake({"evidence": [{"span_id": sp.span_id, "reading": marker, "quote": "$500,000"}]})
    support(ATOM, r, insts, routes, src, memory_trace(), sup_fake)
    att_fake = _fake({"evidence": []})
    attack(ATOM, r, insts, routes, src, memory_trace(), att_fake)
    call = att_fake.calls[0]
    assert marker not in call["prompt"] and marker not in call["system"]
    assert call["system"] == ATTACK_SYSTEM and call["template"] == ATTACK_TEMPLATE


def test_two_separate_prompts_neither_mentions_the_other():
    assert SUPPORT_SYSTEM != ATTACK_SYSTEM and SUPPORT_TEMPLATE != ATTACK_TEMPLATE
    for text in (ATTACK_SYSTEM, ATTACK_TEMPLATE):
        assert "support pass" not in text.lower() and "supporting evidence" not in text.lower()


def test_span_ids_are_constrained_in_the_schema(env):
    (insts, routes), r, src, spans = env
    fake = _fake({"evidence": []})
    support(ATOM, r, insts, routes, src, memory_trace(), fake)
    enum = fake.calls[0]["schema"]["properties"]["evidence"]["items"]["properties"]["span_id"]["enum"]
    assert enum == [h.span_id for h in r.hits]


# ---- guard counterfactuals: what gets through without each guard


def test_span_id_guard_counterfactual(env):
    """Without the span-id check, a citation to a passage the model was never shown would pass:
    the span is real, so the file verifier accepts it. Only the span-id check stops it."""
    from proofgraph.checker import verify_citation
    from proofgraph.passes import _cite

    (insts, routes), r, src, spans = env
    shown = {h.span_id for h in r.hits}
    packet = ingest(LABEL, RAW).instruments  # any real passage in the packet that the model was not shown
    outside = next(sp for i in packet for sp in i.spans if sp.span_id not in shown and "$" in sp.text)
    inst = next(i for i in packet if i.doc_id == outside.doc_id)
    unguarded = _cite(outside, inst, 0, len(outside.text), src)
    assert verify_citation(unguarded, src, within=inst) is None  # the verifier alone lets it through
    res = support(ATOM, r, insts, routes, src, memory_trace(),
                  _fake({"evidence": [{"span_id": outside.span_id, "reading": "r", "quote": outside.text}]}))
    assert res.failed and res.evidence == ()  # the guard does not


def test_exactly_once_guard_counterfactual(env):
    """Without the exactly-once rule, an ambiguous quote cites the wrong figure. In Reliance's block
    "$0" appears twice (each D&O, then all D&O); a plain find takes the first, whichever was meant."""
    sp = _span_with(env, "Corporate Reimbursement")
    assert sp.text.count("$0") == 2
    first = sp.text.find("$0")
    assert "Each Director" in sp.text[first:first + 70]  # what an unguarded locator would cite
    assert locate("$0", sp.text) is None  # the guard refuses to choose



# ---- admission: identification is decided in code, per document


def test_admission_takes_exactly_the_documents_mapped_to_the_policy(env):
    (insts, routes), r, src, spans = env
    assert {i.doc_id for i in insts} == {"london_fd960228", "london_fd960229", "coda_end13",
                                          "reliance_binder", "ace_binder", "cna_binder"}
    assert {d for d, _ in routes} == {i.doc_id for i in insts}
    assert {h.doc_id for h in r.hits} <= {i.doc_id for i in insts}


def test_identification_strength_rides_on_every_piece_of_evidence(env):
    (insts, routes), r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    res = attack(ATOM, r, insts, routes, src, memory_trace(),
                 _fake({"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "$500,000"}]}))
    ev = res.evidence[0]
    assert ev.doc_id == "reliance_binder" and ev.identification.strength.value == "judgment"
    assert ev.identification.reasoning


def test_the_prompt_shows_identification_and_strength(env):
    (insts, routes), r, src, spans = env
    fake = _fake({"evidence": []})
    support(ATOM, r, insts, routes, src, memory_trace(), fake)
    prompt = fake.calls[0]["prompt"]
    assert "describes FD960228; identification: judgment" in prompt
    assert "do not re-decide it" in prompt


def test_a_passage_from_an_unadmitted_document_never_reaches_the_model(env):
    (insts, routes), r, src, spans = env
    fake = _fake({"evidence": []})
    res = support(ATOM, r, insts, routes[:1], src, memory_trace(), fake)  # drop most identifications
    assert res.failed and fake.calls == []


def test_a_broken_identification_citation_excludes_its_document():
    from proofgraph.ingest import ingest

    src = open_source(RAW / LABEL.file)
    m = DocumentMappingFile.model_validate_json((ROOT / "data" / "document_mappings.json").read_text())
    docs = tuple(d if d.doc_id != "cna_binder" else d.model_copy(update={"describes": tuple(
        rt.model_copy(update={"citation": rt.citation.model_copy(update={"text": "X" * len(rt.citation.text)})})
        for rt in d.describes)}) for d in m.documents)
    insts, _ = admit(ingest(LABEL, RAW).instruments, m.model_copy(update={"documents": docs}), "FD960228", src)
    assert "cna_binder" not in {i.doc_id for i in insts}


# ---- scopes: admission tests containment, not document membership


def _norm(t):
    return " ".join(t.split())


def test_every_admitted_passage_lies_inside_its_scope(env):
    (insts, routes), r, src, spans = env
    scope = {d: rt.citation.locator for d, rt in routes}
    for inst in insts:
        shift = inst.file_start - inst.source_start
        for sp in inst.spans:
            loc = scope[inst.doc_id]
            assert loc.start <= shift + sp.start and shift + sp.end <= loc.end, (inst.doc_id, sp.text[:40])


def test_the_fd960229_row_of_the_schedule_is_not_admitted_as_fd960228(env):
    (insts, routes), r, src, spans = env
    item7 = next(i for i in insts if i.doc_id == "coda_end13")
    text = _norm(" ".join(sp.text for sp in item7.spans))
    assert "757/FD960228" in text
    for other in ("757/FD960229", "81385411B", "DOX132034203", "752034765-96"):
        assert other not in text


def test_a_binders_own_terms_are_not_admitted_as_the_primarys(env):
    (insts, routes), r, src, spans = env
    text = {i.doc_id: _norm(" ".join(sp.text for sp in i.spans)) for i in insts}
    assert "$10,000,000 Aggregate each policy period" not in text["reliance_binder"]  # Reliance's own limit
    assert "$500,000 Corporate Reimbursement, each loss" in text["reliance_binder"]  # what it says of the primary
    assert "GS-8099D" not in text["ace_binder"] and "($0/$0/$1M)" in text["ace_binder"]
    assert "FD960229" not in text["london_fd960229"]  # the cover note's own policy stays out
