"""One screen that replays the checker. Opening it does not call a model."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from proofgraph.engine.route import run_program
from proofgraph.engine.spans import propose_spans
from proofgraph.schema import Case, ClaimProgram, Verdict

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures"
FIXTURES = {
    "Detention": FIXTURE_DIR / "detention_program.json",
    "The sum": FIXTURE_DIR / "sum_program.json",
}


class ReplayError(Exception):
    """A fixture problem the screen can show as text."""


@dataclass(frozen=True)
class FactRow:
    quote: str
    grounded: bool


@dataclass(frozen=True)
class LinkRow:
    link_id: str
    status: str
    strength: str
    detail: str


@dataclass(frozen=True)
class SpanRow:
    quote: str
    value: int | float | str
    scale: str | None
    kind: str


@dataclass(frozen=True)
class ReplayPacket:
    claim: str
    verdict: str
    label: str | None
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    fetch: tuple[str, ...]
    fact_checks: tuple[FactRow, ...]
    link_results: tuple[LinkRow, ...]


def build_packet(path: Path) -> ReplayPacket:
    """Run one local fixture through the engine. No network."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReplayError(f"could not read fixture: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReplayError("fixture must contain case and program")
    try:
        case = Case.model_validate(payload["case"])
        program = ClaimProgram.model_validate(payload["program"])
    except KeyError as exc:
        raise ReplayError("fixture must contain case and program") from exc
    except ValidationError as exc:
        raise ReplayError(f"fixture does not match the schema: {exc}") from exc
    verdict = run_program(case, program)
    return _packet(case, program, verdict)


def span_rows(text: str) -> tuple[SpanRow, ...]:
    """Candidate spans from plain text. No model call."""

    if not text.strip():
        return ()
    rows: list[SpanRow] = []
    for fact in propose_spans(text):
        value = fact.value if fact.value is not None else ""
        rows.append(
            SpanRow(
                quote=fact.quote or "",
                value=value,
                scale=fact.scale,
                kind=fact.kind,
            )
        )
    return tuple(rows)


def value_text(value: int | float | str) -> str:
    """Show a whole number without a trailing decimal."""

    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def failure_message(exc: BaseException) -> str:
    """Text for the page. A traceback is not included."""

    text = str(exc).strip()
    if not text or text.startswith("Traceback"):
        return exc.__class__.__name__
    return text.splitlines()[0].strip() or exc.__class__.__name__


def main() -> None:
    """Draw the one review screen. Streamlit stays inside this call."""

    import streamlit as st

    st.set_page_config(page_title="Claim checker", layout="centered")
    st.header("Claim checker")
    st.write("Code decides. The model does not grade the answer.")
    choice = st.radio(
        "Show",
        ["Detention", "The sum", "Paste text"],
        horizontal=True,
    )
    if choice == "Paste text":
        _show_spans(st)
        return
    _show_fixture(st, FIXTURES[choice])


def _packet(case: Case, program: ClaimProgram, verdict: Verdict) -> ReplayPacket:
    quotes = {fact.id: fact.quote or "" for fact in program.facts}
    return ReplayPacket(
        claim=case.claim,
        verdict=verdict.verdict,
        label=verdict.label,
        reasons=tuple(verdict.reasons),
        reason_codes=tuple(verdict.reason_codes),
        fetch=tuple(verdict.fetch),
        fact_checks=tuple(
            FactRow(quote=quotes.get(check.fact_id, ""), grounded=check.status == "grounded")
            for check in verdict.fact_checks
        ),
        link_results=tuple(
            LinkRow(
                link_id=result.link_id,
                status=result.status,
                strength=result.strength,
                detail=result.detail,
            )
            for result in verdict.link_results
        ),
    )


def _show_fixture(st, path: Path) -> None:
    try:
        packet = build_packet(path)
    except Exception as exc:
        st.error(failure_message(exc))
        return
    _show_packet(st, packet)


def _show_packet(st, packet: ReplayPacket) -> None:
    _text(st, packet.claim)
    st.title(packet.verdict)
    st.header(packet.label if packet.label else "none")
    if packet.reasons:
        for reason in packet.reasons:
            _text(st, reason, scale="reason")
    else:
        _text(st, "No reason recorded.", scale="reason")
    st.markdown("**Reason codes**")
    st.write(", ".join(packet.reason_codes) if packet.reason_codes else "none")
    st.markdown("**What to fetch**")
    if packet.fetch:
        for line in packet.fetch:
            _text(st, line)
    else:
        st.write("Nothing to fetch.")
    st.divider()
    st.subheader("Fact checks")
    if not packet.fact_checks:
        st.write("No fact checks.")
    for row in packet.fact_checks:
        _text(st, row.quote or "No quote")
        st.write("grounded" if row.grounded else "not grounded")
    st.subheader("Link results")
    if not packet.link_results:
        st.write("No link results.")
    for row in packet.link_results:
        st.write(f"{row.link_id} · {row.status} · {row.strength}")
        if row.detail:
            _text(st, row.detail)


def _show_spans(st) -> None:
    text = st.text_area("Source text", height=180)
    if not text.strip():
        st.write("Paste plain text to see candidate spans.")
        return
    rows = span_rows(text)
    if not rows:
        st.write("No number, date, or time in that text.")
        return
    for row in rows:
        _text(st, row.quote)
        scale = row.scale if row.scale else "none"
        st.write(f"{value_text(row.value)} · {scale} · {row.kind}")


def _text(st, text: str, *, scale: str = "body") -> None:
    """Show text as text. Dollar amounts stay on the page."""

    size, weight = {
        "body": ("1.05rem", "400"),
        "reason": ("1.45rem", "650"),
    }[scale]
    safe = html.escape(text)
    st.html(
        f"<p style='font-size:{size};font-weight:{weight};"
        f"line-height:1.45;margin:0.25rem 0 0.85rem 0'>{safe}</p>"
    )


if __name__ == "__main__":
    main()
