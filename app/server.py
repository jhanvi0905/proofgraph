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
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.limit import LiveRunLimit, visitor_id
from app.result import _doc_name, crop_png, render
from proofgraph.claims import load_claims
from proofgraph.pipeline import PacketRun, run_packet
from proofgraph.schema import DocumentMappingFile, SourceManifest
from proofgraph.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
WEB = Path(__file__).resolve().parent / "web"
KEEP = 50


# Plain-English names for the registry's keys, for the form. The keys themselves are frozen in slots.json.
QUESTION = {
    "SPECIMEN-HO3.money.special_limit": "Special limit on money",
    "SPECIMEN-HO3.jewelry_theft.special_limit": "Special limit on theft of jewelry",
    "SPECIMEN-HO3.firearms_theft.special_limit": "Special limit on theft of firearms",
    "SPECIMEN-HO3.silverware_theft.special_limit": "Special limit on theft of silverware",
    "FD960228.corp_reimbursement.retention": "Corporate reimbursement retention on FD960228",
    "81385411.d_and_o.limit": "D&O limit on the Chubb excess layer (81385411)",
    "752-034765-96.d_and_o.limit": "D&O limit on the ERMA excess layer (752-034765-96)",
}
KIND = {"policy_form": "Base form", "declarations": "Declarations", "endorsement": "Endorsement", "binder": "Binder",
        "cover_note": "Cover note", "correspondence": "Correspondence"}
HOW = {"read": "stated in the document", "derived": "derived from what it states", "judgment": "a person's judgment"}


def _packets() -> list[dict]:
    """The two pre-loaded packets, each with every question the registry has for it. A question runs only
    when a claim has been written for it; the others are listed and switched off."""
    fb = DATA / "family_b"
    labels = json.loads((fb / "labels.json").read_text(encoding="utf-8"))
    claims_b = {c.claim_id: c for c in load_claims(fb / "claims.json", fb / "slots.json")}
    by_slot_b = {claims_b[p["claim_id"]].slot: claims_b[p["claim_id"]] for p in labels["packets"] if p["packet_id"].endswith("-endorsed")}
    slots_b = [e["key"] for e in json.loads((fb / "slots.json").read_text(encoding="utf-8"))["slots"]]
    slots_a = [e["key"] for e in json.loads((DATA / "slots.json").read_text(encoding="utf-8"))["slots"]]
    mappings_a = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    mappings_b = DocumentMappingFile.model_validate_json((fb / "document_mappings.json").read_text(encoding="utf-8"))
    by_slot_a = {c.slot: c for c in load_claims(DATA / "claims.json", DATA / "slots.json")}
    return [
        {"id": "homeowners", "title": "ISO homeowners: base form HO 00 03 with endorsement HO 00 15",
         "docs": ["ho_00_03", "ho_00_15"], "mappings": mappings_b, "slots": slots_b, "claims": by_slot_b,
         "default": "SPECIMEN-HO3.jewelry_theft.special_limit"},
        {"id": "gillette", "title": "Gillette D&O program, 1996 SEC filing",
         "docs": [d.doc_id for d in mappings_a.documents], "mappings": mappings_a, "slots": slots_a, "claims": by_slot_a,
         "default": "FD960228.corp_reimbursement.retention"},
    ]


def _samples() -> list[dict]:
    """The two runs the hero and the tests use, by their old ids."""
    home, gil = _packets()
    return [
        {"id": "endorsement-replaces-limit", "title": "an endorsement that replaces a special limit (ISO HO 00 03 + HO 00 15)",
         "claim": home["claims"][home["default"]], "docs": home["docs"], "mappings": home["mappings"]},
        {"id": "documents-disagree", "title": "three documents that disagree on a retention (Gillette D&O, 1996)",
         "claim": gil["claims"][gil["default"]], "docs": gil["docs"], "mappings": gil["mappings"]},
    ]


def _sse(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


STATUS = {"supported": "supported", "contradicted": "contradicted", "unresolved": "unresolved", "not_found": "not_found"}


def _reason(run: PacketRun, named: dict) -> str:
    v = run.verdict
    if v is None:
        return run.failure or ""
    if v.supported_reason and v.supported_reason.value == "resolved_by_rule":
        return f"Decided by a rule: {v.governing_rule.value.replace('_', ' ')}; {_doc_name(v.governing_doc_id, named)} governs."
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
    info = {i.doc_id: i for s in manifest.sources for i in s.instruments}
    named = {i.doc_id: (s, i) for s in manifest.sources for i in s.instruments}

    def stream(sample: dict):
        claim = sample["claim"]
        try:
            run = run_packet(sample["id"], claim, sample["docs"], sample["mappings"], DATA, Trace(None))
            admitted = dict(run.documents)
            policy = claim.slot.split(".", 1)[0]
            rows = []
            for d in sample["docs"]:
                m = next((x for x in sample["mappings"].documents if x.doc_id == d), None)
                route = next((r for r in m.describes if r.policy == policy), None) if m else None
                other = sorted({r.policy for r in m.describes} - {policy}) if m else []
                rows.append({"name": _doc_name(d, named), "id": d, "kind": KIND.get(info[d].instrument_type.value, "") if d in info else "",
                             "policy": policy if route else (", ".join(other) or "none recorded"),
                             "how": HOW.get(route.strength.value, "") if route else "", "strength": route.strength.value if route else "",
                             "passages": admitted.get(d, 0), "in_scope": route is not None})
            yield _sse("admitted", {"policy": policy, "docs": rows})
            yield _sse("parts", {"parts": [{"id": "a0", "text": claim.text, "span": [0, len(claim.text)]}]})
            status = STATUS.get(run.verdict.verdict.value, "error") if run.verdict else "error"
            yield _sse("partdone", {"part_id": "a0", "status": status, "reason": _reason(run, named)})
            if run.verdict and run.verdict.unresolved_reason:
                yield _sse("disagreement", {"part_id": "a0", "text": _reason(run, named)})
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

    @app.get("/api/packets")
    def packets():
        out = []
        for p in _packets():
            maps = {d.doc_id: d for d in p["mappings"].documents}
            docs = []
            for d in p["docs"]:
                i = info[d]
                m = maps[d].describes[0] if d in maps and maps[d].describes else None
                docs.append({"doc_id": d, "name": _doc_name(d, {d: (None, i)}), "kind": KIND[i.instrument_type.value],
                             "policy": m.policy if m else None, "how": HOW[m.strength.value] if m else None,
                             "strength": m.strength.value if m else None, "effective": i.effective_date})
            qs = [{"slot": k, "label": QUESTION.get(k, k), "claim": p["claims"][k].text if k in p["claims"] else None}
                  for k in p["slots"]]
            out.append({"id": p["id"], "title": p["title"], "docs": docs, "questions": qs, "default": p["default"]})
        return out

    @app.post("/api/run/{packet_id}/{slot}")
    def run_question(packet_id: str, slot: str):
        p = next((x for x in _packets() if x["id"] == packet_id), None)
        if p is None:
            return JSONResponse({"refusal": "That packet is not available."}, status_code=404)
        if slot not in p["slots"]:
            return JSONResponse({"refusal": "That question is not in the registry for this packet, so nothing ran."}, status_code=400)
        if slot not in p["claims"]:
            return JSONResponse({"refusal": "No claim has been written for this question yet, so nothing ran."}, status_code=400)
        sample = {"id": f"{packet_id}:{slot}", "title": f"{QUESTION.get(slot, slot)} ({p['title']})",
                  "claim": p["claims"][slot], "docs": p["docs"], "mappings": p["mappings"]}
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

    # Real crops of the documents, rendered from the PDFs in data/raw at request time (never committed).
    media = {
        "ho15-header": ("ho_00_15_04_91.pdf", 1, ["HOMEOWNERS", "HO 00 15 04 91", "THIS ENDORSEMENT CHANGES THE POLICY. PLEASE READ IT CAREFULLY.",
                                                  "SPECIAL PERSONAL PROPERTY COVERAGE", "Form HO 00 03 Only"], False, (24, 56), True),
        "ho03-limits": ("ho_00_03_04_91.pdf", 2, ["5. $1000 for loss by theft of jewelry, watches, furs,",
                                                  "precious and semi-precious stones."], True, (96, 96)),
        "ho15-limits": ("ho_00_15_04_91.pdf", 2, ["5. $1,000 for loss by theft, misplacing or losing of",
                                                  "jewelry, watches, furs, precious and semi-", "precious stones."], True, (80, 80)),
    }
    rendered: dict[str, bytes] = {}

    def _edgar_png() -> bytes:
        """Item VII of the Gillette filing (a public SEC document), its Primary row boxed, drawn from the raw text."""
        import io

        from PIL import Image, ImageDraw, ImageFont

        raw = (DATA / "raw" / "gillette_10k405_1996.txt").read_bytes().decode("ascii")
        start = raw.index("ITEM VII Schedule of Underlying")
        lines = [ln.rstrip() for ln in raw[start:raw.index("</TABLE>", start)].split("\n")
                 if ln.strip() and not ln.strip().startswith("<")]
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 26) if Path("/System/Library/Fonts/Menlo.ttc").exists() \
            else ImageFont.load_default()
        lh, pad = 40, 28
        width = int(max(font.getlength(ln) for ln in lines)) + 2 * pad
        img = Image.new("RGB", (width, lh * len(lines) + 2 * pad), "white")
        d = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            y = pad + i * lh
            if ln.startswith("Primary"):
                d.rectangle((pad - 8, y - 6, pad + font.getlength(ln) + 8, y + lh - 8), fill=(236, 244, 248), outline=(22, 54, 201), width=3)
            d.text((pad, y), ln, fill=(14, 26, 43), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    @app.get("/media/{name}.png")
    def media_png(name: str):
        if name == "gillette-item7":
            if name not in rendered:
                rendered[name] = _edgar_png()
            return Response(rendered[name], media_type="image/png", headers={"Cache-Control": "max-age=3600"})
        if name not in media:
            return Response(status_code=404)
        if name not in rendered:
            file, page, lines, boxed, pad, *full = media[name]
            path = DATA / "raw" / file
            if not path.exists():
                return Response(status_code=404)
            rendered[name] = crop_png(path, page, lines, boxed, pad, bool(full and full[0]))
        return Response(rendered[name], media_type="image/png", headers={"Cache-Control": "max-age=3600"})

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (WEB / "index.html").read_text(encoding="utf-8")

    app.mount("/web", StaticFiles(directory=WEB), name="web")
    return app


app = create_app()
