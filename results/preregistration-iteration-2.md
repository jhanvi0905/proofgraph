# Iteration 2: pre-registration and results

Written before any Iteration 2 code, after the first gate run. **Run 1** (rules as built; `runs/review-off.jsonl`, `runs/review-on.jsonl`, n = 29): flag off 9/29 correct, ProofGraph 7/29, +1 fixed (TC25), −3 broken (TC12, TC17, TC38), wrongly supported 0/28 in both arms at case level, but TC4 part 2 is wrongly supported at part level. The scorer prints PASS; the decision was HOLD, because flag on is below flag off and the system never answers "supported" on a gold-supported case. Iteration 2 fixes the decision layer with general rules only. No case is patched.

### Guardrails (overfitting)

- The reasoning core is **frozen at the five rules in section C**. No decision rule may name a document type, domain, synonym or case id in code. Any new rule must state its general principle in this brief first and be justified by a held-out case, not only a suite case.
- Thresholds use the fixed defaults below. Never tune them on the suite.
- All invariants hold: flag off byte-identical (golden page, `replay_compare` 0 differences), `tests/test_boundaries.py` untouched and green, every model call through MuseClient, no gold read in product code.
- Results from the suite after this iteration are labelled **run 2, after error analysis**. The clean check (G2) is the only unbiased number.

### A. Schema (graph construction)

1. Statement types: **Rule** (bearer, deontic type, action, conditions), **Fact** (a factual statement about an instance), **Event** (type, date, actor, quote), Document, Entity. Table rows as Records: skipped this iteration.
2. Event types come from a fixed list chosen by the model at extraction: appoint, approve_or_adopt, start, terminate, amend, deliver, pay, notify, file, other. No synonym lists in code; approval, adoption and ratification all map to approve_or_adopt through the model's choice.
3. Conditions that wait on an event ("until approved by the Board", "upon adoption") are extracted as event anchors.
4. Exceptions become **defeats** edges (exception → the rule it carves out).
5. **overrides** edges come only from the documents' own words, each verified against its quote: amended and restated, a /A filing, replaces, supersedes, notwithstanding, subject to, an order-of-precedence clause, and "reduced to" / "modified" / "set aside" in a decision.
6. One declared data file (not code), governance only: statute > articles > bylaws > board resolution > officer act.

### B. Comparator labels (N4), judged per claim part

1. First: does this statement address the claim part's predicate? If not: irrelevant.
2. Relation: agrees / conflicts / not_mentioned / irrelevant.
3. For each attached exception: applies to this claim's case / does not apply / unsure.
4. For amendments: replaces / adds / deletes / restates (as before).

### C. Reasoning core (A5, frozen)

1. **Type rule.** A Rule can never establish a Fact about an instance; facts need Fact or Event statements.
2. **Defeat.** An exception defeats its rule only if labelled "applies"; "unsure" means weakened; "does not apply" means the rule stands and the exception shows as a note. The second read (N5) runs on every part that becomes supported under this rule.
3. **Override.** An extracted overrides edge wins; otherwise the later document of the same role on the same subject wins; otherwise the governance data file; otherwise "documents disagree". All role-specific precedence code is deleted.
4. **Time.** Claims about time ("before", "from", "continuously", "effective") compare event dates in code. An event anchor resolves to the matching event; if the condition is satisfied at D′ later than the claim's date D, "qualifies" becomes contradicted, with the reason "<effect> from D′, not D". If the anchor cannot be resolved, keep "qualifies".
5. **Verdict.** The weakest link sets the label. "not_found" only when no statement is labelled agrees / conflicts / qualifies on either route. Walk-and-read agreement compares those relevant sets, not raw citations.

### D. Retrieval (I1, I2, I4)

1. Seed the walk from every linked entity: names, events and the predicate's concepts.
2. Statements the full read cites go to the comparator, not only into the agreement count.
3. I3: class hops (is-a, holds office) carry no decay. Trust ordering and rotation across documents stay. This is a **deliberate change** to the decay in I3, logged here.

### E. Text quality (fixed defaults, not tuned)

- Score each page. If more than 2% of tokens are `(cid:` codes, or more than 5% of words are over 25 characters, send the page through the existing Muse Spark transcription path with line boxes.
- For missing spaces, retry pdfplumber with a tighter `x_tolerance` and keep whichever text scores better.

### F. Order of work

C5 (not_found) → B and C1 → C2 → A5, A6 and C3 → A2 to A4, then C4 → D → E. Tests first for each; one commit per item with the rule name in the message. Re-cache the three demo packets (TC17, TC40, one contract-plus-memo pack) when done.

### G. Evaluation (run once, code frozen first)

1. Suite: rerun all 29 cases once. Report run 1 and run 2 side by side: correct, wrongly supported, fixed and broken ids, per-tier rows. Label run 2 "after error analysis".
2. Clean check: 30 ContractNLI contract-and-hypothesis pairs never used before. Gold comes mechanically from the published labels (the `scripts/build_gold.py` logic, never authored). Report flag off against flag on.
3. One ablation on the held-out slice: the Iteration 2 core against the run-1 rules.
4. Spend approved up to **$15** in total. Post all tables and stop for the team's decision on the flag.

### H. In parallel

F1–F5 (auth, server, live page, review page, tokens) do not depend on the gate and run in their own session. F6 (deploy host) still needs the team's answer first.

### Iteration 2 results (locked)

Code evaluated: commit `a654dc1` (tag `iteration-2-evaluated`). No rule was changed after the run. Spend about $11.5 of the approved $15. Run files: `runs/review-off.jsonl` (flag off), `runs/review-on.jsonl` (run 1), `runs/review-on-2.jsonl` (run 2, after error analysis), `runs/clean-*.jsonl` (clean check and ablation). Full traces and candidate fixes: `results/run2-analysis.md`.

| Slice | Flag off | Run-1 rules | Iteration 2 rules |
| --- | --- | --- | --- |
| Suite, 29 cases (labelled after error analysis) | 9/29 correct, 0/28 wrongly supported | 7/29, 0/28 | 14/29, 1/28 (TC17), +8 fixed / −3 broken |
| Clean check, 30 unused ContractNLI pairs | 15/30, 2/20 | 9/30, 0/20 | 19/30, 1/20 (cnli-85), +7 fixed / −3 broken |

- Gate rule: HOLD on the suite (wrongly supported 0 to 1), PASS on the clean check (2 to 1). The decision on the flag is left to the team.
- Open weaknesses, none patched: S2 exceptions that agree with the claim (0/7 on the clean slice; the same pattern as TC37 and TC38), S5 override edges that miss the clashing statement's entities (2/7 on the suite), TC17's dismissed approval rule, valid quotes 91% to 79%.
- Any further rule needs its principle written here first and a new held-out slice, since both slices are now used.
