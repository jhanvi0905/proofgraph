"""pgrun: command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from proofgraph.arbiter import arbitrate, arbitrate_wording
from proofgraph.assertions import assert_one
from proofgraph.model import embed
from proofgraph.passes import attack, describe, support
from proofgraph.retrieve import admit, retrieve
from proofgraph.atomize import atomize
from proofgraph.claims import load_claims, question_policies
from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.schema import DocumentMappingFile, RetrievalEval, Assertion, Claim, MappingFile, SourceManifest, TraceRecord, load_predicate_set
from proofgraph.pipeline import verified_amends
from proofgraph.trace import Trace

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _load_manifest() -> SourceManifest:
    return SourceManifest.model_validate_json((DATA / "instruments.json").read_text(encoding="utf-8"))


def _cmd_spans(args: argparse.Namespace) -> None:
    manifest = _load_manifest()
    label = next((s for s in manifest.sources if s.source_id == args.source), None)
    if label is None:
        raise SystemExit(f"unknown source {args.source}; known: {[s.source_id for s in manifest.sources]}")
    result = ingest(label, DATA / "raw")
    width = args.width
    print(f"{'span_id':16}  {'pg':>2}  {'start':>6}  {'end':>6}  {'section_path':40}  text")
    for inst in result.instruments:
        if args.doc and inst.doc_id != args.doc:
            continue
        for sp in inst.spans:
            path = " > ".join(sp.section_path[1:])[-40:]
            preview = " ".join(sp.text.split())[:width]
            print(f"{sp.span_id:16}  {sp.page:>2}  {sp.start:>6}  {sp.end:>6}  {path:40}  {preview}")
        if inst.definitions:
            print(f"  definitions in {inst.doc_id}: {', '.join(d.term for d in inst.definitions)}")
    n = sum(len(i.spans) for i in result.instruments)
    print(f"\n{result.source.source_id}: {len(result.instruments)} instruments, {n} spans, "
          f"{len(result.source.page_starts)} pages, extractor {result.source.extractor}")


def _claim(claim_id: str) -> Claim:
    """The author's claim, its slot resolved against data/slots.json before anything runs."""
    claims = {c.claim_id: c for c in load_claims(DATA / "claims.json", DATA / "slots.json")}
    if claim_id not in claims:
        raise SystemExit(f"unknown claim {claim_id!r}; known: {sorted(claims)}")
    return claims[claim_id]


def _cmd_atomize(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    res = atomize(_claim(args.claim_id), load_predicate_set(DATA / "predicates.json"), trace)
    print(res.to_json())
    r = trace.records[-1]
    print(f"\nmodel={r.model} prompt_hash={r.prompt_hash} tokens={r.input_tokens}+{r.output_tokens} "
          f"cache_hit={r.cache_hit} rejects={res.rejects} repairs={res.repairs} trace={args.trace}")


def _load_assertions(trace: Trace):
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    result = ingest(label, DATA / "raw")
    src = open_source(DATA / "raw" / label.file)
    mappings = MappingFile.model_validate_json((DATA / "mappings.json").read_text(encoding="utf-8"))
    insts = {i.doc_id: i for i in result.instruments}
    return [assert_one(inp, mappings, insts[inp.instrument_doc_id], src, trace) for inp in mappings.assertions]


def _print_assertion(a) -> None:
    if not isinstance(a, Assertion):
        print(f"INVALID {a.mapping_id}: {a.reason}\n")
        return
    cur = a.amount.currency.value if a.amount.currency else "not stated"
    basis = f"{a.basis.value}  ({a.basis_phrase.text!r})" if a.basis else "not stated"
    print(f"{a.assertion_id}")
    print(f"  slot        {a.slot}")
    loc = a.citation.locator
    where = f"raw file {loc.start}-{loc.end}" if loc.kind == "raw_offsets" else f"page {loc.page}, quote found once"
    print(f"  citation    {a.citation.text!r}  {where}")
    print(f"  value       {a.value.text!r} -> {a.amount.minor_units} minor units")
    print(f"  currency    {cur}")
    print(f"  basis       {basis}")
    print(f"  asserted by {a.instrument.doc_id} ({a.instrument.instrument_type.value}), binds {', '.join(a.instrument.policy_numbers)}, effective {a.instrument.effective_date}")
    for r in a.routes:
        print(f"  route       {r.strength.value.upper():8} {r.mapping_id} ({r.method.value})")
    print(f"  rests on    {a.weakest.value.upper()}\n")


def _cmd_assert(args: argparse.Namespace) -> None:
    for a in _load_assertions(Trace(Path(args.trace))):
        _print_assertion(a)


SLOT = "FD960228.corp_reimbursement.retention"


def _verdict_line(v) -> str:
    """The verdict, its reason, and which instrument governs and by which rule (D9: also the claim's value)."""
    why = v.supported_reason or v.unresolved_reason or v.not_found_reason
    out = f"{v.verdict.value}{' (' + why.value + ')' if why else ''}"
    if v.governing_rule is not None:
        out += f" [{v.governing_rule.value}: governing instrument {v.governing_doc_id}]"
    if v.claim_comparison is not None:
        out += f" claim {v.claim_value!r} vs governing {v.governing_value!r}"
    return out


def _print_d9(v) -> None:
    """The D9 parts of a verdict: the missing-document check, and the claim against the governing value."""
    for c in v.amends_checks:
        print(f"  amends {c.outcome.upper():8} {c.reason} [{c.strength.value}]")
    if not v.amends_checks:
        print("  amends   no asserting document records what it amends")
    cc = v.claim_comparison
    if cc is not None:
        state = "compared" if cc.compared else "NOT compared"
        print(f"  claim    {state}: claim {v.claim_value!r} vs {cc.b} {v.governing_value!r}: {cc.reason.value} ({cc.detail})")
    if v.unresolved_detail:
        print(f"  why      {v.unresolved_detail[:220]}")


def _gillette_question():
    """Family A's packet: every instrument in the exhibit, their document mappings (amends verified), the policy set."""
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    docs = tuple(i.doc_id for i in label.instruments)
    mappings = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    return docs, verified_amends(mappings, list(docs), DATA / "raw"), question_policies(SLOT, DATA / "slots.json")


def _cmd_verdict(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    results = _load_assertions(trace)
    for a in results:
        _print_assertion(a)
    valid = tuple(a for a in results if isinstance(a, Assertion))
    docs, checked, policies = _gillette_question()
    v = arbitrate(_claim("retention"), valid, docs, checked, policies)
    trace.write(TraceRecord(
        stage="arbiter", packet_id=None, atom_id=SLOT, span_ids=(), model=None, prompt_hash=None,
        input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False, verdict=v.verdict,
        rejects=tuple(f"{p.a}~{p.b}:{p.reason.value}" for p in v.pairs if not p.compared), repairs=0,
        detail=v.to_json(),
    ))
    print("pairs")
    for p in v.pairs:
        state = "compared    " if p.compared else "NOT compared"
        print(f"  {state} {p.a} vs {p.b}: {p.reason.value} ({p.detail}); values: {p.value.value}")
    print(f"in scope (issued under {SLOT.split('.')[0]}): {', '.join(v.in_scope) or 'none'}")
    print("rules")
    for r in v.rules:
        print(f"  {'FIRED' if r.fired else 'no   '} {r.name.value}: {r.reason}")
    print("weakest route per assertion")
    for aid, r in zip(v.assertions, v.weakest_routes):
        print(f"  {r.strength.value.upper():8} {aid}: {r.mapping_id}")
    print("D9 checks")
    _print_d9(v)
    print(f"\nVERDICT  {_verdict_line(v)}   slot {v.slot}   unresolved pairs {v.unresolved_pairs}   governing {v.governing_assertion}")


def _labelled_spans(instruments) -> dict[str, str]:
    """span_id -> assertion_id, for spans holding a hand-labelled citation (the answer key, not an input)."""
    mappings = MappingFile.model_validate_json((DATA / "mappings.json").read_text(encoding="utf-8"))
    insts = {i.doc_id: i for i in instruments}
    out = {}
    for inp in mappings.assertions:
        inst, loc = insts[inp.instrument_doc_id], inp.citation.locator
        shift = inst.file_start - inst.source_start
        for sp in inst.spans:
            if shift + sp.start <= loc.start and loc.end <= shift + sp.end:
                out[sp.span_id] = inp.assertion_id
    return out


def _cmd_retrieve(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    res = atomize(_claim(args.claim_id), load_predicate_set(DATA / "predicates.json"), trace)
    if not res.atoms:
        print(f"atomize failed: {[e.code.value for e in res.errors]}")
        return
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    instruments = ingest(label, DATA / "raw").instruments
    gold = _labelled_spans(instruments)
    spans = {sp.span_id: sp for i in instruments for sp in i.spans}
    for atom in res.atoms:
        r = retrieve(atom, instruments, trace, embed=None if args.sparse_only else embed)
        print(f"atom {atom.atom_id}: {atom.predicate} slot={atom.slot} quantity_raw={atom.quantity_raw!r}")
        print(f"query  {' '.join(r.query_terms)}")
        print(f"searched {r.candidates} spans ({r.deduped} duplicates dropped, {r.capped} capped), dense={r.dense}\n")
        print(f"{'rk':>2}  {'bm25':>4} {'dns':>4}  {'doc':24} {'pg':>2}  text")
        for h in r.hits:
            mark = f"  <- labelled: {gold[h.span_id]}" if h.span_id in gold else ""
            text = " ".join(spans[h.span_id].text.split())[:60]
            print(f"{h.rank:>2}  {h.bm25_rank or '-':>4} {h.dense_rank or '-':>4}  {h.doc_id:24} {h.page:>2}  {text}{mark}")
        found = {gold[h.span_id] for h in r.hits if h.span_id in gold}
        print(f"\nrecall@{len(r.hits)}: {len(found)} of {len(set(gold.values()))} labelled citations "
              f"(missed: {', '.join(sorted(set(gold.values()) - found)) or 'none'})")


def _cmd_recall(args: argparse.Namespace) -> None:
    ev = RetrievalEval.model_validate_json((DATA / "retrieval_eval.json").read_text(encoding="utf-8"))
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    instruments = ingest(label, DATA / "raw").instruments
    spans = {sp.span_id: sp for i in instruments for sp in i.spans}
    trace = Trace(Path(args.trace))
    norm = lambda t: " ".join(t.split())
    total = found_total = 0
    print(f"{'query':28} {'found':>5}  missed")
    for q in ev.queries:
        r = retrieve(q.atom, instruments, trace, embed=None if args.sparse_only else embed)
        top = [spans[h.span_id] for h in r.hits]
        missed = [g for g in q.gold if not any(sp.doc_id == g.doc_id and norm(g.quote) in norm(sp.text) for sp in top)]
        total += len(q.gold)
        found_total += len(q.gold) - len(missed)
        print(f"{q.query_id:28} {len(q.gold) - len(missed)}/{len(q.gold):<3}  {', '.join(g.doc_id for g in missed) or '-'}")
    print(f"\nrecall@10: {found_total}/{total} gold quotes over {len(ev.queries)} queries "
          f"({'bm25 only' if args.sparse_only else 'bm25 + dense'})")


def _chain(trace: Trace, quiet: bool = False):
    """Claim file -> atomize -> admit -> retrieve -> support and attack. Only the claim is written by hand."""
    claim = _claim("retention")
    res = atomize(claim, load_predicate_set(DATA / "predicates.json"), trace)
    if not res.atoms:
        raise SystemExit(f"atomize failed: {[e.code.value for e in res.errors]}")
    atom = res.atoms[0]
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    ingested = ingest(label, DATA / "raw")
    src = open_source(DATA / "raw" / label.file)
    mappings = DocumentMappingFile.model_validate_json((DATA / "document_mappings.json").read_text(encoding="utf-8"))
    policy = claim.slot.split(".", 1)[0]
    admitted, routes = admit(ingested.instruments, mappings, policy, src, trace, ingested.source.extractor)
    r = retrieve(atom, admitted, trace, embed=embed)
    results = (support(atom, r, admitted, routes, src, trace), attack(atom, r, admitted, routes, src, trace))
    if not quiet:
        print(f"claim (written by the author)\n  {claim.text}\n  slot: {claim.slot}\n")
        print(f"atom\n  " + describe(atom).replace("\n", "\n  "))
        print(f"\nadmitted (text inside a scope mapped to {policy}; decided in code, not by the model)")
        for doc, route in routes:
            scope = " ".join(route.citation.text.split())
            print(f"  {route.strength.value.upper():8} {doc:24} {scope[:70]!r}{'...' if len(scope) > 70 else ''}")
        print(f"\nretrieved {len(r.hits)} passages from admitted scopes\n")
    return claim, atom, admitted, results


def _cmd_passes(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    claim, atom, admitted, results = _chain(trace)
    labelled = [(inp.citation.locator.start, inp.citation.locator.end, inp.assertion_id)
                for inp in MappingFile.model_validate_json((DATA / "mappings.json").read_text(encoding="utf-8")).assertions]
    for res in results:
        rec = [t for t in trace.records if t.stage == res.side.value][-1]
        print(f"{res.side.value.upper()}  {len(res.evidence)} kept  failed={res.failed} repairs={res.repairs} rejects={res.rejects}  "
              f"tokens={rec.input_tokens}+{rec.output_tokens} cache_hit={rec.cache_hit}")
        for e in res.evidence:
            loc = e.citation.locator
            hit = next((aid for a, b, aid in labelled if a < loc.end and loc.start < b), None)
            mark = f"   <- labelled: {hit}" if hit else ""
            value = f"value {e.value.text!r}" if e.value else "no value"
            print(f"  {e.doc_id:24} [{e.identification.strength.value}] {e.quote.text!r}{mark}")
            print(f"  {'':24} {value}; {e.reading}")
        for err in res.errors:
            print(f"  ERROR {err}")
        print()


def _cmd_derive(args: argparse.Namespace) -> None:
    """The verdict from the pipeline's own evidence, beside the verdict from hand-labelled citations."""
    from proofgraph.assertions import assert_from_evidence

    trace = Trace(Path(args.trace))
    claim, atom, admitted, results = _chain(trace, quiet=True)
    insts = {i.doc_id: i for i in admitted}
    derived = [assert_from_evidence(e, insts[e.doc_id], claim.slot, trace) for res in results for e in res.evidence]
    valid = tuple(a for a in derived if isinstance(a, Assertion))
    print(f"claim (written by the author): {claim.text}\n")
    print("assertions derived from the passes' evidence")
    for a in derived:
        if not isinstance(a, Assertion):
            print(f"  INVALID {a.mapping_id}: {a.reason}")
            continue
        cur = a.amount.currency.value if a.amount.currency else "not stated"
        basis = a.basis.value if a.basis else "not stated"
        routes = ", ".join(f"{r.mapping_id.split(':')[0]}={r.strength.value}" for r in a.routes)
        print(f"  {a.instrument.doc_id:20} value {a.value.text!r:18} currency {cur:10} basis {basis:11} routes {routes}")
    docs, checked, policies = _gillette_question()
    v = arbitrate(claim, valid, docs, checked, policies)
    hand = arbitrate(claim, tuple(a for a in _load_assertions(Trace(None)) if isinstance(a, Assertion)), docs, checked, policies)
    trace.write(TraceRecord(
        stage="arbiter", packet_id="derived", atom_id=claim.slot, span_ids=(), model=None, prompt_hash=None,
        input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False, verdict=v.verdict,
        rejects=tuple(f"{p.a}~{p.b}:{p.reason.value}" for p in v.pairs if not p.compared), repairs=0, detail=v.to_json(),
    ))
    why = _verdict_line
    print("\nrules")
    for r in v.rules:
        print(f"  {'FIRED' if r.fired else 'no   '} {r.name.value}: {r.reason[:150]}")
    print("D9 checks")
    _print_d9(v)
    print(f"\nVERDICT from the pipeline     {why(v)}   {len(v.assertions)} assertions, {v.unresolved_pairs} unresolved pairs, governing {v.governing_assertion}")
    print(f"VERDICT from hand labels     {why(hand)}   {len(hand.assertions)} assertions, {hand.unresolved_pairs} unresolved pairs")
    print("MOVED" if why(v) != why(hand) else "verdict unchanged", "(same verdict, different evidence)" if why(v) == why(hand) and len(v.assertions) != len(hand.assertions) else "")


def _cmd_familyb(args: argparse.Namespace) -> None:
    """The family B transfer run: every labelled packet, scored against labels committed before the run.

    Orchestration only. The frozen passes take one source file, so admission, retrieval and the
    passes run once per source in the packet, and the arbiter sees the union of assertions.
    --dry-run stops before any model call and prints what each packet would admit.

    D9: the packets in labels.json are scored twice, against their preregistered label and against
    the D9 expectation in labels_d9.json; the new D9 packets (a wrong amount, the endorsement
    without its base form, a wording claim) are scored against labels_d9.json only.
    """
    import json as _json

    from proofgraph.assertions import assert_from_evidence, clause_from_evidence

    fb = DATA / "family_b"
    labels = _json.loads((fb / "labels.json").read_text(encoding="utf-8"))
    d9 = _json.loads((fb / "labels_d9.json").read_text(encoding="utf-8"))
    d9_expected = {p["packet_id"]: p["expected"] for p in d9["packets"]}
    packets = [dict(p, prereg=True) for p in labels["packets"]] + [dict(p, prereg=False) for p in d9["packets"] if "claim_id" in p]
    claims = {c.claim_id: c for c in load_claims(fb / "claims.json", fb / "slots.json")}
    mappings = DocumentMappingFile.model_validate_json((fb / "document_mappings.json").read_text(encoding="utf-8"))
    manifest = _load_manifest()
    by_doc = {i.doc_id: s for s in manifest.sources for i in s.instruments}
    trace = Trace(Path(args.trace))
    norm = lambda t: " ".join(t.split())
    rows = []
    ablations = []
    for pk in packets:
        claim = claims[pk["claim_id"]]
        policy = claim.slot.split(".", 1)[0]
        policies = question_policies(claim.slot, fb / "slots.json")
        checked = verified_amends(mappings, pk["instruments"], DATA / "raw")
        atom = None
        if not args.dry_run:
            res = atomize(claim, load_predicate_set(DATA / "predicates.json"), trace)
            if not res.atoms:
                rows.append((pk, None, [], f"atomize failed: {[e.code.value for e in res.errors]}"))
                continue
            atom = res.atoms[0]
        evidence, assertions, clauses, notes = [], [], [], []
        for doc in pk["instruments"]:
            label = by_doc[doc]
            ingested = ingest(label, DATA / "raw")
            src = open_source(DATA / "raw" / label.file)
            insts = tuple(i for i in ingested.instruments if i.doc_id == doc)
            admitted, routes = admit(insts, mappings, policy, src, trace, ingested.source.extractor)
            notes.append(f"{doc}: {sum(len(i.spans) for i in admitted)} passage(s) admitted")
            if args.dry_run or not admitted:
                continue
            r = retrieve(atom, admitted, trace, embed=embed)
            for res in (support(atom, r, admitted, routes, src, trace), attack(atom, r, admitted, routes, src, trace)):
                if res.failed:
                    notes.append(f"{doc} {res.side.value} FAILED: {res.errors}")
                for e in res.evidence:
                    evidence.append(e)
                    if claim.kind == "wording":
                        clauses.append(clause_from_evidence(e, admitted[0], trace))
                        continue
                    a = assert_from_evidence(e, admitted[0], claim.slot, trace)
                    if isinstance(a, Assertion):
                        assertions.append(a)
                    else:
                        notes.append(f"{doc}: invalid assertion: {a.reason}")
        if args.dry_run:
            rows.append((pk, None, [], "; ".join(notes)))
            continue
        docs = tuple(pk["instruments"])
        if claim.kind == "wording":
            v = arbitrate_wording(claim, tuple(clauses), docs, checked, policies)
        else:
            v = arbitrate(claim, tuple(assertions), docs, checked, policies)
        if args.ablate and claim.kind == "amount":
            # 1. naive build: values compared as strings, no precedence rules
            texts = {a.value.text for a in assertions}
            naive = "documents_disagree" if len(texts) > 1 else ("supported" if assertions else "not_found")
            # 2. the comparator, with precedence disabled: no instrument is in the rules' scope
            out_of_scope = tuple(a.model_copy(update={"instrument": a.instrument.model_copy(update={"policy_numbers": ()})})
                                 for a in assertions)
            nr = arbitrate(claim, out_of_scope, docs, checked, policies)
            nr_reason = nr.supported_reason or nr.unresolved_reason or nr.not_found_reason
            ablations.append((pk["packet_id"], naive, f"{nr.verdict.value} ({nr_reason.value if nr_reason else '-'})",
                              sorted(texts)))
        trace.write(TraceRecord(stage="arbiter", packet_id=pk["packet_id"], atom_id=claim.slot, span_ids=(), model=None,
                                prompt_hash=None, input_tokens=0, output_tokens=0, latency_ms=0, cache_hit=False,
                                verdict=v.verdict, rejects=(), repairs=0, detail=v.to_json()))
        cited = [g for g in pk["gold"] if any(e.doc_id == g["doc_id"] and norm(g["line"]) in norm(e.citation.text) for e in evidence)]
        rows.append((pk, v, cited, "; ".join(notes)))

    def fmt(ex):
        return f"{ex['verdict']} ({ex['reason'] or '-'}{', ' + ex['rule'] + ' -> ' + ex['governing_doc_id'] if ex['rule'] else ''})"

    def key(v):
        reason = v.supported_reason or v.unresolved_reason or v.not_found_reason
        return {"verdict": v.verdict.value, "reason": reason.value if reason else None,
                "rule": v.governing_rule.value if v.governing_rule else None,
                "governing_doc_id": v.governing_doc_id if v.governing_rule else None}

    print(f"{'packet':28} {'preregistered label':42} {'expected under D9':48} {'got':48} {'pre':4} {'D9':4} gold")
    hits_pre = hits_d9 = n_pre = 0
    for pk, v, cited, note in rows:
        exp_pre = fmt(pk["expected"]) if pk["prereg"] else "(new under D9)"
        exp_d9 = d9_expected.get(pk["packet_id"])
        if v is None:
            print(f"{pk['packet_id']:28} {exp_pre:42} {fmt(exp_d9) if exp_d9 else '-':48} {'(dry run)' if args.dry_run else 'FAILED':48} {note}")
            continue
        got = key(v)
        ok_pre = pk["prereg"] and got == pk["expected"]
        ok_d9 = exp_d9 is not None and got == exp_d9
        n_pre += pk["prereg"]
        hits_pre += ok_pre
        hits_d9 += ok_d9
        print(f"{pk['packet_id']:28} {exp_pre:42} {fmt(exp_d9) if exp_d9 else '-':48} {fmt(got):48} "
              f"{('yes' if ok_pre else 'NO') if pk['prereg'] else '-':4} {'yes' if ok_d9 else 'NO':4} {len(cited)}/{len(pk['gold'])}  {note}")
        extra = []
        if v.claim_comparison is not None:
            cc = v.claim_comparison
            extra.append(f"claim {v.claim_value!r} vs governing {v.governing_value!r}: {cc.reason.value}")
        extra += [f"amends {c.outcome}: {c.reason}" for c in v.amends_checks]
        if v.unresolved_detail:
            extra.append(f"why: {v.unresolved_detail}")
        if v.quoted is not None:
            extra.append(f"quoted (not checked) {v.quoted.doc_id} p.{v.quoted.page}: {v.quoted.text!r}")
        extra += [f"clash [judgment] {c.doc_id} p.{c.page}: {c.text!r} ({c.reading})" for c in v.clashes]
        for line in extra:
            print(f"{'':28} {line}")
    if not args.dry_run:
        print(f"\npreregistered label matched: {hits_pre}/{n_pre} packets (labels.json, scored as run at eeb9a2f; the rules moved at D9)")
        print(f"D9 expectation matched:      {hits_d9}/{len(rows)} packets (labels_d9.json, not preregistered)")
    if ablations:
        print(f"\n{'packet':28} {'naive (string compare, no rules)':34} {'comparator, rules disabled':38} values")
        for pid, naive, nr, texts in ablations:
            print(f"{pid:28} {naive:34} {nr:38} {texts}")


def _cmd_fetch(args: argparse.Namespace) -> bool:
    from proofgraph.fetch import fetch_sources

    ok = True
    for r in fetch_sources(_load_manifest(), DATA / "raw"):
        print(f"  {r.status:14} {r.source_id:18} {r.detail}")
        ok = ok and r.status in ("present", "downloaded")
    return ok


def _cmd_demo(args: argparse.Namespace) -> None:
    """One command from a clean clone: fetch and hash-check sources, then the published trace."""
    print("1. sources (fetched by pinned URL, refused unless the sha256 matches)")
    _cmd_fetch(args)
    manifest = _load_manifest()
    gillette = next(s for s in manifest.sources if s.source_id == "gillette_ex10e")
    if not (DATA / "raw" / gillette.file).exists():
        print("\nThe Gillette filing is required for the demo; see the line above.")
        return
    print("\n2. verdict on the retention slot (citations hand-labelled, see README)\n")
    _cmd_verdict(args)
    print("\n3. retrieval recall@10 on labelled queries\n")
    _cmd_recall(argparse.Namespace(sparse_only=False, trace=args.trace))
    print("\n4. support and attack passes (replayed from data/recorded/model; no API key needed)\n")
    _cmd_passes(args)
    print("\n5. the verdict from the pipeline's own evidence, beside the hand-labelled one\n")
    _cmd_derive(args)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pgrun")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("spans", help="print a source as a table of spans")
    sp.add_argument("source")
    sp.add_argument("--doc", default=None, help="limit to one instrument doc_id")
    sp.add_argument("--width", type=int, default=70)
    sp.set_defaults(func=_cmd_spans)
    at = sub.add_parser("atomize", help="split one claim into atoms (one model call, cached)")
    at.add_argument("claim_id", help="a claim id from data/claims.json")
    at.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    at.set_defaults(func=_cmd_atomize)
    asr = sub.add_parser("assert", help="print the assertions on the retention slot")
    asr.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    asr.set_defaults(func=_cmd_assert)
    vd = sub.add_parser("verdict", help="assertions, pairs, rules and verdict for the retention slot")
    vd.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    vd.set_defaults(func=_cmd_verdict)
    rt = sub.add_parser("retrieve", help="atomize a claim, retrieve the top ten spans, mark the labelled ones")
    rt.add_argument("claim_id", help="a claim id from data/claims.json")
    rt.add_argument("--sparse-only", action="store_true", help="BM25 only, no dense ranking")
    rt.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    rt.set_defaults(func=_cmd_retrieve)
    rc = sub.add_parser("recall", help="recall@10 on the labelled retrieval queries")
    rc.add_argument("--sparse-only", action="store_true")
    rc.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    rc.set_defaults(func=_cmd_recall)
    ps = sub.add_parser("passes", help="support and attack passes on the retention atom, side by side (two model calls)")
    ps.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    ps.set_defaults(func=_cmd_passes)
    dv = sub.add_parser("derive", help="the verdict from the pipeline's own evidence, beside the hand-labelled one")
    dv.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    dv.set_defaults(func=_cmd_derive)
    fbp = sub.add_parser("familyb", help="the family B transfer run, scored against the preregistered labels")
    fbp.add_argument("--dry-run", action="store_true", help="admission only, no model calls")
    fbp.add_argument("--ablate", action="store_true", help="also score the same assertions without precedence, and with naive string comparison")
    fbp.add_argument("--trace", default=str(ROOT / "runs" / "familyb_trace.jsonl"))
    fbp.set_defaults(func=_cmd_familyb)
    ft = sub.add_parser("fetch", help="download sources by pinned URL and check their sha256")
    ft.set_defaults(func=_cmd_fetch)
    dm = sub.add_parser("demo", help="one command: fetch sources, then verdict, recall and passes")
    dm.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    dm.set_defaults(func=_cmd_demo)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
