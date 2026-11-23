"""D9 rules, each with a counterfactual: comparability, the claim against the governing value, the
resolved_by_rule fix, the missing-document check (with its excluded record), and wording claims.

Unit tests build assertions on the homeowners lines by hand (the arbiter never opens a file).
The last tests replay the three D9 packets end to end from data/recorded/model, with no API key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from proofgraph.arbiter import arbitrate, arbitrate_wording
from proofgraph.numbers import compare, compare_claim, find_basis, parse_amount
from proofgraph.schema import (
    Assertion, Citation, Claim, Clause, ComparisonReason, DocumentMappingFile, Excerpt, InstrumentRef, InstrumentType,
    MappingMethod,
    RouteRef, RouteStrength, RuleName, Side, SupportedReason, UnresolvedReason, ValueComparison, Verdict,
)

ROOT = Path(__file__).resolve().parent.parent
FB = ROOT / "data" / "family_b"
SLOT = "SPECIMEN-HO3.jewelry_theft.special_limit"
MAPS = DocumentMappingFile.model_validate_json((FB / "document_mappings.json").read_text()).documents
BOTH = ("ho_00_03", "ho_00_15")
ROUTES = (RouteRef(mapping_id="identify", method=MappingMethod.JUDGMENT, strength=RouteStrength.JUDGMENT),)

INST = {
    "ho_00_03": InstrumentRef(doc_id="ho_00_03", version="04 91", instrument_type=InstrumentType.POLICY_FORM,
                              policy_numbers=("SPECIMEN-HO3",), effective_date=None),
    "ho_00_15": InstrumentRef(doc_id="ho_00_15", version="04 91", instrument_type=InstrumentType.ENDORSEMENT,
                              policy_numbers=("SPECIMEN-HO3",), effective_date=None),
}
LINE = {"ho_00_03": "5. $1000 for loss by theft of jewelry, watches, furs,",
        "ho_00_15": "5. $1,000 for loss by theft, misplacing or losing of"}


def _cite(doc: str, text: str) -> Citation:
    return Citation.model_validate({"source_file": f"{doc}.pdf", "sha256_of_file": "0" * 64,
                                    "locator": {"kind": "page_quote", "page": 2}, "text": text})


def asserted(doc: str, text: str | None = None, value: str | None = None) -> Assertion:
    text = text or LINE[doc]
    value = value or text.split()[1]
    start = text.index(value)
    b = find_basis(text)
    return Assertion(assertion_id=f"a:{doc}", slot=SLOT, instrument=INST[doc], citation=_cite(doc, text),
                     value=Excerpt(start=start, end=start + len(value), text=value), amount=parse_amount(value),
                     basis=b[0] if b else None,
                     basis_phrase=Excerpt(start=b[1], end=b[2], text=text[b[1]:b[2]]) if b else None,
                     routes=ROUTES, weakest=RouteStrength.JUDGMENT)


def claim(value: str = "$1,000", slot: str = SLOT) -> Claim:
    return Claim(claim_id="c", text="t", slot=slot, kind="amount", value=value)


# ---------------------------------------------------------------- comparability (build item 2)


def test_two_amounts_with_no_basis_and_one_currency_are_compared():
    """D9: neither side states a basis, so the question fixes the quantity, and the pair is compared.
    Before D9 (both must state a basis) this exact pair was basis_not_stated, never compared."""
    p = compare(asserted("ho_00_03"), asserted("ho_00_15"))
    assert (p.compared, p.reason, p.value) == (True, ComparisonReason.EQUAL, ValueComparison.EQUAL)


def test_one_side_stating_a_basis_is_a_named_mismatch_saying_which_side_lacked_it():
    with_basis = asserted("ho_00_15", "5. $1,000 each occurrence for loss by theft", "$1,000")
    p = compare(asserted("ho_00_03"), with_basis)
    assert (p.compared, p.reason, p.detail) == (False, ComparisonReason.BASIS_NOT_STATED, "not stated by a:ho_00_03")


def test_one_side_stating_a_currency_is_a_named_mismatch():
    bare = asserted("ho_00_15", "5. 1,000 for loss by theft, misplacing or losing of", "1,000")
    p = compare(asserted("ho_00_03"), bare)
    assert (p.compared, p.reason, p.detail) == (False, ComparisonReason.CURRENCY_NOT_STATED, "not stated by a:ho_00_15")
    q = compare(bare, asserted("ho_00_15", "5. 1,000 for loss", "1,000"))
    assert q.compared and q.reason is ComparisonReason.EQUAL  # neither states a currency: comparable


def test_claim_against_an_assertion_uses_the_same_rule():
    assert compare_claim("$1,000", asserted("ho_00_03")).compared
    cc = compare_claim("$1,000 each occurrence", asserted("ho_00_03"))
    assert (cc.compared, cc.reason, cc.detail) == (False, ComparisonReason.BASIS_NOT_STATED, "not stated by a:ho_00_03")
    assert compare_claim("1,000", asserted("ho_00_03")).reason is ComparisonReason.CURRENCY_NOT_STATED


# ---------------------------------------------------------------- the claim against the governing value (build item 1)


def test_the_claim_value_decides_supported_or_contradicted():
    a = (asserted("ho_00_03"), asserted("ho_00_15"))
    right = arbitrate(claim("$1,000"), a, BOTH, MAPS)
    wrong = arbitrate(claim("$1,500"), a, BOTH, MAPS)
    assert right.verdict is Verdict.SUPPORTED and wrong.verdict is Verdict.CONTRADICTED
    # contradicted shows both amounts and names how the governing one was chosen
    assert (wrong.claim_value, wrong.governing_value) == ("$1,500", "$1,000")
    assert wrong.governing_rule is RuleName.ENDORSEMENT_OVER_BASE and wrong.governing_doc_id == "ho_00_15"
    assert wrong.governing_reason is SupportedReason.NO_CONFLICT and wrong.supported_reason is None
    assert wrong.claim_comparison.value is ValueComparison.DIFFERENT


def test_a_claim_not_comparable_with_the_governing_value_is_unresolved_naming_the_mismatch():
    v = arbitrate(claim("$1,000 each occurrence"), (asserted("ho_00_03"), asserted("ho_00_15")), BOTH, MAPS)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.AMOUNTS_NOT_COMPARABLE)
    assert v.unresolved_detail.startswith("claim '$1,000 each occurrence' vs ho_00_15 '$1,000': basis_not_stated")


# ---------------------------------------------------------------- resolved_by_rule only over a real difference


def test_resolved_by_rule_needs_a_compared_pair_whose_numerals_differ():
    """Bug fixed at D9: the jewelry pair ($1000 vs $1,000) was labelled resolved_by_rule. Equal pairs are
    no dispute: the rule still names HO 00 15, with reason no_conflict. A real difference is resolved_by_rule."""
    same = arbitrate(claim("$1,000"), (asserted("ho_00_03"), asserted("ho_00_15")), BOTH, MAPS)
    assert same.supported_reason is SupportedReason.NO_CONFLICT and same.governing_rule is RuleName.ENDORSEMENT_OVER_BASE
    raised = asserted("ho_00_15", "5. $1,500 for loss by theft, misplacing or losing of", "$1,500")
    differ = arbitrate(claim("$1,500"), (asserted("ho_00_03"), raised), BOTH, MAPS)
    assert differ.verdict is Verdict.SUPPORTED and differ.supported_reason is SupportedReason.RESOLVED_BY_RULE
    assert differ.governing_doc_id == "ho_00_15"
    # without the rule the same difference is documents_disagree
    off = arbitrate(claim("$1,500"), tuple(a.model_copy(update={"instrument": a.instrument.model_copy(
        update={"policy_numbers": ()})}) for a in (asserted("ho_00_03"), raised)), BOTH, MAPS)
    assert off.unresolved_reason is UnresolvedReason.DOCUMENTS_DISAGREE


# ---------------------------------------------------------------- missing-document check (build item 3)


def test_endorsement_without_its_base_form_is_refused_naming_both():
    v = arbitrate(claim(), (asserted("ho_00_15"),), ("ho_00_15",), MAPS)
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT)
    assert "ho_00_15" in v.unresolved_detail and "HO 00 03" in v.unresolved_detail
    assert v.rules[0].name is RuleName.AMENDED_INSTRUMENT_ABSENT and v.rules[0].fired and len(v.rules) == 1
    assert v.amends_checks[0].outcome == "absent" and v.amends_checks[0].strength is RouteStrength.JUDGMENT


def test_missing_document_check_counterfactual():
    """Without the amends routes, the same one-document packet is supported: the check is what refuses."""
    off = arbitrate(claim(), (asserted("ho_00_15"),), ("ho_00_15",), ())
    assert off.verdict is Verdict.SUPPORTED and off.amends_checks == ()
    present = arbitrate(claim(), (asserted("ho_00_03"), asserted("ho_00_15")), BOTH, MAPS)
    assert present.verdict is Verdict.SUPPORTED and present.amends_checks[0].outcome == "present"


def test_an_amended_instrument_outside_the_policy_set_is_excluded_and_recorded():
    """Same packet, but the question's policies do not include SPECIMEN-HO3's form: skipped, never dropped."""
    v = arbitrate(claim(), (asserted("ho_00_15"),), ("ho_00_15",), MAPS, policies=("OTHER",))
    assert v.unresolved_reason is not UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT
    (c,) = v.amends_checks
    assert c.outcome == "excluded" and c.reason == "ho_00_15 amends HO 00 03, outside this question's policies OTHER"


def test_a_document_that_does_not_assert_is_not_checked():
    """HO 00 15 says nothing about money, so its amends route plays no part in a money question."""
    money = asserted("ho_00_03", "1. $200 on money, bank notes, bullion, gold other", "$200")
    money = money.model_copy(update={"slot": "SPECIMEN-HO3.money.special_limit"})
    v = arbitrate(claim("$200", "SPECIMEN-HO3.money.special_limit"), (money,), BOTH, MAPS)
    assert v.verdict is Verdict.SUPPORTED and v.amends_checks == ()


# ---------------------------------------------------------------- wording claims


def _clause(doc: str, side: Side, text: str) -> Clause:
    return Clause(clause_id=f"{side.value}:{doc}", side=side, instrument=INST[doc], citation=_cite(doc, text), page=2,
                  reading="r", identification=ROUTES[0])


WORDING = Claim(claim_id="w", text="t", slot="SPECIMEN-HO3.jewelry_theft.loss_wording", kind="wording")


def test_wording_claims_get_the_governing_clause_quoted_and_clashes_as_judgment():
    clauses = (_clause("ho_00_03", Side.ATTACK, LINE["ho_00_03"]), _clause("ho_00_15", Side.SUPPORT, LINE["ho_00_15"]))
    v = arbitrate_wording(WORDING, clauses, BOTH, MAPS)
    assert v.verdict is Verdict.QUOTED and v.claim_kind == "wording" and v.claim_comparison is None
    assert v.quoted.doc_id == "ho_00_15" and v.quoted.text == LINE["ho_00_15"] and v.quoted.checked is False
    assert v.governing_rule is RuleName.ENDORSEMENT_OVER_BASE
    (clash,) = v.clashes
    assert clash.doc_id == "ho_00_03" and clash.strength is RouteStrength.JUDGMENT
    assert v.supported_reason is None and v.unresolved_reason is None  # never a code verdict


def test_wording_claims_never_reach_the_amount_arbiter_and_still_get_the_missing_document_check():
    with pytest.raises(ValueError):
        arbitrate(WORDING, (), BOTH, MAPS)
    v = arbitrate_wording(WORDING, (_clause("ho_00_15", Side.SUPPORT, LINE["ho_00_15"]),), ("ho_00_15",), MAPS)
    assert v.unresolved_reason is UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT and v.quoted is None
    assert arbitrate_wording(WORDING, (), BOTH, MAPS).verdict is Verdict.NOT_FOUND


# ---------------------------------------------------------------- the D9 packets, replayed end to end

RAW = ROOT / "data" / "raw"
needs_pdfs = pytest.mark.skipif(not all((RAW / f).exists() for f in ("ho_00_03_04_91.pdf", "ho_00_15_04_91.pdf")),
                                reason="ISO forms absent")


@pytest.fixture(scope="module")
def d9_runs():
    from proofgraph.claims import load_claims, question_policies
    from proofgraph.pipeline import run_packet
    from proofgraph.trace import memory_trace

    saved = os.environ.pop("ANTHROPIC_API_KEY", None)  # must replay from data/recorded/model
    try:
        claims = {c.claim_id: c for c in load_claims(FB / "claims.json", FB / "slots.json")}
        mappings = DocumentMappingFile.model_validate_json((FB / "document_mappings.json").read_text())
        packets = [p for p in json.loads((FB / "labels_d9.json").read_text())["packets"] if "claim_id" in p]
        out = {}
        for p in packets:
            c = claims[p["claim_id"]]
            out[p["packet_id"]] = run_packet(p["packet_id"], c, p["instruments"], mappings, ROOT / "data", memory_trace(),
                                             question_policies(c.slot, FB / "slots.json")).verdict
        return out
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


@needs_pdfs
def test_third_packet_endorsement_alone_is_refused(d9_runs):
    v = d9_runs["B-jewelry-endorsement-alone"]
    assert (v.verdict, v.unresolved_reason) == (Verdict.UNRESOLVED, UnresolvedReason.GOVERNING_INSTRUMENT_ABSENT)
    assert v.amends_checks[0].reason == "ho_00_15 amends HO 00 03 (policy SPECIMEN-HO3), which is not in the packet"


@needs_pdfs
def test_a_wrong_amount_on_the_full_packet_is_contradicted(d9_runs):
    v = d9_runs["B-jewelry-wrong-endorsed"]
    assert v.verdict is Verdict.CONTRADICTED and (v.claim_value, v.governing_value) == ("$1,500", "$1,000")
    assert v.governing_doc_id == "ho_00_15" and v.governing_rule is RuleName.ENDORSEMENT_OVER_BASE


@needs_pdfs
def test_the_wording_claim_quotes_ho_00_15_and_surfaces_ho_00_03_as_a_clash(d9_runs):
    v = d9_runs["B-jewelry-wording-endorsed"]
    assert v.verdict is Verdict.QUOTED and v.quoted.doc_id == "ho_00_15" and "misplacing or losing" in v.quoted.text
    assert [c.doc_id for c in v.clashes] == ["ho_00_03"] and v.clashes[0].strength is RouteStrength.JUDGMENT
