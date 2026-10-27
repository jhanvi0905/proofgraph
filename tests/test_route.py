"""Hand-written programs and routing."""

import ast
import json
import re
from pathlib import Path

from proofgraph.adapters.findver import _case_from_record
from proofgraph.clients.muse import MuseError, _parse
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


def test_dollar_amounts_with_omitted_scale_sum():
    case = Case(
        id="dollar-omitted-scale",
        dataset="findver",
        mode="passage",
        claim="November and August cash collected together equal $43,378,608.",
        sources=[
            Source(
                id="nov",
                kind="text",
                text="November cash collected was $40,622,540.",
            ),
            Source(
                id="aug",
                kind="text",
                text="August cash collected was $2,756,068.",
            ),
        ],
    )
    program = ClaimProgram(
        facts=[
            Fact(
                id="f_nov_amt",
                label="november cash collected",
                source_id="nov",
                quote="November cash collected was $40,622,540.",
                value=40622540,
                kind="number",
            ),
            Fact(
                id="f_aug_amt",
                label="august cash collected",
                source_id="aug",
                quote="August cash collected was $2,756,068.",
                value=2756068,
                kind="number",
            ),
        ],
        links=[
            Link(
                id="l_sum",
                kind="compute",
                inputs=["f_nov_amt", "f_aug_amt"],
                statement="November cash plus August cash equals the claimed total",
                expr="f_nov_amt+f_aug_amt == 43378608",
                claim_span="$43,378,608",
            )
        ],
        required=["l_sum"],
        unverifiable_parts=[],
    )
    verdict = run_program(case, program)
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert verdict.link_results[0].status == "pass"
    assert "SCALE_AMBIGUOUS" not in verdict.reason_codes
    assert verdict.link_results[0].detail != "SCALE_AMBIGUOUS"


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


AGGREGATE_REASON = (
    "The November 2022 redemption aggregate amount of $40,622,540 and the "
    "August 2023 redemption amount of $2,756,068 total the claimed $43,378,608."
)


def _cached_numeric_301() -> tuple[Case, ClaimProgram]:
    """Offline replay: the cached program and the FinDVer case. No model call."""
    records = json.loads(Path("data/FinDVer/data/test.json").read_text())
    record = next(item for item in records if item.get("example_id") == "numeric-test-301")
    case = _case_from_record(Path("data/FinDVer"), record)
    expr = "f_nov_amt+f_aug_amt == 43378608"
    for path in sorted(Path("cache").glob("*.json")):
        payload = json.loads(path.read_text())
        try:
            program = _parse(payload["response"], ClaimProgram)
        except (MuseError, KeyError, TypeError):
            continue
        if any(link.expr == expr for link in program.links):
            return case, program
    raise AssertionError("cached numeric-test-301 program is missing")


def test_cached_numeric_301_month_year_wording_does_not_block():
    case, program = _cached_numeric_301()
    assert case.id == "numeric-test-301"
    verdict = run_program(case, program)
    assert verdict.verdict == "SUPPORTED"
    assert verdict.label == "COMPUTED"
    assert verdict.reasons == [AGGREGATE_REASON]
    assert verdict.reason_codes == []
    assert "CHECKER_UNAVAILABLE" not in verdict.reason_codes
    assert "SCALE_AMBIGUOUS" not in verdict.reason_codes
    total = next(item for item in verdict.link_results if item.link_id == "l_total")
    assert total.status == "pass"
    assert total.detail != "SCALE_AMBIGUOUS"
    for fact in program.facts:
        assert fact.quote
        assert fact.quote not in verdict.reasons[0]
    assert "shares were redeemed" not in verdict.reasons[0]

    detention_payload = json.loads((FIXTURES / "detention_program.json").read_text())
    detention_case, detention_program = _bundle(detention_payload)
    detention = run_program(detention_case, detention_program)
    assert detention.verdict == "CONTRADICTED"
    assert detention.label == "COMPUTED"
    assert detention.reasons == [DETENTION_REASON]


def test_wording_span_absent_from_quotes_stays_checker_unavailable():
    case = Case(
        id="wording-absent",
        dataset="findver",
        mode="passage",
        claim="November and August cash collected together equal $43,378,608.",
        sources=[
            Source(id="nov", kind="text", text="November cash collected was $40,622,540."),
            Source(id="aug", kind="text", text="August cash collected was $2,756,068."),
        ],
    )
    program = ClaimProgram(
        facts=[
            Fact(
                id="f_nov_amt",
                label="november cash collected",
                source_id="nov",
                quote="November cash collected was $40,622,540.",
                value=40622540,
                kind="number",
            ),
            Fact(
                id="f_aug_amt",
                label="august cash collected",
                source_id="aug",
                quote="August cash collected was $2,756,068.",
                value=2756068,
                kind="number",
            ),
        ],
        links=[
            Link(
                id="l_sum",
                kind="compute",
                inputs=["f_nov_amt", "f_aug_amt"],
                statement="November cash plus August cash equals the claimed total",
                expr="f_nov_amt+f_aug_amt == 43378608",
                claim_span="$43,378,608",
            ),
            Link(
                id="l_when",
                kind="wording",
                inputs=["f_nov_amt"],
                statement="The collection happened in December 2024.",
                claim_span="December 2024",
            ),
        ],
        required=["l_sum", "l_when"],
        unverifiable_parts=[],
    )
    verdict = run_program(case, program)
    assert verdict.verdict == "UNRESOLVED"
    assert verdict.label is None
    assert verdict.reason_codes == ["CHECKER_UNAVAILABLE"]
    wording = next(item for item in verdict.link_results if item.link_id == "l_when")
    assert wording.status == "blocked"
    assert wording.detail == "CHECKER_UNAVAILABLE"


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
