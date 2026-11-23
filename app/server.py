"""The web front end: the restored browser UI over the v2 pipeline.

Routes are the ones app/web/app.js calls. Only the labelled examples run, from the model
responses recorded in data/recorded/model, so no API key is needed and nothing is charged.
Uploads and free-form claims are refused with a plain reason: retrieval and the passes run
on any text, but which policy a document describes is decided by a person before the run, and a guessed one
would give a confident wrong answer instead of a refusal.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.limit import LiveRunLimit, visitor_id
from app.upload import Refusal, UploadStore
from app.result import _absent_detail, _doc_name, crop_png, render
from proofgraph.claims import load_claims
from proofgraph.grouping import BASIS_PHRASE, REFUSAL_TEXT, decide_typed, gather_typed, read_claim, refusal_text
from proofgraph.model import complete_json
from proofgraph.numbers import find_basis, parse_amount
from proofgraph.pipeline import PacketRun, run_packet
from proofgraph.schema import DOLLARS_COUNTRY_NOT_PRINTED, MINOR_UNITS, Basis, DocumentMappingFile, ParseFailure, SourceManifest
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
    "SPECIMEN-HO3.jewelry_theft.loss_wording": "Which losses the jewelry limit covers (wording)",
}
KIND = {"policy_form": "Base form", "declarations": "Declarations", "endorsement": "Endorsement", "binder": "Binder",
        "cover_note": "Cover note", "correspondence": "Correspondence"}
HOW = {"read": "stated in the document", "derived": "derived from what it states", "judgment": "a person's judgment"}


def _packets() -> list[dict]:
    """The pre-loaded packets. Each lists its claims (one question can carry a right and a wrong claim) and every
    registry question; a question with no claim written is listed and switched off."""
    fb = DATA / "family_b"
    claims_b = {c.claim_id: c for c in load_claims(fb / "claims.json", fb / "slots.json")}
    claims_a = {c.claim_id: c for c in load_claims(DATA / "claims.json", DATA / "slots.json")}
    slots_b = [e["key"] for e in json.loads((fb / "slots.json").read_text(encoding="utf-8"))["slots"]]
    slots_a = [e["key"] for e in json.loads((DATA / "slots.json").read_text(encoding="utf-8"))["slots"]]
    mappings_a = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    mappings_b = DocumentMappingFile.model_validate_json((fb / "document_mappings.json").read_text(encoding="utf-8"))
    home = ["fb_jewelry", "fb_jewelry_wrong", "fb_jewelry_wording", "fb_money", "fb_firearms", "fb_silverware"]
    packs = [
        {"id": "homeowners", "title": "ISO homeowners: base form HO 00 03 with endorsement HO 00 15",
         "docs": ["ho_00_03", "ho_00_15"], "mappings": mappings_b, "slots": slots_b, "choices": [claims_b[c] for c in home]},
        {"id": "endorsement-alone", "title": "ISO homeowners: endorsement HO 00 15 without its base form",
         "docs": ["ho_00_15"], "mappings": mappings_b, "slots": slots_b, "choices": [claims_b["fb_jewelry"]]},
        {"id": "gillette", "title": "Gillette D&O program, 1996 SEC filing",
         "docs": [d.doc_id for d in mappings_a.documents], "mappings": mappings_a, "slots": slots_a, "choices": list(claims_a.values())},
    ]
    for p in packs:  # by question: the first claim written for it (the upload flow and old links use this)
        p["claims"] = {}
        for c in p["choices"]:
            p["claims"].setdefault(c.slot, c)
        p["default"] = p["choices"][0].claim_id
    return packs


def _samples() -> list[dict]:
    """The runs the hero and the tests use. Ids are stable links."""
    home, alone, gil = _packets()
    by = {c.claim_id: c for c in home["choices"]}

    def s(sid, title, pack, claim):
        return {"id": sid, "title": title, "claim": claim, "docs": pack["docs"], "mappings": pack["mappings"]}
    return [
        s("endorsement-replaces-limit", "a claim that is right (ISO HO 00 03 with HO 00 15)", home, by["fb_jewelry"]),
        s("documents-disagree", "documents that disagree on a retention (Gillette D&O, 1996)", gil, gil["choices"][0]),
        s("claim-is-wrong", "a claim that is wrong (ISO HO 00 03 with HO 00 15)", home, by["fb_jewelry_wrong"]),
        s("base-form-missing", "an endorsement without its base form (ISO HO 00 15 alone)", alone, alone["choices"][0]),
        s("wording-quoted", "a wording claim, quoted not checked (ISO HO 00 15)", home, by["fb_jewelry_wording"]),
    ]


def _sse(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


STATUS = {"supported": "supported", "contradicted": "contradicted", "unresolved": "unresolved", "not_found": "not_found",
          "quoted": "quoted"}
RULE = {"endorsement_over_base": "an endorsement overrides the form it changes where they differ",
        "later_effective_date": "a later effective date overrides an earlier one"}


def _reason(run: PacketRun, named: dict) -> str:
    """One plain line under the answer: why, naming the governing document, or the reason it cannot decide."""
    v = run.verdict
    if v is None:
        return run.failure or ""
    gov = _doc_name(v.governing_doc_id, named) if v.governing_doc_id else None
    rule = f" ({RULE[v.governing_rule.value]})" if v.governing_rule and v.governing_rule.value in RULE else ""
    verdict = v.verdict.value
    if verdict == "supported":
        return f"{gov} controls{rule} and states {v.governing_value}." if gov else f"The documents that state it agree on {v.governing_value}."
    if verdict == "contradicted":
        return (f"{gov or 'The governing document'} controls{rule} and states {v.governing_value}; "
                f"the claim says {v.claim_value}.")
    if verdict == "quoted" and v.quoted:
        return f"Quoted from {_doc_name(v.quoted.doc_id, named)}, page {v.quoted.page}. Quoted, not checked: a claim about wording is not judged."
    if verdict == "quoted":
        return "Quoted, not checked. " + (v.unresolved_detail or "")
    if v.unresolved_reason:
        head = {"documents_disagree": "The documents state different amounts, and no rule says which one controls.",
                "amounts_not_comparable": "The amounts cannot be compared.",
                "governing_instrument_absent": "A document needed to decide this is missing."}.get(v.unresolved_reason.value, "")
        # One plain sentence, never the arbiter's internal detail (assertion ids, reason codes): the evidence
        # below the answer carries the specifics.
        if v.unresolved_reason.value == "governing_instrument_absent":
            return f"{head} {_absent_detail(v, named)}".strip()
        if v.unresolved_reason.value == "amounts_not_comparable":
            if v.claim_comparison is not None and v.claim_comparison.reason.value == "currency_country_not_printed":
                return (f"{head} One side prints only \"$\", dollars with no country, and the other names a currency. "
                        "Set the claim's currency when you confirm the lines.")
            return f"{head} Their currency or basis (per loss, per claim, in total) differs, or one side does not state it."
        return head
    return "None of these documents addresses this question."


def create_app(complete=complete_json, uploads_dir: Path | None = None, limit: LiveRunLimit | None = None,
               upload_limit: LiveRunLimit | None = None) -> FastAPI:
    """`complete` is the model call the proposer uses (tests pass a fake). `limit` caps live runs and `upload_limit`
    caps uploads (each upload calls the model once per file); examples replay recorded responses and are never limited."""
    app = FastAPI(title="ProofGraph")
    reviews: OrderedDict[str, str] = OrderedDict()
    limit = limit or LiveRunLimit()
    upload_limit = upload_limit or LiveRunLimit()
    uploads = UploadStore(uploads_dir or DATA / "uploads", DATA / "predicates.json", complete)

    def maps(data: Path):
        m = SourceManifest.model_validate_json((data / "instruments.json").read_text(encoding="utf-8"))
        return ({i.doc_id: i for s in m.sources for i in s.instruments}, {i.doc_id: (s, i) for s in m.sources for i in s.instruments})

    info_main, named_main = maps(DATA)
    info, named = info_main, named_main

    def stream(sample: dict):
        claim = sample["claim"]
        data = sample.get("data", DATA)  # an uploaded packet runs from its own folder: raw/, instruments.json, predicates.json
        info, named = (maps(data) if data != DATA else (info_main, named_main))
        try:
            run = run_packet(sample["id"], claim, sample["docs"], sample["mappings"], data, Trace(None))
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
            reviews[rid] = render(run, data, f"ProofGraph: {sample['title']}", question=QUESTION.get(claim.slot, claim.slot), rerun=sample.get("rerun"))
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
        sample = {**sample, "rerun": f"/?sample={sample_id}"}
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
                             "strength": m.strength.value if m else None, "effective": i.effective_date,
                             "source": named[d][0].url, "pages": [i.first_page, i.last_page]})
            qs = [{"id": c.claim_id, "slot": c.slot, "label": QUESTION.get(c.slot, c.slot), "claim": c.text, "kind": c.kind}
                  for c in p["choices"]]
            qs += [{"id": k, "slot": k, "label": QUESTION.get(k, k), "claim": None, "kind": None}
                   for k in p["slots"] if k not in p["claims"]]
            out.append({"id": p["id"], "title": p["title"], "docs": docs, "questions": qs, "default": p["default"]})
        return out

    @app.post("/api/run/{packet_id}/{key}")
    def run_question(packet_id: str, key: str):
        """`key` is a claim id, or a registry question (which runs its first claim)."""
        p = next((x for x in _packets() if x["id"] == packet_id), None)
        if p is None:
            return JSONResponse({"refusal": "That packet is not available."}, status_code=404)
        claim = next((c for c in p["choices"] if c.claim_id == key), None) or p["claims"].get(key)
        if claim is None and key not in p["slots"]:
            return JSONResponse({"refusal": "That question is not on the fixed list for these documents, so nothing ran."}, status_code=400)
        if claim is None:
            return JSONResponse({"refusal": "No claim has been written for this question yet, so nothing ran."}, status_code=400)
        sample = {"id": f"{packet_id}:{claim.claim_id}", "title": f"{QUESTION.get(claim.slot, claim.slot)} ({p['title']})",
                  "claim": claim, "docs": p["docs"], "mappings": p["mappings"], "rerun": f"/?run={packet_id}/{claim.claim_id}"}
        return StreamingResponse(stream(sample), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    def refuse(exc: Refusal) -> JSONResponse:
        body = {"refusal": exc.text}
        if exc.errors:
            body["errors"] = exc.errors
        return JSONResponse(body, status_code=exc.status)

    def guarded(fn):
        try:
            return fn()
        except Refusal as exc:
            return refuse(exc)

    def who(request: Request) -> str:
        return visitor_id(request.headers, request.client.host if request.client else None)

    # ---- upload, propose, confirm, run. Nothing runs on an unconfirmed proposal.

    @app.post("/api/upload")
    def upload(request: Request, files: list[UploadFile] = File(...)):
        if not upload_limit.allow(who(request)):
            return JSONResponse({"refusal": "Too many uploads from here for now. Try again later."}, status_code=429)
        return guarded(lambda: uploads.view(uploads.create([(f.filename or "", f.file.read()) for f in files])))

    @app.get("/api/upload/{upload_id}")
    def upload_view(upload_id: str):
        return guarded(lambda: uploads.view(upload_id))

    @app.post("/api/upload/{upload_id}/confirm")
    def upload_confirm(upload_id: str, body: dict):
        return guarded(lambda: uploads.confirm(upload_id, body))

    @app.post("/api/upload/{upload_id}/rows")
    def upload_row(upload_id: str, body: dict):
        return guarded(lambda: uploads.add_row(upload_id, body))

    @app.post("/api/upload/{upload_id}/run/{slot}")
    def upload_run(upload_id: str, slot: str, request: Request):
        try:
            if uploads.confirmed(upload_id) is None:
                raise Refusal("No one has confirmed what each uploaded document is yet, so nothing ran.")
            folder, docs, mappings = uploads.packet(upload_id)
        except Refusal as exc:
            return refuse(exc)
        policies = {r.policy for m in mappings.documents for r in m.describes}
        known, claims = [], {}
        for p in _packets():
            known += [k for k in p["slots"] if k.split(".", 1)[0] in policies]
            claims.update({k: c for k, c in p["claims"].items() if k.split(".", 1)[0] in policies})
        if slot not in known:
            return JSONResponse({"refusal": "That question is not on the fixed list for these documents, so nothing ran."}, status_code=400)
        if slot not in claims:
            return JSONResponse({"refusal": "No claim has been written for this question yet, so nothing ran."}, status_code=400)
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return JSONResponse({"refusal": "This server is not set up to call the model, so a new check cannot run. The worked examples still work."}, status_code=400)
        if not limit.allow(who(request)):
            return JSONResponse({"refusal": "Too many runs from here for now. Try again later."}, status_code=429)
        sample = {"id": f"upload-{upload_id}:{slot}", "title": f"{QUESTION.get(slot, slot)} (uploaded packet)", "claim": claims[slot],
                  "docs": docs, "mappings": mappings, "data": folder}
        return StreamingResponse(stream(sample), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    # ---- D11: a typed claim, read by code, gathered, confirmed by a person, then decided.

    gathered: OrderedDict[str, tuple] = OrderedDict()

    def claim_packet(key: str):
        """(docs, mappings, data folder, policies) for a worked packet id or "upload:<id>"."""
        if key.startswith("upload:"):
            uid = key.split(":", 1)[1]
            if uploads.confirmed(uid) is None:
                raise Refusal("No one has confirmed what each uploaded document is yet, so nothing ran.")
            folder, docs, mappings = uploads.packet(uid)
        else:
            p = next((x for x in _packets() if x["id"] == key), None)
            if p is None:
                raise Refusal("That packet is not available.", status=404)
            folder, docs, mappings = DATA, p["docs"], p["mappings"]
        policies = tuple(sorted({r.policy for m in mappings.documents if m.doc_id in docs for r in m.describes}))
        return docs, mappings, folder, policies

    def read_view(r):
        cur = "dollars, country not printed" if r.currency == DOLLARS_COUNTRY_NOT_PRINTED else r.currency
        return {"kind": r.kind, "written": r.written, "value": r.value, "currency": cur,
                "basis": BASIS_PHRASE.get(r.basis) if r.basis else None, "policy_matches": list(r.policy_matches),
                "refusal": refusal_text(r.refusal, r.token) if r.refusal else None}

    @app.post("/api/claim/read")
    def claim_read(body: dict):
        """What code read from the claim, and the policies it can be checked against. No model call."""
        try:
            _, _, _, policies = claim_packet(str(body.get("packet", "")))
        except Refusal as exc:
            return refuse(exc)
        return {**read_view(read_claim(str(body.get("text", "")), policies)), "policies": list(policies)}

    @app.post("/api/claim/gather")
    def claim_gather(body: dict, request: Request):
        """The for and against reads on the claim's own text. Returns candidate lines for a person to confirm."""
        try:
            docs, mappings, folder, policies = claim_packet(str(body.get("packet", "")))
        except Refusal as exc:
            return refuse(exc)
        r = read_claim(str(body.get("text", "")), policies)
        if r.refusal:
            return JSONResponse({"refusal": refusal_text(r.refusal, r.token)}, status_code=400)
        policy = str(body.get("policy", ""))
        if policy not in policies:
            return JSONResponse({"refusal": REFUSAL_TEXT["policy_not_in_packet"]}, status_code=400)
        source = "matched_in_claim" if policy in r.policy_matches and body.get("policy_source") == "matched_in_claim" else "chosen"
        if not limit.allow(who(request)):
            return JSONResponse({"refusal": "Too many runs from here for now. Try again later."}, status_code=429)
        try:
            g = gather_typed(r, policy, "typed", docs, mappings, folder, Trace(None))
        except Exception as exc:  # a live read needs the model; say so instead of guessing
            if not os.environ.get("ANTHROPIC_API_KEY"):
                return JSONResponse({"refusal": "This claim hasn't been checked before, and this server is not set up to call the model."}, status_code=400)
            return JSONResponse({"refusal": f"The reads stopped: {type(exc).__name__}. Nothing was decided."}, status_code=500)
        if g.run.failure:
            return JSONResponse({"refusal": "The claim couldn't be turned into one checkable statement, so nothing was read."}, status_code=400)
        gid = uuid.uuid4().hex[:12]
        gathered[gid] = (g, folder, source)
        while len(gathered) > KEEP:
            gathered.popitem(last=False)
        info, named = maps(folder) if folder != DATA else (info_main, named_main)
        lines = []
        for c in g.candidates:
            b = find_basis(c.quote) if g.read.kind == "amount" else None
            lines.append({"line_id": c.line_id, "doc": _doc_name(c.doc_id, named), "page": c.page,
                          "where": f"page {c.page}" if c.page else f"characters {c.start:,}\u2013{c.end:,}",
                          "quote": c.quote, "value": c.value, "side": "against" if c.side == "attack" else "for",
                          "no_value": ("states several amounts; the reads did not say which is the claim's" if c.no_value else None),
                          "basis": BASIS_PHRASE.get(b[0]) if b else None})
        basis_in_lines = sorted({x["basis"] for x in lines if x["basis"]})
        named = set()  # D12: named currencies the lines print, for a "$" claim's currency to be set at confirmation
        for c in g.candidates:
            a = parse_amount(c.value) if c.value else None
            if a is not None and not isinstance(a, ParseFailure) and a.currency is not None \
                    and a.currency.value != DOLLARS_COUNTRY_NOT_PRINTED:
                named.add(a.currency.value)
        return {"gather_id": gid, "read": read_view(g.read), "policy": policy, "policy_source": source, "lines": lines,
                "nothing_found": [_doc_name(d, named) for d in g.nothing_found],
                "ask_basis": g.read.kind == "amount" and not g.read.basis and bool(basis_in_lines),
                "basis_options": [{"id": k.value, "label": v} for k, v in BASIS_PHRASE.items()], "basis_in_lines": basis_in_lines,
                "ask_currency": g.read.kind == "amount" and g.read.currency == DOLLARS_COUNTRY_NOT_PRINTED and bool(named),
                "currency_in_lines": sorted(named)}

    @app.post("/api/claim/{gather_id}/decide")
    def claim_decide(gather_id: str, body: dict):
        """The person's grouping becomes the question; the unchanged decision tree runs on it."""
        if gather_id not in gathered:
            return JSONResponse({"refusal": "That check has expired. Read the claim again."}, status_code=404)
        g, folder, source = gathered[gather_id]
        by = " ".join(str(body.get("confirmed_by", "")).split())
        if not by:
            return JSONResponse({"refusal": "Enter your name: who is confirming which lines are about the claim."}, status_code=400)
        basis = body.get("basis")
        try:
            basis_set = Basis(basis) if basis else None
        except ValueError:
            return JSONResponse({"refusal": "That basis is not one the comparator knows."}, status_code=400)
        currency = str(body.get("currency") or "").strip().upper() or None
        if currency is not None and currency not in MINOR_UNITS:
            return JSONResponse({"refusal": REFUSAL_TEXT["currency_not_known"]}, status_code=400)
        d = decide_typed(g, set(body.get("confirmed", [])), {str(k): str(v) for k, v in (body.get("dropped") or {}).items()},
                         confirmed_by=by, policy_source=source, basis_set=basis_set, currency_set=currency)
        if d.refusal:
            return JSONResponse({"refusal": REFUSAL_TEXT[d.refusal]}, status_code=400)
        gathered.pop(gather_id, None)
        info, named = maps(folder) if folder != DATA else (info_main, named_main)
        d.record["confirmed_on"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        d.record["dropped"] = [{**x, "doc": _doc_name(x["doc_id"], named)} for x in d.record["dropped"]]
        d.record["nothing_found"] = [_doc_name(x, named) for x in d.record["nothing_found"]]
        rid = uuid.uuid4().hex[:12]
        reviews[rid] = render(d.run, folder, "ProofGraph: a typed claim", question=f"A typed claim on policy {d.record['policy']}", record=d.record)
        while len(reviews) > KEEP:
            reviews.popitem(last=False)
        status = STATUS.get(d.run.verdict.verdict.value, "error")
        return {"review_id": rid, "status": status, "reason": _reason(d.run, named)}

    @app.post("/api/review")
    async def review(request: Request):
        # Kept as a refusal: the one-shot upload-and-run would have to guess which policy each document describes.
        # The flow that does not guess is /api/upload, then confirm, then run.
        return JSONResponse({"refusal": "A run cannot start from an upload alone: the system would have to guess which policy each document describes, "
                                        "and a wrong guess produces a confident wrong answer instead of saying so. "
                                        "Upload the files at /api/upload, confirm what each one is, then run a question; or run one of the examples."},
                            status_code=400)

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
