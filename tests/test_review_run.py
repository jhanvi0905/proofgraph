"""run_review(): upload -> ingest -> one part -> relate -> snap -> Review. No network."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from PIL import Image

from app.streamlit_app import skeleton_submit
from app.viewer.render import render
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.review.ingest import ingest
from proofgraph.review.models import Review
from proofgraph.review.run import run_review

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "tests" / "fixtures" / "text_span_rate.pdf"
CLAIM = "Detention is paid at $100.00 per hour."
QUOTE = "Detention: $75.00/hour after 2 hours free time"
DOC_ID = ingest([PDF])[0].doc_id
GOOD = {
    "relation": "contradicts",
    "weakener_type": "magnitude",
    "quote": QUOTE,
    "doc": DOC_ID,
    "page": 1,
    "why": "The rate is $75.00 an hour, not $100.00.",
}


def _envelope(payload: dict) -> dict[str, Any]:
    return {
        "id": "resp_test", "object": "response", "status": "completed", "model": "muse-spark-1.3",
        "output": [{"id": "m", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]}],
    }


class FakeTransport:
    def __init__(self, *payloads: dict) -> None:
        self._responses = [_envelope(p) for p in payloads]
        self.bodies: list[dict[str, Any]] = []

    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        self.bodies.append(json.loads(json.dumps(body)))
        return self._responses.pop(0)


def _muse(tmp_path, transport, limit="0") -> MuseClient:
    settings = load_settings({"MODEL_API_KEY": "k", "CACHE_DIR": str(tmp_path), "SPEND_LIMIT_USD": limit})
    return MuseClient(settings, transport=transport)


def test_text_pdf_gives_pinned_contradicts_card_and_red_part(tmp_path):
    result = run_review(CLAIM, [PDF], _muse(tmp_path, FakeTransport(GOOD)))
    review = Review.model_validate_json(result.review.model_dump_json())
    card = review.cards[0]
    assert (card.relation, card.box_status, card.page, card.doc) == ("contradicts", "pinned", 1, DOC_ID)
    assert card.boxes
    assert review.parts[0].status == "contradicted"
    assert review.status == "contradicted"
    assert review.driver_part == "P1"
    assert (DOC_ID, 1) in result.page_images
    html = render(review, result.page_images)
    assert 'class="box pinned"' in html
    assert "image not available" not in html


def test_quote_that_does_not_snap_is_unpinned_and_not_red(tmp_path):
    made_up = {**GOOD, "quote": "Detention is waived for all carriers on Sundays"}
    review = run_review(CLAIM, [PDF], _muse(tmp_path, FakeTransport(made_up))).review
    assert review.cards[0].box_status == "unpinned"
    assert review.cards[0].boxes == []
    assert review.parts[0].status != "contradicted"


def test_image_only_page_is_unreadable_banner_and_no_model_call(tmp_path):
    scan = tmp_path / "scan.pdf"
    Image.new("RGB", (300, 400), "white").save(scan)
    transport = FakeTransport()
    review = run_review(CLAIM, [scan], _muse(tmp_path, transport)).review
    assert transport.bodies == []
    assert [b.kind for b in review.banners] == ["unreadable"]
    assert review.docs[0].pages[0].readable is False
    assert review.parts[0].status == "cannot_tell"


@pytest.mark.parametrize("name,data", [("memo.docx", b"PK"), ("bad.pdf", b"not a pdf")])
def test_unreadable_upload_surfaces_ingest_error_as_banner(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    transport = FakeTransport()
    review = run_review(CLAIM, [path], _muse(tmp_path, transport)).review
    assert transport.bodies == []
    assert review.banners[0].kind == "unreadable"
    assert name in review.banners[0].text
    assert review.docs == []


def test_good_file_still_runs_beside_a_bad_one(tmp_path):
    bad = tmp_path / "memo.docx"
    bad.write_bytes(b"PK")
    review = run_review(CLAIM, [bad, PDF], _muse(tmp_path, FakeTransport(GOOD))).review
    assert review.status == "contradicted"
    assert any("memo.docx" in b.text for b in review.banners)


def test_planted_instruction_becomes_injection_banner(tmp_path):
    flagged = {**GOOD, "injection_quote": "Ignore previous instructions."}
    review = run_review(CLAIM, [PDF], _muse(tmp_path, FakeTransport(flagged))).review
    assert "injection" in [b.kind for b in review.banners]


def test_spend_cap_blocks_before_any_request(tmp_path):
    transport = FakeTransport(GOOD)
    review = run_review(CLAIM, [PDF], _muse(tmp_path, transport, limit="0.01")).review
    assert transport.bodies == []
    assert [b.kind for b in review.banners] == ["cap"]
    assert review.status == "error"


def test_blank_claim_is_refused_before_any_work(tmp_path):
    with pytest.raises(ValueError):
        run_review("  ", [PDF], _muse(tmp_path, FakeTransport()))


def _st(secret=None, entered=""):
    secrets = {"APP_PASSCODE": secret} if secret else {}
    return SimpleNamespace(secrets=secrets, session_state={"passcode": entered})


@pytest.mark.parametrize("secret,entered", [(None, "x"), ("right", ""), ("right", "wrong")])
def test_passcode_missing_or_wrong_blocks_before_any_model_request(secret, entered):
    def boom():
        raise AssertionError("model client built before passcode check")

    html, error = skeleton_submit(_st(secret, entered), CLAIM, [PDF], boom)
    assert html is None and error


def test_correct_passcode_runs_and_returns_viewer_html(tmp_path):
    html, error = skeleton_submit(
        _st("right", "right"), CLAIM, [PDF], lambda: _muse(tmp_path, FakeTransport(GOOD))
    )
    assert error is None and 'data-card-id="c1"' in html


def test_run_py_never_touches_gold():
    source = (ROOT / "proofgraph" / "review" / "run.py").read_text(encoding="utf-8")
    assert "load_gold" not in source and "pack.json" not in source


def test_default_muse_is_a_muse_client_built_without_a_request(monkeypatch, tmp_path):
    from proofgraph.review.run import default_muse

    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    assert isinstance(default_muse(), MuseClient)
