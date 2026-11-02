"""Quote bounds: widen a quote to its sentence or list item; reject fragments. Pure code."""

import pytest

from proofgraph.review.bounds import enabled, expand_quote, reject_quote

TEXT = (
    "The Buyer shall pay the invoice. Under Sec. 5.2 of the Agreement, fees are due within 30 days; "
    "late fees accrue at 1.5% per month. See e.g. clause 4 for details."
)
LIST = "The Seller shall:\n a. deliver the goods on time\n b. insure the goods in transit\n c. pay all duties"


def test_expands_to_the_sentence_across_section_number_and_abbreviation():
    out = expand_quote("fees are due within", TEXT)
    assert out == "Under Sec. 5.2 of the Agreement, fees are due within 30 days;"


def test_semicolon_ends_a_clause_and_decimal_does_not_end_a_sentence():
    assert expand_quote("late fees accrue", TEXT) == "late fees accrue at 1.5% per month."


def test_eg_does_not_end_a_sentence():
    assert expand_quote("clause 4", TEXT) == "See e.g. clause 4 for details."


def test_first_sentence_starts_at_the_beginning():
    assert expand_quote("pay the invoice", TEXT) == "The Buyer shall pay the invoice."


def test_list_item_stays_its_own_item():
    assert expand_quote("insure the goods", LIST) == "b. insure the goods in transit"


def test_first_list_item_takes_the_lead_in_line():
    out = expand_quote("a. deliver the goods", LIST)
    assert out == "The Seller shall: a. deliver the goods on time"


def test_quote_in_wrapped_lines_is_one_normalised_string():
    text = "Intro sentence.\nFees are due\nwithin thirty days\nof the invoice date."
    assert expand_quote("within thirty", text) == "Fees are due within thirty days of the invoice date."


def test_matching_ignores_case_and_punctuation():
    assert expand_quote("LATE FEES, ACCRUE", TEXT) == "late fees accrue at 1.5% per month."


def test_unlocatable_quote_is_returned_unchanged():
    assert expand_quote("not on the page at all", TEXT) == "not on the page at all"
    assert expand_quote("", TEXT) == ""


def test_result_over_cap_falls_back_to_the_raw_quote():
    assert expand_quote("fees are due", TEXT, cap=30) == "fees are due"


def test_line_without_sentence_end_stays_on_its_line():
    text = "head line\nDetention: $75.00/hour after 2 hours free time\nLinehaul: $1,840.00"
    assert expand_quote("$75.00/hour after", text) == "Detention: $75.00/hour after 2 hours free time"


@pytest.mark.parametrize("quote", [
    "", "   ", "Too short here", "12 March 2024", "Issued: 12 March 2024", "March 3, 2024 12 2025 2026 2027",
    "SECTION FIVE PAYMENT TERMS", "The Seller shall deliver the following:",
])
def test_reject(quote):
    assert reject_quote(quote)


def test_full_sentence_is_kept():
    assert not reject_quote("The Buyer shall pay the invoice within thirty days.")
    assert not reject_quote("Detention: $75.00/hour after 2 hours free time")


def test_flag_is_exactly_one(monkeypatch):
    monkeypatch.delenv("PROOFGRAPH_QUOTE_BOUNDS", raising=False)
    assert not enabled()
    monkeypatch.setenv("PROOFGRAPH_QUOTE_BOUNDS", "1")
    assert enabled()
    monkeypatch.setenv("PROOFGRAPH_QUOTE_BOUNDS", "true")
    assert not enabled()
