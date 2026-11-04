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

The remaining days were resequenced. Wednesday morning is two probes, then stop.

## 2026-10-29 — MVP claim run

Run a claim and an evidence packet through the engine; check the shared ship-export packet offline; check a live claim and read attached evidence; a product-decision packet the MVP can run; the same-day MVP contract and the $50 spend cap recorded.

## 2026-10-31 — Review layer foundations

The review package: PDF and scan ingest, the review JSON contract and a TC40 fixture, the first viewer, and a loader for gold files that stays out of product code. A suite manifest and fetch script, a probe memo, a Direct Muse baseline, boxed-bundle grounding (text in the box, blind re-read, SAM count), retries on 429 and 5xx with a total spend cap, and the judge journey screen with a passcode gate.

## 2026-11-01 — Review pipeline

Claim split with verified spans, a per-part relation call, quote snapping to line rectangles, the blind check of cards, parts run in parallel, scan transcription inside the run, the absence receipt that separates not found from cannot tell, and a scorer with per-pool rows. Boundary tests lock gold and the checker out of product code. A part is not marked supported on disagreed evidence alone.

## 2026-11-02 — Evidence map

An optional evidence map behind a flag: passages grouped by relation, a stance map, the argument ledger, an inferred timeline and plain-language copy. Offline replay tooling to show the second check changes nothing when it is off.

## 2026-11-03 — Evidence graph

Each document is read into rule and fact statements with exact quotes graded against the page; entities are merged by fixed rules; typed links, amendments, precedence and dates; claim linking, a typed walk, a full read, a comparator and a blind second read; the decision is made in code. All of it sits behind `PROOFGRAPH_GRAPH=1`, with the flag off unchanged. New dependencies: FastAPI, uvicorn, python-multipart, networkx and RapidFuzz. A gate table compares the flag off with the flag on.

## 2026-11-04 — Iteration 2, web app, deploy

The first gate run showed the graph worse than no graph (7 of 29 cases correct against 9). After error analysis, Iteration 2 was pre-registered as general rules only (comparator labels, a rule cannot establish a fact, defeat and override order, event dates for time claims, text-quality repair) and evaluated once on frozen code. Suite: 14 of 29 correct against 9 with no graph, with one wrongly supported answer. On 30 ContractNLI pairs never used before: 19 of 30 against 15, with one wrongly supported answer against two. The rules from before Iteration 2 scored 9 of 30 on the same pairs. Weaknesses are in `results/run2-analysis.md`.

The web app (server, live reading page, review page, shared review links), the container and Render blueprint, a synthetic sample packet that warms itself on first start, and removal of internal planning material from the public tree.

Later on 2026-11-04, after the first deploy:

- **Crash fix.** pdfium is not thread-safe, so two requests rendering PDF pages at the same time crashed the server process. Page rendering now goes through one process-wide lock; output is unchanged (replay check: 0 differences). Four concurrent runs crashed the built image under a 512 MB limit before the fix; six passed after it.
- **UI clarity.** A "New check" button and a toggle for how the documents were read; the review page serves its page images from cacheable URLs instead of embedding them (the saved download still embeds them); the empty page pane stays shut until a quote is selected; each quote says "Show on page N" and the ledger has a title and one instruction.
- **Copy.** The entrance headline, lede and three steps say in plain words what a visitor gets; copy that described the code was removed, and tests keep it out of the entrance.
- **Example button.** The first screen offers "Run an example" before the empty form, through the same function as the example card below it.
- **Navigation.** One sticky bar over the entrance with four labelled destinations, plain section titles in place of reference marks, and a section explaining all five answers. During a check, a run bar shows which of three steps it is on; the finished review has a contents bar and plain titles for its footer sections. `DESIGN.md` describes the three bars.
