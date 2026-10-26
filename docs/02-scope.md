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
6. App: case browser, proof graph drawn on the documents, objection timeline, replay mode
7. Public deploy (replay mode by default; live mode behind a passcode and spend cap)

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

## Definition of done for submission
- [ ] Public GitHub repo, MIT licence, README with the scope sentence and generated results
- [ ] `make test` green in CI
- [ ] `results/report.md` generated from committed `runs/`
- [ ] App deployed in replay mode
- [ ] 3-minute video showing only hackathon-built work
- [ ] `BUILT_DURING_HACKATHON.md` with the daily log
- [ ] Submitted on the CV platform before **Nov 4, 22:00 IST** (deadline Nov 5, 07:30 IST)
