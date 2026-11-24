"""Phase B, step 2: a person types rows the proposer could not place, then confirms every row. argv: spec.json"""
import os
import json, pathlib, sys
from fastapi.testclient import TestClient
from app.server import create_app
from app.limit import LiveRunLimit
S = pathlib.Path(os.environ["PROOFGRAPH_TAX_WORKDIR"]) / ""
c = TestClient(create_app(uploads_dir=S / "tax_uploads", limit=LiveRunLimit(0), upload_limit=LiveRunLimit(0)))
spec = json.loads(pathlib.Path(sys.argv[1]).read_text())
for pk in spec:
    uid = pk["upload_id"]
    for t in pk.get("typed", []):
        r = c.post(f"/api/upload/{uid}/rows", json=t); print(pk["id"], "typed row", t["row_id"], r.status_code, r.json().get("refusal"), r.json().get("errors"))
    r = c.post(f"/api/upload/{uid}/confirm", json={"confirmed_by": "Tax holdout run (author)", "rows": pk["rows"]})
    print(pk["id"], "confirm", r.status_code, json.dumps(r.json())[:300])
    conf = json.loads((S / "tax_uploads" / uid / "confirmed.json").read_text())
    for row in conf["rows"]:
        print("   ", row["doc_id"], row["kind"], row["policy"], row["effective_date"], row["effective_source"])
