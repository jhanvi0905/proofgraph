"""Hand-written programs and routing."""

import ast
import json
import re
from pathlib import Path

from proofgraph.engine.graph import to_dot
from proofgraph.engine.route import run_program
from proofgraph.schema import Case, ClaimProgram, Fact, Link, Source

FIXTURES = Path(__file__).parent / "fixtures"
DETENTION_REASON = (
    "Detention should be $165.00, not $450.00 (4.2 h on site, 2 h free, $75/h)"
)


def _bundle(payload: dict) -> tuple[Case, ClaimProgram]:
    return Case.model_validate(payload["case"]), ClaimProgram.model_validate(payload["program"])


def test_detention_program_is_contradicted_and_computed():
    payload = json.loads((FIXTURES / "detention_program.json").read_text())
    case, program = _bundle(payload)
    verdict = run_program(case, program)
    assert verdict.verdict == "CONTRADICTED"
    assert verdict.label == "COMPUTED"
    assert verdict.reasons == [DETENTION_REASON]
    assert verdict.rounds == 0
    assert verdict.flags == []
    assert "checker=fallback" not in verdict.reason_codes
    assert case.answer is None


def test_supported_sum_names_the_claim_total_and_keeps_detention():
    payload = json.loads((FIXTURES / "sum_program.json").read_text())
    case, program = _bundle(payload)
    verdict = run_program(case, program)
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert len(verdict.reasons) == 1
    reason = verdict.reasons[0]
    totals = re.findall(r"\$\d{1,3}(?:,\d{3})+(?:\.\d+)?", case.claim)
    assert totals
    assert totals[-1] in reason
    assert "check holds" in reason
    for fact in program.facts:
        assert fact.quote
        assert fact.quote in reason

    detention_payload = json.loads((FIXTURES / "detention_program.json").read_text())
    detention_case, detention_program = _bundle(detention_payload)
    detention = run_program(detention_case, detention_program)
    assert detention.verdict == "CONTRADICTED"
    assert detention.label == "COMPUTED"
    assert detention.reasons == [DETENTION_REASON]


def test_detention_graph_emits_dot():
    payload = json.loads((FIXTURES / "detention_program.json").read_text())
    case, program = _bundle(payload)
    dot = to_dot(program, run_program(case, program))
    assert dot.startswith("digraph proof {")
    assert "CONTRADICTED" in dot
    assert "COMPUTED" in dot
    assert "f_rate -> l_detention;" in dot
    assert "l_detention -> verdict;" in dot


def test_stated_scale_program_is_supported():
    payload = json.loads((FIXTURES / "scale_program.json").read_text())
    case, program = _bundle(payload["stated"])
    verdict = run_program(case, program)
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert verdict.rounds == 0
    assert "SCALE_AMBIGUOUS" not in verdict.reason_codes


def test_ambiguous_scale_program():
    payload = json.loads((FIXTURES / "scale_program.json").read_text())
    case, program = _bundle(payload["ambiguous"])
    verdict = run_program(case, program)
    assert verdict.verdict == "UNRESOLVED"
    assert verdict.reason_codes == ["SCALE_AMBIGUOUS"]
    assert verdict.rounds == 0
    assert verdict.flags == []


def test_wording_link_blocks_without_a_model():
    case = Case(
        id="wording-1",
        dataset="contractnli",
        mode="passage",
        claim="The carrier may inspect the goods.",
        sources=[Source(id="c6", kind="text", text="The carrier may inspect the goods.")],
    )
    program = ClaimProgram(
        facts=[
            Fact(
                id="f1",
                label="inspection",
                source_id="c6",
                quote="The carrier may inspect the goods.",
                value="inspect",
                kind="text",
            )
        ],
        links=[
            Link(
                id="l1",
                kind="wording",
                inputs=["f1"],
                statement="The carrier may inspect the goods.",
                claim_span="inspect the goods",
            )
        ],
        required=["l1"],
        unverifiable_parts=[],
    )
    verdict = run_program(case, program)
    assert verdict.verdict == "UNRESOLVED"
    assert verdict.reason_codes == ["CHECKER_UNAVAILABLE"]
    assert verdict.flags == []
    assert verdict.rounds == 0


def test_engine_does_not_import_proposer_or_muse():
    root = Path("proofgraph/engine")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for name in modules:
                assert "propose" not in name
                assert "muse" not in name.split(".")


def test_engine_does_not_read_sealed_case_fields():
    root = Path("proofgraph/engine")
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                assert node.attr not in {"answer", "gold_evidence"}
