"""The domain layer is frozen: every listed file must be byte-identical to its hash at the freeze.

Parser, ingest and retrieval may change (layout has nothing to do with insurance meaning);
predicates, slots, the arbiter, the comparators, the passes and the labels may not.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FREEZE = json.loads((ROOT / "data" / "freeze.json").read_text())


@pytest.mark.parametrize("path", sorted(FREEZE["files"]))
def test_frozen_file_is_unchanged(path):
    digest = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    assert digest == FREEZE["files"][path], f"{path} changed after the domain freeze"


def test_the_freeze_covers_the_domain_layer():
    must = {"proofgraph/arbiter.py", "proofgraph/numbers.py", "proofgraph/assertions.py", "proofgraph/schema.py",
            "proofgraph/passes.py", "data/predicates.json", "data/slots.json", "data/document_mappings.json"}
    assert must <= set(FREEZE["files"])
