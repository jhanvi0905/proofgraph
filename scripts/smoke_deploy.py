"""Smoke test for a running deploy: the cached sample, and optionally one live claim.

  uv run python scripts/smoke_deploy.py https://your-service.onrender.com [--passcode X]
  uv run python scripts/smoke_deploy.py URL --live-claim "..." --live-file packet.pdf   # costs model spend

Checks /api/config and /api/samples, runs every sample and reads its event stream to the end, then opens the
saved review and its share link. Exit 0 only when every step passes. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


def get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def stream(request: urllib.request.Request) -> tuple[list[str], dict]:
    """Read a text/event-stream to its end; returns the event names and the last 'done' payload."""
    names, done, event = [], {}, ""
    with urllib.request.urlopen(request, timeout=600) as r:
        for raw in r:
            line = raw.decode().rstrip("\n")
            if line.startswith("event:"):
                event = line.split(":", 1)[1].strip()
                names.append(event)
            elif line.startswith("data:") and event in ("done", "failed"):
                done = {"event": event, **json.loads(line.split(":", 1)[1])}
    return names, done


def multipart(fields: dict[str, str], files: list[Path]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items()]
    for f in files:
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{f.name}"\r\n'
                     "Content-Type: application/octet-stream\r\n\r\n".encode() + f.read_bytes() + b"\r\n")
    return b"".join(parts) + f"--{boundary}--\r\n".encode(), f"multipart/form-data; boundary={boundary}"


def check(ok: bool, label: str, detail: str = "") -> bool:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{(' - ' + detail) if detail else ''}")
    return ok


def finished(base: str, names: list[str], done: dict, label: str) -> bool:
    status = done.get("status")
    ok = check(done.get("event") == "done" and status not in (None, "error", "checking"), f"{label}: stream ends in an answer",
               f"{len(names)} events, status {status}{', ' + '; '.join(done.get('banners', [])) if status == 'error' else ''}")
    if ok:
        rid = done["review_id"]
        ok &= check(get(f"{base}/api/review/{rid}")[0] == 200, f"{label}: saved review opens")
        ok &= check(get(f"{base}/r/{rid}")[0] == 200, f"{label}: share link opens")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("url")
    ap.add_argument("--passcode", default="")
    ap.add_argument("--live-claim")
    ap.add_argument("--live-file", type=Path, action="append", default=[])
    a = ap.parse_args()
    base = a.url.rstrip("/")
    ok = check(get(base + "/")[0] == 200, "entrance page loads")
    code, body = get(base + "/api/config")
    ok &= check(code == 200, "/api/config", body.strip())
    code, body = get(base + "/api/samples")
    samples = json.loads(body) if code == 200 else []
    ok &= check(bool(samples), "samples are offered", ", ".join(s["id"] for s in samples))
    for s in samples:
        req = urllib.request.Request(f"{base}/api/sample/{s['id']}", data=urllib.parse.urlencode({"passcode": a.passcode}).encode(), method="POST")
        names, done = stream(req)
        ok &= finished(base, names, done, f"sample {s['id']}")
    if a.live_claim and a.live_file:
        data, ctype = multipart({"claim": a.live_claim, "passcode": a.passcode}, a.live_file)
        names, done = stream(urllib.request.Request(base + "/api/review", data=data, headers={"Content-Type": ctype}, method="POST"))
        ok &= finished(base, names, done, "live claim")
    print("ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
