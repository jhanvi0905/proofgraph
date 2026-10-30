# 07 · Build plan

All times are IST. **Deadline: Thu Nov 5, 07:30 IST (Nov 4, 9:00 PM ET). Target submission: Wed Nov 4, 22:00 IST.**
The recorded start is **Mon Oct 26, 21:30 IST** (decision D20).

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

28 Oct panel (D27) closed Wednesday on the two probes. That sitting held `SPEND_LIMIT_USD` at $10. The live cap is $50 per run (D29). The table below is the remaining window. Owners, the gate, and the stopped rows are in `docs/12-sprint-manager.md`. The deadline is unchanged: **Thu Nov 5, 07:30 IST**. Submit target: **Wed Nov 4, 22:00 IST**. `docs/02-scope.md` is unchanged. `docs/08-guardrails.md` names the $50 default.

| Day | Goal | Done when |
|---|---|---|
| **Wed 28** | Closed. Both probes returned. In flight, and not this day's exit: Senior Software Engineer on the live Streamlit check; Staff Applied AI Engineer on the Files API upload; Verification & Reasoning Engineer on the text-in-box draft. **21:30: Agents 102 (must attend, Product & Hackathon Strategy Lead).** The human builder lands the working tree on the public branch. This panel does not commit it. | Probes returned. Judges still see a fixture replay until that landing. |
| **Thu 29** | The live check on the detention/legal-hours claim. The upload path, with no `File id:` line. After the upload, the same owner does the blind re-read, then SAM with noun `cardboard box`. Bind text-in-box once `file_id` exists. The full numeric run stays stopped. | A live verdict is on screen. The upload is `input_file`. |
| **Fri 30** | Principal Engineer & Technical Lead runs one hand-made bundle, only after upload, text-in-box, blind re-read, and SAM exist. *21:30 Fireworks session (optional)* | The bundle verifies with boxes, including the clock re-read and a `cardboard box` count. |
| **Sat 31** | Product & Hackathon Strategy Lead picks one false claim from the five Direct Muse approved, or the detention probe. | That claim is chosen. ContractNLI, whole-filing, traps, self-check, 16 freight bundles, and the Muse Code gate stay stopped. |
| **Sun Nov 1** | D29. No FinDVer and no ContractNLI. If Friday's bundle is still open, that bundle is overdue. If it has closed, finish any open gate box that is already due. The stratified sampler does not start. | The day did not start a benchmark run. No app polish. |
| **Mon Nov 2** | Senior Software Engineer deploys that live check and holds the URL for the submission form. Judges do not receive it before Wed 4. The cap is $50 per run and counts SAM image calls. Product & Hackathon Strategy Lead writes the README from the D26 sentence and says 2 of 27 in the same breath. **Feature freeze tonight.** | The deployed URL runs a live check and is ready to paste into the form. README has that sentence and no "results have not been run" line. Gate boxes 4 and 5 can become yes tonight. Boxes 1–3 have to be yes already or this day does not open a benchmark. |
| **Tue Nov 3** | Video from a real run (`10-demo-and-submission.md`). The same sentence, and 2 of 27 in the same breath. The human makes the animation. The video does not wait on the 250. If the five gate boxes are yes, Staff Applied AI Engineer runs the full FinDVer numeric command with `n` omitted. The script aborts when the printed estimate is above $50. Do not shrink `n`. Office hours 20:30–21:30 | 3:00 video uploaded (unlisted). The FinDVer command either finished or aborted on its print. It did not start if any gate box was no. |
| **Wed Nov 4** | Buffer, re-record if needed, **submit by 22:00**, post on X. Principal Engineer & Technical Lead. The URL goes into the submission form here. Judges do not have it before this. ContractNLI may use the morning only under D29, and only before submit prep starts. | Submission confirmed, with the URL in the form. Hard deadline Thu Nov 5, 07:30 IST. |

Nice, only after the five musts, and only if Wednesday is not still submit prep. No day of their own. Staff Applied AI Engineer: one live objection round if a trigger code fires; six freight bundles only if the one bundle is already done. The mixed FinDVer slice left this list on 28 Oct. D29 supersedes that Sunday slice. The full numeric file is the named result, and it waits for the gate.

The Muse Code gate, FinDVer whole-filing, conflict traps, self-check spend, 16 freight bundles, and app polish do not return in this window. Contender B, the −quote ablation, and the −coverage rerun stay stopped. The full numeric testmini and ContractNLI return only under D29. The 30-claim scoreboard stays the scoreboard until that full-file report exists. Do not present 0 versus 5 as a win. `docs/02-scope.md` still does not cut either benchmark. D29 is when they may start.

## Implementation notes (feasibility probe, 28 Oct)

These fill gaps in Friday's visual-citation row. The same notes are on the Friday tasks in `docs/12-sprint-manager.md`. The probe ran outside the repo on one synthetic freight packet, load PG-SPIKE-01. It is not the hand-made bundle. Product code did not change.

- **Files API.** Upload with `purpose="user_data"`. Send `input_text` plus `input_file` with `detail` `high`. Cache the `file_id` under the file's SHA-256. The string-input propose path stays for text cases.
- **Text-in-box.** Map the 0–1000 box with pdfplumber's top-down `top`. Try a 2% margin, then 3%, then 4%, and keep the smallest whose words contain the fact value. On the probe PDF, 2% matched nothing, 3% matched only `Detention: $75.00/hour after 2 hours free time`, and 4% also matched the next linehaul line.
- **Blind re-read.** Send the crop to Baseten as an `image_url` data URL. Match clocks as times: the probe ink was `07:40` and the checker returned `7:40`. Muse `input_image` is the fallback when Baseten rejects the image.
- **SAM.** Send a still as an `input_image` data URL and stream `sam-3.1`. The count is the number of `<|box;` records. Discard mask payloads. A still does not need a `file_id`. On the schedule, Staff Applied AI Engineer still does it after the upload and the blind re-read. The noun `carton` returned an empty segmentation on a 12-carton drawing. The noun `cardboard box` returned 12, with the first box on a drawn carton. The hand-made bundle uses `cardboard box`, and `carton` is retried only on a phone photo of real cartons. SAM responses reported `images_processed: 1` and zero tokens, so the spend cap counts those image calls.

The rescue row "SAM counts are poor" still means re-stage the photos and report agreement honestly. A zero from the noun `carton` on a drawing is an empty segmentation to re-prompt before the photos are re-staged.

## Rescue decisions
| If… | Then… |
|---|---|
| The Meta API doesn't work from India | Run everything on Muse Spark Open via Baseten; ask in #office-hours |
| Day 1 slips past Checkpoint B | Skip the IE half on Day 2; protect the numeric run |
| The fresh full-numeric print is above $50 | The script aborts. Do not shrink `n`. Do not raise the cap again in that sitting. The 30-claim scoreboard stays. Contender B, the −quote ablation, and the −coverage rerun stay stopped. |
| The objection loop is flaky | Cap it at 1 round, log it, move on |
| SAM counts are poor | Re-stage the photos; keep the count check, report agreement honestly. The bundle noun is `cardboard box`. |
| The app eats more than one day | The live check is the app. App polish stays stopped. |
| Friday's bundle is still open Saturday | The bundle is overdue and comes first. Six freight bundles do not start. Monday's deploy of the text check still ships. |
| Behind on Nov 2 | The stopped rows stay stopped. Do not drop the live check, the one bundle, the D26 sentence, or the deploy. |
