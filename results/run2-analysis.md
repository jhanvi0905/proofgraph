# Run 2 analysis: how the graphs formed and what the walk never traced

Code frozen at `a654dc1`. Suite run `runs/review-on-2.jsonl` (29 cases, flag on). Produced with `scripts/analyze_run.py` (per-case table in `results/run2-suite-analysis.md`), `scripts/trace_runs.py` and `scripts/view_graph.py`, reading the graph cache. Gold is read only by these dev scripts. The clean-check and ablation sections are pending; they are added when those runs end.

## 1. Result in one table

| System (n = 29) | Correct | Wrongly supported | Fixed / broken vs flag off |
|---|---|---|---|
| Flag off | 9/29 (31%) | 0/28 | none |
| Run 1 graph | 7/29 (24%) | 0/28 | +1 / −3 |
| Run 2 graph | 14/29 (48%) | 1/28 (TC17) | +8 / −3 |

Fixed: TC4, 14, 20, 23, 25, 41, 44, 46. Broken: TC12, 17, 38. Read-from-page tier: 15/17 right, none wrongly supported. Valid quotes fell from 91% to 79%. By scenario: S7 (not mentioned) 4/4, S1 9/13, S2 2/5, S4 1/2, **S5 (override across documents) 2/7**.

## 2. How the graphs were formed (29 graphs, 1,496 statements)

- **Extraction is faithful.** 84% of statements are page-tier (778 exact, 705 normalised), 15% model-tier (6 fuzzy, the rest inferred bearers), and 7 (0.5%) could not be aligned and are marked unclear, so they never decide.
- **Statement types.** 746 rules, 657 facts, 93 events. Only 17 of 29 cases have any event statement; 83 of the 93 events carry a date.
- **Edges.** 3,850 `mentions` (3,220 page, 613 model, 17 unclear) dominate. Class links: `is_a` 168 (82 unclear), `holds_office` 48 (12 unclear), `defined_by` 102. Exceptions: `defeats` 115, `conditions` 37. Precedence: `overrides` 32 (**16 unclear**), `outranks` 8 (from the governance file), `supersedes` 1. Citations: `cites` 6.
- **Entity merging is conservative by design.** 12 plural merges, and 101 Jaro-Winkler near-misses kept as unclear links that never merge.
- **Rejections counted, none silent.** 165 member lists not found in their quote, 29 relations whose names were not in the quote, 2 ambiguous override targets; comparator and linking dropped 5 ids.
- **Walk and full read.** Agreement flags across parts: 12 agree, 28 partial, 6 both empty, 2 disagree.
- **Time anchors.** 155 exceptions or conditions, of which 35 (in 14 cases) were marked as waiting on an event. This is the material the time rule (C4) can act on.

## 3. Where gold evidence fell out (73 gold relations, 29 cases)

| Stage | Gold relations | Share |
|---|---|---|
| extracted as a statement | 67 | 92% |
| reached by the walk | 53 | 73% |
| shown as a card (judged relevant) | 37 | 51% |
| decisive | 36 | 49% |

Caveat on the first row: the match needs one statement to share at least half of the gold quote's words, so long gold spans (TC37, TC40) read as "not extracted" although the matching statement exists. The three later stages are not affected by this. The six not-extracted items otherwise include the planted injection notes in frt-07 and fin-08, which are correctly kept out of the rules.

### What was not traced through the graph

1. **Extracted but never reached by the walk (14 relations, 19 points).** The claim's entities never connected to them: the frt-07 email "Copy. Driver was going to roll at 5am", the frt-07 clause "this Rate Confirmation supersedes any Carrier tariff", frt-01 table rows read from an image page ("APPT 10/08/2025 08:00", "BILLS SIGNED …"), frt-03's "requested date moved by DC scheduling", aipm-05 "The beta may proceed now", frt-05's concealed-damage notice email, leg-02's program-terms liability cap. These are mostly emails, scanned or image pages, and table rows. This is a linking and entity-naming gap.
2. **Reached by the walk but judged not relevant (16 relations, 22 points). This is the largest loss.** The comparator answered "does not address the claim" or "not mentioned" for statements the gold calls decisive: frt-07 "No TONU shall be paid if the cancellation is communicated before 18:00", aipm-05 "GA launch shall not proceed until SR-7 verification has passed", "GA locales: … pt-BR", frt-05 "Carrier shall not be liable for concealed damage unless …", frt-03's appointment window, and leg-02's "In the event of a conflict between this Amendment and the Agreement, this Amendment prevails". It is the same mechanism as TC17: the predicate check at the first step discards requirement and precedence statements even when an attached exception was labelled "applies".
3. **Shown but not decisive (1 relation).** TC41's survival clause.

## 4. Why the override scenario (S5) failed

Overrides edges exist, but the decision cannot use them:

- **Name mismatch.** An overrides edge points from the overriding statement to the entity it overrides, and a conflicting statement is overridden only if it mentions that same entity. In TC11 and TC12 the award's edge points to "penalty of termination" while the notice's statement mentions "termination", so no match. In frt-07 the clause overrides "accessorial schedule" while the dispute letter's statement mentions "standard accessorial schedule".
- **Ambiguity makes edges unclear.** leg-02's "this Amendment prevails over the Agreement" is unclear because "Agreement" names more than one entity across the packet's documents (the two contracts each define it). Half of all 32 overrides edges are unclear; unclear never decides.
- **Roles.** The arbitration award and the PERB decision are tagged `other`, which the governance file does not rank, and the notice is tagged `officer_act`, the lowest rank. With no usable edge and no comparable roles, the answer is "documents disagree" (TC12, TC11 part 2, frt-07, fin-08, leg-02).

## 5. Per-case failures, traced

| Case | Gold → answer | What the graph did |
|---|---|---|
| TC17 | contradicted → **supported** | Three recitals and memo statements all say she served from May 7. The bylaws approval rule and its condition were judged "does not address" even though the condition was labelled "applies". |
| TC12 | contradicted → cannot_tell | Clash between award and notice; override edge exists but its target does not match what the notice mentions. |
| TC18 | contradicted → cannot_tell | Resolution (May 13) against appointment letter (May 7); the claim gives no date, so the time rule never ran. |
| TC37, TC38 | supported → weakened | Carve-out exceptions are still treated as limiting the claim. |
| TC10 | supported → cannot_tell | Purchase-order lines from the PNG never connect to the invoice lines. |
| TC27 | not_found → cannot_tell | Only 6 statements in the packet; a statement judged relevant by one route blocks "not found". |
| frt-03, fin-07, leg-02 | supported → cannot_tell or weakened | Clash or non-relevance as in sections 3 and 4. fin-07 part 4 had no linked entity at all. |

## 6. Candidate fixes (not applied; each needs its principle added to the brief and held-out justification first)

1. A statement carrying an exception or condition labelled "applies" bears on the claim whatever the predicate check says. This targets the TC17 failure and the largest funnel loss.
2. Match an overrides target to a statement's entities by containment of names, not equality, and resolve an ambiguous target to the document-local entity first. This targets S5.
3. Let a document with no governance role still win by being the later document of the same role on the same subject, so `other` is not a dead end.
4. Extend entity linking to emails, table rows and image pages so the walk reaches them.

## 7. Clean check and ablation (30 ContractNLI pairs never used before; gold is the published label)

| System (n = 30) | Correct | Wrongly supported | Fixed / broken vs flag off |
|---|---|---|---|
| Flag off | 15/30 (50%), CI 33–67% | 2/20 (10%) | none |
| Run-1 rules (ablation) | 9/30 (30%), CI 17–48% | 0/20 | +1 / −7 |
| **Iteration 2 rules** | **19/30 (63%), CI 45–78%** | **1/20 (5%)** | **+7 / −3** |

- The Iteration 2 rules got 10 pairs right that the run-1 rules got wrong, and none the other way round.
- The run-1 graph was worse than no graph (9 against 15). Iteration 2 is better than no graph (19 against 15), although at n = 30 the intervals overlap.
- Fixed against flag off: cnli-41, 67, 129, 212, 213, 218, 225 (six are "not mentioned" cases). Broken: cnli-62, 157, 289, all S2.
- Wrongly supported with the graph: cnli-85 (S8, a blank-template statement read as supporting "all information shall be expressly identified"). Flag off had two (cnli-65, cnli-77), which the graph turns into `weakened`.
- **S2 (exception or condition) is 0/7 on this slice.** In five of the seven the comparator labels the exception "applies" and the code weakens the statement, but in these claims the exception is the thing the claim asserts (for example "may retain some Confidential Information after return", with the one-copy retention exception). An exception that applies and itself agrees with the claim should support it, not defeat it. This is evidence from a held-out slice for a fifth candidate fix, and it is also the over-qualification seen in TC37 and TC38 on the suite.

Caveat: the suite was used for error analysis after run 1, so run 2 on the suite is labelled after error analysis. This clean slice was not looked at while building, so it is the unbiased number. Any fix chosen from these results needs a new held-out slice.
