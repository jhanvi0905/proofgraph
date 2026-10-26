"""Safe calculator, claim tolerance, and the scale rule."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, DivisionByZero, InvalidOperation
from typing import Literal

from proofgraph.engine.numbers import Literal as NumberLiteral
from proofgraph.engine.numbers import iter_literals, numeric_value
from proofgraph.schema import Fact

_FUNCS = {"abs", "min", "max", "round", "hours_between", "days_between"}
_PERCENT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)%")
_CLOCK = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_DETENTION = re.compile(
    r"^\(hours_between\((\w+),(\w+)\)-(\w+)\)\*(\w+)==(\w+)$"
)
_SCALES = {
    "units": Decimal(1),
    "thousands": Decimal(1000),
    "millions": Decimal(1_000_000),
}


class EvalError(Exception):
    """The expression is outside the calculator whitelist."""


@dataclass(frozen=True)
class _Value:
    value: Decimal | str | bool
    literal: Decimal | None = None


@dataclass(frozen=True)
class ComputeResult:
    status: Literal["pass", "fail", "blocked"]
    code: str | None
    detail: str


def literal_tolerance(literal: NumberLiteral) -> Decimal:
    """Half a unit of the last digit, or the wider hedge band."""
    if literal.hedged:
        return max(literal.unit, abs(literal.value) * Decimal("0.02"))
    return literal.unit / Decimal(2)


def hours_between(start: object, end: object) -> Decimal:
    """Hours from start clock to end clock. An earlier end is the next day."""
    start_s = _clock_seconds(start)
    end_s = _clock_seconds(end)
    if end_s < start_s:
        end_s += 24 * 3600
    return Decimal(end_s - start_s) / Decimal(3600)


def days_between(start: object, end: object) -> Decimal:
    """Whole days from start date to end date (ISO dates)."""
    return Decimal((_parse_date(end) - _parse_date(start)).days)


def evaluate(
    expr: str,
    bindings: dict[str, object] | None = None,
    claim: str = "",
) -> Decimal | bool:
    """Evaluate a whitelisted expression. Comparisons use claim-text tolerance."""
    value = _evaluate_value(expr, bindings or {}, claim)
    if isinstance(value.value, bool):
        return value.value
    if isinstance(value.value, Decimal):
        return value.value
    raise EvalError("EVAL_ERROR")


def check_compute(expr: str | None, facts: list[Fact], claim: str) -> ComputeResult:
    """Evaluate a compute link, searching plausible scales when none is stated."""
    if expr is None or not expr.strip():
        return ComputeResult("blocked", "EVAL_ERROR", "EVAL_ERROR")
    missing = [fact for fact in facts if _needs_scale_search(fact)]
    try:
        if not missing:
            bindings = _bind(facts)
            holds = _as_bool(expr, bindings, claim)
            return _from_bool(holds, expr, bindings)
        trials: list[tuple[bool, dict[str, object]]] = []
        for name in ("units", "thousands", "millions"):
            multipliers = {fact.id: _SCALES[name] for fact in missing}
            bindings = _bind(facts, multipliers)
            trials.append((_as_bool(expr, bindings, claim), bindings))
    except EvalError:
        return ComputeResult("blocked", "EVAL_ERROR", "EVAL_ERROR")
    outcomes = {item[0] for item in trials}
    if len(outcomes) > 1:
        return ComputeResult("blocked", "SCALE_AMBIGUOUS", "SCALE_AMBIGUOUS")
    return _from_bool(trials[0][0], expr, trials[0][1])


def _needs_scale_search(fact: Fact) -> bool:
    return fact.scale is None and fact.kind == "number" and numeric_value(fact.value) is not None


def _bind(
    facts: list[Fact],
    multipliers: dict[str, Decimal] | None = None,
) -> dict[str, object]:
    scales = multipliers or {}
    env: dict[str, object] = {}
    for fact in facts:
        number = numeric_value(fact.value)
        if number is None:
            if isinstance(fact.value, str):
                env[fact.id] = fact.value
                continue
            raise EvalError("EVAL_ERROR")
        env[fact.id] = number * scales.get(fact.id, Decimal(1))
    return env


def _as_bool(expr: str, bindings: dict[str, object], claim: str) -> bool:
    value = _evaluate_value(expr, bindings, claim)
    if isinstance(value.value, bool):
        return value.value
    raise EvalError("EVAL_ERROR")


def _from_bool(holds: bool, expr: str, bindings: dict[str, object]) -> ComputeResult:
    if holds:
        return ComputeResult("pass", None, "expression holds")
    reason = _detention_reason(expr, bindings)
    if reason is not None:
        return ComputeResult("fail", None, reason)
    return ComputeResult("fail", None, "expression does not hold")


def _detention_reason(expr: str, bindings: dict[str, object]) -> str | None:
    match = _DETENTION.fullmatch(re.sub(r"\s+", "", expr))
    if match is None:
        return None
    arrived, departed, free_id, rate_id, invoice_id = match.groups()
    try:
        hours = hours_between(bindings[arrived], bindings[departed])
        free = Decimal(str(bindings[free_id]))
        rate = Decimal(str(bindings[rate_id]))
        claimed = Decimal(str(bindings[invoice_id]))
    except (KeyError, EvalError, InvalidOperation, ArithmeticError):
        return None
    computed = (hours - free) * rate
    return (
        f"Detention should be ${_money(computed)}, not ${_money(claimed)} "
        f"({_count(hours)} h on site, {_count(free)} h free, ${_count(rate)}/h)"
    )


def _money(number: Decimal) -> str:
    return f"{number.quantize(Decimal('0.01')):.2f}"


def _count(number: Decimal) -> str:
    if number == number.to_integral_value():
        return str(int(number.to_integral_value()))
    return f"{number.quantize(Decimal('0.1')):.1f}"


def _evaluate_value(expr: str, bindings: dict[str, object], claim: str) -> _Value:
    if "__" in expr:
        raise EvalError("EVAL_ERROR")
    try:
        tree = ast.parse(_PERCENT.sub(r"(\1/100)", expr), mode="eval")
    except SyntaxError as exc:
        raise EvalError("EVAL_ERROR") from exc
    return _eval(tree.body, bindings, iter_literals(claim))


def _eval(node: ast.AST, bindings: dict[str, object], literals: list[NumberLiteral]) -> _Value:
    if isinstance(node, ast.Constant):
        return _constant(node.value)
    if isinstance(node, ast.Name):
        if node.id not in bindings:
            raise EvalError("EVAL_ERROR")
        return _from_binding(bindings[node.id])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        inner = _eval(node.operand, bindings, literals)
        number = _decimal(inner)
        if isinstance(node.op, ast.UAdd):
            return _Value(number, literal=inner.literal)
        literal = None if inner.literal is None else -inner.literal
        return _Value(-number, literal=literal)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = _eval(node.left, bindings, literals)
        right = _eval(node.right, bindings, literals)
        try:
            result = _apply_op(node.op, _decimal(left), _decimal(right))
        except (ZeroDivisionError, DivisionByZero, InvalidOperation) as exc:
            raise EvalError("EVAL_ERROR") from exc
        literal = result if left.literal is not None and right.literal is not None else None
        return _Value(result, literal=literal)
    if isinstance(node, ast.Compare):
        current = _eval(node.left, bindings, literals)
        ok = True
        for op, comparator in zip(node.ops, node.comparators, strict=True):
            other = _eval(comparator, bindings, literals)
            ok = ok and _compare(op, current, other, literals)
            current = other
        return _Value(ok)
    if isinstance(node, ast.Call):
        return _call(node, bindings, literals)
    raise EvalError("EVAL_ERROR")


def _constant(value: object) -> _Value:
    if isinstance(value, bool) or value is None:
        raise EvalError("EVAL_ERROR")
    if isinstance(value, (int, float)):
        number = Decimal(str(value))
        return _Value(number, literal=number)
    if isinstance(value, str):
        return _Value(value)
    raise EvalError("EVAL_ERROR")


def _from_binding(value: object) -> _Value:
    if isinstance(value, str):
        return _Value(value)
    if isinstance(value, Decimal):
        return _Value(value)
    if isinstance(value, bool):
        raise EvalError("EVAL_ERROR")
    if isinstance(value, (int, float)):
        return _Value(Decimal(str(value)))
    raise EvalError("EVAL_ERROR")


def _decimal(value: _Value) -> Decimal:
    if isinstance(value.value, Decimal):
        return value.value
    raise EvalError("EVAL_ERROR")


def _apply_op(op: ast.operator, left: Decimal, right: Decimal) -> Decimal:
    if isinstance(op, ast.Add):
        return left + right
    if isinstance(op, ast.Sub):
        return left - right
    if isinstance(op, ast.Mult):
        return left * right
    if isinstance(op, ast.Div):
        if right == 0:
            raise EvalError("EVAL_ERROR")
        return left / right
    raise EvalError("EVAL_ERROR")


def _compare(
    op: ast.cmpop,
    left: _Value,
    right: _Value,
    literals: list[NumberLiteral],
) -> bool:
    if isinstance(left.value, str) or isinstance(right.value, str):
        if not isinstance(left.value, str) or not isinstance(right.value, str):
            raise EvalError("EVAL_ERROR")
        equal = left.value == right.value
        if isinstance(op, ast.Eq):
            return equal
        if isinstance(op, ast.NotEq):
            return not equal
        raise EvalError("EVAL_ERROR")
    if not isinstance(left.value, Decimal) or not isinstance(right.value, Decimal):
        raise EvalError("EVAL_ERROR")
    if isinstance(op, (ast.Eq, ast.NotEq)):
        tolerance = max(_tolerance(left.literal, literals), _tolerance(right.literal, literals))
        matched = abs(left.value - right.value) <= tolerance
        return matched if isinstance(op, ast.Eq) else not matched
    if isinstance(op, ast.Lt):
        return left.value < right.value
    if isinstance(op, ast.LtE):
        return left.value <= right.value
    if isinstance(op, ast.Gt):
        return left.value > right.value
    if isinstance(op, ast.GtE):
        return left.value >= right.value
    raise EvalError("EVAL_ERROR")


def _tolerance(literal: Decimal | None, literals: list[NumberLiteral]) -> Decimal:
    if literal is None:
        return Decimal(0)
    matches = [literal_tolerance(item) for item in literals if item.value == literal]
    if not matches:
        return Decimal(0)
    return max(matches)


def _call(node: ast.Call, bindings: dict[str, object], literals: list[NumberLiteral]) -> _Value:
    if node.keywords or not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
        raise EvalError("EVAL_ERROR")
    if any(isinstance(arg, ast.Starred) for arg in node.args):
        raise EvalError("EVAL_ERROR")
    args = [_eval(arg, bindings, literals) for arg in node.args]
    name = node.func.id
    if name == "abs":
        if len(args) != 1:
            raise EvalError("EVAL_ERROR")
        return _Value(abs(_decimal(args[0])))
    if name in {"min", "max"}:
        if not args:
            raise EvalError("EVAL_ERROR")
        numbers = [_decimal(arg) for arg in args]
        return _Value(min(numbers) if name == "min" else max(numbers))
    if name == "round":
        if len(args) not in {1, 2}:
            raise EvalError("EVAL_ERROR")
        digits = 0
        if len(args) == 2:
            places = _decimal(args[1])
            if places != places.to_integral_value():
                raise EvalError("EVAL_ERROR")
            digits = int(places)
        return _Value(round(_decimal(args[0]), digits))
    if name == "hours_between":
        if len(args) != 2:
            raise EvalError("EVAL_ERROR")
        return _Value(hours_between(args[0].value, args[1].value))
    if name == "days_between":
        if len(args) != 2:
            raise EvalError("EVAL_ERROR")
        return _Value(days_between(args[0].value, args[1].value))
    raise EvalError("EVAL_ERROR")


def _clock_seconds(value: object) -> int:
    if not isinstance(value, str):
        raise EvalError("EVAL_ERROR")
    match = _CLOCK.fullmatch(value.strip())
    if match is None:
        raise EvalError("EVAL_ERROR")
    hour, minute, second = int(match.group(1)), int(match.group(2)), int(match.group(3) or 0)
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise EvalError("EVAL_ERROR")
    return hour * 3600 + minute * 60 + second


def _parse_date(value: object) -> date:
    if not isinstance(value, str):
        raise EvalError("EVAL_ERROR")
    match = _DATE.match(value.strip())
    if match is None:
        raise EvalError("EVAL_ERROR")
    try:
        return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except ValueError as exc:
        raise EvalError("EVAL_ERROR") from exc
