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
