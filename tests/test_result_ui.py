"""The result page: amber for can't-settle, the proof of precedence side by side, sign-off, and the commit line."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(
    not all((ROOT / "data" / "raw" / f).exists() for f in ("gillette_10k405_1996.txt", "ho_00_03_04_91.pdf", "ho_00_15_04_91.pdf")),
    reason="sources absent")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    os.environ.pop("ANTHROPIC_API_KEY", None)
    from app.server import create_app

    return TestClient(create_app())


def _rid(client, sample):
    body = client.post(f"/api/sample/{sample}").text
    return re.search(r'"review_id": "([0-9a-f]+)"', body).group(1)


def test_clash_mark_is_amber_not_red_or_green():
    css = (ROOT / "app/web/tokens.css").read_text()
    clash = [l for l in css.splitlines() if "m-clash" in l or ".u.clash" in l]
    assert any("var(--amber)" in l for l in clash)
    assert not any("pen-red" in l or "pen-green" in l for l in clash)
    from app.result import _mark
    assert '<path d="M5 9h14M5 15h14M15 5L9 19"/>' in _mark("clash")


def test_result_css_has_no_dark_override():
    assert "prefers-color-scheme" not in (ROOT / "app/web/result.css").read_text()


def test_precedence_crops_side_by_side_when_a_rule_fired(client):
    page = client.get(f"/api/review/{_rid(client, 'endorsement-replaces-limit')}").text
    assert 'class="precedence"' in page or 'class="precedence" ' in page
    assert "Controls: " in page and "Overridden: " in page
    assert page.index("Controls: ") < page.index("How this was decided")
    assert "The check against the claim found" in page


def test_cant_settle_page_has_a_lead_crop_and_no_precedence_pair(client):
    page = client.get(f"/api/review/{_rid(client, 'documents-disagree')}").text
    assert "This can&rsquo;t be settled" in page or "This can’t be settled" in page
    assert page.index("lead-src") < page.index("How this was decided")
    assert "Overridden: " not in page


def test_approve_route(client):
    rid = _rid(client, "claim-is-wrong")
    assert "Approved by" in client.get(f"/api/review/{rid}").text  # the control
    assert "kept in memory" in client.get(f"/api/review/{rid}").text
    bad = client.post(f"/api/review/{rid}/approve", json={"approved_by": "   "})
    assert bad.status_code == 400 and "name" in bad.json()["refusal"]
    assert client.post("/api/review/nope/approve", json={"approved_by": "A"}).status_code == 404
    ok = client.post(f"/api/review/{rid}/approve", json={"approved_by": "Ada Lovelace"})
    assert ok.status_code == 200 and ok.json()["approved_by"] == "Ada Lovelace"
    page = client.get(f"/api/review/{rid}").text
    assert "Approved by Ada Lovelace, " in page and "UTC" in page and 'id="approve-form"' not in page


def test_commit_line_marks_uncommitted_changes(monkeypatch):
    import subprocess
    import app.result as r

    def fake(cmd, **kw):
        out = "abc1234\n" if "rev-parse" in cmd else " M file.py\n"
        return subprocess.CompletedProcess(cmd, 0, out, "")
    monkeypatch.setattr(subprocess, "run", fake)
    monkeypatch.setattr(r, "_COMMIT_CACHE", (0.0, ""))
    assert r._commit() == "abc1234 (with uncommitted changes)"


def test_commit_safe_without_git(monkeypatch):
    import subprocess
    import app.result as r

    def boom(*a, **k):
        raise FileNotFoundError("git")
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(r, "_COMMIT_CACHE", (0.0, ""))
    assert r._commit() == "unknown"


def test_confirmed_policy_is_not_called_a_judgment():
    from app.result import _weakest_label

    class R:
        def __init__(s, m, st): s.mapping_id, s.strength = m, st
    from proofgraph.schema import RouteStrength
    a = type("A", (), {})()
    a.routes = [R("identify_x", RouteStrength.JUDGMENT)]
    a.weakest = RouteStrength.JUDGMENT
    assert _weakest_label(a, True) == "Which policy: confirmed by a person"
    assert "a judgment" in _weakest_label(a, False)
