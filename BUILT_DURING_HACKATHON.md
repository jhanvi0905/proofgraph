# Built during the hackathon

This file logs work built during the Meta Global AI Developer Hackathon. The operative build start is 21:30 IST on Monday 26 October 2026, confirmed by the human.

## 2026-10-27 — Day 1 fixture engine

Deterministic vertical slice only. No model calls and no scored run.

- Scaffold: `pyproject.toml`, `Makefile` (`make test`), `.env.example`, `.github/workflows/ci.yml`
- Frozen schema in `proofgraph/schema.py`, including `Fact.entity`, `Fact.period`, and `Verdict.flags`
- Engine: number parsing, quote grounding, conflict rule, safe calculator (`hours_between`, `days_between`, tolerance, scale), router, combine, DOT export
- Fixtures: detention program returns CONTRADICTED / COMPUTED; stated scale checks `(f3*1000) == 183479000`; a missing scale returns `SCALE_AMBIGUOUS`

Not in this slice: Meta API client, PDFs, SAM, Streamlit, objection rounds, FinDVer download, eval scores.

This entry is behind the tree. That "not in this slice" line is stale. See 2026-10-28. No live model call has been scored.

## 2026-10-28 — Plan resequenced

No product code changed for this note.

The 2026-10-27 entry is behind the tree. Also on disk, tested offline: `clients/muse.py` (cache, one JSON repair, `max_retries=0`, timeouts fail closed), `clients/checker.py` (`blind_wording` only; route does not call it), `propose.py`, `prompts/extract.md` (a PDF is the text line `File id:`, which does not attach the file), `adapters/findver.py` (passage mode, numeric only, dev cap 50; whole-filing raises), a CLI on a fixture file (no `verify --case`), and `app/streamlit_app.py` (two fixtures and pasted text). Still absent: `baseline.py`, `propose.revise`, `prompts/objection.md`, `clients/sam.py`, `pdf.py`, `scripts/run_eval.py`, `scripts/report.py`. `scripts/` is empty.

No live model call has been scored. The detention fixture prints CONTRADICTED / COMPUTED without Muse. Checkpoint A live is next. Checkpoint B was missed, so the IE half stays skipped.

The remaining days are resequenced in `docs/07-build-plan.md` (decision D21). Wednesday morning is two probes, then stop.
