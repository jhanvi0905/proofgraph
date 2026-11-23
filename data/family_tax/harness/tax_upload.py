"""Phase B, step 1: upload one packet's files through /api/upload and print the proposals. argv: packet id, files..."""
import json, pathlib, sys
from fastapi.testclient import TestClient
from app.server import create_app
from app.limit import LiveRunLimit
S = pathlib.Path("/private/tmp/claude-501/-Users-jhanviarora-proofgraph--claude-worktrees-proofgraph-claim-retirement-0b9c72/55a852c0-17de-44db-ab38-7f0858561734/scratchpad")
c = TestClient(create_app(uploads_dir=S / "tax_uploads", limit=LiveRunLimit(0), upload_limit=LiveRunLimit(0)))
pid, files = sys.argv[1], sys.argv[2:]
v = c.post("/api/upload", files=[("files", (pathlib.Path(f).name, open(f, "rb").read(), "application/pdf")) for f in files]).json()
(S / "tax_views").mkdir(exist_ok=True)
(S / "tax_views" / f"{pid}.json").write_text(json.dumps(v, indent=1))
print(json.dumps({"upload_id": v.get("upload_id"), "refused": v.get("refused"), "rows": [{k: r.get(k) for k in ("row_id", "file", "status", "kind", "form_number", "edition", "title", "amends", "policy", "effective_date", "effective_phrase", "how", "rejected", "reason")} | {"quotes": r.get("quotes")} for r in v.get("rows", [])]}, indent=1))
