"""Support and attack passes with a fake model: blindness, span checks, quote checks, one repair."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.model import ModelReply
from proofgraph.passes import ATTACK_SYSTEM, ATTACK_TEMPLATE, SUPPORT_SYSTEM, SUPPORT_TEMPLATE, attack, locate, support
from proofgraph.retrieve import retrieve
from proofgraph.schema import Atom, SourceManifest
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
    insts = ingest(LABEL, RAW).instruments
    r = retrieve(ATOM, insts, memory_trace())  # bm25 only: no embedding download in tests
    spans = {sp.span_id: sp for i in insts for sp in i.spans}
    return insts, r, open_source(RAW / LABEL.file), spans


def _fake(*replies):
    calls = []

    def complete(prompt, schema, *, system, template, effort="low"):
        calls.append({"prompt": prompt, "system": system, "template": template, "schema": schema})
        return ModelReply(json.dumps(replies[len(calls) - 1]), "fake", "ph", 100, 20, 1, False)

    complete.calls = calls
    return complete


def _span_with(env, needle):
    insts, r, src, spans = env
    return next(spans[h.span_id] for h in r.hits if needle in spans[h.span_id].text)


def test_support_keeps_a_verbatim_quote_and_cites_it_exactly(env):
    insts, r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    quote = "$500,000                  Corporate Reimbursement, each loss"
    res = support(ATOM, r, insts, src, memory_trace(), _fake({"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": quote}]}))
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
    insts, r, src, spans = env
    outside = next(sid for sid in spans if sid not in {h.span_id for h in r.hits})
    fake = _fake({"evidence": [{"span_id": outside, "reading": "r", "quote": "x"}]})
    res = attack(ATOM, r, insts, src, memory_trace(), fake)
    assert res.failed and res.evidence == () and len(fake.calls) == 1 and res.repairs == 0


def test_paraphrased_quote_gets_one_repair_then_succeeds(env):
    insts, r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    fake = _fake({"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "a half-million corporate retention"}]},
                 {"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "$500,000"}]})
    res = attack(ATOM, r, insts, src, memory_trace(), fake)
    assert not res.failed and res.repairs == 1 and res.rejects == 1
    assert "does not occur exactly once" in fake.calls[1]["prompt"]


def test_two_bad_attempts_fail_the_pass(env):
    insts, r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    bad = {"evidence": [{"span_id": sp.span_id, "reading": "r", "quote": "not in the text"}]}
    res = support(ATOM, r, insts, src, memory_trace(), _fake(bad, bad))
    assert res.failed and res.evidence == () and res.repairs == 1


def test_attack_is_blind_to_support(env):
    insts, r, src, spans = env
    sp = _span_with(env, "Corporate Reimbursement")
    marker = "SUPPORT-READING-7f3a"
    sup_fake = _fake({"evidence": [{"span_id": sp.span_id, "reading": marker, "quote": "$500,000"}]})
    support(ATOM, r, insts, src, memory_trace(), sup_fake)
    att_fake = _fake({"evidence": []})
    attack(ATOM, r, insts, src, memory_trace(), att_fake)
    call = att_fake.calls[0]
    assert marker not in call["prompt"] and marker not in call["system"]
    assert call["system"] == ATTACK_SYSTEM and call["template"] == ATTACK_TEMPLATE


def test_two_separate_prompts_neither_mentions_the_other():
    assert SUPPORT_SYSTEM != ATTACK_SYSTEM and SUPPORT_TEMPLATE != ATTACK_TEMPLATE
    for text in (ATTACK_SYSTEM, ATTACK_TEMPLATE):
        assert "support pass" not in text.lower() and "supporting evidence" not in text.lower()


def test_span_ids_are_constrained_in_the_schema(env):
    insts, r, src, spans = env
    fake = _fake({"evidence": []})
    support(ATOM, r, insts, src, memory_trace(), fake)
    enum = fake.calls[0]["schema"]["properties"]["evidence"]["items"]["properties"]["span_id"]["enum"]
    assert enum == [h.span_id for h in r.hits]
