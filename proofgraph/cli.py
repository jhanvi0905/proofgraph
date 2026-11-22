"""pgrun: command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from proofgraph.assertions import assert_cell
from proofgraph.atomize import atomize
from proofgraph.ingest import ingest
from proofgraph.schema import Assertion, Claim, MappingFile, SourceManifest, load_predicate_set
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


def _cmd_assert(args: argparse.Namespace) -> None:
    """Item VII's Primary-row retention, the only route mapped so far."""
    label = next(s for s in _load_manifest().sources if s.source_id == "gillette_ex10e")
    result = ingest(label, DATA / "raw")
    raw = (DATA / "raw" / label.file).read_bytes().decode("ascii")
    recs = {r.mapping_id: r for r in MappingFile.model_validate_json((DATA / "mappings.json").read_text(encoding="utf-8")).records}
    inst = next(i for i in result.instruments if i.doc_id == "coda_end13")
    trace = Trace(Path(args.trace))
    a = assert_cell(recs["item7_primary_retention_position3"], recs["item7_primary_policy_number"], inst, result.source, raw, trace)
    if not isinstance(a, Assertion):
        print(f"INVALID {a.mapping_id}: {a.reason}")
        return
    cur = a.amount.currency.value if a.amount.currency else "not stated"
    print(f"slot        {a.slot}")
    print(f"value       {a.value.text!r}  raw file {a.value.start}-{a.value.end}  -> {a.amount.minor_units} minor units")
    print(f"currency    {cur}")
    print(f"basis       {a.basis.value if a.basis else 'not stated'}")
    print(f"asserted by {a.instrument.doc_id} ({a.instrument.instrument_type.value}) binds {', '.join(a.instrument.policy_numbers)}, effective {a.instrument.effective_date}")
    print(f"routes      {', '.join(a.mapping_ids)}")
    print(f"chunk       {trace.records[-1].span_ids}")


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
    asr = sub.add_parser("assert", help="Item VII primary retention cell -> one typed assertion")
    asr.add_argument("--trace", default=str(ROOT / "runs" / "trace.jsonl"))
    asr.set_defaults(func=_cmd_assert)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
