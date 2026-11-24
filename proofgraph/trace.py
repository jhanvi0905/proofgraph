"""Trace: one JSON line per stage, flushed on write, so a crash keeps everything before it.

Stages take a Trace and do not write files themselves. That keeps them testable:
a test passes a MemoryTrace and reads its records.
"""

from __future__ import annotations

from pathlib import Path

from proofgraph.schema import TraceRecord


class Trace:
    def __init__(self, path: Path | None):
        self._path = path
        self.records: list[TraceRecord] = []
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, record: TraceRecord) -> None:
        self.records.append(record)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(record.to_json() + "\n")
                f.flush()


def memory_trace() -> Trace:
    return Trace(None)
