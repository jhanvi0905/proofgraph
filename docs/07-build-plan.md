# 07 · Build plan

All times are IST. **Deadline: Thu Nov 5, 07:30 IST (Nov 4, 9:00 PM ET). Target submission: Wed Nov 4, 22:00 IST.**
The recorded start is **Mon Oct 26, 21:30 IST** (decision D20).

Daily board: `docs/12-sprint-manager.md`. This file is the calendar. The sprint manager names overdue and due tasks and keeps later tasks scheduled until their dependency is done. A running product is due by the end of Tue 3 Nov. Wed 4 is submit buffer.

## Tonight (Mon Oct 26), no code commits
- [ ] Kickoff stream at 21:30
- [ ] Claim the $150 Meta Model API credits (card required; set a spend limit)
- [ ] Apply for Baseten ($100, 2M TPM) and Modal ($100) credits
- [ ] Access tests from `04-meta-models.md`: JSON output, a box on a PDF page, a SAM carton count; note the model IDs
- [ ] Clone FinDVer; download ContractNLI manually into `data/contract-nli/`; open one record of each

## Day 1 (Tue Oct 27): the vertical slice
Original timetable, kept as history. The last column is the reading on Wed 28 morning.

| Time | Task | Done when | Status |
|---|---|---|---|
| 0–0:20 | **T1** scaffold: pyproject, Makefile, .env.example, .gitignore, LICENSE, README with the pre-registered criteria, BUILT_DURING_HACKATHON.md | `make test` runs | Done |
| 0:20–0:40 | **T2** `schema.py`, then freeze | Sample JSON validates | Done |
| 0:40–1:30 | **T3** FinDVer adapter (passage mode) + leak test | 250 numeric cases load; leak test passes | Partial |
| 0:40–1:30 *(agent, parallel)* | **T5** `numbers.py` + `calc.py` with tests | 15+ calculator tests, number-parsing tests pass | Done |
| 1:30–2:30 | **T4** `clients/muse.py` + `cache.py` | Valid object returned; repeat call comes from cache; repair retry works | Partial |
| 1:30–2:30 *(agent, parallel)* | **T6** `ground.py` (quote match, conflicts) with tests | 12+ grounding tests pass | Done |
| 2:30–3:30 | **T7** `propose.py` + `prompts/extract.md` | ≥ 4 of 5 dev claims return valid programs | Partial |
| **~3:30** | **Checkpoint A** | One real claim goes end to end: program → calculator result printed | Live slipped |
| 3:30–5:00 | **T8** `route.py` + `combine.py` + `graph.py` | Hand-written programs give the expected verdict and label | Done |
| 5:00–5:30 | **T8b** `clients/checker.py` (fallback mode until Baseten works) + `test_boundaries.py` | Restricted signatures; boundary test passes | Partial |
| 5:30–6:00 | **T9** `baseline.py` (A) | 5 claims answered with reasons | Slipped |
| 6:00–7:30 | **T10** `run_eval.py` + `report.py` | 30-claim scoreboard generated from `runs/` | Slipped |
| **~7:30** | **Checkpoint B** | Credible proof on 30 claims | Missed |
| 7:30–8:30 | CLI + DOT export, README update, push, log in BUILT_DURING_HACKATHON.md | **Checkpoint C:** a fresh clone reproduces the report from cache | Partial |

## Where the code is (Wed 28 morning)
Present and tested offline: schema, cache, config; engine numbers, calc (`hours_between` already exists), ground, route, combine, graph, spans; `clients/muse.py` (cache, one JSON repair, `max_retries=0`, timeouts fail closed); `clients/checker.py` `blind_wording` only (route does not call it; a wording link returns `CHECKER_UNAVAILABLE`); `propose.py` and `prompts/extract.md` (a PDF is the text line `File id:`, which does not attach the file); `adapters/findver.py` passage mode, numeric only, dev cap 50, whole-filing raises; CLI on a fixture file, no `verify --case`; `app/streamlit_app.py` two fixtures and pasted text.

Absent: `baseline.py`, `propose.revise`, `prompts/objection.md`, `clients/sam.py`, `pdf.py`, `scripts/run_eval.py`, `scripts/report.py`. `scripts/` is empty.

The next checkpoint is **Checkpoint A live**: one Muse program through `run_program`, printed verdict. The detention fixture already prints CONTRADICTED / COMPUTED without Muse. Checkpoint B (30-claim scoreboard vs Direct Muse) comes after that. Day 1 missed Checkpoint B, so the rescue rule applies: skip the FinDVer fact-lookup / IE half and protect the numeric run.

`BUILT_DURING_HACKATHON.md` for 2026-10-27 is behind this tree. No live model call has been scored.

## Remaining days
Resequenced Wed 28 (decision D21). Wednesday morning is the early slice only. The submission list does not shrink: Contender A and B, the 30-claim scoreboard, the full numeric passage run, the −quote ablation and the −coverage cache rerun, the objection loop, ContractNLI, whole-filing, conflict traps, self-check, boxes, SAM, 16 freight bundles, what-to-fetch, the app, deploy, the video, and the Wed 4 22:00 submit all stay. IE stays skipped. The Muse Code gate stays a Saturday stretch after freight rows exist.

| Day | Goal | Done when |
|---|---|---|
| **Wed 28** | Early slice, morning only. One text claim: live propose → `run_program` → verdict, label, reasons. Then one Baseten `blind_wording` call on one quote and one statement. Stop. | Both probes returned. If either returns 429, the retry cap is in before any further call. **21:30: Agents 102 (must attend).** |
| **Thu 29** | HTTP retries first. Then Contender A, `run_eval`, `report`, and the 30-claim numeric scoreboard (Checkpoint B). Then one counterevidence/illegible line in `prompts/extract.md`, dev slice only. Then the full numeric passage run. Skip IE. Contender B, the −quote ablation, and the −coverage cache rerun only after the report script exists. Fixture-test the objection loop at the end of the day only if that scoreboard is already in `runs/`. | Checkpoint B is in `runs/`. The prompt line is frozen for the numeric run. IE is not run. |
| **Fri 30** | Objection loop on cached cases if Thursday did not finish it. Then Files API and the SAM token parser, text-in-box, and blind re-read. | One hand-made bundle verifies with boxes. `hours_between` is already in `calc.py`. *21:30 Fireworks session (optional).* |
| **Sat 31** | ContractNLI (~300), FinDVer whole-filing (50), conflict traps, self-check. Then 16 freight bundles, what-to-fetch, `pick_demo_cases.py`. | Those rows are in the report. Freight rows exist before any Muse Code gate. |
| **Sun Nov 1** | App. Objection timeline reads plan / act / observe, red refusal, what-to-fetch handoff. No new backend. | The app replays with no API key. The current fixture screen is not this app. |
| **Mon Nov 2** | Deploy (Streamlit Community Cloud). **Feature freeze tonight.** | Public URL works in replay mode |
| **Tue Nov 3** | Video from real runs only (`10-demo-and-submission.md`). Office hours 20:30–21:30 | 3:00 video uploaded (unlisted) |
| **Wed Nov 4** | Buffer. Re-record if needed. **Submit by 22:00.** Post on X. | Submission confirmed |

Wednesday do-not-start list: do not edit `prompts/extract.md`. Do not start Files API, SAM, retries, demo framing, or the Muse Code gate. If a Wednesday probe returns 429, then and only then add the retry cap before any further calls. The counterevidence line is required on Thursday, and Files API and SAM are required on Friday. That list only holds them until the live program returns.

28 Oct update: both probes returned and neither was 429, so retries stay on Thursday. `clients/checker.py` is still the Muse client; pointing it at Baseten is unblocked. Route calling the checker stays blocked on that client. D24: an UNRESOLVED fall-through keeps a null label, and `combine.py` does not change.

Thursday retries, when they start: at most 4 backoff retries on 429/5xx, ~180s timeout, one JSON repair, then `EXTRACTION_FAILED`. Timeouts stay unrepaired. The dev-slice prompt line changes no schema and spends nothing on the full set.

Friday attachments: upload once, cache `file_id` by SHA-256, send `input_text` + `input_file`; `input_image` for a crop. SAM count is the number of `<|box|>` tokens. The noun prompt is a noun such as carton, never signature.

The Muse Code verify-before-acting gate (`02-scope.md`, D15) is a Saturday stretch, and only after freight rows exist.

## How to proceed
1. Do the Wednesday slice. Stop after the two probes.
2. Do not start a task whose dependency is unmet.
3. Independent tasks may run only when they do not block the critical path: live probe → retries → scoreboard → numeric run → objection loop → boxes and SAM → freight → app → video.
4. If Thursday slips, skip IE, cap the objection loop at one round, and still protect the numeric scoreboard and Friday's one boxed bundle.
5. Log the day in `BUILT_DURING_HACKATHON.md`. Do not write result numbers that are not in `results/report.md`.

## Dependencies
Critical path: live probe → retries → scoreboard → numeric run → objection loop → boxes and SAM → freight → app → video.

1. **Live text propose → `run_program` (Wed morning).** Depends on nothing new. Gates every later loop that spends.
2. **One `blind_wording` probe.** Depends on the live propose having returned, so the key is known. It can run after that, the same morning. It does not depend on the scoreboard.
3. **HTTP retries.** Depends on the Wednesday probe existing as a client. Do not start before that single probe unless the probe returns 429. Gates every later multi-call run.
4. **Contender A, `run_eval`, `report`, 30-claim numeric scoreboard.** Depends on the live propose path and on retries. Gates the full numeric run, Contender B, ablations, and any prompt edit.
5. **Counterevidence / illegible line in `prompts/extract.md`.** Depends on the two probes having settled, and on a report script so the dev slice can be scored. It must not land before the first live program.
6. **Full numeric passage run.** Depends on Checkpoint B and on that prompt line being frozen for the run.
7. **Objection loop (`revise`).** Depends on a scored numeric row in `runs/` before the loop is trusted. The fixture test can be written once combine reason codes exist (they do). If Thursday is slipping, do not start the loop before the scoreboard. It must not block the numeric scoreboard or Friday's boxed bundle.
8. **Files API attachments.** Depends on the string-input propose path already working on text. Independent of SAM. Gates text-in-box and the hand-made bundle. Must not block the scoreboard.
9. **SAM parser.** Independent of Files API once a photo fixture exists. The bundle demo depends on both. It does not depend on ContractNLI. Must not block the upload path.
10. **text-in-box and blind re-read.** text-in-box depends on Files API plus pdf words. Blind re-read depends on `input_image` crops. Neither depends on SAM. Must not block each other. The bundle waits for both, and for SAM.
11. **ContractNLI, whole-filing, traps, self-check.** Depend on the objection loop and on the numeric scoreboard pattern (same eval and report). Independent of SAM and of freight photos. Must not block Friday's one boxed bundle.
12. **Freight bundles and what-to-fetch.** Depend on boxes (Files API, text-in-box, blind re-read, SAM count) and on the engine. The Muse Code gate depends on freight rows. Must not start while the scoreboard is still missing.
13. **App timeline (plan / act / observe).** Depends on a verdict object. The handoff is meaningful once fetch lines exist. It can be built against fixtures before deploy. Independent of the video edit. Must not block the boxed bundle.
14. **Deploy, video, submit.** Deploy depends on the app running with no key. Video depends on real runs (the scoreboard plus at least one boxed freight case). Submit depends on a public repo, the video, and `BUILT_DURING_HACKATHON.md`. Deploy must not wait on the video edit.

### Side by side
- After Checkpoint B, the prompt-line dev slice can be prepared while report formatting is cleaned. The prompt must not change during the scored numeric run.
- Friday, the SAM parser and text-in-box can be written in parallel after the upload path exists. The bundle waits for both.
- Saturday, ContractNLI eval and freight document staging can overlap only after the objection loop is capped and tested. Do not overlap them if the scoreboard is still missing.
- Sunday app and Monday deploy are sequential. The video script can be outlined Sunday from `docs/10-demo-and-submission.md`. Recording waits for real runs.

## Rescue decisions
| If… | Then… |
|---|---|
| The Meta API doesn't work from India | Run everything on Muse Spark Open via Baseten; ask in #office-hours |
| Day 1 slips past Checkpoint B | **Fired.** Skip the FinDVer fact-lookup / IE half. Protect the numeric run |
| The objection loop is flaky, or Thursday is slipping | Cap it at 1 round, log it, and do not start it before the scoreboard. Still protect the numeric scoreboard and Friday's one boxed bundle |
| About to add `hours_between` | Stop. It already exists in `calc.py` |
| SAM counts are poor | Re-stage the photos; keep the count check, report agreement honestly |
| The app eats more than one day | Ship the Streamlit table + Graphviz; the overlay becomes video-only |
| Behind on Nov 2 | Cut in the order given in `02-scope.md` |
