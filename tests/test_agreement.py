"""C5 (Iteration 2): walk-and-read agreement compares the statements labelled relevant, not raw citations."""

from proofgraph.review.compare import Item
from proofgraph.review.full_read import ReadResult, relevant_agreement


def _labels(**kw):
    return {i: Item(id=i, label=label) for i, label in kw.items()}


def test_irrelevant_statements_on_both_routes_are_both_empty():
    labels = _labels(a1="irrelevant", a2="irrelevant", a3="irrelevant")
    flag = relevant_agreement(labels, ReadResult(cited=("a1",)))
    assert flag.flag == "both_empty"


def test_walk_relevant_and_read_empty_is_disagree_with_the_relevant_ids_listed():
    labels = _labels(a1="agrees", a2="irrelevant")
    flag = relevant_agreement(labels, ReadResult(cited=()))
    assert (flag.flag, flag.walk_only, flag.read_only) == ("disagree", ("a1",), ())


def test_same_relevant_set_agrees_and_overlap_is_partial():
    labels = _labels(a1="conflicts", a2="qualifies", a3="irrelevant")
    assert relevant_agreement(labels, ReadResult(cited=("a1", "a2", "a3"))).flag == "agree"
    assert relevant_agreement(labels, ReadResult(cited=("a1",))).flag == "partial"


def test_a_cited_statement_the_comparator_never_judged_counts_as_relevant():
    flag = relevant_agreement(_labels(a1="irrelevant"), ReadResult(cited=("zz",)))
    assert (flag.flag, flag.read_only) == ("disagree", ("zz",))


def test_an_aligned_passage_the_statements_miss_counts_as_relevant():
    read = ReadResult(cited=(), extra=(("d1", 2, "quote", None),))
    assert relevant_agreement({}, read).flag == "disagree"
