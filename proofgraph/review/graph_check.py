"""Second read of the deciding statements (N5): Muse Spark Open, blind, through ``check_card_detail``.

The checker is handed exactly two strings: the deciding statement together with its attached
exception or condition, and the claim part. It never sees the comparator's label, the relation, the
verdict, the page or any other statement. The label is used only afterwards, to compare.
"""

from __future__ import annotations

from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor

import networkx as nx

from proofgraph.clients.checker import blind_wording
from proofgraph.review.check import MAX_WORKERS, Checker, check_card_detail
from proofgraph.review.compare import Item, attached_exceptions
from proofgraph.review.models import CheckAnswer, CheckName

MAX_SECOND_READS = 6  # per claim part
_RELATION = {"agrees": "supports", "conflicts": "contradicts", "qualifies": "weakens"}


def checker_text(g: nx.MultiDiGraph, rule: str) -> str:
    parts = [g.nodes[rule]["quote"]]
    parts += [f"Exception or condition: {g.nodes[e]['quote']}" for e in attached_exceptions(g, rule)]
    return "\n".join(parts)


def second_reads(part_text: str, labels: Sequence[Item], g: nx.MultiDiGraph, *, checker: Checker = blind_wording,
                 cap: int = MAX_SECOND_READS) -> dict[str, tuple[CheckName, CheckAnswer | None]]:
    """Check up to ``cap`` labelled statements (conflicts first); the rest are not run."""
    order = {"conflicts": 0, "qualifies": 1, "agrees": 2}
    todo = sorted((i for i in labels if i.label in _RELATION), key=lambda i: (order[i.label], i.id))[:cap]

    def run(item: Item) -> tuple[str, tuple[CheckName, CheckAnswer | None]]:
        return item.id, check_card_detail(checker_text(g, item.id), part_text,
                                          relation=_RELATION[item.label], checker=checker)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        done = dict(pool.map(run, todo))
    return {i.id: done.get(i.id, ("not_run", None)) for i in labels}


def confirm_support(deciding: Sequence[str], labels: dict[str, Item], checks: dict[str, tuple[CheckName, CheckAnswer | None]],
                    part_text: str, g: nx.MultiDiGraph, *, checker: Checker = blind_wording
                    ) -> dict[str, tuple[CheckName, CheckAnswer | None]]:
    """C2: a part that becomes supported always gets its deciding statements second-read, whatever the claim budget."""
    pending = [labels[i] for i in deciding if i in labels and checks.get(i, ("not_run", None))[0] == "not_run"]
    if not pending:
        return checks
    return {**checks, **second_reads(part_text, pending, g, checker=checker, cap=len(pending))}
