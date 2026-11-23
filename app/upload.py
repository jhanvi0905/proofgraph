"""The upload door: upload, propose, confirm, run.

Files are stored under data/uploads/<upload_id>/ (gitignored) with their sha256. A proposer proposes what each
file is; a person confirms or corrects every row; the confirmed mapping is frozen as JSON next to the files, with who
confirmed it and when (UTC). Nothing runs on an unconfirmed proposal. The upload directory doubles as a data
directory for run_packet: raw/<files>, instruments.json, predicates.json, document_mappings.json.

A route's citation is its admission scope (see admit() in retrieve.py), so it is the verified identifying line unless
the person names a wider block of lines (scope_page and scope_text), which is verified the same way.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import uuid
from pathlib import Path

from proofgraph.checker import open_source, verify_citation
from proofgraph.ingest import pdf_text_layer
from proofgraph.model import complete_json
from proofgraph.propose import Row, edition_date, propose, verify_line
from proofgraph.schema import (
    AmendsRoute,
    Citation,
    DocumentMapping,
    DocumentMappingFile,
    DocumentRoute,
    Extractor,
    InstrumentLabel,
    InstrumentType,
    MappingMethod,
    RouteStrength,
    SourceLabel,
    SourceManifest,
)
from proofgraph.trace import Trace

MAX_FILES = 8
MAX_BYTES = 30 * 1024 * 1024
ID_RE = re.compile(r"^[0-9a-f]{12}$")
HOW = ("read", "judgment")  # no mechanical step exists for an upload, so "derived" is not offered


class Refusal(Exception):
    def __init__(self, text: str, status: int = 400, errors: list[str] | None = None):
        super().__init__(text)
        self.text, self.status, self.errors = text, status, errors or []


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "doc"


class UploadStore:
    def __init__(self, root: Path, predicates: Path, complete=complete_json) -> None:
        self.root, self.predicates, self.complete = root, predicates, complete

    # ------------------------------------------------------------ paths
    def dir(self, upload_id: str) -> Path:
        if not ID_RE.match(upload_id) or not (self.root / upload_id).is_dir():
            raise Refusal("That upload is not available.", 404)
        return self.root / upload_id

    def _read(self, upload_id: str) -> dict:
        return json.loads((self.dir(upload_id) / "proposal.json").read_text(encoding="utf-8"))

    def _write(self, upload_id: str, state: dict) -> None:
        (self.dir(upload_id) / "proposal.json").write_text(json.dumps(state, indent=1, sort_keys=True), encoding="utf-8")

    # ------------------------------------------------------------ upload and propose
    def create(self, files: list[tuple[str, bytes]]) -> str:
        if not files:
            raise Refusal("No files were sent.")
        if len(files) > MAX_FILES:
            raise Refusal(f"At most {MAX_FILES} files per upload.")
        upload_id = uuid.uuid4().hex[:12]
        folder = self.root / upload_id
        (folder / "raw").mkdir(parents=True)
        rows: list[dict] = []
        refused: list[dict] = []
        trace = Trace(folder / "propose.trace.jsonl")
        seen: set[str] = set()
        for n, (name, data) in enumerate(files, 1):
            name = Path(name or f"file{n}.pdf").name
            sha = hashlib.sha256(data).hexdigest()
            why = self._unreadable(data)
            if why:
                refused.append({"file": name, "sha256": sha, "refusal": why})
                continue
            if sha in seen:
                refused.append({"file": name, "sha256": sha, "refusal": "the same file was sent twice; the second copy is ignored"})
                continue
            seen.add(sha)
            stored = f"{n}_{re.sub(r'[^A-Za-z0-9._-]', '_', name)}"
            if not stored.lower().endswith(".pdf"):
                stored += ".pdf"
            path = folder / "raw" / stored
            path.write_bytes(data)
            try:
                pages, _, has_text = pdf_text_layer(path, 0)
            except Exception:
                path.unlink()
                refused.append({"file": name, "sha256": sha, "refusal": "not a readable PDF"})
                continue
            if not has_text:
                path.unlink()
                refused.append({"file": name, "sha256": sha, "refusal": "no readable text layer"})
                continue
            try:
                row = propose(path, name, stored, sha, trace, self.complete)
            except Exception as exc:  # report, never guess: the person can type a row instead
                row = Row(file=name, stored=stored, sha256=sha, pages=pages, status="unplaceable",
                          reason=f"{name} could not be identified: reading what is printed on it failed ({type(exc).__name__}). "
                                 "Type its kind, policy, how you know, and one line printed on it.")
            rows.append(row.model_dump(mode="json"))
        self._write(upload_id, {"upload_id": upload_id, "created_at": _now(), "rows": rows, "refused": refused})
        return upload_id

    @staticmethod
    def _unreadable(data: bytes) -> str | None:
        if len(data) > MAX_BYTES:
            return f"larger than {MAX_BYTES // (1024 * 1024)} MB"
        if not data.startswith(b"%PDF"):
            return "not a PDF"
        return None

    # ------------------------------------------------------------ read
    def confirmed(self, upload_id: str) -> dict | None:
        p = self.dir(upload_id) / "confirmed.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def view(self, upload_id: str) -> dict:
        state = self._read(upload_id)
        conf = self.confirmed(upload_id)
        rows = [{**r, "row_id": r["sha256"][:12]} for r in state["rows"]]
        return {"upload_id": upload_id, "confirmed": conf is not None,
                "confirmed_by": conf["confirmed_by"] if conf else None, "confirmed_at": conf["confirmed_at"] if conf else None,
                "kinds": [t.value for t in InstrumentType], "how_options": list(HOW), "rows": rows,
                "refused": state["refused"], "unplaced": [r["row_id"] for r in rows if r["status"] == "unplaceable"]}

    # ------------------------------------------------------------ the mapping form fallback
    def add_row(self, upload_id: str, body: dict) -> dict:
        if self.confirmed(upload_id):
            raise Refusal("These documents are already confirmed and can no longer be changed.", 409)
        state = self._read(upload_id)
        key = str(body.get("row_id", ""))
        row = next((r for r in state["rows"] if r["sha256"][:12] == key), None)
        if row is None or row["status"] == "proposed":
            raise Refusal("Name a row the proposer could not place (row_id from the proposal).")
        kind, policy, how, reason = (str(body.get(k, "")).strip() for k in ("kind", "policy", "how", "reason"))
        quote_text, page = str(body.get("quote", "")), body.get("page")
        q, why = (None, "give one line printed on the document, and its page") if not quote_text.strip() or not isinstance(page, int) \
            else verify_line(self.dir(upload_id) / "raw" / row["stored"], page, quote_text)
        errors = _row_errors(kind, policy, how, reason, (q.text,) if q else ())
        if why:
            errors.append(why)
        if q is not None and q.count != 1:
            errors.append(f"the line {q.text!r} occurs {q.count} times on page {q.page}; give a line that occurs once")
        if errors:
            raise Refusal("That row cannot be added.", 400, errors)
        qd = {**q.model_dump(), "field": "typed"}
        row.update(status="typed", kind=kind, policy=policy, how=how, reason="", typed_reason=reason, quotes=[qd], anchor=qd)
        self._write(upload_id, state)
        return self.view(upload_id)

    # ------------------------------------------------------------ confirm and freeze
    def confirm(self, upload_id: str, body: dict) -> dict:
        folder = self.dir(upload_id)
        if self.confirmed(upload_id):
            raise Refusal("These documents are already confirmed and can no longer be changed.", 409)
        who = str(body.get("confirmed_by", "")).strip()
        if not who:
            raise Refusal("Say who confirmed this mapping (confirmed_by).")
        state = self._read(upload_id)
        placed = {r["sha256"][:12]: r for r in state["rows"] if r["status"] in ("proposed", "typed")}
        sent = {str(r.get("row_id", "")): r for r in body.get("rows", []) if isinstance(r, dict)}
        errors = [f"{placed[k]['file']}: not confirmed; confirm, correct or exclude every document" for k in placed if k not in sent]
        errors += [f"unknown row {k!r}" for k in sent if k not in placed]
        routes, labels, doc_ids, record, excluded, pending_amends = [], [], set(), [], [], []
        for key, row in placed.items():
            r = sent.get(key)
            if r is None:
                continue
            if r.get("exclude") is True:
                excluded.append(row["file"])
                continue
            kind, policy, how, reason = (str(r.get(k, "")).strip() for k in ("kind", "policy", "how", "reason"))
            reason = reason or row.get("typed_reason") or ""
            row_errors = [f"{row['file']}: {e}" for e in _row_errors(kind, policy, how, reason, tuple(q["text"] for q in row["quotes"]))]
            path = folder / "raw" / row["stored"]
            src = open_source(path)
            citation, scope = None, None
            if r.get("scope_page") is not None or r.get("scope_text"):
                try:
                    scope = Citation.model_validate({"source_file": row["stored"], "sha256_of_file": src.sha256,
                                                     "locator": {"kind": "page_quote", "page": r.get("scope_page")},
                                                     "text": "\n".join(" ".join(ln.split()) for ln in str(r.get("scope_text", "")).split("\n"))})
                except Exception:
                    row_errors.append(f"{row['file']}: give a page and at least one line from it")
                if scope is not None and (broken := verify_citation(scope, src)):
                    row_errors.append(f"{row['file']}: these lines were not found on that page: {broken}")
                    scope = None
            if scope is not None:
                citation = scope
            elif row["anchor"]:
                a = row["anchor"]
                citation = Citation.model_validate({"source_file": row["stored"], "sha256_of_file": src.sha256,
                                                    "locator": {"kind": "page_quote", "page": a["page"]}, "text": a["text"]})
                if broken := verify_citation(citation, src):
                    row_errors.append(f"{row['file']}: the line you gave was not found on that page: {broken}")
            if row_errors:
                errors += row_errors
                continue
            doc_id, n = _slug(row["form_number"] or row["title"] or Path(row["file"]).stem), 2
            base = doc_id
            while doc_id in doc_ids:
                doc_id, n = f"{base}_{n}", n + 1
            doc_ids.add(doc_id)
            strength = RouteStrength(how)
            method = MappingMethod.JUDGMENT if how == "judgment" else MappingMethod.LABEL
            written = reason
            routes.append(DocumentMapping(doc_id=doc_id, describes=(DocumentRoute(
                policy=policy, method=method, strength=strength, reasoning=written if how == "judgment" else None, citation=citation,
                scope="citation" if scope is not None else "document"),)))
            amends_q = next((q for q in row["quotes"] if q["field"] == "amends"), None)
            if amends_q:
                pending_amends.append((len(routes) - 1, amends_q, row, policy, src.sha256))
            eff = edition_date(row["edition"])
            labels.append(SourceLabel(
                source_id=doc_id, file=row["stored"], url=None, fetch_note="uploaded by a person; see confirmed.json",
                sha256_of_file=src.sha256, extractor=Extractor.PDF_COLUMNS, edgar_type=None, edgar_sequence=None,
                instruments=(InstrumentLabel(doc_id=doc_id, version=row["edition"] or "uploaded", instrument_type=InstrumentType(kind),
                                             issuer=row["form_number"] or row["title"] or row["file"], policy_numbers=(policy,),
                                             effective_date=eff, first_page=1, last_page=row["pages"]),)))
            record.append({"doc_id": doc_id, "file": row["file"], "sha256": row["sha256"], "kind": kind, "policy": policy, "how": how,
                           "reason": written, "proposed_kind": row["kind"], "proposed_policy": row["policy"],
                           "proposed_how": row["how"], "proposed_form": row["form_number"], "route_citation": citation.model_dump(mode="json")})
        # D10: what an uploaded endorsement amends, from its printed line. The amended document counts as
        # present when another confirmed file's printed form number (edition dropped) appears in that line.
        cores = {_core(rec["proposed_form"]): rec["doc_id"] for rec in record if rec.get("proposed_form")}
        for i, q, row, policy, sha in pending_amends:
            cit = Citation.model_validate({"source_file": row["stored"], "sha256_of_file": sha,
                                           "locator": {"kind": "page_quote", "page": q["page"]}, "text": q["text"]})
            if verify_citation(cit, open_source(folder / "raw" / row["stored"])):
                continue  # repeats on its page; the check cannot rest on it, so it is not recorded
            line = " ".join(q["text"].upper().split())
            hit = next((d for c, d in cores.items() if c and c in line and d != routes[i].doc_id), None)
            routes[i] = routes[i].model_copy(update={"amends": AmendsRoute(
                instrument=q["text"], instrument_doc_id=hit, policy=policy, method=MappingMethod.LABEL,
                strength=RouteStrength.READ, reasoning=None, citation=cit)})
        if not routes and not errors:
            errors.append("every document was excluded, so there is nothing to check")
        if errors:
            raise Refusal("What each document is was not confirmed.", 400, errors)
        mapping = DocumentMappingFile(note=f"Confirmed by {who} on {_now()}: uploaded documents, mapping proposed by the model and confirmed by a person.",
                                      documents=tuple(routes))
        (folder / "instruments.json").write_text(SourceManifest(note="Uploaded documents; kinds as confirmed.", sources=tuple(labels)).model_dump_json(indent=1), encoding="utf-8")
        (folder / "document_mappings.json").write_text(mapping.model_dump_json(indent=1), encoding="utf-8")
        shutil.copyfile(self.predicates, folder / "predicates.json")
        (folder / "confirmed.json").write_text(json.dumps(
            {"upload_id": upload_id, "confirmed_by": who, "confirmed_at": _now(), "rows": record, "excluded": excluded,
             "refused": state["refused"]}, indent=1, sort_keys=True), encoding="utf-8")
        return self.view(upload_id)

    # ------------------------------------------------------------ for a run
    def packet(self, upload_id: str) -> tuple[Path, list[str], DocumentMappingFile]:
        folder = self.dir(upload_id)
        mappings = DocumentMappingFile.model_validate_json((folder / "document_mappings.json").read_text(encoding="utf-8"))
        return folder, [m.doc_id for m in mappings.documents], mappings


def _core(form: str) -> str:
    """A printed form number without its edition: "HO 00 03 04 91" -> "HO 00 03"."""
    t = " ".join((form or "").upper().split())
    return re.sub(r"\s+\d{2}\s+\d{2}$", "", t)


def _row_errors(kind: str, policy: str, how: str, reason: str, quotes: tuple[str, ...]) -> list[str]:
    errors = []
    if kind not in {t.value for t in InstrumentType}:
        errors.append(f"kind must be one of {[t.value for t in InstrumentType]}")
    if not policy:
        errors.append("name the policy this document describes")
    if how not in HOW:
        errors.append(f"how we know must be one of {list(HOW)}")
    if how == "judgment" and not reason:
        errors.append("a judgment needs a written reason")
    if how == "read" and not any(" ".join(policy.lower().split()) in " ".join(q.lower().split()) for q in quotes):
        errors.append("'read' needs the policy to be printed in a verified quote; otherwise it is a judgment")
    return errors
