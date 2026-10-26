"""Proof-graph DOT export."""

from proofgraph.schema import ClaimProgram, Verdict


def to_dot(program: ClaimProgram, verdict: Verdict) -> str:
    """Render facts, links, and the verdict as a Graphviz DOT graph."""
    lines = ["digraph proof {", "  rankdir=LR;"]
    for fact in program.facts:
        label = _escape(fact.id) + "\\n" + _escape(fact.label)
        lines.append(f'  {fact.id} [shape=box, label="{label}"];')
    known = {fact.id for fact in program.facts}
    for link in program.links:
        lines.append(f'  {link.id} [shape=ellipse, label="{_escape(link.kind)}"];')
        for fact_id in link.inputs:
            if fact_id in known:
                lines.append(f"  {fact_id} -> {link.id};")
    label = verdict.verdict if verdict.label is None else f"{verdict.verdict}\\n{verdict.label}"
    lines.append(f'  verdict [shape=doubleoctagon, label="{label}"];')
    required = set(program.required)
    for link in program.links:
        if link.id in required:
            lines.append(f"  {link.id} -> verdict;")
    lines.append("}")
    return "\n".join(lines)


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')
