# 12 · Sprint manager

The sprint manager is a standing role for the builder and for any agent. It does not implement features. It reads this file and `docs/07-build-plan.md`. It names the work due that day, and any task that slipped. It keeps the rest of the plan on the board until the dependency is actually done.

Waiting means later today, or a later day. Waiting is not a cut.

**Hard deadline: Thu 5 Nov 2026, 07:30 IST (Nov 4, 9:00 PM ET). Team submit target: Wed 4 Nov 2026, 22:00 IST.**

A running product exists by the end of **Tue 3 Nov 2026**. Wed 4 is buffer and submit. Tuesday is the animation, which the human makes from a real run. The product is already running before Tuesday starts.

D25 (28 Oct): the judge-facing Streamlit app runs a live check. It does not play a saved verdict. The app URL is for judges. The key stays in the host secret store, and a spend cap bounds the remaining Meta credit. Scored `runs/` stay the report record. Streamlit stays. Vercel stays out.

## Job

1. Each morning, name the tasks that are due that day, and any overdue task. Overdue work comes first and blocks new scope. Due tasks get built that day.
2. Sequence by dependency. A later task waits until its dependency is done.
3. Keep the scheduled build. Do not drop Files API, SAM, the `prompts/extract.md` counterevidence line, the objection loop, ContractNLI, freight, the app timeline, deploy, or the video. The Muse Code gate is the only stretch, and only after freight rows exist.

Day 1 engine work is already in the tree. Do not rebuild `hours_between`. The FinDVer fact-lookup / IE half stays skipped. That rescue rule is already decided.

## Morning invocation

Each morning the builder says: "Run the sprint manager."

The manager then reports, in this order:

1. Overdue tasks, if any. Those come first.
2. Tasks due today. That includes the prompt line on Thursday, Files API and SAM on Friday, and every other row dated that day.
3. Tasks that may run beside today's work, because their dependency is already met.
4. Tasks that wait, with the dependency named. Waiting means later today or a later day. It does not mean cancelled.

## Task board

"Beside" means the dependency is already met, so the task can run at the same time as the named work. A task with an open dependency stays on the board and waits.

The human asked for owners on 28 Oct 2026. Until that ask, Q1 kept owners off this board. Each open task names one of the six panel roles. A waiting task keeps its owner. The owner starts when the dependency is met. Dates, D21, and the stop after the two Wednesday probes are unchanged.

Later on 28 Oct both probes returned. The Wed 28 exit sentence is met. Neither probe returned 429. D24 keeps the label null on an UNRESOLVED fall-through, so a blank label is not a remaining gap. The legal-hours product-path re-probe also returned no 429. `CHECKER_UNAVAILABLE` is gone. `EVAL_ERROR` is absent on that verdict. Start now means there is no unmet dependency. Waiting means an unmet dependency or a later day. Retries, the scoreboard, and Friday through submit stay where they are.

| Task | Owner | Due | Depends on | Beside | Done | Status |
|---|---|---|---|---|---|---|
| Live text propose → `run_program` → printed verdict | Staff Applied AI Engineer | Wed 28 | Nothing new | No. It is the first call. | One real Muse ClaimProgram, plus a verdict, label, and reasons. | Returned. Exit met. Label is null. Reason codes include `CHECKER_UNAVAILABLE` and `EVAL_ERROR`. |
| One `blind_wording` probe on one quote and one statement | Staff Applied AI Engineer | Wed 28 | The live propose returned the same morning, so the key works. Not the scoreboard. | Same morning, after that return. | One label, or an honest checker error. Then stop. Agents 102 at 21:30. | Returned `entails` from a one-off script. Product `clients/checker.py` was not called. Exit met. |
| Point `clients/checker.py` `blind_wording` at Baseten Chat Completions | Staff Applied AI Engineer | Wed 28 | Nothing unmet. The Baseten key is in `.env`. One Chat Completions call already returned `entails`. `docs/04` Call 3 names this file, this URL, and `meta-models/muse-spark-open-1026`. | Beside the `hours_between` prompt and the assumed-rule route. This row is the prerequisite for route. | `blind_wording` posts `chat.completions.create` to `https://inference.baseten.co/v1` for that model. It does not call `MuseClient.structured`. | Done. The re-probe sent three `chat.completions.create` calls to that URL for that model. `MuseClient.structured` is not called. |
| Tell Call 1 to emit `hours_between` for clock facts | Staff Applied AI Engineer | Wed 28 | Nothing unmet. `hours_between` is already in `calc.py`. The live program has returned, so the hold on editing `prompts/extract.md` before that program is lifted. This is not the counterevidence line. | Beside the Baseten client and the assumed-rule route. | Temporal expressions use `hours_between` on clock facts, and claim numbers stay numeric literals as Call 1 already shows. The calculator is not taught to subtract clock strings. | Done in `prompts/extract.md`. Call 1 must emit a comparison, with no `//` comments, and currency as a numeric literal such as 450. Claim numbers stay numeric literals (`183479000`). The legal-hours re-probe emitted `(hours_between(f_arr, f_dep) - f_free) * f_rate == 450`. `calc.py` was not changed. `EVAL_ERROR` is absent on that verdict. |
| Route an assumed rule with no expr to rule logic | Verification & Reasoning Engineer | Wed 28 | Nothing unmet. `docs/03-architecture.md` already routes a rule to logic. The product brief already defines ASSUMED as a shown rule. Combine already accepts that strength. | Beside the Baseten client and the `hours_between` prompt. | A rule with `expr` null and `rule_source` assumed is not `EVAL_ERROR`. Strength is ASSUMED. No new label. | Done. Re-probe link `l6` has `expr` null and `rule_source` assumed. Status pass. Strength ASSUMED. No new label. |
| Decide the label on an UNRESOLVED fall-through | Product & Hackathon Strategy Lead | Wed 28 | Nothing unmet. Schema, combine, and `test_unverifiable_part_blocks_support` allow null. | No. It blocked only a label engine change, and that change is not assigned. | A recorded choice in `QUESTIONS.md` Q3. No label value is invented here. | Decided. D24. The label stays null. `combine.py` does not change. |
| Route wording links through `blind_wording` | Verification & Reasoning Engineer | Wed 28, after the Baseten client | `clients/checker.py` posting to Baseten Chat Completions. Not before that. | No. | A wording link is sent to the blind checker. `CHECKER_UNAVAILABLE` is not the result for every wording link. The engine still does not import the proposer or `clients.muse`. | Done. Re-probe wording results were pass, `not_mentioned`, and pass. `CHECKER_UNAVAILABLE` was not the result. The engine does not import the proposer or `clients.muse`. |
| Live detention re-probe: verdict, label, and reasons | Staff Applied AI Engineer | Wed 28, after the checker path and the `EVAL_ERROR` cause | The Baseten client, route calling that client, Call 1 emitting `hours_between`, and assumed-rule logic. Q3 is decided: a fall-through label stays null. | No. | One product-path print of the verdict and the reasons. The label stays null when the fall-through is UNRESOLVED. Not another one-off script. | Done on the product path: `propose` then `run_program`. Legal-hours run: verdict `CONTRADICTED`. Label `COMPUTED`. Reason: expression does not hold. Reason codes empty. `EVAL_ERROR` is absent. Four HTTP calls. Published Spark-rate spend $0.03417475. No 429. Artifact `cache/probes/2026-10-28/reprobe-legal-hours.json`. The earlier run remains at `cache/probes/2026-10-28/reprobe-result.json`. |
| Accept the Wednesday task bar | QA & Reliability Engineer | Wed 28, after those fixes exist | The Baseten client, route calling the checker, the `hours_between` prompt, assumed-rule logic, and the live re-probe. Q3 is decided. | No. | The product-path result is accepted once it exists. A null label on UNRESOLVED is the accepted label. The exit sentence is already met. | Accepted. Product path returned `CONTRADICTED`, label `COMPUTED`, reason `expression does not hold`, reason codes empty. `EVAL_ERROR` is absent. `CHECKER_UNAVAILABLE` is absent. A null label remains the accepted label for an UNRESOLVED fall-through (D24). This verdict is a settled chain, so the label is `COMPUTED`. Artifact `cache/probes/2026-10-28/reprobe-legal-hours.json`. |
| HTTP retries | Staff Applied AI Engineer | Thu 29. Sooner if the Wednesday probe returned 429: start immediately, before any further call. | The Wednesday probes have returned. Neither returned 429, and the legal-hours re-probe also returned no 429, so this does not start now. It stays Thursday. | No. | At most 4 backoff retries on 429/5xx, ~180s timeout, one JSON repair, then `EXTRACTION_FAILED`. Timeouts stay unrepaired. Tests still fail closed on bad JSON. | Done. `MuseClient` and the Baseten checker each retry HTTP 429 and 5xx at most 4 times, backoff 1s, 2s, 4s, 8s. Each attempt times out at 180s. The SDK retry count stays 0. One JSON repair, then `EXTRACTION_FAILED`. Timeouts, including HTTP 504, are not retried and not repaired. `tests/test_muse.py` and `tests/test_boundaries.py`. No live call for this row. |
| Contender A, `run_eval`, `report`, 30-claim numeric scoreboard | Staff Applied AI Engineer | Thu 29 | The live propose has returned. Retries have not. No 429, so retries were not pulled forward. This stays behind retries. | No. It follows retries. | A row in `runs/<dataset>-<mode>-<system>-<date>.jsonl` and `results/report.md` versus Direct Muse. `scripts/run_eval.py` and `scripts/report.py` are still absent. This row is that writer. It is not a second task. | Done. Writer is `scripts/run_eval.py` and `scripts/report.py`. It estimates with `POST /v1/responses/input_tokens` and aborts above `SPEND_LIMIT_USD`. Rows: `runs/findver-passage-pg-testmini-2026-10-28.jsonl` and `runs/findver-passage-a-testmini-2026-10-28.jsonl`. `results/report.md` compares them. The filename includes the split so a dev try cannot overwrite the scored file. Estimate for this run was $7.248668897795591182364729460. |
| One counterevidence and illegible line in `prompts/extract.md` | Staff Applied AI Engineer | Thu 29. Required that day. | Both Wednesday probes have returned. The report script does not exist. It must not land during the 30-claim scored run. | Yes, on the dev slice, once the report script exists. It must not change the prompt during the 30-claim scored run. | The line is in the prompt. The dev slice was the only place it was tried. No schema change. No full-set spend. | Done. The line is in `prompts/extract.md`. Tried only on the dev split, 50 claims, `runs/findver-passage-pg-dev-2026-10-28.jsonl`. No schema change. The file was not edited during the testmini run. Prompt sha256 `cc91960dedbe2bfff5b4e102c7d362658a51f567012dc08b2c95a1224bd85d44`. |
| Full numeric passage run | Staff Applied AI Engineer | Thu 29 | The scoreboard, and that prompt line frozen. | No. | The numeric passage set is scored on the frozen prompt. The FinDVer IE / fact-lookup half is not run. | Waiting. The prompt line is frozen, and the 30-claim scoreboard exists. The pre-run estimate for all numeric testmini, system `pg`, is $47.98515781563126252505010020, above `SPEND_LIMIT_USD` $10. Command not run: `python scripts/run_eval.py --dataset findver --mode passage --split testmini --systems pg --seed 7`. The human must raise the cap. IE was not run. |
| Contender B, the −quote ablation, and the −coverage cache rerun | Staff Applied AI Engineer | Thu 29 | The report script, and the frozen prompt line. | After the numeric run is on that frozen line. | Those rows are in the report. | Waiting. The full numeric passage run was not scored. Its estimate is above $10, so this row does not start. |
| Objection loop fixture test | Staff Applied AI Engineer | Thu 29, end of day, and only once the scoreboard is already in `runs/`. If Thursday slips, Friday morning. | A scored numeric row in `runs/`. | No. It waits for that row. It is not cancelled. | The loop is fixture-tested and capped. | Done. The testmini scoreboard row was already in `runs/`. `proofgraph/pipeline.py` `verify` caps the loop at 3 even if `max_rounds` is higher. `propose.revise` and `prompts/objection.md` exist. `tests/test_objection.py` passes with a fake transport. `NOT_MENTIONED` does not start a round. |
| Files API | Staff Applied AI Engineer | Fri 30 | The string-input text propose already works. | Upload is first for the PDF. Text-in-box starts once it works. SAM and blind re-read do not wait on upload. | Upload once. Cache the `file_id` under the file's SHA-256. The PDF part is `input_file` with `detail` `high`, beside `input_text`. The body contains `input_file`, not the line "File id:". A crop uses `input_image`. See the 28 Oct implementation notes. | Waiting |
| SAM token parser in `clients/sam.py` | Staff Applied AI Engineer | Fri 30 | A photo fixture. The hand-made bundle also needs text-in-box and blind re-read. | Yes, beside text-in-box. A still does not wait on upload. | The count is the number of box-token records in the streamed `output_text`. The token shape is in the 28 Oct implementation notes. Mask payloads are discarded. The hand-made bundle noun is `cardboard box`. `carton` is retried only on a phone photo of real cartons. A signature prompt is not used. | Waiting |
| text-in-box | Verification & Reasoning Engineer | Fri 30 | Files API, plus pdf words. Not SAM. | Yes, beside blind re-read, and beside SAM. | The 0–1000 box maps onto pdfplumber with top-down `top`. Try margins 2%, then 3%, then 4%, and keep the smallest whose words contain the fact value. `hours_between` stays as it is. See the 28 Oct implementation notes. | Waiting |
| blind re-read | Staff Applied AI Engineer | Fri 30 | A crop from the image that was sent. Not SAM. Not the Files API. | Yes, beside text-in-box. | Baseten re-reads the crop from an `image_url` data URL. Clock strings match as times, so `7:40` and `07:40` agree. Muse `input_image` is the fallback when Baseten rejects the image. See the 28 Oct implementation notes. | Waiting |
| One hand-made bundle | Principal Engineer & Technical Lead | Fri 30. This is Friday's exit. | Files API, text-in-box, blind re-read, and SAM. | No. It waits for all four. | The bundle verifies with boxes. | Waiting |
| ContractNLI (~300) | Staff Applied AI Engineer | Sat 31 | The scoreboard pattern, and the objection loop capped. Not SAM. | Yes, beside whole-filing, traps, and self-check. Beside freight staging only after the loop is capped. | ContractNLI rows are in the report. | Waiting |
| FinDVer whole-filing (50) | Staff Applied AI Engineer | Sat 31 | The scoreboard pattern, and the objection loop capped. | Yes, beside the Saturday eval group. | 50 whole-filing rows are in the report. | Waiting |
| Conflict traps | Staff Applied AI Engineer | Sat 31 | The scoreboard pattern, and the objection loop capped. | Yes, beside the Saturday eval group. | Trap rows are in the report. | Waiting |
| Self-check | Staff Applied AI Engineer | Sat 31 | The scoreboard pattern, and the objection loop capped. | Yes, beside the Saturday eval group. | The self-check run is in the report. | Waiting |
| 16 freight bundles | Staff Applied AI Engineer | Sat 31 | The Friday box path. | Yes, beside the Saturday evals, once the objection loop is capped. | 16 bundles have run through the box path. | Waiting |
| what-to-fetch | Product & Hackathon Strategy Lead | Sat 31 | The freight bundles. | With the freight work. | Fetch lines exist, so the app handoff is real. | Waiting |
| `pick_demo_cases.py` | Product & Hackathon Strategy Lead | Sat 31 | The freight bundles. | With the freight work. | The script picks the demo cases. | Waiting |
| Muse Code verify-before-acting gate | Staff Applied AI Engineer | Sat 31. Stretch. The only stretch. | Freight rows exist. | No. It waits for those rows. | The gate has run on a freight case. This item may be skipped. | Waiting |
| Live Streamlit check for judges | Senior Software Engineer | Sun 1 | The propose path, and a prepared document or a pasted claim. Fetch lines make the what-to-fetch handoff real. | Yes, beside wiring the host secret. | A judge action runs propose and the engine. The screen shows the verdict, the reasons, plan / act / observe, a red refusal, and what-to-fetch from that run. It does not play a stored verdict. | Waiting |
| Judge deploy | Senior Software Engineer | Mon 2 | That live app. | No. | The judge URL runs a live check. The key is in Streamlit secrets. The spend cap is on, and it counts SAM image calls as well as Spark tokens. Feature freeze that night. | Waiting |
| Animation from a real run | Product & Hackathon Strategy Lead | Tue 3 | The product is already running: live verdict, scoreboard, and at least one boxed bundle. | An outline may be written on an earlier day. The animation waits for a real run. | A 3:00 animation is uploaded, unlisted, and matches a real run. The human makes it. Tuesday is not the day the app first works. | Waiting |
| Buffer and submit | Principal Engineer & Technical Lead | Wed 4 | The deploy, the animation, the public repo, and `BUILT_DURING_HACKATHON.md`. | Re-cut the animation only if the cut needs it. The live URL stays with the judges. | Submitted by 22:00 IST. Post on X. | Waiting |

### Holds

- Wed 28, 21:30. Agents 102. Attend. Owner: Product & Hackathon Strategy Lead. Due today.
- Fri 30, 21:30. Fireworks session. Optional. Owner: Product & Hackathon Strategy Lead. Waiting.
- Tue 3, 20:30–21:30. Office hours. Owner: Product & Hackathon Strategy Lead. Waiting.

## Implementation notes (feasibility probe, 28 Oct)

One synthetic freight packet, load PG-SPIKE-01, run outside the repo. It is not Friday's bundle. Product code did not change. Published token spend was about $0.009. The rate PDF uploaded, Muse returned the detention line exactly, the POD crop read back as a clock, and SAM counted 12 of 12 drawn cartons when the noun was `cardboard box`. These notes are the missing acceptance detail for the Friday rows above. The rows stay Waiting.

**Files API.** `files.create` with `purpose="user_data"` returned a `file_id`. The Responses body is a user message with `input_text` and `input_file`. The PDF part sets `detail` to `high`. The cache key is the SHA-256 of the file bytes, and the stored value is the `file_id`. A later upload of the same bytes can return a new id. The string-input propose path stays for text cases. The probe deleted its upload after the call.

**Text-in-box.** Map the 0–1000 box onto the pdfplumber page with the top-down `top` coordinate. On this rate PDF the box sat about 2.1% of the page height below the glyph centers. A 2% margin matched no words. A 3% margin matched `Detention: $75.00/hour after 2 hours free time` and no other line. A 4% margin also matched `Linehaul: $1,840.00`. Try 2%, then 3%, then 4%, and keep the smallest margin whose words contain the fact value.

**Blind re-read.** Baseten Chat Completions accepted the crop as an `image_url` data URL on `meta-models/muse-spark-open-1026` and returned `7:40` for ink that reads `07:40`. Compare clock values as times, so those two strings agree. A Muse `input_image` call on the same crop is the fallback when Baseten rejects the image. This crop did not need the fallback.

**SAM.** A still goes up as an `input_image` data URL on a streamed `sam-3.1` response. The count is the number of `<|box;` records in the completed `output_text`. One record looks like `<|box;x1=261;y1=463;x2=419;y2=611;w=960;h=720|>`. Discard the mask payload. On the 12-carton drawing, the noun `carton` returned an empty segmentation. The noun `cardboard box` returned 12 records, and the first box sat on a drawn carton. The hand-made bundle uses `cardboard box`. Run `carton` again only when a phone photo of real cartons exists. Both SAM responses reported `images_processed: 1` and zero tokens. The Monday spend cap counts those image calls, or a 16-bundle run can pass the token cap while SAM is still being billed.

**Bundle.** Truth on this packet was arrived 07:40, departed 11:55, free time 2 hours, rate $75, 12 cartons, invoice $450 and 10 cartons. `hours_between` is 4.25 and the fair detention charge is $168.75, so the $450 claim fails once those lines ground. Friday's exit is still one hand-made bundle with a real file, a box, a re-read, and a SAM count.

### Day exits

The exit is the required work that must be true before the day closes. Other rows due that day are still required. If they are open at the end of the day, they move.

The QA & Reliability Engineer accepts the exit after that result exists. Acceptance waits on the result. It does not pull the next day forward.

| Day | Exit |
|---|---|
| Wed 28 | Both probes have returned. |
| Thu 29 | The scoreboard is in `runs/`. The prompt line is frozen. The numeric passage run is scored on that line. |
| Fri 30 | One hand-made bundle verifies with boxes, including a SAM count. |
| Sat 31 | ContractNLI, whole-filing, traps, self-check, and freight rows are in the report. |
| Sun 1 | The Streamlit app runs one live check. It does not play a stored verdict. |
| Mon 2 | The judge URL runs that live check under the spend cap. Features are frozen. |
| Tue 3 | The human's animation is uploaded and matches a real run. |
| Wed 4 | The entry is submitted by 22:00 IST. |

28 Oct: the Wed 28 exit sentence is met. The legal-hours product-path re-probe is recorded. `EVAL_ERROR` is absent, so the stricter task bar is accepted. A null label stays the accepted label on an UNRESOLVED fall-through.

## Slip rule

If a day ends with its exit undone, move every unfinished required task to the next morning. Those tasks are overdue. Overdue work is first. The new day's due tasks are still due that day, after the overdue work.

Cut only after that move still cannot fit. Cut only in this order:

1. Muse Code gate.
2. ContractNLI size. A smaller slice still ships.
3. Freight count above 6. Six bundles still ship.
4. App polish.

Do not cut Files API, SAM, the prompt line, the numeric scoreboard, one boxed bundle, the live judge app, or deploy in order to look minimal. A Tuesday product with no file attachment and no SAM count has missed the Meta tooling story.

ContractNLI and the full freight set should be in by Saturday. If Saturday slips, a smaller ContractNLI slice and 6 freight bundles still ship. The Muse Code gate may be absent.

Say any real cut in `BUILT_DURING_HACKATHON.md`.

## Tuesday product

By the end of Tue 3 Nov, all of these are true:

- A live text verdict.
- A numeric scoreboard versus Direct Muse.
- The counterevidence prompt line is already in the frozen prompt.
- One bundle has a Files API attachment, a box, text-in-box or blind re-read, and a SAM count.
- The objection loop is capped, and it has been used on the fixture or on that bundle.
- The Streamlit app is deployed for judges and runs a live check, with plan / act / observe and what-to-fetch. It does not play a saved verdict.
