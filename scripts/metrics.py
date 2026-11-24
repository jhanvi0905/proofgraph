"""Evaluation metrics for every recorded run set. Prints markdown tables. No network, no API key.

    uv run python scripts/metrics.py

Sources of each number:
- Family A, family B, D11: replayed here from data/recorded/model (a call with no recorded response is
  skipped and reported; nothing is ever sent to the API). Tokens are the recorded ones. Replays carry no latency.
- Tax: data/family_tax/run{1,2}_results.json (outcomes and shown lines). Cost, from results/family_tax.md.
- Family C and IRS: no machine-readable run records exist in the repo. The rows below are transcribed by hand
  from results/family_c.md and results/live_irs.md. Check them against those files.
Definitions are in results/metrics.md.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

os.environ["ANTHROPIC_API_KEY"] = ""  # replays only: this script never calls the API

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data"

from proofgraph import model  # noqa: E402
from proofgraph.claims import load_claims, question_policies  # noqa: E402
from proofgraph.schema import DocumentMappingFile, Claim  # noqa: E402
from proofgraph.trace import Trace  # noqa: E402

PRICE_IN, PRICE_OUT = 4 / 1e6, 20 / 1e6  # claude-opus-5-5, USD per token
ANSWERS = {"supported", "contradicted", "quoted"}  # never a refusal


# ------------------------------------------------------------------ one observation per (run, claim)

@dataclass
class Obs:
    set_id: str
    item: str
    exp: str  # supported contradicted quoted unresolved not_found refuse refusal_any
    exp_reason: str | None
    got: str  # supported contradicted quoted unresolved not_found refuse
    got_reason: str | None
    exp_gov: str | None = None
    exp_rule: str | None = None
    got_gov: str | None = None
    got_rule: str | None = None
    prec_labelled: bool = True  # False when the set has no label for governing document or rule
    rule_labelled: bool = True  # False when only the governing document is labelled (tax)


def is_refusal(cat: str) -> bool:
    return cat not in ANSWERS


def exp_is_refusal(cat: str) -> bool:
    return cat in {"unresolved", "not_found", "refuse", "refusal_any"}


def cat_match(o: Obs) -> bool:
    if o.exp == "refusal_any":
        return is_refusal(o.got)
    return o.exp == o.got


def full_match(o: Obs) -> bool:
    if not cat_match(o):
        return False
    return o.exp_reason is None or o.exp_reason == o.got_reason


@dataclass
class SetInfo:
    set_id: str
    title: str
    status: str  # dev | holdout | not clean
    obs: list[Obs] = field(default_factory=list)
    note: str = ""


# ------------------------------------------------------------------ replay engine

class NeedsLive(Exception):
    pass


CALLS: list[dict] = []  # every model call made by a replay: key, source, tokens


def _install_spy() -> None:
    """Wrap complete_json so every call is logged and a call with no stored response never reaches the API."""
    real = model.complete_json

    def spy(prompt, schema, *, system, template, effort="low"):
        key = hashlib.sha256(json.dumps([model.MODEL, system, prompt, schema, effort], sort_keys=True).encode()).hexdigest()
        rec = (model.RECORDED_DIR / f"{key}.json").exists()
        loc = (model.CACHE_DIR / f"{key}.json").exists()
        if not rec and not loc:
            raise NeedsLive(key[:12])
        reply = real(prompt, schema, system=system, template=template, effort=effort)
        CALLS.append({"key": key, "source": "recorded" if rec else "local_cache", "in": reply.input_tokens,
                      "out": reply.output_tokens})
        return reply

    from proofgraph import atomize as A, passes as P
    A.atomize.__defaults__ = (spy,)
    P.support.__defaults__ = (spy,)
    P.attack.__defaults__ = (spy,)


@dataclass
class RunStats:
    """Per replayed packet: model calls, tokens, and what became of each piece of model evidence."""
    set_id: str
    item: str
    calls: int = 0
    tok_in: int = 0
    tok_out: int = 0
    repairs: int = 0
    proposed: int = 0  # evidence items the model returned (every attempt of every pass)
    kept: int = 0  # passed the pass-level check (id shown, quote found once, citation verifies)
    pass_rejects: Counter = field(default_factory=Counter)
    accepted: int = 0  # became an Assertion or Clause
    invalid: Counter = field(default_factory=Counter)  # InvalidAssertion reasons
    skipped: str | None = None
    sources: Counter = field(default_factory=Counter)

    @property
    def cost(self) -> float:
        return self.tok_in * PRICE_IN + self.tok_out * PRICE_OUT


def _reject_kind(msg: str) -> str:
    if "does not occur exactly once" in msg:
        return "quote not found exactly once in the passage"
    if "was not among the passages given" in msg:
        return "passage id not shown to the model"
    m = re.sub(r"^span \S+: ", "", msg)
    return "citation check: " + m[:70]


def _stats(set_id: str, item: str, trace: Trace, run, n0: int) -> RunStats:
    st = RunStats(set_id, item)
    for r in trace.records:
        if r.stage in ("atomize", "support", "attack") and r.model:
            st.calls += 1
            st.tok_in += r.input_tokens
            st.tok_out += r.output_tokens
            st.repairs += r.repairs if r.stage != "atomize" else 0
        if r.stage in ("support", "attack"):
            m = re.search(r"proposed=(\d+) kept=(\d+)", r.detail or "")
            if m:
                st.proposed += int(m.group(1))
                st.kept += int(m.group(2))
            for e in r.rejects:
                st.pass_rejects[_reject_kind(e)] += 1
    for c in CALLS[n0:]:
        st.sources[c["source"]] += 1
    if run is not None:
        st.accepted = len(run.assertions) + len(run.clauses)
        for inv in run.invalid:
            st.invalid[inv.reason.split(":")[0][:60]] += 1
    return st


def _out(v) -> tuple[str, str | None, str | None, str | None]:
    reason = v.supported_reason or v.unresolved_reason or v.not_found_reason
    return (v.verdict.value, reason.value if reason else None,
            v.governing_rule.value if v.governing_rule else None, v.governing_doc_id)


def _manifest_gillette():
    mappings = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    return mappings, [d.doc_id for d in mappings.documents]


def replay_all() -> tuple[dict[str, SetInfo], list[RunStats], list[str]]:
    from proofgraph.pipeline import run_packet
    from proofgraph.grouping import decide_typed, gather_typed, read_claim

    _install_spy()
    sets: dict[str, SetInfo] = {}
    stats: list[RunStats] = []
    skipped: list[str] = []
    fb = DATA / "family_b"

    # ---- family A (dev): the retention packet, from the pipeline's own evidence (pgrun derive)
    sets["A"] = SetInfo("A", "Family A, Gillette D&O retention (dev set)", "dev")
    claims_a = {c.claim_id: c for c in load_claims(DATA / "claims.json", DATA / "slots.json")}
    mappings_a, docs_a = _manifest_gillette()
    for cid, c in claims_a.items():
        tr, n0 = Trace(None), len(CALLS)
        try:
            run = run_packet("gillette", c, docs_a, mappings_a, DATA, tr, question_policies(c.slot, DATA / "slots.json"))
        except NeedsLive as e:
            skipped.append(f"A:{cid} (needs live call {e})")
            continue
        # expected: the hand-labelled verdict (README, DECISIONS D8: unresolved, documents_disagree); cited in regression_d11.json
        exp = next(x for x in json.load(open(DATA / "regression_d11.json"))["claims"] if x["claim_id"] == cid)
        g = _out(run.verdict) if run.verdict else ("refuse", run.failure, None, None)
        sets["A"].obs.append(Obs("A", cid, exp["verdict"], exp["reason"], g[0], g[1], exp["governing_doc_id"],
                                 exp["governing_rule"], g[3] if g[2] else None, g[2]))
        stats.append(_stats("A", cid, tr, run, n0))

    # ---- family B: every packet once, scored against both label files
    labels = json.loads((fb / "labels.json").read_text(encoding="utf-8"))
    d9 = json.loads((fb / "labels_d9.json").read_text(encoding="utf-8"))
    d9_exp = {p["packet_id"]: p["expected"] for p in d9["packets"]}
    pk_all = [dict(p, prereg=True) for p in labels["packets"]] + [dict(p, prereg=False) for p in d9["packets"] if "claim_id" in p]
    claims_b = {c.claim_id: c for c in load_claims(fb / "claims.json", fb / "slots.json")}
    mappings_b = DocumentMappingFile.model_validate_json((fb / "document_mappings.json").read_text(encoding="utf-8"))
    sets["B-pre"] = SetInfo("B-pre", "Family B, preregistered labels (labels.json)", "holdout",
                            note="replayed under the current (post-D9) rules; the as-run table in results/family_b.md was 8 of 8")
    sets["B-D9"] = SetInfo("B-D9", "Family B, D9 expectations (labels_d9.json)", "not clean",
                           note="labels written after the rules were built, by the person who built them; 3 packets added after seeing the system")
    for pk in pk_all:
        c = claims_b[pk["claim_id"]]
        tr, n0 = Trace(None), len(CALLS)
        try:
            run = run_packet(pk["packet_id"], c, pk["instruments"], mappings_b, DATA, tr, question_policies(c.slot, fb / "slots.json"))
        except NeedsLive as e:
            skipped.append(f"B:{pk['packet_id']} (needs live call {e})")
            continue
        g = _out(run.verdict) if run.verdict else ("refuse", run.failure, None, None)
        gov = g[3] if g[2] else None  # labels name a governing document only when a rule named it
        if pk["prereg"]:
            e = pk["expected"]
            sets["B-pre"].obs.append(Obs("B-pre", pk["packet_id"], e["verdict"], e["reason"], g[0], g[1], e["governing_doc_id"], e["rule"], gov, g[2]))
        e = d9_exp[pk["packet_id"]]
        sets["B-D9"].obs.append(Obs("B-D9", pk["packet_id"], e["verdict"], e["reason"], g[0], g[1], e["governing_doc_id"], e["rule"], gov, g[2]))
        stats.append(_stats("B", pk["packet_id"], tr, run, n0))

    # ---- D11 regression: five claims typed as text, every candidate line confirmed
    sets["D11"] = SetInfo("D11", "D11 regression, typed claims (regression_d11.json)", "not clean",
                          note="regression fixture written from earlier replays; re-runs the family A claim and four family B claims as typed text")
    fx = json.loads((DATA / "regression_d11.json").read_text(encoding="utf-8"))
    packs = {"gillette": (mappings_a, docs_a), "homeowners": (mappings_b, ["ho_00_03", "ho_00_15"])}
    for e in fx["claims"]:
        mp, docs = packs[e["packet"]]
        pols = tuple(sorted({d.policy for m in mp.documents for d in m.describes}))
        r = read_claim(e["claim_text"], pols)
        tr, n0 = Trace(None), len(CALLS)
        try:
            g = gather_typed(r, r.policy_matches[0], e["claim_id"], docs, mp, DATA, tr)
            d = decide_typed(g, {c.line_id for c in g.candidates}, {}, confirmed_by="metrics", policy_source="matched_in_claim")
        except NeedsLive as ex:
            skipped.append(f"D11:{e['claim_id']} (needs live call {ex})")
            continue
        exp_reason = e["reason"] or e["supported_reason"]
        if d.refusal or d.run.verdict is None:
            o = Obs("D11", e["claim_id"], e["verdict"], exp_reason, "refuse", d.refusal or g.run.failure, e["governing_doc_id"],
                    e["governing_rule"])
        else:
            v = _out(d.run.verdict)
            o = Obs("D11", e["claim_id"], e["verdict"], exp_reason, v[0], v[1], e["governing_doc_id"], e["governing_rule"],
                    d.run.verdict.governing_doc_id, v[2])
        sets["D11"].obs.append(o)
        stats.append(_stats("D11", e["claim_id"], tr, g.run, n0))
    return sets, stats, skipped


# ------------------------------------------------------------------ recorded runs without replay (tax, C, IRS)

def _tax_cat(result: str, reason: str) -> tuple[str, str | None]:
    if result in ("supported", "contradicted", "quoted"):
        return result, None
    if result == "no lines":
        return "refuse", "no_lines"
    if "more than one amount" in reason:
        return "refuse", "more_than_one_value"
    if "dates" in reason:
        return "refuse", "dates_not_supported"
    if "more than one amount, and the reads did not say" in reason or "states more than one amount" in reason:
        return "refuse", "value_ambiguous"
    if "couldn't be turned" in reason:
        return "refuse", "atomize_refused"
    return "refuse", "other"


def _tax_got(r: dict) -> tuple[str, str | None, str | None, str | None]:
    cat, reason = _tax_cat(r["result"], r.get("reason", ""))
    if cat == "refuse" and r["id"] in ("S2",):
        reason = "value_ambiguous"
    text = r.get("reason", "")
    gov = "plaw" if cat in ("supported", "contradicted") and re.match(r"(PUBLIC LAW|PLAW)", text) else None
    rule = "endorsement_over_base" if gov and "endorsement overrides" in text else None
    return cat, reason, gov, rule


def load_tax() -> dict[str, SetInfo]:
    out = {}
    pre = json.loads((DATA / "family_tax" / "preregistration.json").read_text(encoding="utf-8"))
    claims = {c["id"]: c for p in pre["packets"] for c in p["claims"]}
    for run in ("run1", "run2"):
        res = json.loads((DATA / "family_tax" / f"{run}_results.json").read_text(encoding="utf-8"))
        real = SetInfo(f"Tax-real-{run[-1]}", f"Tax holdout run {run[-1]}, real-world labels", "holdout",
                       note="labels = the real answer from the law; governing document label (the Public Law) derived by this script's author from each claim's real_world_why")
        pred = SetInfo(f"Tax-pred-{run[-1]}", f"Tax holdout run {run[-1]}, preregistered predictions as labels", "holdout",
                       note="labels are the author's predictions of what the system returns, not the right answer")
        for r in res:
            c = claims[r["id"]]
            cat, reason, gov, rule = _tax_got(r)
            real.obs.append(Obs(real.set_id, r["id"], c["real_world"], None, cat, reason, "plaw", None, gov, rule, prec_labelled=True, rule_labelled=False))
            m = re.match(r"(unresolved|refused) \((\w+)\)", c["predicted"])
            pc = "unresolved" if m.group(1) == "unresolved" else "refuse"
            pred.obs.append(Obs(pred.set_id, r["id"], pc, m.group(2), cat, reason if cat in ("refuse",) else (None if cat != "unresolved" else reason), None, None, gov, rule, prec_labelled=False))
        out[real.set_id] = real
        out[pred.set_id] = pred
    return out


def load_family_c_irs() -> dict[str, SetInfo]:
    """Transcribed from results/family_c.md and results/live_irs.md (no machine-readable record exists)."""
    S, C, Q = "supported", "contradicted", "quoted"
    R = "refuse"
    exp = {"C1": (S, None), "C2": (C, None), "C3": (S, None), "C4": (Q, None), "C5": ("refusal_any", None)}

    def mk(set_id, title, status, rows, note):
        s = SetInfo(set_id, title, status, note=note)
        for cid, (g, gr) in rows.items():
            e, er = exp[cid]
            s.obs.append(Obs(set_id, cid, e, er, g, gr, prec_labelled=False))
        return s

    sets = {
        "C-orig1": mk("C-orig1", "Family C (Chubb cyber), original run 1, parser as frozen", "holdout",
                      {"C1": (R, "no_lines"), "C2": (R, "no_lines"), "C3": (S, None), "C4": (R, "atomize_refused"), "C5": (R, "no_lines")},
                      "preregistered; one live run per claim"),
        "C-orig2": mk("C-orig2", "Family C, original run 2 (watermark glyphs dropped), C4 not re-run", "not clean",
                      {"C1": (S, None), "C2": (R, "no_lines"), "C3": (R, "no_lines"), "C5": (R, "no_lines")},
                      "parser fix made after seeing run 1"),
        "C-D12-1": mk("C-D12-1", "Family C under D12, run 1", "not clean",
                      {"C1": (S, None), "C2": (C, None), "C3": (S, None), "C4": (Q, None), "C5": (R, "no_lines")},
                      "D12 fixes made after seeing Family C output"),
        "C-D12-2": mk("C-D12-2", "Family C under D12, run 2", "not clean",
                      {"C1": (S, None), "C2": (C, None), "C3": (S, None), "C4": (Q, None), "C5": (R, "no_lines")},
                      "D12 fixes made after seeing Family C output"),
    }
    irs = SetInfo("IRS", "IRS live runs (results/live_irs.md)", "not clean",
                  note="not preregistered; row 5 has one line set aside by a person")
    rows = [("HSA $4,300", S, S, None, "later_effective_date"), ("HSA $4,150", C, C, None, "later_effective_date"),
            ("401k $23,500", S, S, None, "later_effective_date"), ("401k $23,000, all lines confirmed", C, "unresolved", "documents_disagree", None),
            ("401k $23,000, one line set aside", C, C, None, "later_effective_date")]
    for item, e, g, gr, rule in rows:
        irs.obs.append(Obs("IRS", item, e, None, g, gr, None, None, "named" if rule else None, rule, prec_labelled=False))
    sets["IRS"] = irs
    return sets


# ------------------------------------------------------------------ metrics

POOLS = [
    ("Holdouts pooled, clean (B-pre, Tax-real x2 runs, C-orig1)", ["B-pre", "Tax-real-1", "Tax-real-2", "C-orig1"]),
    ("All sets pooled (A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS)", ["A", "B-D9", "Tax-real-1", "Tax-real-2", "C-orig1", "C-D12-1", "C-D12-2", "IRS"]),
]
ORDER = ["A", "B-pre", "B-D9", "D11", "Tax-real-1", "Tax-real-2", "Tax-pred-1", "Tax-pred-2", "C-orig1", "C-orig2", "C-D12-1", "C-D12-2", "IRS"]


def rows_for(sets: dict[str, SetInfo]):
    for sid in ORDER:
        if sid in sets:
            yield sid, sets[sid].obs
    for name, members in POOLS:
        yield name, [o for m in members if m in sets for o in sets[m].obs]


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "n=0"


def md(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


COLS = [("supported", None), ("contradicted", None), ("unresolved", "documents_disagree"), ("unresolved", "governing_instrument_absent"),
        ("unresolved", "amounts_not_comparable"), ("not_found", None), ("quoted", None), ("refuse", None), ("refusal_any", None)]


def col_name(c):
    return c[0] if c[1] is None else f"unresolved: {c[1]}"


def table1(sets, strict: bool) -> str:
    fn = full_match if strict else cat_match
    rows = []
    for name, obs in rows_for(sets):
        cells = []
        for cat, reason in COLS:
            sel = [o for o in obs if o.exp == cat and (reason is None or o.exp_reason == reason)]
            if cat == "unresolved" and reason is None:
                continue
            cells.append(f"{sum(fn(o) for o in sel)}/{len(sel)}" if sel else "-")
        rows.append([name] + cells + [pct(sum(fn(o) for o in obs), len(obs))])
    return md(["set"] + [col_name(c) for c in COLS if not (c[0] == "unresolved" and c[1] is None)] + ["all"], rows)


def refusal_counts(obs):
    tp = sum(is_refusal(o.got) and exp_is_refusal(o.exp) for o in obs)
    fp = sum(is_refusal(o.got) and not exp_is_refusal(o.exp) for o in obs)
    fn = sum((not is_refusal(o.got)) and exp_is_refusal(o.exp) for o in obs)
    return tp, fp, fn


# ------------------------------------------------------------------ what matters for this system

VERDICTS = ("supported", "contradicted")  # an answer with a verdict; "quoted" is an answer without one


def resolver(o: Obs) -> str:
    """Who can turn this non-answer into an answer: classified from the recorded reason and run set, never by hand per item."""
    r = o.got_reason or ""
    if o.set_id.startswith("C-orig"):
        return "fixed since (D12)"
    if r in ("atomize_refused", "more_than_one_value") or o.got == "quoted" or r == "no_lines":
        return "small system fix"  # prompts worded for insurance; "IRC" read as a currency; percentages not amounts
    if r in ("dates_not_supported", "value_ambiguous"):
        return "design gap"  # claims about a date; amending ("by striking") text
    if o.set_id == "IRS":
        return "person at confirmation"  # the "from $23,000" line, set aside in the next row
    return "other"


def what_matters(o_list) -> dict:
    real = [o for o in o_list]
    answered = [o for o in real if o.got in VERDICTS]
    wrong = [o for o in answered if o.got != o.exp]
    answerable = [o for o in real if o.exp in VERDICTS]
    right = [o for o in answerable if o.got == o.exp]
    wording = [o for o in real if o.exp == "quoted"]
    over = [o for o in answerable if o.got not in VERDICTS]
    exp_ref = [o for o in real if exp_is_refusal(o.exp)]
    refusals = [o for o in real if is_refusal(o.got)]
    named = [o for o in refusals if o.got_reason]
    return dict(n=len(real), answered=len(answered), wrong=len(wrong), right=len(right), answerable=len(answerable),
                wording=len(wording), wording_ok=sum(o.got == "quoted" for o in wording), over=over,
                exp_ref=len(exp_ref), ref_ok=sum(is_refusal(o.got) for o in exp_ref), refusals=len(refusals), named=len(named))


def table0(sets) -> tuple[str, str]:
    groups = [(sid, sets[sid].obs) for sid in ["A", "B-pre", "B-D9", "Tax-real-1", "Tax-real-2", "C-orig1", "C-D12-1", "C-D12-2", "IRS"] if sid in sets]
    groups += [(name, [o for m in members if m in sets for o in sets[m].obs]) for name, members in POOLS]
    rows, over_all = [], Counter()
    for name, obs in groups:
        w = what_matters(obs)
        rows.append([name, str(w["n"]), pct(w["wrong"], w["answered"]) + " wrong", pct(w["answered"] - w["wrong"], w["answered"]),
                     pct(w["right"], w["answerable"]), pct(w["ref_ok"], w["exp_ref"]), pct(w["wording_ok"], w["wording"]),
                     pct(w["named"], w["refusals"])])
        if name.startswith("Holdouts pooled"):
            over_all = Counter(resolver(o) for o in w["over"])
    t = md(["set", "n", "wrong answers (of answers given)", "answer precision", "coverage (answered right, of answerable)",
            "refused when it should (of expected refusals)", "wording claims quoted", "refusals with a named reason"], rows)
    o = md(["who can resolve it", "over-refusals in the clean holdout pool"], [[k, str(v)] for k, v in over_all.most_common()])
    return t, o


def table2(sets) -> str:
    rows = []
    for name, obs in rows_for(sets):
        tp, fp, fn = refusal_counts(obs)
        prec = pct(tp, tp + fp) if tp + fp else "n/a (no refusals)"
        rec = pct(tp, tp + fn) if tp + fn else "n/a (none expected)"
        under_quoted = sum(o.got == "quoted" and exp_is_refusal(o.exp) for o in obs)
        rows.append([name, str(len(obs)), str(tp), str(fp), str(fn), prec, rec, str(fp), f"{fn}" + (f" (of which quoted: {under_quoted})" if under_quoted else ""),
                     str(sum(is_refusal(o.got) for o in obs)), str(sum(exp_is_refusal(o.exp) for o in obs))])
    return md(["set", "n", "TP", "FP", "FN", "precision", "recall", "over-refusals (=FP)", "under-refusals (=FN)", "system refusals", "expected refusals"], rows)


def table3(sets) -> str:
    rows = []
    for name, obs in rows_for(sets):
        items = [o for o in obs if o.prec_labelled and (o.exp_gov or o.exp_rule or o.got_rule)]
        if not items:
            lab = [o for o in obs if o.got_rule]
            rows.append([name, "0" if obs and all(o.prec_labelled for o in obs) else "no labels", "-", "-", f"rule fired in output on {len(lab)}" if lab else "-"])
            continue
        gm = sum(o.got_gov == o.exp_gov for o in items)
        rl = [o for o in items if o.rule_labelled]
        rm = sum(o.got_rule == o.exp_rule for o in rl)
        fired = [o for o in items if o.got_rule]
        fm = sum(o.got_gov == o.exp_gov and (o.got_rule == o.exp_rule or not o.rule_labelled) for o in fired)
        rows.append([name, str(len(items)), pct(gm, len(items)), pct(rm, len(rl)) if rl else "no rule labels", f"rule fired on {len(fired)}; of those governing (+rule where labelled) match {fm}/{len(fired)}"])
    return md(["set", "n items", "governing document matches", "rule matches (labelled items)", "note"], rows)


def table4(stats: list[RunStats], tax_sets) -> tuple[str, str]:
    by = defaultdict(list)
    for s in stats:
        by[s.set_id].append(s)
    rows, rej = [], []
    for sid, ss in by.items():
        prop = sum(s.proposed for s in ss)
        kept = sum(s.kept for s in ss)
        acc = sum(s.accepted for s in ss)
        inv = sum(sum(s.invalid.values()) for s in ss)
        rep = sum(s.repairs for s in ss)
        rows.append([sid, str(len(ss)), str(prop), pct(kept, prop) if prop else "n=0", pct(acc, kept) if kept else "n=0", pct(acc, prop) if prop else "n=0", str(inv), str(rep)])
        pr = Counter()
        iv = Counter()
        for s in ss:
            pr.update(s.pass_rejects)
            iv.update(s.invalid)
        rej.append([sid, "; ".join(f"{k}: {v}" for k, v in pr.items()) or "none", "; ".join(f"{k}: {v}" for k, v in iv.items()) or "none"])
    # tax: lines shown to the person, from the run records (pass-level rejects are not recorded there)
    for sid in ("Tax-real-1", "Tax-real-2"):
        run = "run" + sid[-1]
        res = json.loads((DATA / "family_tax" / f"{run}_results.json").read_text(encoding="utf-8"))
        lines = [(r["read"]["kind"], l) for r in res for l in r.get("lines", [])]
        amt = [l for k, l in lines if k == "amount"]
        ok = [l for l in amt if l["value"] is not None]
        wd = [l for k, l in lines if k == "wording"]
        rows.append([f"{sid} (shown lines only)", str(sum(1 for r in res if "lines" in r)), "not recorded", "not recorded", pct(len(ok) + len(wd), len(amt) + len(wd)), "not recorded", str(len(amt) - len(ok)), "not recorded"])
        rej.append([sid, "not recorded", "; ".join(f"{k}: {v}" for k, v in Counter(l["no_value"][:60] for l in amt if l["value"] is None).items()) or "none"])
    return (md(["set", "claims with lines / packet runs", "evidence items proposed by the model", "passed pass-level check", "of those: became Assertion/Clause", "end to end: accepted / proposed", "invalid assertions", "repairs"], rows),
            md(["set", "pass-level rejects (reason: count)", "assertion-level rejects (reason: count)"], rej))


# costs transcribed from the results docs where no run record exists
DOC_COSTS = [
    # name, calls label, calls, input tokens, output tokens, USD stated in the doc (None: from tokens), units, unit label
    ("B as run (results/family_b.md)", "20 real of 32", 20, 27643, 1620, None, 8, "packets"),
    ("B D9 packets (results/family_b.md)", "10 real calls", 10, 13901, 1230, None, 3, "packets"),
    ("Tax, everything: 2 runs + 7 proposals + 1 trial (results/family_tax.md)", "119 live calls", 119, 462117, 38223, None, 1, "total"),
    ("Tax run 1 (cost stated, tokens not)", "53 calls", 53, None, None, 1.15, 12, "claims (2 made no model call)"),
    ("Tax run 2 (cost stated, tokens not)", "54 calls", 54, None, None, 1.19, 12, "claims (2 made no model call)"),
    ("Family C, 3 live runs under D12 (results/family_c.md)", "47 live calls", 47, 122068, 9706, None, 15, "claim-runs"),
]


def table5(stats: list[RunStats]) -> tuple[str, str, str]:
    by = defaultdict(list)
    for s in stats:
        by[s.set_id].append(s)
    rows = []
    for sid, ss in by.items():
        costs = [s.cost for s in ss]
        calls = [s.calls for s in ss]
        rows.append([sid, str(len(ss)), str(sum(calls)), f"{sum(calls)/len(ss):.1f} / {max(calls)}", f"{sum(s.tok_in for s in ss):,}", f"{sum(s.tok_out for s in ss):,}",
                     f"${sum(costs):.3f}", f"${sum(costs)/len(ss):.3f}", f"${max(costs):.3f}"])
    t1 = md(["set (replayed)", "packets", "model calls", "calls per packet mean / max", "input tokens", "output tokens", "cost if every call were live", "mean per packet", "max per packet"], rows)
    # unique responses (an identical prompt is stored once and replayed from the cache)
    uniq = {}
    for c in CALLS:
        uniq[c["key"]] = c
    tin = sum(c["in"] for c in uniq.values())
    tout = sum(c["out"] for c in uniq.values())
    src = Counter(c["source"] for c in uniq.values())
    t2 = (f"Distinct model responses used by all replays: {len(uniq)} ({dict(src)}); {tin:,} input and {tout:,} output tokens = ${tin*PRICE_IN + tout*PRICE_OUT:.2f}. "
          f"Total calls made across replays: {len(CALLS)}.")
    drows = []
    for name, calls, n, ti, to, usd, units, unit in DOC_COSTS:
        cost = usd if usd is not None else (ti * PRICE_IN + to * PRICE_OUT if ti else None)
        drows.append([name, calls, f"{ti:,}" if ti else "not given", f"{to:,}" if to else "not given",
                      f"${cost:.2f}" if cost is not None else "-", f"${cost/n:.3f}" if cost is not None else "-",
                      f"${cost/units:.3f} ({units} {unit})" if cost is not None else "-"])
    t3 = md(["live run (transcribed from the results doc)", "calls", "input tokens", "output tokens", "cost at $4/$20", "per call", "per unit (mean; max not recorded)"], drows)
    return t1, t2, t3


def latency_note() -> str:
    paths = sorted((DATA / "uploads").glob("*/propose.trace.jsonl")) if (DATA / "uploads").exists() else []
    lats = []
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if r.get("latency_ms") and not r.get("cache_hit"):
                lats.append(r["latency_ms"])
    base = "Latency: replays record 0 ms (no call is made). The repo holds no latency for any claim run (tax, Family C, IRS and family B live traces were not committed). "
    if lats:
        base += (f"Local, uncommitted, gitignored data/uploads/*/propose.trace.jsonl holds {len(lats)} live document-proposal calls "
                 f"(not claim runs): min {min(lats)/1000:.1f} s, median {sorted(lats)[len(lats)//2]/1000:.1f} s, max {max(lats)/1000:.1f} s.")
    else:
        base += "No local propose traces with latency were found."
    return base


def main() -> None:
    sets, stats, skipped = replay_all()
    sets.update(load_tax())
    sets.update(load_family_c_irs())
    print("# ProofGraph metrics (generated by scripts/metrics.py)\n")
    print("## Run sets\n")
    print(md(["id", "set", "status", "n", "note"], [[s.set_id, s.title, s.status, str(len(s.obs)), s.note] for sid in ORDER if (s := sets.get(sid))]))
    if skipped:
        print("\nSkipped (needed a live call; none made): " + "; ".join(skipped))
    t0, o0 = table0(sets)
    print("\n## 0. What matters for this system\n")
    print(t0)
    print("\n### Over-refusals: answerable claims it declined, by who can resolve them\n")
    print(o0)
    print("\n## 1. Bucket accuracy by expected category (category match, k/n)\n")
    print(table1(sets, False))
    print("\n### 1b. Same, requiring the reason to match where the label gives one\n")
    print(table1(sets, True))
    print("\n## 2. Refusal precision and recall\n")
    print(table2(sets))
    print("\n## 3. Precedence accuracy\n")
    print(table3(sets))
    a, b = table4(stats, sets)
    print("\n## 4. Derivation validity\n")
    print(a)
    print("\nReject reasons:\n")
    print(b)
    t1, t2, t3 = table5(stats)
    print("\n## 5. Cost and latency\n")
    print(t1)
    print("\n" + t2 + "\n")
    print(t3)
    print("\n" + latency_note())
    miss = [(o.set_id, o.item, o.exp, o.exp_reason, o.got, o.got_reason) for sid in ORDER if sid in sets for o in sets[sid].obs if not full_match(o)]
    print("\n## Mismatches (expected vs got, reason-strict)\n")
    print(md(["set", "item", "expected", "exp reason", "got", "got reason"], [[str(x) for x in m] for m in miss]))


if __name__ == "__main__":
    main()
