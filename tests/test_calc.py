"""Safe calculator, tolerance, and scale."""

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from proofgraph.engine.calc import EvalError, check_compute, evaluate
from proofgraph.schema import Fact


def _fact(value: object, scale: str | None = None) -> Fact:
    return Fact(
        id="f3",
        label="revenue",
        source_id="s",
        value=value,  # type: ignore[arg-type]
        kind="number",
        scale=scale,  # type: ignore[arg-type]
        quote="183,479",
    )


def test_addition():
    assert evaluate("1 + 2") == 3


def test_subtraction():
    assert evaluate("5 - 2") == 3


def test_multiplication():
    assert evaluate("4 * 3") == 12


def test_division():
    assert evaluate("8 / 2") == 4


def test_parentheses():
    assert evaluate("((1 + 2) * 3) == 9") is True


def test_equality_true_and_false():
    assert evaluate("2 + 2 == 4") is True
    assert evaluate("2 + 2 == 5") is False


def test_unary_minus():
    assert evaluate("-3 + 5 == 2") is True


def test_comparisons():
    assert evaluate("1 < 2") is True
    assert evaluate("2 <= 2") is True
    assert evaluate("3 > 1") is True
    assert evaluate("3 >= 4") is False


def test_abs_min_max():
    assert evaluate("abs(-4)") == 4
    assert evaluate("min(3, 1, 2)") == 1
    assert evaluate("max(3, 1)") == 3


def test_round():
    assert evaluate("round(1.4)") == 1
    assert evaluate("round(1.6)") == 2


def test_percent_suffix():
    assert evaluate("12.5% == 0.125") is True
    assert evaluate("18% == 0.18") is True


def test_exact_literal_tolerance_includes_half_step():
    claim = "Revenue was $183,479,000."
    assert evaluate("(183479 * 1000 + 500) == 183479000", claim=claim) is True


def test_exact_literal_tolerance_rejects_beyond_half_step():
    claim = "Revenue was $183,479,000."
    assert evaluate("(183479 * 1000 + 501) == 183479000", claim=claim) is False


def test_percent_point_tolerance():
    claim = "The margin was 18.2%."
    assert evaluate("(1825 / 10000) == 18.2%", claim=claim) is True
    assert evaluate("(1826 / 10000) == 18.2%", claim=claim) is False


def test_hedge_widens_tolerance():
    assert evaluate("18.5 == 18.2", claim="about 18.2") is True
    assert evaluate("18.5 == 18.2", claim="18.2") is False


def test_hedge_still_rejects_a_far_value():
    assert evaluate("20 == 18.2", claim="about 18.2") is False


def test_hours_between_same_day():
    assert evaluate('hours_between("10:00", "14:12")') == Decimal("4.2")


def test_hours_between_overnight():
    assert evaluate('hours_between("22:00", "02:00")') == 4


def test_days_between():
    assert evaluate('days_between("2026-10-27", "2026-10-29")') == 2


def test_detention_hours_times_rate():
    assert evaluate('(hours_between("10:00", "14:12") - 2) * 75') == 165


def test_stated_scale_uses_the_expression_once():
    result = check_compute(
        "(f3*1000) == 183479000",
        [_fact(183479, "thousands")],
        "Revenue was $183,479,000.",
    )
    assert result.status == "pass"
    assert result.code is None


def test_missing_scale_is_ambiguous_when_verdicts_differ():
    result = check_compute(
        "f3 == 183479000",
        [_fact(183479, None)],
        "Revenue was $183,479,000.",
    )
    assert result.status == "blocked"
    assert result.code == "SCALE_AMBIGUOUS"


def test_dollar_quote_with_omitted_scale_is_units_and_the_sum_passes():
    facts = [
        Fact(
            id="f_nov_amt",
            label="november redemption",
            source_id="p87",
            value=40622540,
            kind="number",
            quote=(
                "at a price of approximately $10.29 per share, in an "
                "aggregate amount of $40,622,540."
            ),
        ),
        Fact(
            id="f_aug_amt",
            label="august redemption",
            source_id="p88",
            value=2756068,
            kind="number",
            quote=(
                "at a price of approximately $10.88 per share or $2,756,068, "
                "including income"
            ),
        ),
    ]
    result = check_compute(
        "f_nov_amt+f_aug_amt == 43378608",
        facts,
        "The combined redemptions equal $43,378,608.",
    )
    assert result.status == "pass"
    assert result.code is None
    assert "SCALE_AMBIGUOUS" not in result.detail


def test_bare_number_with_omitted_scale_stays_ambiguous():
    fact = Fact(
        id="f3",
        label="revenue",
        source_id="s",
        value=183479,
        kind="number",
        quote="Revenue 183,479.",
    )
    result = check_compute(
        "f3 == 183479000",
        [fact],
        "Revenue was $183,479,000.",
    )
    assert result.status == "blocked"
    assert result.code == "SCALE_AMBIGUOUS"


def test_same_result_under_every_scale_stands():
    assert check_compute("f3 == 0", [_fact(0)], "The figure is 0.").status == "pass"


def test_all_scales_failing_stands_as_failure():
    assert check_compute("f3 == 5", [_fact(3)], "The figure is 5.").status == "fail"


def test_division_by_zero_is_eval_error():
    with pytest.raises(EvalError):
        evaluate("1 / 0")


def test_unknown_name_is_eval_error():
    with pytest.raises(EvalError):
        evaluate("f1 + 1")


@pytest.mark.parametrize(
    "expr",
    [
        "__import__('os')",
        "(1).real",
        "(lambda: 1)()",
        "2 ** 3",
        "items[0]",
        "1 % 2",
        "open('x')",
    ],
)
def test_whitelist_rejects(expr: str):
    with pytest.raises(EvalError):
        evaluate(expr, {"items": 1})


def test_calculator_source_does_not_call_eval():
    tree = ast.parse(Path("proofgraph/engine/calc.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile"}
