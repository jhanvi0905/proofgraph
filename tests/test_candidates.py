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


# ----------------------------------------------------------------------------- snap-ability and unit cap

def _layout(rows):
    """Words laid out like a PDF text layer: rows of (y, [(text, y_offset)]) left to right."""
    from proofgraph.review.ingest import Word
    words = []
    for y, row in rows:
        x = 100
        for text, dy in row:
            words.append(Word(text, (x, y + dy, x + 40, y + dy + 10)))
            x += 45
    return words


def test_every_candidate_is_an_exact_match_on_the_page_words(monkeypatch):
    monkeypatch.setenv("PROOFGRAPH_EVIDENCE_MAP", "1")  # the by-line word ordering is part of map mode
    from proofgraph.review.run import _page_text
    from proofgraph.review.snap import _exact, _normalise, snap
    row1 = [(w, 0) for w in "Notes and other business information.".split()]
    # a bold run-in heading whose boxes sit a few units off the baseline of the body text
    row2 = [("2.", 0), ("PERIOD", 3), ("OF", 3), ("DEPOSIT.", 3), ("The", 0), ("tenant", 0), ("paid", 0), ("the", 0), ("deposit", 0)]
    row3 = [(w, 0) for w in "to the landlord in full.".split()]
    footer = [("Page", 0), ("1", 0), ("of", 0), ("4", 0)]
    words = _layout([(100, row1), (120, row2), (140, row3), (900, footer)])
    text = _page_text(words)
    cands = build_candidates(CLAIM, [page(text)]).candidates
    assert cands
    page_string = "".join(_normalise(w.text) for w in words)
    for c in cands:
        assert _exact(_normalise(c.text), page_string) is not None, c.text
        assert snap(c.text, words).status == "pinned"


def test_long_list_item_is_cut_at_sentence_ends_and_pieces_cover_it():
    sentence = "The tenant paid the deposit and shall keep every receipt for the records of the landlord."
    item = "5. " + " ".join([sentence] * 12)
    assert len(item) > 800
    r = build_candidates(CLAIM, [page(item)], cap=100)
    assert len(r.candidates) > 1
    assert all(len(c.text) <= 400 for c in r.candidates)
    assert r.candidates[0].text.startswith("5. The tenant")
    assert " ".join(c.text for c in r.candidates) == item
    assert r.rule_version == "candidates-2"
