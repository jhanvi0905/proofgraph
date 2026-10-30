# 12 · Sprint manager

The sprint manager is a standing role for the builder and for any agent. It does not implement features. It reads this file and `docs/07-build-plan.md`. It names the work due that day, and any task that slipped. It keeps the rest of the plan on the board until the dependency is actually done.

Waiting means later today, or a later day. Waiting is not a cut. Stopped means the row does not return in this window. Nice means it starts only after the five musts below are done, and it has no day of its own.

**Hard deadline: Thu 5 Nov 2026, 07:30 IST (Nov 4, 9:00 PM ET). Team submit target: Wed 4 Nov 2026, 22:00 IST.**

A running product exists by the end of **Tue 3 Nov 2026**. Wed 4 is buffer and submit. Tuesday is the animation, which the human makes from a real run. The product is already running before Tuesday starts.

D25 (28 Oct): the judge-facing Streamlit app runs a live check. It does not play a saved verdict. The app URL is for judges. The key stays in the host secret store, and a spend cap bounds the remaining Meta credit. Scored `runs/` stay the report record. Streamlit stays. Vercel stays out.

## Job

1. Each morning, name the tasks that are due that day, and any overdue task. Overdue work comes first and blocks new scope. The public-branch landing is the human's item. It does not stop an owner who is already in flight. Due tasks get built that day.
2. Sequence by dependency. A later task waits until its dependency is done.
3. Keep the 28 Oct panel schedule. Do not drop the public-branch landing, the live judge check, Files API, text-in-box, the blind re-read, SAM, the one boxed bundle, the D26 sentence, deploy, or the video. Do not restart a stopped row to fill a quiet day. The per-run spend cap is $50 (D29). FinDVer and ContractNLI still wait for the gate.

Day 1 engine work is already in the tree. Do not rebuild `hours_between`. The FinDVer fact-lookup / IE half stays skipped. That rescue rule is already decided.

## Morning invocation

Each morning the builder says: "Run the sprint manager."

The manager then reports, in this order:

1. Overdue tasks, if any. Those come first.
2. Tasks due today. Thursday is the live check and the upload path. Friday is the one bundle. Saturday is the demo-case pick. Monday is the deploy and the README sentence. Tuesday is the video, and the full FinDVer command only if the D29 gate is all yes. Wednesday is submit. ContractNLI runs that morning only under D29.
3. Tasks that may run beside today's work, because their dependency is already met. In-flight work stays with its owner.
4. Tasks that wait, with the dependency named. Waiting means later today or a later day. It does not mean cancelled. Stopped rows are not waiting.

## Task board

"Beside" means the dependency is already met, so the task can run at the same time as the named work. A task with an open dependency stays on the board and waits.

The human asked for owners on 28 Oct 2026. Until that ask, Q1 kept owners off this board. Each open task names one of the six panel roles. A waiting task keeps its owner. The owner starts when the dependency is met. Dates, D21, and the stop after the two Wednesday probes are unchanged.

Later on 28 Oct both probes returned. The Wed 28 exit sentence is met. Neither probe returned 429. D24 keeps the label null on an UNRESOLVED fall-through, so a blank label is not a remaining gap. The legal-hours product-path re-probe also returned no 429. `CHECKER_UNAVAILABLE` is gone. `EVAL_ERROR` is absent on that verdict. Start now means there is no unmet dependency. Waiting means an unmet dependency or a later day. Retries and the 30-claim scoreboard stay done.

Record of the 28 Oct panel (D27), not the live order: Wednesday can close. The deadline does not move. The full numeric passage run is stopped, and so is every row that waits on it. `SPEND_LIMIT_USD` stays $10. `docs/02-scope.md` and `docs/08-guardrails.md` are unchanged. The remaining order is the five musts, then submit. Sunday is buffer.

Record of the 28 Oct second sitting (D28), not the live order: the full numeric command stays stopped. Sunday is no longer an empty buffer if Friday's bundle has closed. That day is the stratified FinDVer slice in D28, then ContractNLI only if D28's three return conditions are already true. If the bundle is still open Sunday morning, the bundle comes first and both slices stay stopped.

Live order (D29, 28 Oct night). The two paragraphs above record those sittings. They are not the current cap and not the current start rule. The human raised the per-run cap to $50. The recorded full-run estimate is about $2.01 under that cap. FinDVer still does not start until the five-box gate is all yes. The full numeric command, `n` omitted, earns Tue 3 Nov once the gate is yes. It does not run on Sunday. ContractNLI is not on the calendar until the same gate is yes and its own zip, adapter, and printed estimate exist. `docs/02-scope.md` is unchanged. D27 and D28 are not amended.

| Order | Task | Owner | Lands |
|---|---|---|---|
| Must 1 | Land the working tree on the public branch judges will open. Judges still see a fixture replay on `origin/main`. | Human builder. The sprint manager tracks it. This panel does not commit. | Wed 28 night. Overdue Thu 29 morning if the tree is still local. It does not stop the in-flight owners. |
| Must 2 | Streamlit runs propose and the engine on the detention/legal-hours claim. The screen does not play a stored verdict. | Senior Software Engineer | Thu 29. Already in flight. |
| Must 3 | One hand-made bundle in product code: Files API upload, text-in-box, blind re-read of the clock crop, SAM noun `cardboard box`. | Upload: Staff Applied AI Engineer, in flight. Text-in-box: Verification & Reasoning Engineer, draft in flight, bind once `file_id` exists. Blind re-read, then SAM: Staff Applied AI Engineer, serial, after the upload. The bundle run: Principal Engineer & Technical Lead. | Fri 30. This is Friday's exit. The outside-repo spike (~$0.009) is not this bundle. |
| Must 4 | README and the video use the D26 sentence only. In the same breath, say the 50 true claims were right on 2 of 27 answered. On screen: one false claim from the five Direct Muse approved, or the detention probe. | Product & Hackathon Strategy Lead. The human makes the animation. The false-claim pick stays Saturday. | README Mon 2. Video Tue 3. |
| Must 5 | Deploy that live check and hold the URL for the submission form. Judges do not receive it before Wed 4. The $50 per-run cap counts SAM image calls. | Senior Software Engineer | Mon 2. Feature freeze that night. The URL goes into the form at submit. |
| Submit | Buffer and submit. | Principal Engineer & Technical Lead | Wed 4, 22:00 IST. |

## Gate before FinDVer or ContractNLI (D29)

"Delivered well on the other results" means every box below is yes. A box is no until the evidence in the right column exists. FinDVer does not start while any box is no, even though the recorded estimate is under $50. ContractNLI uses this same gate, and then its own preconditions.

| Box | Yes only if |
|---|---|
| 1. Tree landed | The branch judges open contains `scripts/run_eval.py`, `scripts/report.py`, `runs/findver-passage-pg-testmini-2026-10-28.jsonl`, `runs/findver-passage-a-testmini-2026-10-28.jsonl`, and `results/report.md`. That branch is not a fixture replay. Today this box is no. `origin/main` is still the fixture replay. The runner is in `stash@{0}` until the human lands it. This panel does not apply the stash and does not commit. |
| 2. Live detention check | On that same branch, a judge action runs propose and the engine on the detention/legal-hours claim and shows the verdict and the reasons. The screen does not play a stored verdict. The check is in the working tree. It is not on `origin/main`. This box is no until it is on the branch judges open and has returned there. |
| 3. One boxed bundle | One hand-made bundle has verified in product code with all four of these: a Files API upload (`input_file`, and the body does not contain the line `File id:`), text-in-box bound on a real `file_id`, a blind re-read of the clock crop, and a SAM count for the noun `cardboard box`. Today this box is no. Upload is in flight. The text-in-box draft is not bound. The blind re-read does not exist. The SAM count does not exist. Friday's bundle is not done. |
| 4. Deploy | The live check is deployed, the key is in the host secret store, and the URL is ready to paste into the submission. Judges do not have that URL until the human submits on Wed 4 Nov. Feature freeze has happened. This box is no. It is Monday 2 Nov's exit. The $50 cap counts SAM image calls as well as Spark tokens. |
| 5. Honest README | README uses the D26 sentence and, in the same breath, says the 50 true claims were right on 2 of 27 answered. It has no 0-versus-5 banner. It has no line that says results have not been run. This box is no. It is Monday 2 Nov's exit. |

The concrete FinDVer result, once the gate is yes and the run finishes, is the scored file from `python scripts/run_eval.py --dataset findver --mode passage --split testmini --systems pg --seed 7` with `n` omitted. The report names that dataset, passage mode, the testmini split, seed 7, system `pg`, and that `n` was omitted (the 250 numeric rows). It shows the false-label rows and the true-label rows separately. Gold-true numeric rows start at row 126, so the full file is the slice that includes true-claim behavior. A file-order prefix is not that slice. The result is not a 0-versus-5 banner. The 30-claim pair stays the false-only comparison already scored. The 50-row dev file stays the tune split and is not this result.

The abort lives in `stash@{0}` `scripts/run_eval.py`: `if estimate > settings.spend_limit_usd`. Equality does not abort. The recorded estimate `$47.98515781563126252505010020` is $2.01484218436873747494989980 under $50. A few cents of slack would not flip that comparison. The comparison is exact `Decimal`, not a float. The fresh `estimate_usd` print on the day is what aborts. Cached generation spend of about $1.80433050 is not subtracted from the estimate. Do not pass `--n`. If the print is above $50, the script stops before any scored call. Do not shrink the file to force the call. The paired 30-claim estimate `$7.248668897795591182364729460` was a different command. It is not the estimate for this one.

ContractNLI preconditions, all yes or the run does not start. No dollar figure is invented.

1. The five boxes above are yes.
2. The official zip is in `data/contract-nli`. It is absent. Do not download it until a person does that manual step.
3. An adapter loads one test record. The adapter is absent.
4. That run's own printed `estimate_usd` is at or under $50. No estimate exists today.
5. The FinDVer run is not occupying the machine.
6. Submit prep has not started.

The cap is per run. A ContractNLI run is not assumed to cost $50. It still cannot start without its own print.

In flight, and left with those owners: the live text check, the Files API upload, and the text-in-box draft. Product & Hackathon Strategy Lead attends Agents 102 at 21:30.

Stopped, with no day: Contender B, the −quote ablation, the −coverage rerun, FinDVer whole-filing, conflict traps, self-check spend, 16 freight bundles, the Muse Code gate, app polish, a 0-versus-5 banner, and any README line that says results have not been run. The full numeric testmini and ContractNLI are not in this list. They are D29. They have no day until the gate is yes. The stratified sampler from D28 does not start.

Nice, only after musts 1–5 are done. No day. If Wed 4 is still submit prep, these are cut.

| Nice | Owner | Gate |
|---|---|---|
| One live objection round | Staff Applied AI Engineer | A trigger code actually fires. |
| Six freight bundles | Staff Applied AI Engineer | The one bundle is already done. |

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
| Land the working tree on the public branch judges will open | Human builder. The sprint manager tracks it. This panel does not commit. | Wed 28 night. Overdue Thu 29 morning if the tree is still local. | Nothing in the product. The work is already in this tree and is not on `origin/main`. | Yes, beside the in-flight owners. It does not stop them. | `origin/main` is the tree judges open. It includes the retries, `run_eval`, `report`, the pipeline, the objection fixture, and the extract prompt lines. Judges do not see a fixture replay. | Human action. Not started by this panel. |
| Full numeric passage run | Staff Applied AI Engineer | Tue 3 Nov, and only after the D29 gate is all yes. If the gate is still no Tuesday morning, this does not start. If the gate first becomes yes Wednesday morning before submit prep, that morning is the only fallback. If the gate is still no when submit prep starts, the run does not start. | The five gate boxes. The runner is on the branch judges open. The fresh `estimate_usd` print is at or under $50. The script aborts when the print is greater than the cap. | No. It does not start on Thursday, Friday, Saturday, or Sunday. It does not take Monday's deploy. | `python scripts/run_eval.py --dataset findver --mode passage --split testmini --systems pg --seed 7` with `n` omitted finishes, or the script aborts on the print before any scored call. The report names the split and shows false-label and true-label rows separately. IE was not run. `n` is not shrunk by hand. | Waiting on the gate. Command not run. Recorded estimate `$47.98515781563126252505010020`. |
| Contender B, the −quote ablation, and the −coverage cache rerun | Staff Applied AI Engineer | Stopped 28 Oct. No day. | The full numeric run, which is stopped. | No. | Those rows are not in this window. | Stopped. They waited on the numeric run. |
| Objection loop fixture test | Staff Applied AI Engineer | Thu 29, end of day, and only once the scoreboard is already in `runs/`. If Thursday slips, Friday morning. | A scored numeric row in `runs/`. | No. It waits for that row. It is not cancelled. | The loop is fixture-tested and capped. | Done. The testmini scoreboard row was already in `runs/`. `proofgraph/pipeline.py` `verify` caps the loop at 3 even if `max_rounds` is higher. `propose.revise` and `prompts/objection.md` exist. `tests/test_objection.py` passes with a fake transport. `NOT_MENTIONED` does not start a round. |
| Files API | Staff Applied AI Engineer | Thu 29. Started Wed 28. | The string-input text propose already works. | Upload is first. The text-in-box draft may run beside it. Blind re-read and SAM wait, serial, same owner. | Upload once. Cache the `file_id` under the file's SHA-256. The PDF part is `input_file` with `detail` `high`, beside `input_text`. The body contains `input_file`, not the line "File id:". A crop uses `input_image`. See the 28 Oct implementation notes. | In flight |
| blind re-read | Staff Applied AI Engineer | After the upload. Friday morning if still open. | The Files API upload is in the product path. The crop is the clock crop. Not SAM. | No. Serial after the upload, same owner, before SAM. | Baseten re-reads the clock crop from an `image_url` data URL. Clock strings match as times, so `7:40` and `07:40` agree. Muse `input_image` is the fallback when Baseten rejects the image. See the 28 Oct implementation notes. | Waiting |
| SAM token parser in `clients/sam.py` | Staff Applied AI Engineer | After the blind re-read. Friday morning if still open. | The upload, then the blind re-read. A still does not need a `file_id`. The same owner does them in this order. | No. | The count is the number of box-token records in the streamed `output_text`. The token shape is in the 28 Oct implementation notes. Mask payloads are discarded. The noun is `cardboard box`. `carton` is retried only on a phone photo of real cartons. A signature prompt is not used. | Waiting |
| text-in-box | Verification & Reasoning Engineer | Draft now. Bind once `file_id` exists, before the Friday bundle. | The draft has no unmet dependency. Binding waits on `file_id`. Not SAM. | The draft is beside the upload. | The 0–1000 box maps onto pdfplumber with top-down `top`. Try margins 2%, then 3%, then 4%, and keep the smallest whose words contain the fact value. `hours_between` stays as it is. See the 28 Oct implementation notes. | In flight. Local draft. Bind once `file_id` exists. |
| One hand-made bundle | Principal Engineer & Technical Lead | Fri 30. This is Friday's exit. | Files API, text-in-box, blind re-read, and SAM. | No. It waits for all four. | The bundle verifies with boxes, including the clock re-read and a `cardboard box` count. | Waiting |
| ContractNLI (~300) | Staff Applied AI Engineer | Wed 4 Nov morning, only if every ContractNLI precondition in the D29 gate is already yes. If FinDVer aborted Tuesday on its print and is off the machine, and the zip, the adapter, and a printed estimate at or under $50 already exist, the rest of Tuesday may be used instead. If FinDVer is still running, or submit prep has started, this does not start. It does not move to Thursday. | The five gate boxes, then the official zip in `data/contract-nli`, an adapter that loads one test record, and that run's own printed estimate at or under $50. No estimate exists. Do not invent one. | No. | The run does not start until those are true. The cap is per run. This run is not assumed to cost $50. | Not scheduled. Zip absent. Adapter absent. No estimate. |
| FinDVer whole-filing (50) | Staff Applied AI Engineer | Stopped 28 Oct. No day. | None. It does not return this window. | No. | Not in this window. | Stopped |
| Conflict traps | Staff Applied AI Engineer | Stopped 28 Oct. No day. | None. It does not return this window. | No. | Not in this window. | Stopped |
| Self-check | Staff Applied AI Engineer | Stopped 28 Oct. No day. | None. It does not return this window. | No. | Not in this window. The self-check spend does not start. | Stopped |
| 16 freight bundles | Staff Applied AI Engineer | Stopped 28 Oct. No day. | None. It does not return this window. | No. | Sixteen bundles do not run. Six bundles are the nice row below. | Stopped |
| what-to-fetch | Product & Hackathon Strategy Lead | Stopped 28 Oct. No day. | The live check does not wait on fetch lines. | No. | Not required for the live check. App polish stays stopped. | Stopped |
| `pick_demo_cases.py` | Product & Hackathon Strategy Lead | Sat 31 | The five Direct Muse approvals on the 28 Oct run, or the detention probe. Not the freight set. | No. It is Saturday's job. The on-screen pair still waits until the Friday bundle exists. If Sunday is full, the pair lives only in the video. | One false claim is chosen. It is one of the five Direct Muse approved, or the detention probe. | Waiting |
| Muse Code verify-before-acting gate | Staff Applied AI Engineer | Stopped 28 Oct. No day. | None. It does not return this window. | No. | Not in this window. | Stopped |
| Live Streamlit check for judges | Senior Software Engineer | Thu 29. Started Wed 28. | The propose path, and the detention/legal-hours claim. Not fetch lines. | No. It is Thursday's exit, with the upload. | A judge action runs propose and the engine on that claim. The screen shows the verdict and the reasons. It does not play a stored verdict. | In flight |
| Judge deploy | Senior Software Engineer | Mon 2 | That live check. | No. | The deployed URL runs that live check. It is held for the submission form. Judges do not receive it until Wed 4. The key is in Streamlit secrets. The spend cap is $50 per run, and it counts SAM image calls as well as Spark tokens. Feature freeze that night. | Waiting |
| README sentence | Product & Hackathon Strategy Lead | Mon 2 | The D26 sentence in `docs/10-demo-and-submission.md`. The dev cell is right when answered, 2/27. | With the Monday deploy. | README uses the D26 sentence and says the 50 true claims were right on 2 of 27 answered. No 0-versus-5 banner. No line that says results have not been run. If the Tuesday FinDVer file finishes before submit, the README is updated from that report: it names the split and shows the false-label and true-label cells. It still does not claim criterion 1. A results sentence after Monday's feature freeze is allowed. A feature is not. | Waiting |
| Animation from a real run | Product & Hackathon Strategy Lead | Tue 3 | The product is already running: the live verdict, the 30-claim scoreboard, and the boxed bundle if Friday landed. | An outline may be written on an earlier day. The animation waits for a real run. | A 3:00 animation is uploaded, unlisted, and matches a real run. It uses the D26 sentence only, and says 2 of 27 in the same breath. The on-screen false claim is the Saturday pick. The human makes the animation. | Waiting |
| One live objection round | Staff Applied AI Engineer | Nice. No day. | Musts 1–5 are done, and a trigger code actually fires. | No. | One live round, only if a trigger code fires. If Wed 4 is still submit prep, this is cut. | Nice |
| Mixed true/false FinDVer slice under $10 | Verification & Reasoning Engineer would have written the stratified sampler. | Superseded 28 Oct night by D29. No day. | The full numeric file is the named result, and it includes true claims after row 126. A prefix cannot. The sampler is not required for that file. | No. | The sampler is not written. The Sunday command is not run. | Superseded. Does not start. |
| Six freight bundles | Staff Applied AI Engineer | Nice. No day. | Musts 1–5 are done, and the one bundle has already verified. | No. | Six bundles, only then. Sixteen stay stopped. If Wed 4 is still submit prep, this is cut. | Nice |
| Buffer and submit | Principal Engineer & Technical Lead | Wed 4 | The deploy, the animation, the public repo, and `BUILT_DURING_HACKATHON.md`. | Re-cut the animation only if the cut needs it. The URL is entered on the submission form. Judges do not have it before that. | Submitted by 22:00 IST. Post on X. Hard deadline remains Thu 5 Nov, 07:30 IST. | Waiting |

### Holds

- Wed 28, 21:30. Agents 102. Attend. Owner: Product & Hackathon Strategy Lead. Due today.
- Fri 30, 21:30. Fireworks session. Optional. Owner: Product & Hackathon Strategy Lead. Waiting.
- Tue 3, 20:30–21:30. Office hours. Owner: Product & Hackathon Strategy Lead. Waiting.

## Implementation notes (feasibility probe, 28 Oct)

One synthetic freight packet, load PG-SPIKE-01, run outside the repo. It is not Friday's bundle. Product code did not change. Published token spend was about $0.009. The rate PDF uploaded, Muse returned the detention line exactly, the POD crop read back as a clock, and SAM counted 12 of 12 drawn cartons when the noun was `cardboard box`. These notes are the acceptance detail for the Friday rows. The product rows stay open until that bundle exists in the product.

28 Oct panel: Staff Applied AI Engineer does the upload, then the blind re-read, then SAM, in that order. A still does not need a `file_id`. Verification & Reasoning Engineer drafts text-in-box now and binds it once `file_id` exists. The Principal Engineer runs the bundle only after all four exist.

**Files API.** `files.create` with `purpose="user_data"` returned a `file_id`. The Responses body is a user message with `input_text` and `input_file`. The PDF part sets `detail` to `high`. The cache key is the SHA-256 of the file bytes, and the stored value is the `file_id`. A later upload of the same bytes can return a new id. The string-input propose path stays for text cases. The probe deleted its upload after the call.

**Text-in-box.** Map the 0–1000 box onto the pdfplumber page with the top-down `top` coordinate. On this rate PDF the box sat about 2.1% of the page height below the glyph centers. A 2% margin matched no words. A 3% margin matched `Detention: $75.00/hour after 2 hours free time` and no other line. A 4% margin also matched `Linehaul: $1,840.00`. Try 2%, then 3%, then 4%, and keep the smallest margin whose words contain the fact value.

**Blind re-read.** Baseten Chat Completions accepted the crop as an `image_url` data URL on `meta-models/muse-spark-open-1026` and returned `7:40` for ink that reads `07:40`. Compare clock values as times, so those two strings agree. A Muse `input_image` call on the same crop is the fallback when Baseten rejects the image. This crop did not need the fallback.

**SAM.** A still goes up as an `input_image` data URL on a streamed `sam-3.1` response. The count is the number of `<|box;` records in the completed `output_text`. One record looks like `<|box;x1=261;y1=463;x2=419;y2=611;w=960;h=720|>`. Discard the mask payload. On the 12-carton drawing, the noun `carton` returned an empty segmentation. The noun `cardboard box` returned 12 records, and the first box sat on a drawn carton. The hand-made bundle uses `cardboard box`. Run `carton` again only when a phone photo of real cartons exists. Both SAM responses reported `images_processed: 1` and zero tokens. The Monday spend cap counts those image calls. A token cap alone would not see them. Sixteen bundles stay stopped.

**Bundle.** Truth on this packet was arrived 07:40, departed 11:55, free time 2 hours, rate $75, 12 cartons, invoice $450 and 10 cartons. `hours_between` is 4.25 and the fair detention charge is $168.75, so the $450 claim fails once those lines ground. Friday's exit is still one hand-made bundle with a real file, a box, a re-read, and a SAM count.

### Day exits

The exit is the required work that must be true before the day closes. Other rows due that day are still required. If they are open at the end of the day, they move.

The QA & Reliability Engineer accepts the exit after that result exists. Acceptance waits on the result. It does not pull the next day forward.

| Day | Exit |
|---|---|
| Wed 28 | Both probes have returned. Met. Wednesday can close. In-flight work is Thursday's. |
| Thu 29 | The live Streamlit check has returned a verdict on the detention/legal-hours claim. The Files API upload is in the product path and does not write `File id:`. The full numeric run is not the exit. |
| Fri 30 | One hand-made bundle verifies with boxes, including the clock re-read and a SAM count for `cardboard box`. |
| Sat 31 | One false claim is picked from the five Direct Muse approved, or the detention probe. Stopped Saturday rows stay stopped. |
| Sun 1 | D29. No FinDVer run and no ContractNLI run. If Friday's bundle is still open, that bundle is overdue and comes first. If the bundle has closed, finish any open gate box that is already due. The stratified sampler does not start. No app polish. |
| Mon 2 | The deployed URL runs that live check under the $50 per-run cap, and the cap counts SAM image calls. The URL is held for the submission form. Judges do not receive it until Wed 4. README uses the D26 sentence and says 2 of 27 in the same breath. Features are frozen. |
| Tue 3 | The human's animation is uploaded, matches a real run, uses the D26 sentence, and says 2 of 27 in the same breath. The video does not wait on the 250. If the five gate boxes are yes that morning, Staff Applied AI Engineer runs the full FinDVer command with `n` omitted and lets the script abort when the print is above $50. |
| Wed 4 | The entry is submitted by 22:00 IST. ContractNLI may use the morning only when every D29 precondition is already yes and submit prep has not started. |

28 Oct: the Wed 28 exit sentence is met. The legal-hours product-path re-probe is recorded. `EVAL_ERROR` is absent, so the stricter task bar is accepted. A null label stays the accepted label on an UNRESOLVED fall-through.

## Slip rule

If a day ends with its exit undone, move every unfinished required task to the next morning. Those tasks are overdue. Overdue work is first. The new day's due tasks are still due that day, after the overdue work.

The 28 Oct panel already made the cut that protects the deadline. D29 raises the per-run cap to $50 and still does not start FinDVer or ContractNLI before the gate. Do not start either run to fill a quiet day. Do not shrink `n` to force the $47.99 command through. Contender B, the −quote ablation, the −coverage rerun, FinDVer whole-filing, conflict traps, self-check spend, 16 freight bundles, the Muse Code gate, and app polish stay stopped. A 0-versus-5 banner stays off the judge screen. A README line that says results have not been run stays out.

Do not cut the public-branch landing, the live judge check, Files API, text-in-box, the blind re-read, SAM, the one boxed bundle, the D26 sentence, deploy, or the video. The 30-claim scoreboard already in `runs/` stays the scoreboard. A Tuesday product with no file attachment and no SAM count has missed the Meta tooling story.

If Friday's bundle is still open Saturday morning, that bundle is overdue and comes first. Six freight bundles do not start. The Monday deploy of the text check still ships. The on-screen pair then lives only in the video.

The public-branch landing stays overdue until the human does it. It does not block the in-flight owners or the Friday bundle. Judges still see a fixture replay until that landing is on the branch they open.

Nice rows start only after musts 1–5 are done. If Wednesday is still submit prep, those rows are cut. They do not move the deadline.

Say any real cut in `BUILT_DURING_HACKATHON.md`. The panel does not write that log.

## Tuesday product

By the end of Tue 3 Nov, all of these are true:

- The public branch judges open is this tree, not a fixture replay.
- The Streamlit app is deployed and has run propose and the engine on the detention/legal-hours claim. It does not play a saved verdict.
- The 30-claim scoreboard is the scoreboard until a D29 full-file report exists. README and the video use the D26 sentence and say the 50 true claims were right on 2 of 27 answered. The Tuesday product does not require the 250. If that file has finished, name it and show the false-label and true-label cells. Do not replace that with a 0-versus-5 banner.
- The counterevidence prompt line is already in the frozen prompt.
- One bundle has a Files API attachment, a box, a blind re-read of the clock crop, and a SAM count for `cardboard box`.
- The objection loop is capped on the fixture. A live round is nice only, and only if a trigger code fires after the five musts.
