# Questions

Open items the sprint manager cannot decide from `docs/12-sprint-manager.md`. Work on an open item stays stopped until the human picks. Q1, Q2, and Q3 are resolved. Q3 keeps the label null on an UNRESOLVED fall-through. No engine label change. Q4 is open and is not a build task. The next unblocked build tasks are the Start now rows on `docs/12-sprint-manager.md`.

## Q1 · Morning assignments have no file in the sprint docs

Resolved on 28 Oct 2026. The human asked for an owner column. The previous recommendation was to keep the 28 Oct owners in the morning report and leave the board as it is until the human asked for that rule change. That rule is updated. The owner column is on the task board in `docs/12-sprint-manager.md`. The holds there name an owner. `docs/07-build-plan.md` stays the calendar and does not list owners.

No rule in `docs/12-sprint-manager.md` or `docs/11-decision-log.md` forbade the column. The hold was this question. Dates, D21, and the stop after the two Wednesday probes are unchanged. The live probe stays with the Staff Applied AI Engineer.

The human's panel (27 Oct 2026, repeated 28 Oct 2026) is six roles:

1. Principal Engineer & Technical Lead. Architecture, technical decisions, task decomposition, dependencies, delegation, integration, and delivery.
2. Staff Applied AI Engineer. Meta Muse integration, model interfaces, structured extraction, inference efficiency, and AI reliability.
3. Verification & Reasoning Engineer. Evidence relationships, provenance, deterministic verification, contradiction detection, and abstention logic.
4. Senior Software Engineer. Repository architecture, modularity, clean code, interfaces, dependency management, and maintainability.
5. Product & Hackathon Strategy Lead. MVP scope, demonstrable value, and challenges to extra features.
6. QA & Reliability Engineer. Testing, edge cases, regression prevention, reproducibility, and acceptance criteria.

Decided:

- Add an owner column to `docs/12-sprint-manager.md`.
- The morning-report-only option is closed.

## Q2 · The second Wednesday probe is a Baseten call, and that key is empty

Resolved on 28 Oct 2026 by the user, option 1. The Baseten key is in `.env`. The one wording call went to `meta-models/muse-spark-open-1026` at `https://inference.baseten.co/v1`. The Muse Spark fallback was not used. Baseten auth succeeded.

The call overlapped the live detention propose. Wording HTTP started at 2026-10-27T20:27:38.744Z and ended at 2026-10-27T20:27:41.801Z. The Meta propose HTTP started at 2026-10-27T20:27:38.746Z and ended at 2026-10-27T20:27:54.903Z.

Wording outcome: label `entails`. Quote: `Detention: $75.00/hour after 2 hours free time`. Statement: `The rate applies after free time.` One Chat Completions call, response id `chatcmpl-571e8cebe037449e99c8da2d3b4a377c`, 196 prompt tokens and 353 completion tokens. No checker error. Artifact: `cache/probes/2026-10-28/wording-result.json`.

Live propose outcome, for the dependency this question was waiting on: one `muse-spark-1.3` detention propose, response id `resp_6ae1094a9571c4125b0a4fce`, 420 input tokens and 4540 output tokens, then `run_program`. Verdict `UNRESOLVED`. The label field is empty. Reason: how partial billable hours are billed (prorated versus rounded to full-hour increments). Reason codes: `UNVERIFIABLE_PART`, `CHECKER_UNAVAILABLE`, `EVAL_ERROR`. Artifact: `cache/probes/2026-10-28/propose-result.json`. Cached response: `cache/e91f8d82d44b293abb3d43e1bcbda8679f28b0b20ced8c87cc776a5a5514ff79.json`. The 27 Oct cache entry for that same prompt was moved aside before the call so this probe was a new HTTP request. It is kept at `cache/probes/2026-10-28/held/`.

`proofgraph/clients/checker.py` still calls `MuseClient` on the Meta API. This probe did not use that function. It rendered `prompts/blind_wording.md` and sent one Baseten request. No product module was edited. Two HTTP calls, no 429, no JSON repair, no fallback. Stop.

## Q3 · An UNRESOLVED fall-through has no label, and the Wednesday task asks for one

Resolved on 28 Oct 2026 by the user, option 1. Recorded as D24 in `docs/11-decision-log.md`. The label stays null when no required link decided the verdict. `combine.py` does not change. COMPUTED, CHECKED, and ASSUMED stay on a chain that was decided.

The live detention propose returned verdict `UNRESOLVED` and label null. `proofgraph/schema.py` allows null. `proofgraph/engine/combine.py` sets the label to None on the unresolved fall-through. `tests/test_combine.py` `test_unverifiable_part_blocks_support` does not assert a label. `docs/03-architecture.md` §2 allows null, and §7.6 sets the label from the weakest required link that decided the verdict. `docs/01-product-brief.md` defines the three labels for a chain that was decided. The Wednesday task sentence asked for a label. The human kept null.

Decided:

- Keep null. Option 2, forcing COMPUTED, CHECKED, or ASSUMED onto that fall-through, is closed.
- The Baseten client, the `hours_between` prompt, assumed-rule routing, and the live re-probe do not wait on a label value. A later UNRESOLVED fall-through still prints no label.

## Q4 · A line on the page that the model never cites

Open. Queued on 28 Oct 2026. Not a build task. Do not change the engine, the prompt, or the page check for this item until the human picks.

The page check, once built, opens the page the model named and looks inside the box. It does not scan the rest of the page for a line the model left out. A second rate on that page stays invisible unless the model also copied it, the claim’s own numbers are uncovered, or the counterevidence line caused the model to bring the opposing passage back. Two copied figures for the same label, entity, and period can then conflict. A figure the model never writes down is not found by the box check.

The human asked to hold this and think later. No option is chosen.

## Q5 · The dark-image rule is tuned on synthetic images only

Open. Raised by R-03b (`fix/r-03b-dark-image`).

`_image_page` in `proofgraph/review/ingest.py` now inverts an image only when its mean gray is under 100 and at least half of its pixels are near-black (gray 30 or below). On generated images the inverted scans score 0.65 to 0.85 near-black, a dark photo of a light page scores 0.28 to 0.35, and every real light scan in the repo scores 0.06 or less. These are synthetic numbers, so the 0.5 cut is unproven on real files.

A dark-mode screenshot has the same histogram as a white-on-black negative, so it is inverted too. That is harmless, since the text comes out dark on light.

Needed from the human: drop one real dark phone photo of a document and one real inverted scan into the data folder (do not commit them). The two skipped real-file tests in `tests/test_scan.py` (branch `feat/r-13-scan`, PR 43) will then run and check the rule on real input.
