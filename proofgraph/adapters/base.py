"""Adapter contract and leak-field stripping. See docs/05 and docs/06."""

from collections.abc import Iterator
from typing import Protocol

from proofgraph.schema import Case

# docs/05 names the FinDVer fields that contain the answer or the worked
# solution. docs/08 also bars entailment_label from the engine; the adapter
# maps that bool onto Case.answer, then strips the raw key. Final-plan C12 adds
# the pack and suite gold keys (gold, note, ground_truth, expected_verdict).
LEAK_FIELDS = frozenset(
    {
        "explanation",
        "explaination",
        "python_calculation",
        "execution_result",
        "knowledge",
        "entailment_label",
        "gold",
        "note",
        "ground_truth",
        "expected_verdict",
    }
)


def strip_leak_fields(record: dict[str, object]) -> dict[str, object]:
    """Copy a raw row without fields that reveal the answer."""
    return {key: value for key, value in record.items() if key not in LEAK_FIELDS}


def for_engine(case: Case) -> Case:
    """Return the case a proposer or the engine may see.

    ``answer`` and ``gold_evidence`` stay on the adapter's case for
    ``scripts/report.py`` only.
    """
    return case.model_copy(update={"answer": None, "gold_evidence": []})


class Adapter(Protocol):
    """One dataset plugged into the shared pipeline."""

    def cases(self, split: str, mode: str, n: int | None, seed: int = 7) -> Iterator[Case]: ...
