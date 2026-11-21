"""pgrun: command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from proofgraph.ingest import ingest
from proofgraph.schema import SourceManifest

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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="pgrun")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("spans", help="print a source as a table of spans")
    sp.add_argument("source")
    sp.add_argument("--doc", default=None, help="limit to one instrument doc_id")
    sp.add_argument("--width", type=int, default=70)
    sp.set_defaults(func=_cmd_spans)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
