from proofgraph.review.candidates import Candidate
from proofgraph.review.timeline import Dated, infer_dates, order, referenced_documents


def _c(id, doc, page, text, offset=0):
    return Candidate(id, doc, page, text, offset, "sentence", ())


def _pages(**kw):
    return {(d, 1): t for d, t in kw.items()}


def test_in_passage_beats_header():
    c = _c("k1", "d1", 2, "Effective 7 May 2026 the rate changes.")
    d = infer_dates([c], _pages(d1="Adopted: January 2, 2020"))["k1"]
    assert d == Dated("2026-05-07", "in passage")


def test_date_forms():
    for text in ("on May 7, 2026 x", "on 7th May 2026 x", "on 2026-05-07 x", "on Sept. 7, 2026"):
        got = infer_dates([_c("k", "d1", 1, text)], {})["k"].date
        assert got in ("2026-05-07", "2026-09-07")


def test_referenced_document_phrase_removed_first():
    c = _c("k1", "d1", 1, "Per the letter dated May 7, 2026, the fee applies from June 1, 2026.")
    assert infer_dates([c], {})["k1"].date == "2026-06-01"


def test_header_fallback():
    c = _c("k1", "d1", 3, "No date here.")
    pages = _pages(d1="Policy\nEffective: March 3, 2021\nSee also June 1, 2019.")
    assert infer_dates([c], pages)["k1"] == Dated("2021-03-03", "document header")


def test_header_must_be_early_on_page_one():
    c = _c("k1", "d1", 3, "No date here.")
    pages = _pages(d1="x" * 700 + " Dated: March 3, 2021")
    assert infer_dates([c], pages)["k1"].source == "first page"


def test_first_page_earliest():
    c = _c("k1", "d1", 3, "Nothing.")
    pages = _pages(d1="Reported 9 July 2022 and 1 February 2022.")
    assert infer_dates([c], pages)["k1"] == Dated("2022-02-01", "first page")


def test_undated_and_ambiguous_numeric_skipped():
    c = _c("k1", "d1", 1, "Due 03/04/2021.")
    assert infer_dates([c], _pages(d1="Signed 05/06/2020"))["k1"] == Dated(None, "undated")
    assert infer_dates([_c("k", "d1", 1, "Due 2021-02-30.")], {})["k"].date is None


def test_order_undated_last_and_stable():
    items = [
        (_c("a", "d1", 2, "", 5), Dated(None, "undated")),
        (_c("b", "d2", 1, "", 9), Dated("2020-01-01", "in passage")),
        (_c("c", "d1", 1, "", 3), Dated("2020-01-01", "in passage")),
        (_c("d", "d1", 1, "", 1), Dated("2019-01-01", "in passage")),
        (_c("e", "d1", 1, "", 3), Dated("2020-01-01", "in passage")),
    ]
    ids = [c.id for c, _ in order(items)]
    assert ids == ["d", "c", "e", "b", "a"]
    assert order(items) == order(items)


def test_referenced_positives():
    refs = referenced_documents(
        [("k1 d1 p2", "See the letter dated May 7, 2026 for terms."),
         ("k2 d1 p3", "The amendment of the earlier version dated 3 June 2025 applies.")],
        {"d1": "2026-05-07", "d2": None})
    assert [(r.date, r.status) for r in refs] == [("2026-05-07", "supplied"), ("2025-06-03", "not supplied")]
    assert refs[0].phrase.startswith("letter") and refs[0].cited_in == "k1 d1 p2"


def test_referenced_negatives():
    assert referenced_documents([("k", "The report was dated May 7, 2026."),
                                 ("k", "A letter " + "x" * 60 + " dated May 7, 2026."),
                                 ("k", "letter dated 05/07/2026")], {}) == []
