"""FinDVer numeric passage loading and leak stripping."""

import json
from pathlib import Path

import pytest

from proofgraph.adapters import FinDVerAdapter, for_engine
from proofgraph.adapters.base import LEAK_FIELDS

FIXTURE = Path(__file__).parent / "fixtures" / "findver"
LEAK_MARKERS = (
    "LEAK_EXPLANATION",
    "LEAK_EXPLAINATION",
    "LEAK_PYTHON",
    "LEAK_EXEC",
    "LEAK_KNOWLEDGE",
    "LEAK_GOLD",
    "LEAK_NOTE",
    "LEAK_GROUND_TRUTH",
    "LEAK_EXPECTED_VERDICT",
)


def test_numeric_passage_fixture_loads():
    cases = list(FinDVerAdapter(FIXTURE).cases("testmini", "passage", None))
    assert [case.id for case in cases] == ["numeric-fixture-0", "numeric-fixture-1"]

    contradicted, supported = cases
    assert contradicted.dataset == "findver"
    assert contradicted.mode == "passage"
    assert contradicted.claim == "Gross revenue was 180996."
    assert contradicted.answer == "CONTRADICTED"
    assert contradicted.gold_evidence == ["p107"]
    assert len(contradicted.sources) == 1
    source = contradicted.sources[0]
    assert source.id == "p107"
    assert source.kind == "table"
    assert source.text == "Gross | 183,479 | Net | 180,996 |"
    assert "\u200b" not in (source.text or "")

    assert supported.answer == "SUPPORTED"
    assert [item.id for item in supported.sources] == ["p2", "p1"]
    assert [item.kind for item in supported.sources] == ["table", "text"]
    assert supported.sources[0].text == "Units | 10 |"
    assert supported.sources[1].text == "Revenue was 10."

    limited = list(FinDVerAdapter(FIXTURE).cases("testmini", "passage", 1))
    assert [case.id for case in limited] == ["numeric-fixture-0"]


def test_leak_fields_never_reach_the_engine_view():
    raw = json.loads((FIXTURE / "data" / "testmini.json").read_text())
    hostile = raw[1]
    assert hostile["example_id"] == "numeric-fixture-0"
    assert LEAK_FIELDS <= set(hostile)

    filing = json.loads((FIXTURE / "financial_reports" / "acme.json").read_text())
    assert "\u200b" in filing["context"][2]["context"]

    case = list(FinDVerAdapter(FIXTURE).cases("testmini", "passage", 1))[0]
    visible = for_engine(case)
    assert visible.answer is None
    assert visible.gold_evidence == []
    assert visible.claim == case.claim
    assert visible.sources == case.sources
    assert case.answer == "CONTRADICTED"

    visible.gold_evidence.append("p107")
    assert case.gold_evidence == ["p107"]

    for payload in (case.model_dump(), visible.model_dump()):
        blob = json.dumps(payload)
        assert LEAK_FIELDS.isdisjoint(payload)
        for marker in LEAK_MARKERS:
            assert marker not in blob


def test_dev_split_keeps_numeric_file_order():
    cases = list(FinDVerAdapter(FIXTURE).cases("dev", "passage", None))
    assert [case.id for case in cases] == ["numeric-dev-0", "numeric-dev-1"]
    assert cases[0].answer == "SUPPORTED"
    assert cases[1].answer == "CONTRADICTED"
    assert "LEAK_EXPLANATION" not in json.dumps(cases[0].model_dump())
    assert "LEAK_PYTHON" not in json.dumps(cases[1].model_dump())


def test_dev_split_caps_at_fifty_numeric(tmp_path: Path):
    records = [_numeric(example_id=f"numeric-{index}") for index in range(51)]
    _write_claims(tmp_path, records, name="test.json")
    cases = list(FinDVerAdapter(tmp_path).cases("dev", "passage", None))
    assert len(cases) == 50
    assert cases[0].id == "numeric-0"
    assert cases[-1].id == "numeric-49"
    assert all(for_engine(case).answer is None for case in cases)

    one = list(FinDVerAdapter(tmp_path).cases("dev", "passage", 1))
    assert [case.id for case in one] == ["numeric-0"]


def test_malformed_rows_fail(tmp_path: Path):
    _write_claims(tmp_path, [_numeric(entailment_label="false")])
    with pytest.raises(ValueError, match="entailment_label"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))

    _write_claims(tmp_path, [_numeric(relevant_context=[])])
    with pytest.raises(ValueError, match="relevant_context"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))

    _write_claims(tmp_path, ["not-a-record"])
    with pytest.raises(ValueError, match="object"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))

    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "testmini.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="list"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))


def test_missing_passage_and_escaped_report_fail(tmp_path: Path):
    _write_claims(tmp_path, [_numeric(relevant_context=[404])])
    with pytest.raises(ValueError, match="404"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))

    _write_claims(tmp_path, [_numeric(report="../secret.json")])
    with pytest.raises(ValueError, match="report"):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))


def test_unknown_split_and_whole_mode_fail():
    adapter = FinDVerAdapter(FIXTURE)
    with pytest.raises(ValueError, match="split"):
        list(adapter.cases("train", "passage", None))
    with pytest.raises(ValueError, match="passage"):
        list(adapter.cases("testmini", "whole", None))
    with pytest.raises(ValueError, match="n must be >= 0"):
        list(adapter.cases("testmini", "passage", -1))


def test_missing_claims_file_fails(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))


def _numeric(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "example_id": "numeric-0",
        "subset": "numeric",
        "split": "testmini",
        "statement": "Revenue was 10.",
        "entailment_label": True,
        "relevant_context": [1],
        "report": "acme.json",
        "explanation": "LEAK_EXPLANATION",
    }
    record.update(overrides)
    return record


def _write_claims(root: Path, records: list[object], *, name: str = "testmini.json") -> None:
    reports = root / "financial_reports"
    reports.mkdir(parents=True, exist_ok=True)
    filing = reports / "acme.json"
    if not filing.exists():
        filing.write_text(
            json.dumps(
                {
                    "url": "https://example.test/acme",
                    "report_type": "10-K",
                    "context": [{"id": 1, "context": "Revenue was 10.", "type": "paragraph"}],
                    "html_tables": [],
                }
            ),
            encoding="utf-8",
        )
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / name).write_text(json.dumps(records), encoding="utf-8")


# ---------------------------------------------------------------------------
# R-17: adapters hand the pipeline only the claim and evidence.
# ---------------------------------------------------------------------------

import ast  # noqa: E402

from proofgraph.adapters import strip_leak_fields  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ADAPTERS = ROOT / "proofgraph" / "adapters"
# Final-plan C12: pack and suite gold keys the leak list must also cover.
PACK_GOLD_KEYS = {"gold", "note", "ground_truth", "expected_verdict"}


@pytest.mark.parametrize("field", sorted(LEAK_FIELDS))
def test_each_leak_field_is_dropped_from_case_and_engine_view(tmp_path: Path, field: str):
    # entailment_label must stay a bool for the row to load; the others carry a sentinel.
    sentinel = f"SENTINEL-{field}-9d2e"
    _write_claims(tmp_path, [_numeric(**{field: True if field == "entailment_label" else sentinel})])
    case = list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))[0]
    for payload in (case.model_dump(), for_engine(case).model_dump()):
        assert sentinel not in json.dumps(payload)
        assert LEAK_FIELDS.isdisjoint(payload)


def test_engine_view_exposes_only_claim_and_evidence():
    for case in FinDVerAdapter(FIXTURE).cases("testmini", "passage", None):
        visible = for_engine(case)
        assert visible.answer is None
        assert visible.gold_evidence == []
        assert visible.claim and visible.sources
        # gold stays on the adapter's case, not the engine's copy
        assert case.answer is not None and case.gold_evidence


# docs/05 and docs/08, pinned here so shrinking LEAK_FIELDS cannot silently pass.
DOCUMENTED_LEAKS = {
    "explanation", "explaination", "python_calculation", "execution_result", "knowledge",
    "entailment_label",
}


def test_leak_list_keeps_every_documented_field():
    assert DOCUMENTED_LEAKS <= LEAK_FIELDS


def test_strip_leak_fields_removes_every_listed_key_and_keeps_the_rest():
    row = {key: f"SENTINEL-{key}" for key in DOCUMENTED_LEAKS} | {"statement": "kept", "example_id": "x"}
    assert strip_leak_fields(row) == {"statement": "kept", "example_id": "x"}


def test_adapters_do_not_import_gold_or_packs():
    files = list(ADAPTERS.rglob("*.py"))
    assert files
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            assert not any("review.packs" in n or "load_gold" in n for n in names), path.name


def test_leak_list_covers_pack_and_suite_gold_keys():
    assert PACK_GOLD_KEYS <= LEAK_FIELDS


@pytest.mark.parametrize("field", sorted(PACK_GOLD_KEYS))
def test_pack_gold_key_is_stripped_and_absent_from_engine_view(tmp_path: Path, field: str):
    sentinel = f"SENTINEL-{field}-4c1a"
    assert field not in strip_leak_fields({field: sentinel, "statement": "kept"})
    _write_claims(tmp_path, [_numeric(**{field: sentinel})])
    case = list(FinDVerAdapter(tmp_path).cases("testmini", "passage", None))[0]
    for payload in (case.model_dump(), for_engine(case).model_dump()):
        assert sentinel not in json.dumps(payload)
