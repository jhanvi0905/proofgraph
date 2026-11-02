"""Evidence set robustness: retry relate_set once, then fall back to single relate. No network."""

import json

from proofgraph.review.run import AllDone, run_review
from proofgraph.spend import SpendCapReached
from proofgraph.clients.muse import MuseTimeoutError
from tests.test_relate_set import (CLAIM, PDF, Q_DET, SPLIT1, FakeTransport, _agree, _entry,
                                   _envelope, _muse)

SET = {"items": [_entry("contradicts", Q_DET)], "injection_quote": None}
SINGLE = _entry("contradicts", Q_DET) | {"injection_quote": None}


class Boom:
    """A transport entry that raises when reached."""

    def __init__(self, exc):
        self.exc = exc


class ScriptedTransport(FakeTransport):
    def __init__(self, *steps):
        super().__init__()
        self._responses = [s if isinstance(s, Boom) else _envelope(s) for s in steps]

    def create(self, body):
        step = self._responses.pop(0)
        self.bodies.append(json.loads(json.dumps(body)))
        if isinstance(step, Boom):
            raise step.exc
        return step


def _run(tmp_path, monkeypatch, *steps, flag="1"):
    if flag:
        monkeypatch.setenv("PROOFGRAPH_EVIDENCE_SET", flag)
    else:
        monkeypatch.delenv("PROOFGRAPH_EVIDENCE_SET", raising=False)
    transport = ScriptedTransport(SPLIT1, *steps)
    last = None
    for last in run_review(CLAIM, [PDF], _muse(tmp_path, transport), checker=_agree):
        pass
    assert isinstance(last, AllDone)
    return last.result.review, transport


def test_timeout_then_success_on_retry(tmp_path, monkeypatch):
    review, transport = _run(tmp_path, monkeypatch, Boom(MuseTimeoutError("t")), SET)
    assert len(transport.bodies) == 3  # split, relate_set, relate_set
    assert [c.relation for c in review.cards] == ["contradicts"]
    assert review.banners == []


def test_invalid_structure_then_success_on_retry(tmp_path, monkeypatch):
    bad = {"nonsense": 1}
    review, transport = _run(tmp_path, monkeypatch, bad, bad, SET)  # bad + its repair, then good
    assert [c.relation for c in review.cards] == ["contradicts"]
    assert review.banners == []


def test_timeout_twice_falls_back_to_single_relate_with_one_card(tmp_path, monkeypatch):
    review, transport = _run(tmp_path, monkeypatch, Boom(MuseTimeoutError("t")),
                             Boom(MuseTimeoutError("t")), SINGLE)
    assert len(transport.bodies) == 4
    assert "Pick the one passage" in json.dumps(transport.bodies[3])
    assert len(review.cards) == 1 and review.parts[0].status == "contradicted"
    assert [b.kind for b in review.banners] == ["checker_unavailable"]
    assert "single-passage" in review.banners[0].text and "evidence-set" in review.banners[0].text


def test_spend_cap_is_not_retried_or_fallen_back(tmp_path, monkeypatch):
    review, transport = _run(tmp_path, monkeypatch, Boom(SpendCapReached("cap")))
    assert len(transport.bodies) == 2  # split and one relate_set only
    assert review.parts[0].status == "error"
    assert [b.kind for b in review.banners] == ["cap"]


def test_flag_off_does_not_retry_or_fall_back(tmp_path, monkeypatch):
    review, transport = _run(tmp_path, monkeypatch, Boom(MuseTimeoutError("t")), flag=None)
    assert len(transport.bodies) == 2
    assert review.parts[0].status == "error"
    assert review.banners[0].text == "The model call failed: t"  # flag-off text unchanged


def test_flag_on_relate_failure_banner_does_not_blame_the_checker(tmp_path, monkeypatch):
    review, _ = _run(tmp_path, monkeypatch, Boom(MuseTimeoutError("t")), Boom(MuseTimeoutError("t")),
                     Boom(MuseTimeoutError("slow")))
    texts = [b.text for b in review.banners]
    assert any(t == "The evidence search (not the second check) failed: slow" for t in texts)
    assert not any("checker" in t.lower() for t in texts)
