"""pgrun: command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from proofgraph.arbiter import arbitrate
from proofgraph.assertions import assert_one
from proofgraph.model import embed
from proofgraph.retrieve import retrieve
from proofgraph.atomize import atomize
from proofgraph.checker import open_source
from proofgraph.ingest import ingest
from proofgraph.schema import Assertion, Claim, MappingFile, SourceManifest, TraceRecord, load_predicate_set
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


def _cmd_atomize(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    res = atomize(Claim(claim_id=args.claim_id, text=args.claim), load_predicate_set(DATA / "predicates.json"), trace)
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


def _cmd_verdict(args: argparse.Namespace) -> None:
    trace = Trace(Path(args.trace))
    results = _load_assertions(trace)
    for a in results:
        _print_assertion(a)
    valid = tuple(a for a in results if isinstance(a, Assertion))
    v = arbitrate(SLOT, valid)
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
    why = v.unresolved_reason or v.not_found_reason
    print(f"\nVERDICT  {v.verdict.value}{' (' + why.value + ')' if why else ''}   slot {v.slot}   unresolved pairs {v.unresolved_pairs}   governing {v.governing_assertion}")


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
    res = atomize(Claim(claim_id=args.claim_id, text=args.claim), load_predicate_set(DATA / "predicates.json"), trace)
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pgrun")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("spans", help="print a source as a table of spans")
    sp.add_argument("source")
    sp.add_argument("--doc", default=None, help="limit to one instrument doc_id")
    sp.add_argument("--width", type=int, default=70)
    sp.set_defaults(func=_cmd_spans)
    at = sub.add_parser("atomize", help="split one claim into atoms (one model call, cached)")
    at.add_argument("claim")
    at.add_argument("--claim-id", default="c1")
    at.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    at.set_defaults(func=_cmd_atomize)
    asr = sub.add_parser("assert", help="print the assertions on the retention slot")
    asr.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    asr.set_defaults(func=_cmd_assert)
    vd = sub.add_parser("verdict", help="assertions, pairs, rules and verdict for the retention slot")
    vd.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    vd.set_defaults(func=_cmd_verdict)
    rt = sub.add_parser("retrieve", help="atomize a claim, retrieve the top ten spans, mark the labelled ones")
    rt.add_argument("claim")
    rt.add_argument("--claim-id", default="c1")
    rt.add_argument("--sparse-only", action="store_true", help="BM25 only, no dense ranking")
    rt.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    rt.set_defaults(func=_cmd_retrieve)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
