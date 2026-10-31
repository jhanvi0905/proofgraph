# 02 · Scope

Build in this order. Don't start a tier until the one before it works and is tested.

## Tier 0: Day 1 vertical slice (must)
| Item | Done when |
|---|---|
| Repo scaffold, `schema.py` frozen | `make test` runs; schema validates a sample |
| FinDVer adapter (passage mode, numeric subset) | 250 cases load, with no leak fields (test proves it) |
| Muse client with disk cache and retries | Second identical call is served from cache; bad JSON gets one repair retry |
| Proposer (call 1): claim → facts + links | At least 4 of 5 sample claims return schema-valid programs |
| Engine: number parsing, quote grounding, safe calculator, rounding, scale rule | Unit tests pass (15+ calculator, 12+ grounding) |
| Engine: router, coverage, conflicts, combine, label | Hand-written programs give the expected verdict and label |
| Blind wording checker (Muse Spark Open, or a fresh Muse call until Baseten works) | Sees only one quote and one statement; boundary test passes |
| Contender A (Direct Muse) | Returns entailed/refuted plus a reason for 5 claims |
| `run_eval.py` + `report.py` | Scoreboard for 30 claims, generated from `runs/` |
| CLI: `python -m proofgraph verify --case <id>` | Prints verdict, label, reasons; writes a DOT graph |

## Tier 1: in this exact order
1. Full FinDVer run (numeric 250 + fact-lookup 250, passage mode), parts-off test, Contender B
2. Conflict traps (50, built automatically)
3. Objection loop (call 4, max 3 rounds), ContractNLI run (~300 pairs, whole NDA), FinDVer whole-filing mode (50 claims)
4. Visual citations: Muse boxes on PDF pages and photos, text-in-box check, blind re-read of crops, SAM 3.1 count, overlay
5. Freight bundles (16) and Test 4; the "what to fetch" line
6. App: case browser, proof graph drawn on the documents, objection timeline. A judge action runs a live check (decision D25)
7. Deploy on Streamlit Community Cloud for judges. The key stays in the host secret store. A spend cap bounds the remaining Meta credit. The app does not play a saved verdict

## Stretch: only if ahead after Tier 1 item 5
- **Muse Code "verify before acting" gate:** expose `verify()` as a tool, so a Muse Code agent asked to "approve invoice INV-2207" calls ProofGraph, gets CONTRADICTED, and refuses. About half a day.

## Out of scope: never build in this hackathon
- Agent frameworks (LangChain, LangGraph, CrewAI, AutoGen, DSPy pipelines) and multi-agent orchestration
- A tool-using "investigator" agent with search tools (removed by decision D9)
- Vector databases, embeddings or a retrieval pipeline
- Login, user accounts, a database server, payments
- A custom React or front-end framework (Streamlit + Graphviz + the HTML box overlay only)
- An LLM that approves the whole answer ("LLM judge")
- Muse Image or Muse Wonder for decoration
- Voice evidence (Muse Voice Transcribe), which was cut by decision D10
- Fine-tuning or RL post-training (roadmap only)
- Policy or technical-spec benchmarks (roadmap only)
- Docker, Kubernetes, cloud infrastructure beyond Streamlit Community Cloud

## Cut order if time runs short
1. Muse Code gate
2. FinDVer fact-lookup half (keep numeric)
3. Size of the freight set (minimum 6 bundles)
4. App polish

**Never cut:** the engine, both benchmarks against Direct Muse, the conflict traps, the parts-off test (including the self-check run), the proof graph, and the objection loop and visual citations on freight.

## 31 Oct amendment (accepted 31 Oct, D30 to D37)

Tier 0 stays done. Tier 1 and the never-cut list above are replaced for the window that submits on Wed 4 Nov 2026:

| Order | Item | Done when |
|---|---|---|
| 1 | Review layer (`proofgraph/review/`): ingest, claim split, per-part relation reading, snapping, status rule, blind card check, absence receipt (D32) | An uploaded packet and a pasted claim give per-part statuses and boxed cards |
| 2 | Three-pane viewer in one HTML/JS file inside Streamlit (D33) | Cards, parts and boxes link both ways; states render; export works offline |
| 3 | Scan path: Muse Spark transcription with approximate boxes | A scan page yields a card with a dashed box, or page plus quote if probe P1 fails |
| 4 | Evaluation on the 29-case set (D31): DEV runs, then HELD-OUT once | `results/report.md` generated from `runs/`, per pool, with n and intervals |
| 5 | Deploy (D25 with the labelled replay fallback) | The private URL runs the lead case live under the cap |
| Should | Numeric bridge, template note, injection banner, Direct Muse side table, scan re-read upgrade | In that order, only before Mon 2 Nov 20:00 IST |

**Never cut (amended):** the review layer, the blind check on every card, exact boxes on text-layer pages, the held-out run with honest wording, the frozen engine and its tests.

Stopped for this window: full FinDVer runs, ContractNLI 300, conflict traps, the parts-off and self-check runs, the proof graph on documents, the objection loop, the Muse Code gate, SAM counts in the demo, Next.js and FastAPI.

Out-of-scope line amended: "A custom React or front-end framework" stays out; one self-contained vanilla HTML/JS viewer file mounted with `st.components.v1.html` is allowed (D33, guardrail B9).

## Definition of done for submission
- [ ] Public GitHub repo, MIT licence, README with the scope sentence and generated results
- [ ] `make test` green in CI
- [ ] `results/report.md` generated from committed `runs/`
- [ ] App deployed for judges, and a live check runs under the spend cap
- [ ] 3-minute animation, made from a real run, showing only hackathon-built work
- [ ] `BUILT_DURING_HACKATHON.md` with the daily log
- [ ] Submitted on the CV platform before **Nov 4, 22:00 IST** (deadline Nov 5, 07:30 IST)
