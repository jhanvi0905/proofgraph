"""One server, one page (F2): the review runs behind a streamed POST and ends on the review page.

``POST /api/review`` takes a multipart form (claim, files, and a passcode only when APP_PASSCODE is set) and answers with a ``text/event-stream``;
every event of ``run_review`` becomes one named server-sent event, and the last one (``done``) carries the review id.
``POST /api/review/{id}/ask`` runs another claim on the same files (the graph is cached by packet hash, so it is
read once). ``GET /api/review/{id}`` is the review page. The only model path is ``run_review``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import re
import shutil
import tempfile
import uuid
from collections import OrderedDict
from collections.abc import Callable, Iterator
from pathlib import Path

from fastapi import FastAPI, Form, UploadFile
from proofgraph.review.models import Review
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.auth import passcode_refusal
from app.viewer.render import render
from proofgraph.review.ingest import ingest
from proofgraph.review.run import AllDone, PartDone, PartsReady, default_muse, run_review

WEB = Path(__file__).with_name("web")
MAX_FILES = 10
MAX_FILE_BYTES = 25 * 1024 * 1024
KEEP_REVIEWS = 20
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg"}

_EVENT = {"DocStarted": "docstarted", "DocRead": "docread", "PageRead": "pageread", "EntityFound": "entity", "GraphReady": "graphready",
          "PartLinked": "linked", "PathFound": "path"}


REVIEW_ID = re.compile(r"^[0-9a-f]{12}$")


def reviews_dir() -> Path:
    return Path(os.environ.get("CACHE_DIR") or "cache") / "reviews"


def save_review(rid: str, review: Review, images: dict) -> bool:
    """Keep the finished review and its page images on disk so a shared link outlives the process. Never on the model path."""
    try:
        folder = reviews_dir()
        folder.mkdir(parents=True, exist_ok=True)
        for (doc, page), data in images.items():
            (folder / f"{rid}-{doc}-{page}.png").write_bytes(data)
        (folder / f"{rid}.json").write_text(review.model_dump_json(), encoding="utf-8")
        return True
    except OSError:
        return False


def load_review(rid: str) -> tuple[Review, dict] | None:
    if not REVIEW_ID.match(rid):
        return None
    folder = reviews_dir()
    try:
        review = Review.model_validate_json((folder / f"{rid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    images = {}
    for png in folder.glob(f"{rid}-*.png"):
        doc, _, page = png.stem[len(rid) + 1:].rpartition("-")
        if page.isdigit():
            images[(doc, int(page))] = png.read_bytes()
    return review, images


def sse(name: str, data: object) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class Store:
    """Reviews kept in memory with the uploaded files, so another claim can run on the same packet."""

    def __init__(self, keep: int = KEEP_REVIEWS) -> None:
        self.keep = keep
        self.items: OrderedDict[str, dict] = OrderedDict()
        self.dirs: dict[str, Path] = {}

    def packet(self, files: list[tuple[str, bytes]]) -> str:
        pid = uuid.uuid4().hex[:12]
        folder = Path(tempfile.mkdtemp(prefix="proofgraph-"))
        for i, (name, data) in enumerate(files):
            (folder / str(i)).mkdir()  # one folder per file keeps same-named uploads apart and names clean
            (folder / str(i) / name).write_bytes(data)
        self.dirs[pid] = folder
        while len(self.dirs) > self.keep:
            old = next(iter(self.dirs))
            shutil.rmtree(self.dirs.pop(old), ignore_errors=True)
            self.items = OrderedDict((k, v) for k, v in self.items.items() if v["packet"] != old)
        return pid

    def paths(self, pid: str) -> list[Path]:
        return [next((self.dirs[pid] / d.name).iterdir()) for d in sorted(self.dirs[pid].iterdir(), key=lambda d: int(d.name))]

    def add(self, packet: str, html: str, rid: str | None = None) -> str:
        rid = rid or uuid.uuid4().hex[:12]
        self.items[rid] = {"packet": packet, "html": html}
        return rid


def _file_lines(paths: list[Path], names: list[str]) -> list[dict]:
    out = []
    for doc, name in zip(ingest(paths), names):
        if doc.error:
            out.append({"name": name, "ok": False, "pages": 0, "note": doc.error.replace(doc.original_name, name)})
            continue
        scans = sum(1 for p in doc.pages if p.kind != "text")
        note = None
        if scans:
            note = f"{scans} page{'s' if scans != 1 else ''} without a text layer will be transcribed; boxes there are approximate."
        out.append({"name": name, "id": doc.doc_id, "ok": True, "pages": len(doc.pages), "note": note})
    return out


def _clean(name: str | None) -> str:
    base = Path(str(name or "file").replace("\\", "/")).name
    return re.sub(r"[^\w.\- ]", "_", base)[:100] or "file"


def _disagreements(review) -> list[dict]:
    out = []
    for pid, info in ((review.graph or {}).get("parts") or {}).items():
        read_only = info.get("read_only") or []
        if info.get("agreement") in ("partial", "disagree") and read_only:
            n = len(read_only)
            out.append({"part_id": pid, "text": f"Reading every page also points at {n} passage{'s' if n != 1 else ''} "
                                                "that following the links did not reach; open the review to compare."})
    return out


def create_app(make_muse: Callable[[], object] | None = None) -> FastAPI:
    app = FastAPI(title="ProofGraph", docs_url=None, redoc_url=None)
    store = Store()
    muse_factory = make_muse or default_muse

    def stream(claim: str, packet: str, names: list[str]) -> Iterator[str]:
        paths = store.paths(packet)
        yield sse("files", {"files": _file_lines(paths, names)})
        labels: dict[str, list[str]] = {}
        try:
            for ev in run_review(claim, paths, muse_factory()):
                kind = type(ev).__name__
                if isinstance(ev, PartsReady):
                    yield sse("parts", {"parts": [{"id": p.id, "text": p.text, "span": list(p.span)} for p in ev.parts]})
                elif isinstance(ev, PartDone):
                    yield sse("partdone", dataclasses.asdict(ev))
                elif isinstance(ev, AllDone):
                    review = ev.result.review
                    for pid, info in ((review.graph or {}).get("parts") or {}).items():
                        if pid in labels and "path_labels" not in info:
                            info["path_labels"] = labels[pid]
                    rid = uuid.uuid4().hex[:12]
                    saved = save_review(rid, review, ev.result.page_images)
                    page = render(review, ev.result.page_images, replay=review.run.mode == "replayed",
                                  ask=True, share_url=f"/r/{rid}" if saved else None)
                    store.add(packet, page, rid)
                    for note in _disagreements(review):
                        yield sse("disagreement", note)
                    yield sse("done", {"review_id": rid, "status": review.status,
                                       "banners": [b.text for b in review.banners]})
                elif kind in _EVENT:
                    data = dataclasses.asdict(ev)
                    if kind == "PathFound":
                        labels[ev.part_id] = list(ev.labels)
                    yield sse(_EVENT[kind], data)
        except Exception as exc:  # the stream ends with one plain line, never a stack trace
            yield sse("failed", {"text": f"The check stopped: {type(exc).__name__}. Nothing after this point was read."})

    def start(claim: str, passcode: str, packet: str | None, uploads: list[tuple[str, bytes]] | None):
        configured = os.environ.get("APP_PASSCODE")  # no passcode set: open; the spend cap still applies
        refusal = passcode_refusal(passcode, configured) if configured else None
        if refusal is None and not claim.strip():
            refusal = "Write the claim before running the check."
        if refusal is None and packet is None and not uploads:
            refusal = "Upload at least one file."
        if refusal is None and uploads is not None:
            if len(uploads) > MAX_FILES:
                refusal = f"Upload at most {MAX_FILES} files."
            elif any(len(d) > MAX_FILE_BYTES for _, d in uploads):
                refusal = f"Each file must be under {MAX_FILE_BYTES // 2**20} MB."
            elif any(Path(n).suffix.lower() not in ALLOWED for n, _ in uploads):
                refusal = "Upload PDF, PNG or JPG files."
        if refusal is not None:  # before any client exists
            return JSONResponse({"refusal": refusal}, status_code=401 if "passcode" in refusal else 400)
        names = [n for n, _ in uploads] if uploads else [p.name for p in store.paths(packet)]
        if packet is None:
            packet = store.packet(uploads)
        return StreamingResponse(stream(claim.strip(), packet, names), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    def samples() -> list[dict]:
        """Packets offered on the entrance. A manifest in PROOFGRAPH_SAMPLES (samples.json) names each one's claim and
        files; with none set the entrance simply shows no sample cards."""
        manifest = os.environ.get("PROOFGRAPH_SAMPLES")
        if not manifest or not Path(manifest).is_file():
            return []
        base = Path(manifest).parent
        return [s for s in json.loads(Path(manifest).read_text())["samples"]
                if all((base / f).is_file() for f in s["files"])]

    @app.get("/api/config")
    def config():
        return {"passcode_required": bool(os.environ.get("APP_PASSCODE"))}

    @app.get("/api/samples")
    def list_samples():
        return [{"id": s["id"], "title": s["title"], "claim": s["claim"], "docs": [Path(f).stem for f in s["files"]]}
                for s in samples()]

    @app.post("/api/sample/{sample_id}")
    def run_sample(sample_id: str, passcode: str = Form("")):
        sample = next((s for s in samples() if s["id"] == sample_id), None)
        if sample is None:
            return JSONResponse({"refusal": "That packet is not available."}, status_code=404)
        base = Path(os.environ["PROOFGRAPH_SAMPLES"]).parent
        return start(sample["claim"], passcode, None, [(Path(f).name, (base / f).read_bytes()) for f in sample["files"]])

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (WEB / "index.html").read_text(encoding="utf-8")

    @app.post("/api/review")
    async def review(claim: str = Form(""), passcode: str = Form(""), files: list[UploadFile] | None = None):
        uploads = [(_clean(f.filename), await f.read()) for f in files or [] if f.filename]
        return start(claim, passcode, None, uploads)

    @app.post("/api/review/{review_id}/ask")
    def ask(review_id: str, claim: str = Form(""), passcode: str = Form("")):
        item = store.items.get(review_id)
        if item is None or item["packet"] not in store.dirs:
            return JSONResponse({"refusal": "That packet is no longer here. Upload the files again."}, status_code=404)
        return start(claim, passcode, item["packet"], None)

    @app.get("/api/review/{review_id}", response_class=HTMLResponse)
    def get_review(review_id: str):
        item = store.items.get(review_id)
        if item is not None:
            return item["html"]
        loaded = load_review(review_id)
        if loaded is None:
            return HTMLResponse("<p>That review is no longer here.</p>", status_code=404)
        review, images = loaded
        return render(review, images, replay=review.run.mode == "replayed", share_url=f"/r/{review_id}")

    @app.get("/r/{review_id}", response_class=HTMLResponse)
    def shared_review(review_id: str):
        loaded = load_review(review_id)
        if loaded is None:
            return HTMLResponse("<p>That review is not available.</p>", status_code=404)
        review, images = loaded
        return render(review, images, replay=review.run.mode == "replayed", share=True)

    @app.get("/web/tokens.css")
    def tokens():
        return Response((Path(__file__).with_name("viewer") / "tokens.css").read_text(), media_type="text/css")

    app.mount("/web", StaticFiles(directory=WEB), name="web")
    return app


app = create_app()
