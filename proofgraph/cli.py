"""pgrun: command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from proofgraph.arbiter import arbitrate
from proofgraph.assertions import assert_one
from proofgraph.atomize import atomize
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
    raw = (DATA / "raw" / label.file).read_bytes().decode("ascii")
    mappings = MappingFile.model_validate_json((DATA / "mappings.json").read_text(encoding="utf-8"))
    insts = {i.doc_id: i for i in result.instruments}
    return [assert_one(inp, mappings, insts[inp.instrument_doc_id], result.source, raw, trace) for inp in mappings.assertions]


def _print_assertion(a) -> None:
    if not isinstance(a, Assertion):
        print(f"INVALID {a.mapping_id}: {a.reason}\n")
        return
    cur = a.amount.currency.value if a.amount.currency else "not stated"
    basis = f"{a.basis.value}  ({a.basis_phrase.text!r} at {a.basis_phrase.start}-{a.basis_phrase.end})" if a.basis else "not stated"
    print(f"{a.assertion_id}")
    print(f"  slot        {a.slot}")
    print(f"  citation    {a.citation.text!r}  raw file {a.citation.start}-{a.citation.end}")
    print(f"  value       {a.value.text!r} at {a.value.start}-{a.value.end} -> {a.amount.minor_units} minor units")
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
    print(f"\nVERDICT  {v.verdict.value}   slot {v.slot}   unresolved pairs {v.unresolved_pairs}   governing {v.governing_assertion}")


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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
