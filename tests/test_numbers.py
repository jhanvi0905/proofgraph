"""Value comparison: numerals only, currency tokens dropped, integers compared, no document awareness."""

from __future__ import annotations

import inspect

import pytest

from proofgraph import numbers
from proofgraph.numbers import compare_values, numeral
from proofgraph.schema import ValueComparison as V


@pytest.mark.parametrize("a, b, expected", [
    ("$10M", "USD 10,000,000", V.EQUAL),
    ("1,000,000", "USD 1,000,000", V.EQUAL),          # Item VII vs the FD960228 cover note
    ("$1.5 million", "USD 1,500,000", V.EQUAL),
    ("US$10,000,000", "$10,000,000", V.EQUAL),
    ("$1000", "$1,000", V.EQUAL),                     # HO 00 03 style
    ("$500,000", "1,000,000", V.DIFFERENT),          # Reliance vs Item VII
    ("NIL", "NIL", V.NOT_COMPARABLE),
    ("NIL", "$0", V.NOT_COMPARABLE),
    ("USD Nil", "USD 1,000,000", V.NOT_COMPARABLE),
    ("US$10,000,0O0", "$10,000,000", V.NOT_COMPARABLE),  # letter O: no numeral, not repaired
    ("UNDERLYING", "$10M", V.NOT_COMPARABLE),
])
def test_compare_values(a, b, expected):
    assert compare_values(a, b) is expected
    assert compare_values(b, a) is expected


def test_numeral_is_integer_minor_units():
    assert numeral("USD 1,000,000") == numeral("1,000,000") == 100_000_000
    assert numeral("$125,000.50") == 12_500_050
    assert numeral("NIL") is None


def test_value_comparison_takes_only_text():
    """No parameter through which a document, instrument or source could reach it."""
    for fn in (compare_values, numeral):
        params = inspect.signature(fn).parameters
        assert all(p.annotation in ("str", str) for p in params.values()), fn.__name__
    src = inspect.getsource(compare_values) + inspect.getsource(numeral)
    for word in ("doc_id", "instrument", "source_id", "gillette", "coda", "reliance"):
        assert word not in src.lower()
