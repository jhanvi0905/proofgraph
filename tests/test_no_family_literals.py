"""No document family's literals in logic or in text shown to the model.

This sees literals, not shape. It caught nothing of the PDF-citation problem:
assertions.py accepted only raw-file offsets, with no family name anywhere in
it. Passing it is necessary, not sufficient. The real test is family B
running with no code change.

cli.py is exempt: it wires the demo to a named packet on purpose.
Docstrings and comments are exempt: they may cite examples.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FAMILY_LITERALS = [
    # family A
    "gillette", "coda", "reliance", "fd960228", "fd960229", "gs-212", "item7", "item vii",
    "lloyd", "london", "nda 0134456", "corp_reimbursement", "ex-10",
    # family B
    "ho 00 03", "ho_00_03", "homeowners", "iso_ho",
]
EXEMPT = {"cli.py"}


def _docstrings(tree: ast.AST) -> set[int]:
    ids = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _hits(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree)
    found = []
    for node in ast.walk(tree):
        text = None
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip:
            text = node.value
        elif isinstance(node, ast.Name):
            text = node.id
        elif isinstance(node, ast.Attribute):
            text = node.attr
        if text:
            low = text.lower()
            found += [f"{path.name}:{node.lineno}: {lit!r}" for lit in FAMILY_LITERALS if lit in low]
    return found


@pytest.mark.parametrize("path", sorted(p for p in (ROOT / "proofgraph").glob("*.py") if p.name not in EXEMPT),
                         ids=lambda p: p.name)
def test_no_family_literals_in_code(path: Path):
    assert _hits(path) == []


def test_no_family_literals_in_model_facing_data():
    text = (ROOT / "data" / "predicates.json").read_text(encoding="utf-8").lower()
    assert [lit for lit in FAMILY_LITERALS if lit in text] == []
