# 07 · Build plan

All times are IST. **Deadline: Thu Nov 5, 07:30 IST (Nov 4, 9:00 PM ET). Target submission: Wed Nov 4, 22:00 IST.**
The build window opens **Tue Oct 27, 09:30 IST** (00:00 ET). No repo commits before then.

## Tonight (Mon Oct 26), no code commits
- [ ] Kickoff stream at 21:30
- [ ] Claim the $150 Meta Model API credits (card required; set a spend limit)
- [ ] Apply for Baseten ($100, 2M TPM) and Modal ($100) credits
- [ ] Access tests from `04-meta-models.md`: JSON output, a box on a PDF page, a SAM carton count; note the model IDs
- [ ] Clone FinDVer; download ContractNLI manually into `data/contract-nli/`; open one record of each

## Day 1 (Tue Oct 27): the vertical slice
| Time | Task | Done when |
|---|---|---|
| 0–0:20 | **T1** scaffold: pyproject, Makefile, .env.example, .gitignore, LICENSE, README with the pre-registered criteria, BUILT_DURING_HACKATHON.md | `make test` runs |
| 0:20–0:40 | **T2** `schema.py`, then freeze | Sample JSON validates |
| 0:40–1:30 | **T3** FinDVer adapter (passage mode) + leak test | 250 numeric cases load; leak test passes |
| 0:40–1:30 *(agent, parallel)* | **T5** `numbers.py` + `calc.py` with tests | 15+ calculator tests, number-parsing tests pass |
| 1:30–2:30 | **T4** `clients/muse.py` + `cache.py` | Valid object returned; repeat call comes from cache; repair retry works |
| 1:30–2:30 *(agent, parallel)* | **T6** `ground.py` (quote match, conflicts) with tests | 12+ grounding tests pass |
| 2:30–3:30 | **T7** `propose.py` + `prompts/extract.md` | ≥ 4 of 5 dev claims return valid programs |
| **~3:30** | **Checkpoint A** | One real claim goes end to end: program → calculator result printed |
| 3:30–5:00 | **T8** `route.py` + `combine.py` + `graph.py` | Hand-written programs give the expected verdict and label |
| 5:00–5:30 | **T8b** `clients/checker.py` (fallback mode until Baseten works) + `test_boundaries.py` | Restricted signatures; boundary test passes |
| 5:30–6:00 | **T9** `baseline.py` (A) | 5 claims answered with reasons |
| 6:00–7:30 | **T10** `run_eval.py` + `report.py` | 30-claim scoreboard generated from `runs/` |
| **~7:30** | **Checkpoint B** | Credible proof on 30 claims |
| 7:30–8:30 | CLI + DOT export, README update, push, log in BUILT_DURING_HACKATHON.md | **Checkpoint C:** a fresh clone reproduces the report from cache |

## Days 2–9
| Day | Goal | Done when |
|---|---|---|
| **Wed 28** | Tune on dev; full FinDVer (numeric + IE, passage); parts-off (−quote, −coverage); Contender B; conflict traps | Report rows for A, B, PG and ablations; traps built. **21:30: Agents 102 (must attend)** |
| **Thu 29** | Objection loop (call 4); ContractNLI (~300, whole); FinDVer whole-filing (50); self-check ablation | Rounds logged per case; ContractNLI and whole-filing rows in the report |
| **Fri 30** | Visual citations: boxes via Files API, `pdf.py` text-in-box, blind re-read, `sam.py` count, overlay data; `hours_between` | One hand-made bundle verifies end to end with boxes. *21:30 Fireworks session (optional)* |
| **Sat 31** | Make 16 freight bundles; Test 4; the "what to fetch" line; pick demo cases | Freight rows in the report; `pick_demo_cases.py` lists real disagreements |
| **Sun Nov 1** | App: case browser, graph drawn on the documents, objection timeline, replay mode | The app runs with no API key |
| **Mon Nov 2** | Deploy (Streamlit Community Cloud), README, fix rough edges. **Feature freeze tonight.** | Public URL works in replay mode |
| **Tue Nov 3** | Video: script, record, edit (`10-demo-and-submission.md`). Office hours 20:30–21:30 | 3:00 video uploaded (unlisted) |
| **Wed Nov 4** | Buffer, re-record if needed, **submit by 22:00**, post on X | Submission confirmed |

Stretch, only if ahead after Sat: the Muse Code "verify before acting" gate (`02-scope.md`).

## Rescue decisions
| If… | Then… |
|---|---|
| The Meta API doesn't work from India | Run everything on Muse Spark Open via Baseten; ask in #office-hours |
| Day 1 slips past Checkpoint B | Skip the IE half on Day 2; protect the numeric run |
| The objection loop is flaky | Cap it at 1 round, log it, move on |
| SAM counts are poor | Re-stage the photos; keep the count check, report agreement honestly |
| The app eats more than one day | Ship the Streamlit table + Graphviz; the overlay becomes video-only |
| Behind on Nov 2 | Cut in the order given in `02-scope.md` |
