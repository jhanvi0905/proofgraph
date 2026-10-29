"""Text-packet screen. The stamp comes from run_program, not from the wrapper."""

import json

from proofgraph.adapters.base import for_engine
from proofgraph.engine.route import run_program
from proofgraph.schema import Case, ClaimProgram

from app.streamlit_app import (
    PACKET_DIR,
    ReplayError,
    packet_catalog,
    render_review,
    review_packet,
)


def _load(name: str) -> dict:
    return json.loads((PACKET_DIR / name).read_text(encoding="utf-8"))


def _section(html: str, section_id: str) -> str:
    marker = f"id='links-{section_id}'"
    start = html.index(marker)
    nxt = html.find("id='links-", start + len(marker))
    return html[start:] if nxt < 0 else html[start:nxt]


def test_catalog_leads_with_the_shared_file_and_other_worlds():
    keys = [item.key for item in packet_catalog()]
    assert keys[0] == "ship-export-this-week.json"
    assert "late-fee-overcharge.json" in keys
    assert "numeric-val-0.json" in keys
    lead = packet_catalog()[0].payload
    assert "expected" not in lead
    assert "answer" not in lead["case"]
    assert "gold_evidence" not in lead["case"]
    assert [source["id"] for source in lead["case"]["sources"]] == [
        "usage_note",
        "support_note",
        "release_note",
    ]


def test_lead_screen_matches_run_program():
    raw = _load("ship-export-this-week.json")
    review = review_packet(raw)
    case = for_engine(Case.model_validate(raw["case"]))
    program = ClaimProgram.model_validate(raw["program"])
    verdict = run_program(case, program)

    assert review.packet.verdict == verdict.verdict == "CONTRADICTED"
    assert review.packet.label == verdict.label == "COMPUTED"
    assert review.role == "demo"
    assert review.world == "product decision"
    assert review.case.dataset == "freight"
    assert review.case.id == "ship-export-this-week"
    assert [row.status for row in review.packet.link_results] == ["pass", "fail", "pass"]
    assert [row.link_id for row in review.packet.link_results] == ["l_use", "l_cost", "l_should"]

    html = render_review(review)
    passed = _section(html, "pass")
    failed = _section(html, "fail")
    opened = _section(html, "unresolved")
    aside = _section(html, "aside").split("One verdict")[0]

    assert "l_use" in passed
    assert "pass" in passed
    assert "40%" in passed
    assert "usage_note" in passed
    assert "Export is used by 40% of weekly active accounts." in passed
    assert "l_should" not in passed
    assert "l_cost" not in passed

    assert "l_cost" in failed
    assert "fail" in failed
    assert "expression does not hold" in failed
    assert "$4,200" in failed
    assert "support_note" in failed
    assert "Export support costs $4,200 a month." in failed

    assert "UNVERIFIABLE_PART" in opened
    assert "The release note does not mention the export button or this week." in opened
    assert "release_note" in opened
    assert "The release this cycle covers search filters and the billing page." in opened

    assert "l_should" in aside
    assert "ASSUMED" in aside
    assert "did not decide the verdict" in aside
    assert "CONTRADICTED" not in aside
    assert "pass" not in aside

    assert verdict.verdict in html
    assert "gold_evidence" not in html
    assert "expected" not in html
    assert "which contradicts the claimed" not in html
    assert "Sample packet" not in html


def test_another_world_uses_the_same_function():
    raw = _load("late-fee-overcharge.json")
    review = review_packet(raw)
    verdict = run_program(
        for_engine(Case.model_validate(raw["case"])),
        ClaimProgram.model_validate(raw["program"]),
    )
    assert review.packet.verdict == verdict.verdict
    assert review.packet.label == verdict.label
    assert review.world == "contract late fee"
    html = render_review(review)
    assert verdict.verdict in html
    assert "gold_evidence" not in html
    assert "expected" not in html


def test_filing_packet_without_a_program_does_not_invent_a_stamp():
    raw = _load("numeric-val-0.json")
    try:
        review_packet(raw)
    except ReplayError as exc:
        assert "no program" in str(exc)
    else:
        raise AssertionError("a packet with no program must not produce a stamp")


def test_a_different_program_changes_the_lead_verdict():
    raw = _load("ship-export-this-week.json")
    raw["program"] = {"facts": [], "links": [], "required": [], "unverifiable_parts": []}
    review = review_packet(raw)
    assert review.packet.verdict == "UNRESOLVED"
    assert review.packet.verdict != "CONTRADICTED"
