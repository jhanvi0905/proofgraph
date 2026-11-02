"""Read-only: which stored quotes would reject_quote drop, and how many words each has.

Reads cached run outputs (one JSON per case, each with a ``cards`` list holding ``quote``).
Page text is not stored there, so expansion cannot be measured; this shows rejection only.
No model calls, no network, no writes.

Usage: uv run python scripts/measure_bounds.py DIR_OF_JSON
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from proofgraph.review.bounds import reject_quote


def main(argv: list[str]) -> int:
    folder = Path(argv[1]) if len(argv) > 1 else None
    if folder is None or not folder.is_dir():
        print(__doc__)
        return 2
    total = rejected = 0
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for card in data.get("cards", []):
            quote = card.get("quote") or ""
            total += 1
            bad = reject_quote(quote)
            rejected += bad
            print(f"{path.stem}\t{card.get('id', '')}\t{len(quote.split())} words\t"
                  f"{'REJECT' if bad else 'keep'}\t{quote[:220]!r}")
    print(f"{rejected} of {total} quotes would be rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
