# Built during the hackathon

This file logs work built during the Meta Global AI Developer Hackathon. The operative build start is 21:30 IST on Monday 26 October 2026, confirmed by the human.

## 2026-10-27 — Day 1 fixture engine

Deterministic vertical slice only. No model calls and no scored run.

- Scaffold: `pyproject.toml`, `Makefile` (`make test`), `.env.example`, `.github/workflows/ci.yml`
- Frozen schema in `proofgraph/schema.py`, including `Fact.entity`, `Fact.period`, and `Verdict.flags`
- Engine: number parsing, quote grounding, conflict rule, safe calculator (`hours_between`, `days_between`, tolerance, scale), router, combine, DOT export
- Fixtures: detention program returns CONTRADICTED / COMPUTED; stated scale checks `(f3*1000) == 183479000`; a missing scale returns `SCALE_AMBIGUOUS`

Not in this slice: Meta API client, PDFs, SAM, Streamlit, objection rounds, FinDVer download, eval scores.
