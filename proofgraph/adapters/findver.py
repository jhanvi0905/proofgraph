"""FinDVer numeric claims in passage mode. See docs/05-datasets-and-eval.md.

Whole-filing mode is not this loader. Dev is the first 50 numeric rows of
``test.json``, in file order. ``seed`` is part of the adapter contract and
does not reshuffle these prefixes.
"""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Literal, cast

from proofgraph.adapters.base import strip_leak_fields
from proofgraph.schema import Case, Source

_ZWSP = "\u200b"
# Relative claims path, then the numeric cap for that split. None means all.
_SPLITS: dict[str, tuple[str, int | None]] = {
    "testmini": ("data/testmini.json", None),
    "dev": ("data/test.json", 50),
}
_KINDS: dict[str, Literal["text", "table"]] = {
    "paragraph": "text",
    "table": "table",
}


class FinDVerAdapter:
    """Load numeric FinDVer claims with the gold passages attached."""

    def __init__(self, root: Path | str = Path("data/FinDVer")) -> None:
        self.root = Path(root)

    def cases(
        self,
        split: str,
        mode: str,
        n: int | None,
        seed: int = 7,
    ) -> Iterator[Case]:
        """Yield numeric passage cases. ``seed`` does not change membership."""
        del seed
        if mode != "passage":
            raise ValueError(f"FinDVer loader only supports passage mode, got {mode!r}")
        if n is not None and n < 0:
            raise ValueError(f"n must be >= 0, got {n}")
        spec = _SPLITS.get(split)
        if spec is None:
            raise ValueError(f"unknown FinDVer split {split!r}")
        relative, cap = spec
        if cap is None or n is None:
            limit = cap if n is None else n
        else:
            limit = min(cap, n)
        produced = 0
        for value in _read_records(self.root / relative):
            record = _record(value)
            subset = record.get("subset")
            if subset in {"ie", "knowledge"}:
                continue
            if subset != "numeric":
                raise ValueError(f"unknown FinDVer subset {subset!r}")
            if limit is not None and produced >= limit:
                break
            yield _case_from_record(self.root, record)
            produced += 1


def _case_from_record(root: Path, record: dict[str, object]) -> Case:
    example_id = _require_str(record, "example_id")
    if "entailment_label" not in record:
        raise ValueError(f"{example_id}: entailment_label must be bool")
    answer = _answer(example_id, record["entailment_label"])
    kept = strip_leak_fields(record)
    statement = _require_str(kept, "statement")
    _require_str(kept, "split")
    report = _require_str(kept, "report")
    raw_ids = kept.get("relevant_context")
    if not isinstance(raw_ids, list) or len(raw_ids) == 0:
        raise ValueError(f"{example_id}: relevant_context must be a non-empty list")
    sources = _sources(root, example_id, report, raw_ids)
    return Case(
        id=example_id,
        dataset="findver",
        mode="passage",
        claim=statement,
        sources=sources,
        answer=answer,
        gold_evidence=[source.id for source in sources],
    )


def _answer(example_id: str, label: object) -> Literal["SUPPORTED", "CONTRADICTED"]:
    if label is True:
        return "SUPPORTED"
    if label is False:
        return "CONTRADICTED"
    raise ValueError(f"{example_id}: entailment_label must be bool")


def _sources(root: Path, example_id: str, report: str, raw_ids: list[object]) -> list[Source]:
    filing = _record(_read_json(_report_path(root, report)), f"{example_id} filing")
    context = filing.get("context")
    if not isinstance(context, list):
        raise ValueError(f"{example_id}: filing context must be a list")
    index: dict[str, dict[str, object]] = {}
    for item in context:
        passage = _record(item, f"{example_id} passage")
        key = _passage_key(passage.get("id"), example_id)
        if key in index:
            raise ValueError(f"{example_id}: duplicate passage id {key}")
        index[key] = passage
    sources: list[Source] = []
    seen: set[str] = set()
    for raw_id in raw_ids:
        key = _passage_key(raw_id, example_id)
        if key in seen:
            raise ValueError(f"{example_id}: duplicate passage id {key}")
        seen.add(key)
        passage = index.get(key)
        if passage is None:
            raise ValueError(f"{example_id}: passage {key} is not in the filing")
        sources.append(_source(example_id, key, passage))
    return sources


def _source(example_id: str, key: str, passage: dict[str, object]) -> Source:
    kind_name = passage.get("type")
    if not isinstance(kind_name, str) or kind_name not in _KINDS:
        raise ValueError(f"{example_id}: passage {key} type must be paragraph or table")
    text = passage.get("context")
    if not isinstance(text, str):
        raise ValueError(f"{example_id}: passage {key} context must be a string")
    if kind_name == "table":
        text = text.replace(_ZWSP, "")
    return Source(id=f"p{key}", kind=_KINDS[kind_name], text=text)


def _report_path(root: Path, report: str) -> Path:
    relative = Path(report)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"invalid report filename {report!r}")
    return root / "financial_reports" / relative


def _read_records(path: Path) -> list[object]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"FinDVer claims file must be a list: {path}")
    return payload


def _read_json(path: Path) -> object:
    if not path.is_file():
        raise FileNotFoundError(f"FinDVer file not found: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _record(value: object, what: str = "FinDVer record") -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{what} must be an object")
    return cast(dict[str, object], value)


def _require_str(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or value == "":
        found = record.get("example_id", "?")
        raise ValueError(f"{found}: field {key} must be a non-empty string")
    return value


def _passage_key(value: object, example_id: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{example_id}: passage id must be a string or int, got {value!r}")
    if isinstance(value, str) and value == "":
        raise ValueError(f"{example_id}: passage id must be non-empty")
    return str(value)
