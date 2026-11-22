"""The web front end: the restored browser UI over the v2 pipeline.

Routes are the ones app/web/app.js calls. Only the labelled examples run, from the model
responses recorded in data/recorded/model, so no API key is needed and nothing is charged.
Uploads and free-form claims are refused with a plain reason: retrieval and the passes run
on any text, but identification (which policy a document describes) is still labelled by hand.
"""

from __future__ import annotations

import json
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.limit import LiveRunLimit, visitor_id
from app.result import render
from proofgraph.claims import load_claims
from proofgraph.pipeline import PacketRun, run_packet
from proofgraph.schema import DocumentMappingFile, SourceManifest
from proofgraph.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = Path(__file__).resolve().parent / "web"
KEEP = 50


def _samples() -> list[dict]:
    fb = DATA / "family_b"
    labels = json.loads((fb / "labels.json").read_text(encoding="utf-8"))
    claims_b = {c.claim_id: c for c in load_claims(fb / "claims.json", fb / "slots.json")}
    jewelry = next(p for p in labels["packets"] if p["packet_id"] == "B-jewelry-endorsed")
    mappings_a = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    claim_a = load_claims(DATA / "claims.json", DATA / "slots.json")[0]
    return [
        {"id": "endorsement-replaces-limit", "title": "an endorsement that replaces a special limit (ISO HO 00 03 + HO 00 15)",
         "claim": claims_b[jewelry["claim_id"]], "docs": jewelry["instruments"],
         "mappings": DocumentMappingFile.model_validate_json((fb / "document_mappings.json").read_text(encoding="utf-8"))},
        {"id": "documents-disagree", "title": "three documents that disagree on a retention (Gillette D&O, 1996)",
         "claim": claim_a, "docs": [d.doc_id for d in mappings_a.documents], "mappings": mappings_a},
    ]


def _sse(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


STATUS = {"supported": "supported", "contradicted": "contradicted", "unresolved": "unresolved", "not_found": "not_found"}


def _reason(run: PacketRun) -> str:
    v = run.verdict
    if v is None:
        return run.failure or ""
    if v.supported_reason and v.supported_reason.value == "resolved_by_rule":
        return f"Decided by a rule: {v.governing_rule.value.replace('_', ' ')}; {v.governing_doc_id} governs."
    if v.unresolved_reason:
        return {"documents_disagree": "The documents state different amounts and no rule picks one.",
                "uncompared_agreement": "The amounts match but could not be compared on the same terms."}[v.unresolved_reason.value]
    if v.supported_reason:
        return "Nothing disputes it."
    return "No admitted passage states a value for this."


def create_app() -> FastAPI:
    app = FastAPI(title="ProofGraph")
    reviews: OrderedDict[str, str] = OrderedDict()
    limit = LiveRunLimit()  # kept for live runs; examples replay recorded responses and are never limited
    manifest = SourceManifest.model_validate_json((DATA / "instruments.json").read_text(encoding="utf-8"))
    pages = {i.doc_id: i.last_page - i.first_page + 1 for s in manifest.sources for i in s.instruments}

    def stream(sample: dict):
        claim = sample["claim"]
        try:
            run = run_packet(sample["id"], claim, sample["docs"], sample["mappings"], DATA, Trace(None))
            yield _sse("files", {"files": [{"name": d, "id": d, "ok": True, "pages": pages.get(d, 1), "note": f"{n} passage(s) admitted"}
                                           for d, n in run.documents]})
            yield _sse("parts", {"parts": [{"id": "a0", "text": claim.text, "span": [0, len(claim.text)]}]})
            status = STATUS.get(run.verdict.verdict.value, "error") if run.verdict else "error"
            yield _sse("partdone", {"part_id": "a0", "status": status, "reason": _reason(run)})
            if run.verdict and run.verdict.unresolved_reason:
                yield _sse("disagreement", {"part_id": "a0", "text": _reason(run)})
            rid = uuid.uuid4().hex[:12]
            reviews[rid] = render(run, DATA, f"ProofGraph: {sample['title']}")
            while len(reviews) > KEEP:
                reviews.popitem(last=False)
            yield _sse("done", {"review_id": rid, "status": status,
                                "banners": ["The claim and which policy each document describes are written by a person; the rest is the pipeline."]})
        except Exception as exc:  # report, never guess
            yield _sse("failed", {"text": f"The check stopped: {type(exc).__name__}. Nothing after this point was read."})

    @app.get("/api/config")
    def config():
        return {"passcode_required": False, "second_reader": False}

    @app.get("/api/samples")
    def samples():
        return [{"id": s["id"], "title": s["title"], "claim": s["claim"].text, "docs": s["docs"]} for s in _samples()]

    @app.post("/api/sample/{sample_id}")
    def run_sample(sample_id: str):
        sample = next((s for s in _samples() if s["id"] == sample_id), None)
        if sample is None:
            return JSONResponse({"refusal": "That example is not available."}, status_code=404)
        return StreamingResponse(stream(sample), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    @app.post("/api/review")
    async def review(request: Request):
        if not limit.allow(visitor_id(request.headers, request.client.host if request.client else None)):
            return JSONResponse({"refusal": "Too many runs from here for now. Try again later."}, status_code=429)
        return JSONResponse({"refusal": "Uploads and your own claims are not built yet: which policy each document describes is "
                                        "still labelled by hand. Run one of the examples instead."}, status_code=400)

    @app.get("/api/review/{review_id}", response_class=HTMLResponse)
    def review_page(review_id: str):
        page = reviews.get(review_id)
        return HTMLResponse(page or "<p>That result is no longer here. Run the example again.</p>", status_code=200 if page else 404)

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (WEB / "index.html").read_text(encoding="utf-8")

    app.mount("/web", StaticFiles(directory=WEB), name="web")
    return app


app = create_app()
