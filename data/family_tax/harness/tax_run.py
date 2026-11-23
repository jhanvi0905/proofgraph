"""Tax holdout, Phase B: the fc_run_d12.py protocol (server routes, every candidate line confirmed, nothing set aside),
plus the preregistered figure-pick rules and the diagnostic decide. argv[1]: output folder. Set PROOFGRAPH_CACHE to a
fresh empty folder so every call is live."""
import os
import json, pathlib, re, sys
from fastapi.testclient import TestClient
import app.server as server
from proofgraph.trace import Trace
from app.server import create_app
from app.limit import LiveRunLimit
S = pathlib.Path(os.environ["PROOFGRAPH_TAX_WORKDIR"]) / ""
UPLOADS = {"T-SALT": "7ae086963c22", "T-1099K": "f9dd0b20bdb1", "T-BONUS": "5c86f56cc81a"}
out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
server.Trace = lambda _p: Trace(out / "trace.jsonl")
c = TestClient(create_app(uploads_dir=S / "tax_uploads", limit=LiveRunLimit(0), upload_limit=LiveRunLimit(0)))
pre = json.loads(pathlib.Path("data/family_tax/preregistration.json").read_text())
only = set(sys.argv[2:])


def pick(claim: str, line: dict):
    """The preregistered pick rules, mechanically. Returns (index, rule) or (None, why)."""
    q, figs = " ".join(line["quote"].split()), line["figures"]
    if not figs:
        return None, "no figures listed"
    if "by striking" in q:
        return None, "strike line: no pick"
    if len(figs) >= 2 and re.search(r"\(\s*" + re.escape(figs[1]) + r"\s+in the case of a married individual filing a separate", q):
        return 0, "rule 1: other figure is the married-filing-separately parenthetical"
    y = re.search(r"\b(20\d\d)\b", claim)
    if y:
        m = re.search(re.escape(y.group(1)) + r",\s*(\$[\d,]+)", q)
        if m and m.group(1) in figs:
            return figs.index(m.group(1)), f"rule 2: figure printed after {y.group(1)}"
    return None, "no figure for the claim's subject: no pick"


res = []
for pk in pre["packets"]:
    uid, policy = UPLOADS[pk["id"]], pk["policy"]
    for cl in pk["claims"]:
        if only and cl["id"] not in only:
            continue
        rd = c.post("/api/claim/read", json={"packet": "upload:" + uid, "text": cl["text"]}).json()
        rec = {"id": cl["id"], "real_world": cl["real_world"], "predicted": cl["predicted"],
               "read": {k: rd.get(k) for k in ("kind", "written", "value", "currency", "basis", "policy_matches", "refusal")}}
        g = c.post("/api/claim/gather", json={"packet": "upload:" + uid, "text": cl["text"], "policy": policy,
                                               "policy_source": "matched_in_claim" if policy in rd.get("policy_matches", []) else "chosen"}).json()
        if "refusal" in g:
            rec["result"], rec["reason"] = "refused", g["refusal"]
        else:
            rec["lines"] = [{k: l.get(k) for k in ("line_id", "doc", "where", "value", "basis", "side", "no_value", "figures", "quote")} for l in g["lines"]]
            rec["nothing_found"] = g["nothing_found"]; rec["ask_basis"] = g.get("ask_basis"); rec["ask_currency"] = g.get("ask_currency")
            if not g["lines"]:
                rec["result"] = "no lines"
            else:
                figures, picks = {}, []
                for l in g["lines"]:
                    if l.get("no_value"):
                        i, why = pick(cl["text"], l)
                        picks.append({"line_id": l["line_id"], "figures": l["figures"], "pick": i, "why": why})
                        if i is not None:
                            figures[l["line_id"]] = i
                rec["picks"] = picks
                body = {"confirmed": [l["line_id"] for l in g["lines"]], "confirmed_by": "Tax holdout run (author)", "figures": figures}
                r = c.post(f"/api/claim/{g['gather_id']}/decide", json=body)
                d = r.json()
                rec["result"] = d.get("status") or "refused"; rec["reason"] = d.get("reason") or d.get("refusal")
                if d.get("review_id"):
                    (out / f"{cl['id']}_review.html").write_text(c.get(f"/api/review/{d['review_id']}").text)
                elif "set that line aside" in (d.get("refusal") or ""):  # value_ambiguous: the diagnostic decide, not scored
                    aside = {p["line_id"]: "states several amounts; no figure is for the claim's subject" for p in picks if p["pick"] is None}
                    body2 = {"confirmed": [l["line_id"] for l in g["lines"] if l["line_id"] not in aside], "dropped": aside,
                             "confirmed_by": "Tax holdout run (author), diagnostic", "figures": figures}
                    d2 = c.post(f"/api/claim/{g['gather_id']}/decide", json=body2).json()
                    rec["diagnostic"] = {"result": d2.get("status") or "refused", "reason": d2.get("reason") or d2.get("refusal"), "set_aside": list(aside)}
                    if d2.get("review_id"):
                        (out / f"{cl['id']}_diag_review.html").write_text(c.get(f"/api/review/{d2['review_id']}").text)
        res.append(rec)
        print(cl["id"], "| real", cl["real_world"], "| predicted", cl["predicted"], "| got", rec["result"], "|", rec.get("reason"), flush=True)
        for l in rec.get("lines", []):
            print("    ", l["side"], l["doc"][:28], l["where"], l["value"], ("AMBIG " + str(l["figures"])) if l.get("no_value") else "", "|", " ".join(l["quote"].split())[:120], flush=True)
        for p in rec.get("picks", []):
            print("     pick:", p, flush=True)
        if rec.get("diagnostic"):
            print("     diagnostic:", rec["diagnostic"], flush=True)
        (out / "results.json").write_text(json.dumps(res, indent=1))
