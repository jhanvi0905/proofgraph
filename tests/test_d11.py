"""D11: typed claims, a confirmed grouping, the unchanged decision tree."""

from __future__ import annotations

import pytest

from app.server import DATA, _packets
from proofgraph.grouping import Gathered, decide_typed, read_claim
from proofgraph.pipeline import gather
from proofgraph.schema import Basis
from proofgraph.trace import Trace

POLICIES = ("SPECIMEN-HO3", "FD960228", "GS-212C")


@pytest.mark.parametrize("text, kind, written, value", [
    ("the jewelry theft limit is $1,000", "amount", "$1,000", "$1,000"),
    ("the retention is $1M", "amount", "$1M", "$1,000,000"),  # the scale word is read, not dropped
    ("the retention is USD 1,000,000 each claim", "amount", "USD 1,000,000", "USD 1,000,000 each claim"),
    ("the limit is 2.5 million", "amount", "2.5 million", "2,500,000"),
    ("the jewelry limit applies to loss by misplacing", "wording", None, None),
])
def test_code_reads_the_claim(text, kind, written, value):
    r = read_claim(text, POLICIES)
    assert (r.kind, r.written, r.value, r.refusal) == (kind, written, value, None)


@pytest.mark.parametrize("text, refusal", [
    ("", "empty_claim"),
    ("the limit is $1,000 and the deductible is $500", "more_than_one_value"),
    ("the policy took effect on 6/1/96", "dates_not_supported"),
])
def test_unreadable_claims_are_refused_with_a_reason(text, refusal):
    assert read_claim(text, POLICIES).refusal == refusal


def test_a_policy_number_in_the_claim_is_found_and_only_reported():
    r = read_claim("The primary retention under FD960228 is USD 1,000,000.", POLICIES)
    assert r.policy_matches == ("FD960228",)
    assert read_claim("The retention under FD9602289 is $1", POLICIES).policy_matches == ()  # whole tokens only


def test_basis_is_read_only_when_written():
    assert read_claim("the retention is $1M each loss", POLICIES).basis is Basis.EACH_LOSS
    assert read_claim("the retention is $1M", POLICIES).basis is None


def _gathered(packet: str, claim_id: str) -> Gathered:
    """Gather offline: run the reads under an existing claim's key (recorded responses replay), then
    treat the result as a typed claim's candidates. Tests the confirmation and decision, not retrieval."""
    pack = next(p for p in _packets() if p["id"] == packet)
    claim = next(c for c in pack["choices"] if c.claim_id == claim_id)
    run, checked = gather(claim_id, claim, pack["docs"], pack["mappings"], DATA, Trace(None))
    from proofgraph.grouping import Candidate, _loc
    read = read_claim(claim.text, POLICIES)
    g = Gathered(read=read, policy=claim.slot.split(".")[0], temp_slot=claim.slot, doc_ids=pack["docs"], run=run,
                 checked=checked)
    for a in run.assertions:
        page, s, e = _loc(a.citation)
        g.candidates.append(Candidate(a.assertion_id, a.instrument.doc_id, a.assertion_id.split(":")[0], page, s, e,
                                      a.citation.text, a.value.text))
    return g


def test_confirming_every_line_reproduces_the_frozen_answer_and_records_how():
    g = _gathered("homeowners", "fb_jewelry")
    d = decide_typed(g, {c.line_id for c in g.candidates}, {}, confirmed_by="test", policy_source="matched_in_claim")
    v = d.run.verdict
    assert d.refusal is None and v.verdict.value == "supported" and v.governing_doc_id == "ho_00_15"
    assert v.supported_reason.value == "no_conflict" and v.governing_rule.value == "endorsement_over_base"
    assert d.record["grouping_mode"] == "person" and d.record["basis_source"] == "not_stated"
    assert d.record["policy_source"] == "matched_in_claim" and d.record["question"].startswith("SPECIMEN-HO3.")
    assert all(a.slot == d.record["question"] for a in d.run.assertions)  # re-keyed, not re-read


def test_a_dropped_line_needs_a_reason_and_is_recorded_with_its_text():
    g = _gathered("homeowners", "fb_jewelry")
    base = next(c for c in g.candidates if c.doc_id == "ho_00_03")
    rest = {c.line_id for c in g.candidates} - {base.line_id}
    assert decide_typed(g, rest, {base.line_id: " "}, confirmed_by="t", policy_source="chosen").refusal == "confirmation_incomplete"
    assert decide_typed(g, rest, {}, confirmed_by="t", policy_source="chosen").refusal == "confirmation_incomplete"
    g = _gathered("homeowners", "fb_jewelry")
    d = decide_typed(g, rest, {base.line_id: "base form, superseded"}, confirmed_by="t", policy_source="chosen")
    assert d.refusal is None and d.record["dropped"][0]["doc_id"] == "ho_00_03"
    assert d.record["dropped"][0]["reason"] == "base form, superseded" and "jewelry" in d.record["dropped"][0]["text"]


def test_dropping_every_line_is_refused():
    g = _gathered("homeowners", "fb_jewelry")
    d = decide_typed(g, set(), {c.line_id: "not about this" for c in g.candidates}, confirmed_by="t", policy_source="chosen")
    assert d.refusal == "no_line_confirmed"


def test_basis_set_at_confirmation_is_recorded_as_set_there():
    g = _gathered("gillette", "retention")
    d = decide_typed(g, {c.line_id for c in g.candidates}, {}, confirmed_by="t", policy_source="matched_in_claim",
                     basis_set=Basis.EACH_CLAIM)
    assert d.record["basis_source"] == "set_at_confirmation"
    assert d.record["claim_value_compared"] == "USD 1,000,000 each claim"
    assert d.run.verdict.verdict.value == "unresolved" and d.run.verdict.unresolved_reason.value == "documents_disagree"


def test_regression_five_typed_claims_with_no_question_key():
    """D11 acceptance: the five frozen claims, typed as text, every candidate confirmed, no key from slots.json.
    Replays the responses recorded on the first live run. Verdict, reason, governing document and value must
    match data/regression_d11.json; cited documents and values must match; PDF pages must match. One recorded
    finding: the FD960229 quote starts at "POLICY NO" (char 79,787), not "RETENTION" (79,877), same block and figure."""
    import json
    from pathlib import Path

    from proofgraph.grouping import gather_typed

    packs = {p["id"]: p for p in _packets()}
    fx = json.loads((DATA / "regression_d11.json").read_text())
    for e in fx["claims"]:
        pack = packs[e["packet"]]
        pols = tuple(sorted({d.policy for m in pack["mappings"].documents for d in m.describes}))
        r = read_claim(e["claim_text"], pols)
        assert len(r.policy_matches) == 1, (e["claim_id"], r.policy_matches)  # found in the text, shown, then used
        g = gather_typed(r, r.policy_matches[0], e["claim_id"], pack["docs"], pack["mappings"], DATA, Trace(None))
        assert not g.run.failure, g.run.failure
        d = decide_typed(g, {c.line_id for c in g.candidates}, {}, confirmed_by="regression", policy_source="matched_in_claim")
        v = d.run.verdict
        assert v.verdict.value == e["verdict"], e["claim_id"]
        assert (v.unresolved_reason.value if v.unresolved_reason else None) == e["reason"]
        assert v.governing_doc_id == e["governing_doc_id"] and v.governing_value == e["governing_value"]
        got = sorted((a.instrument.doc_id, a.value.text) for a in d.run.assertions)
        assert got == sorted((c["doc_id"], c["value"]) for c in e["cited"]), e["claim_id"]
        for a in d.run.assertions:
            want = next(c for c in e["cited"] if c["doc_id"] == a.instrument.doc_id)
            if "page" in want:
                assert a.citation.locator.page == want["page"]
            elif a.instrument.doc_id == "london_fd960229":
                assert a.citation.locator.start == 79787 and "RETENTION" in a.citation.text  # the recorded finding
            else:
                assert a.citation.locator.start == want["start"]
