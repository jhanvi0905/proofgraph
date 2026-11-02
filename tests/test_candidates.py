"""Candidate pool: deterministic units that share a term with the claim part."""

from proofgraph.review.absence import AbsencePage, build_receipt
from proofgraph.review.candidates import CANDIDATE_RULE_VERSION, build_candidates

CLAIM = "The tenant paid a $250 deposit to the landlord."


def page(text, doc="d1", n=1):
    return AbsencePage(doc, n, text)


def texts(result):
    return [c.text for c in result.candidates]


def test_sentences_split_and_only_matching_ones_are_kept():
    p = page("The weather was mild. The tenant paid the deposit. Parking is extra.")
    r = build_candidates(CLAIM, [p])
    assert texts(r) == ["The tenant paid the deposit."]
    assert r.candidates[0].kind == "sentence"


def test_abbreviations_and_section_numbers_do_not_split():
    p = page("Under Sec. 5.2 the tenant paid a deposit, e.g. $250, to the landlord. Next sentence here.")
    r = build_candidates(CLAIM, [p])
    assert texts(r) == ["Under Sec. 5.2 the tenant paid a deposit, e.g. $250, to the landlord."]
    q = build_candidates(CLAIM, [page("See No. 7 for the deposit. Other text.")])
    assert texts(q) == ["See No. 7 for the deposit."]


def test_list_items_are_units_with_wrapped_lines():
    p = page("Terms:\na. Rent is monthly.\n(i) The tenant pays a deposit\nof $250 on signing.\n7. Pets are banned.")
    r = build_candidates(CLAIM, [p])
    assert texts(r) == ["(i) The tenant pays a deposit\nof $250 on signing."]
    assert r.candidates[0].kind == "list"


def test_table_row_is_a_unit_and_header_is_context_not_text():
    p = page("Item Qty Price\nDeposit 1 250.00\nParking 1 40.00")
    r = build_candidates(CLAIM, [p])
    assert len(r.candidates) == 1
    c = r.candidates[0]
    assert c.kind == "row" and c.text == "Deposit 1 250.00" and c.context == "Item Qty Price"
    assert "Item" not in c.text


def test_term_matching_uses_sweep_stemming_and_number_keys():
    p = page("Deposits of two hundred fifty dollars were received by the landlord.")
    r = build_candidates(CLAIM, [p])
    assert len(r.candidates) == 1
    assert {"deposit", "250"} <= set(r.candidates[0].terms) or "250" in r.candidates[0].terms


def test_cue_words_are_recorded_not_used_to_select():
    p = page("The deposit is not refundable unless the landlord agrees. It rained today.")
    r = build_candidates(CLAIM, [p])
    assert len(r.candidates) == 1
    assert set(r.candidates[0].cues) == {"not", "unless"}
    assert build_candidates(CLAIM, [page("Nothing is owed unless approved.")]).candidates == ()


def test_every_sweep_hit_is_inside_a_candidate():
    pages = [
        page("Intro line.\n1. The tenant paid.\n2. A deposit of $250 is held.\nDate Amount\nRent 1,250.00\n"
             "The landlord, e.g. Mr. Smith, agreed. Unrelated text.", "d1", 1),
        page("A dep-\nosit was returned by the landlord.", "d2", 1),
    ]
    receipt = build_receipt(CLAIM, pages, [])
    r = build_candidates(CLAIM, pages, cap=100)
    assert receipt.uncited_hits and not r.truncated
    by_page = {(p.doc, p.page): p.text for p in pages}
    for h in receipt.uncited_hits:
        assert any((c.doc, c.page) == (h.doc, h.page) and c.offset <= h.offset < c.offset + len(c.text)
                   for c in r.candidates), h


def test_deterministic_and_stable_ids():
    pages = [page("The tenant paid. The landlord left. A deposit of $250 was kept.")]
    a, b = build_candidates(CLAIM, pages), build_candidates(CLAIM, pages)
    assert a == b
    assert [c.id for c in a.candidates] == ["k1", "k2", "k3"]
    assert a.rule_version == CANDIDATE_RULE_VERSION


def test_candidate_text_is_exact_substring_at_offset():
    pages = [page("  Heading\nThe tenant  paid the\ndeposit. a. The landlord\nkept it.\nItem 3 250.00", "d1", 2)]
    r = build_candidates(CLAIM, pages)
    assert r.candidates
    for c in r.candidates:
        assert pages[0].text[c.offset:c.offset + len(c.text)] == c.text


def test_no_duplicate_candidates_and_document_order():
    pages = [page("The tenant paid. The tenant paid.", "dB", 1), page("The landlord waited.", "dA", 1)]
    r = build_candidates(CLAIM, pages)
    keys = [(c.doc, c.page, c.offset) for c in r.candidates]
    assert len(keys) == len(set(keys)) == 3
    assert [c.doc for c in r.candidates] == ["dB", "dB", "dA"]


def test_cap_keeps_one_unit_per_term_and_document_first():
    many = " ".join(f"The tenant sentence {i}." for i in range(10))
    pages = [page(many, "d1", 1), page("A deposit was kept.", "d2", 1), page("The landlord signed.", "d3", 1)]
    r = build_candidates(CLAIM, pages, cap=4)
    assert r.truncated and r.kept == 4 and r.total_matched == 12
    assert {c.doc for c in r.candidates} == {"d1", "d2", "d3"}
    assert [c.id for c in r.candidates] == ["k1", "k2", "k3", "k4"]
    assert r.candidates[0].text == "The tenant sentence 0."  # fill is in document order, no ranking
    assert not build_candidates(CLAIM, pages, cap=40).truncated


def test_no_terms_or_no_text_gives_nothing():
    assert build_candidates("", [page("The tenant paid.")]).candidates == ()
    r = build_candidates(CLAIM, [AbsencePage("d1", 1, None)])
    assert r.candidates == () and r.total_matched == 0 and not r.truncated
