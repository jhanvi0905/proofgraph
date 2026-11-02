import re
from itertools import product

import pytest

from proofgraph.review.reasons import FALLBACK, REASONS, check_reason

RELATIONS = ("supports", "contradicts", "weakens")
ANSWERS = ("entails", "contradicts", "not_mentioned")
BANNED = re.compile(r"\b(true|false|wrong|correct|incorrect|right)\b", re.I)


def test_every_relation_and_answer_has_a_line():
    assert set(REASONS) == set(product(RELATIONS, ANSWERS))
    for key in product(RELATIONS, ANSWERS):
        assert check_reason(key[0], "disagrees", key[1]) == REASONS[key]


@pytest.mark.parametrize("relation", [*RELATIONS, "set_aside", "nonsense", ""])
@pytest.mark.parametrize("answer", [None, "unknown", ""])
def test_fallback_never_raises(relation, answer):
    assert check_reason(relation, "disagrees", answer) == FALLBACK


@pytest.mark.parametrize("check", ["agrees", "unavailable", "not_run", "weird"])
def test_only_disagrees_gets_a_line(check):
    for relation, answer in product(RELATIONS, (*ANSWERS, None)):
        assert check_reason(relation, check, answer) is None


def test_lines_are_distinct_plain_and_neutral():
    lines = [*REASONS.values(), FALLBACK]
    assert len(set(REASONS.values())) == len(REASONS)
    for line in lines:
        assert not BANNED.search(line), line
        assert not re.search(r"\d", line), line
        assert "only sees the quote" in line or "sees only the quote and the part" in line
        assert line.startswith("The second check")
