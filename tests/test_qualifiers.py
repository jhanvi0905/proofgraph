import re
import typing

from proofgraph.review.models import WeakenerType
from proofgraph.review.qualifiers import QUALIFIER_PHRASE, qualifier_phrase


def test_every_weakener_type_has_a_phrase_and_no_extra():
    assert set(QUALIFIER_PHRASE) == set(typing.get_args(WeakenerType))


def test_phrases_have_no_digits_percent_or_confidence():
    for phrase in QUALIFIER_PHRASE.values():
        assert not re.search(r"\d|%|confiden", phrase, re.I)
        assert phrase and len(phrase) < 50


def test_known_phrases_and_absent_type():
    assert qualifier_phrase("time") == "Only true for a time period"
    assert qualifier_phrase("condition") == "Depends on a condition"
    assert qualifier_phrase(None) is None
    assert qualifier_phrase("bogus") is None
