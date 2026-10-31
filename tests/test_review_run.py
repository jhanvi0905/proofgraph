"""run_review(): upload -> ingest -> one part -> relate -> snap -> Review. No network."""

import ast
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest
from PIL import Image

from app.streamlit_app import Refusal, review_events, skeleton_submit
from app.viewer.render import render
from proofgraph.clients.muse import MuseClient
from proofgraph.config import load_settings
from proofgraph.review.ingest import ingest
from proofgraph.review.models import Review
from proofgraph.review import run as run_mod
from proofgraph.review.run import AllDone, PartDone, PartsReady, run_review

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


SPLIT1 = {"parts": [{"text": CLAIM}]}


def _envelope(payload: dict) -> dict[str, Any]:
    return {
        "id": "resp_test", "object": "response", "status": "completed", "model": "muse-spark-1.3",
        "output": [{"id": "m", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": json.dumps(payload), "annotations": []}]}],
    }


def finish(events) -> "run_mod.RunResult":
    """Drain an event stream and return the final result."""
    last = None
    for last in events:
        pass
    assert isinstance(last, AllDone)
    return last.result


def _run(claim, paths, muse, **kw):
    return finish(run_review(claim, paths, muse, checker=kw.pop("checker", _agree), **kw))


def _agree(quote, part):
    return "contradicts" if "Detention" in quote else "entails"


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
    result = _run(CLAIM, [PDF], _muse(tmp_path, FakeTransport(SPLIT1, GOOD)))
    review = Review.model_validate_json(result.review.model_dump_json())
    card = review.cards[0]
    assert (card.relation, card.box_status, card.page, card.doc) == ("contradicts", "pinned", 1, DOC_ID)
    assert card.boxes
    assert review.parts[0].status == "contradicted"
    assert review.status == "contradicted"
    assert review.driver_part == "p1"
    assert (DOC_ID, 1) in result.page_images
    html = render(review, result.page_images)
    assert 'class="box pinned"' in html
    assert "image not available" not in html


def test_quote_that_does_not_snap_is_unpinned_and_not_red(tmp_path):
    made_up = {**GOOD, "quote": "Detention is waived for all carriers on Sundays"}
    review = _run(CLAIM, [PDF], _muse(tmp_path, FakeTransport(SPLIT1, made_up))).review
    assert review.cards[0].box_status == "unpinned"
    assert review.cards[0].boxes == []
    assert review.parts[0].status != "contradicted"


def test_image_only_page_is_unreadable_banner_and_no_model_call(tmp_path):
    scan = tmp_path / "scan.pdf"
    Image.new("RGB", (300, 400), "white").save(scan)
    transport = FakeTransport()
    review = _run(CLAIM, [scan], _muse(tmp_path, transport)).review
    assert transport.bodies == []
    assert [b.kind for b in review.banners] == ["unreadable"]
    assert review.docs[0].pages[0].readable is False
    assert review.parts[0].status == "cannot_tell"


@pytest.mark.parametrize("name,data", [("memo.docx", b"PK"), ("bad.pdf", b"not a pdf")])
def test_unreadable_upload_surfaces_ingest_error_as_banner(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    transport = FakeTransport()
    review = _run(CLAIM, [path], _muse(tmp_path, transport)).review
    assert transport.bodies == []
    assert review.banners[0].kind == "unreadable"
    assert name in review.banners[0].text
    assert review.docs == []


def test_good_file_still_runs_beside_a_bad_one(tmp_path):
    bad = tmp_path / "memo.docx"
    bad.write_bytes(b"PK")
    review = _run(CLAIM, [bad, PDF], _muse(tmp_path, FakeTransport(SPLIT1, GOOD))).review
    assert review.status == "contradicted"
    assert any("memo.docx" in b.text for b in review.banners)


def test_planted_instruction_becomes_injection_banner(tmp_path):
    flagged = {**GOOD, "injection_quote": "Ignore previous instructions."}
    review = _run(CLAIM, [PDF], _muse(tmp_path, FakeTransport(SPLIT1, flagged))).review
    assert "injection" in [b.kind for b in review.banners]


def test_spend_cap_blocks_before_any_request(tmp_path):
    transport = FakeTransport(SPLIT1, GOOD)
    review = _run(CLAIM, [PDF], _muse(tmp_path, transport, limit="0.01")).review
    assert transport.bodies == []
    assert [b.kind for b in review.banners] == ["cap"]
    assert review.status == "error"
    assert review.parts[0].status == "error"


def test_blank_claim_is_refused_before_any_work(tmp_path):
    with pytest.raises(ValueError):
        _run("  ", [PDF], _muse(tmp_path, FakeTransport()))


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
        _st("right", "right"), CLAIM, [PDF], lambda: _muse(tmp_path, FakeTransport(SPLIT1, GOOD))
    )
    assert error is None and 'data-card-id="c1"' in html


def test_run_py_never_touches_gold():
    source = (ROOT / "proofgraph" / "review" / "run.py").read_text(encoding="utf-8")
    assert "load_gold" not in source and "pack.json" not in source


def test_default_muse_is_a_muse_client_built_without_a_request(monkeypatch, tmp_path):
    from proofgraph.review.run import default_muse

    monkeypatch.setenv("CACHE_DIR", str(tmp_path))
    assert isinstance(default_muse(), MuseClient)


# ---- R-15: per-part parallel run, events in completion order ----

CLAIM2 = "Detention is paid at $100.00 per hour. Linehaul is $1,840.00."
PART_A, PART_B = "Detention is paid at $100.00 per hour.", "Linehaul is $1,840.00."
RELATE_A = GOOD
RELATE_B = {**GOOD, "relation": "supports", "weakener_type": None, "quote": "Linehaul: $1,840.00",
            "why": "The linehaul rate matches."}


class SmartTransport:
    """Routes by prompt: split reply, or a per-part relate reply after a per-part delay."""

    def __init__(self, delays=None, fail=(), split=None):
        self.delays, self.fail = delays or {}, set(fail)
        self.split = split or {"parts": [{"text": PART_A}, {"text": PART_B}]}
        self.relate_started: list[str] = []
        self.active = self.peak = 0
        self.lock = threading.Lock()
        self.split_calls = 0

    def create(self, body):
        prompt = body["input"]
        if "CLAIM PART:" not in prompt:
            self.split_calls += 1
            return _envelope(self.split)
        part = PART_A if f"CLAIM PART:\n{PART_A}" in prompt else PART_B
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.relate_started.append(part)
        try:
            time.sleep(self.delays.get(part, 0))
            if part in self.fail:
                raise RuntimeError("upstream down")
            return _envelope(RELATE_A if part == PART_A else RELATE_B)
        finally:
            with self.lock:
                self.active -= 1


def test_part_done_events_arrive_in_completion_order_not_part_order(tmp_path):
    transport = SmartTransport(delays={PART_A: 0.4, PART_B: 0.0})
    done = [e.part_id for e in run_review(CLAIM2, [PDF], _muse(tmp_path, transport), checker=_agree)
            if isinstance(e, PartDone)]
    assert done == ["p2", "p1"]


def test_parts_ready_comes_before_any_part_finishes(tmp_path):
    transport = SmartTransport(delays={PART_A: 0.1, PART_B: 0.1})
    events = list(run_review(CLAIM2, [PDF], _muse(tmp_path, transport), checker=_agree))
    kinds = [type(e).__name__ for e in events]
    assert kinds == ["PartsReady", "PartDone", "PartDone", "AllDone"]
    ready = events[0]
    assert [(p.id, p.status, p.text) for p in ready.parts] == [("p1", "checking", PART_A), ("p2", "checking", PART_B)]


def test_a_failing_part_is_error_and_the_other_finishes(tmp_path):
    transport = SmartTransport(fail=[PART_A])
    review = _run(CLAIM2, [PDF], _muse(tmp_path, transport)).review
    by_id = {p.id: p for p in review.parts}
    assert by_id["p1"].status == "error" and by_id["p2"].status == "supported"
    assert any(b.kind == "checker_unavailable" and "upstream down" in b.text for b in review.banners)
    assert review.status == "error"


def test_final_review_has_every_part_in_order_with_checks_and_keeps_disagreeing_card(tmp_path):
    def checker(quote, part):
        return "contradicts" if "Detention" in quote else "not_mentioned"  # supports + not_mentioned = disagrees

    transport = SmartTransport(delays={PART_A: 0.2})
    review = _run(CLAIM2, [PDF], _muse(tmp_path, transport), checker=checker).review
    assert [p.id for p in review.parts] == ["p1", "p2"]
    assert [c.id for c in review.cards] == ["c1", "c2"]
    assert [c.part for c in review.cards] == ["p1", "p2"]
    assert [p.card_ids for p in review.parts] == [["c1"], ["c2"]]
    assert [c.check for c in review.cards] == ["agrees", "disagrees"]
    assert review.parts[1].status == "supported"  # a disagreement never hides or changes status
    assert review.status == "contradicted" and review.driver_part == "p1"
    Review.model_validate_json(review.model_dump_json())


def test_split_failure_is_a_banner_not_a_crash(tmp_path):
    transport = SmartTransport(split={"parts": [{"text": "not in the claim"}]})
    review = _run(CLAIM2, [PDF], _muse(tmp_path, transport)).review
    assert review.status == "error" and review.parts[0].status == "error"
    assert "EXTRACTION_FAILED" in review.banners[0].text
    assert transport.relate_started == []


def test_worker_threads_never_reach_streamlit():
    tree = ast.parse((ROOT / "proofgraph" / "review" / "run.py").read_text(encoding="utf-8"))
    names = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    names += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    assert not [n for n in names if n.split(".")[0] in {"streamlit", "app"}]
    code = "import sys, proofgraph.review.run; sys.exit(1 if 'streamlit' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", code], cwd=ROOT).returncode == 0


def test_cap_blocks_before_split_is_called(tmp_path):
    transport = SmartTransport()
    review = _run(CLAIM2, [PDF], _muse(tmp_path, transport, limit="0.01")).review
    assert transport.split_calls == 0 and transport.relate_started == []
    assert [b.kind for b in review.banners] == ["cap"]


def test_split_is_not_called_when_passcode_fails():
    def boom():
        raise AssertionError("model client built before passcode check")

    assert [type(e) for e in review_events(_st("right", "wrong"), CLAIM2, [PDF], boom)] == [Refusal]


def test_at_most_four_parts_run_at_once(tmp_path):
    texts = [f"Item {i} costs $1,840.00." for i in range(9)]
    claim = " ".join(texts)
    peak = {"now": 0, "max": 0}
    lock = threading.Lock()

    class Wide(SmartTransport):
        def create(self, body):
            prompt = body["input"]
            if "CLAIM PART:" not in prompt:
                return _envelope({"parts": [{"text": t} for t in texts]})
            with lock:
                peak["now"] += 1
                peak["max"] = max(peak["max"], peak["now"])
            time.sleep(0.05)
            with lock:
                peak["now"] -= 1
            return _envelope(RELATE_B)

    review = _run(claim, [PDF], _muse(tmp_path, Wide())).review
    assert len(review.parts) == 9 and 1 < peak["max"] <= 4


def test_cap_gate_runs_before_split_is_even_called(tmp_path, monkeypatch):
    """The transport never being hit is not enough: split itself must not run when capped."""
    called = []
    monkeypatch.setattr(run_mod, "split", lambda *a, **k: called.append(1))
    review = _run(CLAIM2, [PDF], _muse(tmp_path, SmartTransport(), limit="0.01")).review
    assert called == []
    assert [b.kind for b in review.banners] == ["cap"]
