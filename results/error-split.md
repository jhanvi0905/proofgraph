# Error split (M4): did the graph miss the evidence, or did the reasoning misjudge it?

Run 2 on the suite (`runs/review-on-2.jsonl`, code frozen at `a654dc1`), the 15 cases of 29 that were not correct (case correct = every gold part's status matched; the same rule as the gate table). The causes come from the per-case traces in `results/run2-analysis.md`; the evidence columns are computed by `scripts/error_split.py` (no model call).

Rule used for the split:

- **Graph missed**: a piece of evidence the answer needed was never extracted as a statement, or never reached by the walk or the full read, or a part had no linked entity at all.
- **Reasoning misjudged**: the evidence was in front of the comparator or the decision rules, and the label or the decision was wrong (judged "does not address", an exception or override handled wrongly, a rule that did not run).

## Per case

| Case | Gold → answer | Gold evidence: extracted / reached / shown as card / decisive | Class | What happened |
|---|---|---|---|---|
| TC10 | supported → cannot_tell | no quoted gold relations | Graph missed | Purchase-order lines from the PNG never connect to the invoice lines. |
| TC12 | contradicted → cannot_tell | no quoted gold relations | Reasoning | The clash between award and notice was found; the override edge's target ("penalty of termination") does not match what the notice mentions ("termination"). |
| TC17 | contradicted → supported | no quoted gold relations | Reasoning | The bylaws approval rule and its condition were in the walk and the condition was labelled "applies", but the first check judged the rule "does not address". |
| TC18 | contradicted → cannot_tell | no quoted gold relations | Reasoning | Both dates were found (resolution May 13, appointment letter May 7); the claim gives no date, so the time rule never ran. |
| TC27 | not_found → cannot_tell | no quoted gold relations | Reasoning | Only 6 statements; one judged relevant by one route blocks "not found". |
| TC37 | supported → weakened | 1 relation; its long span matches no single statement | Reasoning | A carve-out exception is still treated as limiting the claim. |
| TC38 | supported → weakened | no quoted gold relations | Reasoning | Same pattern as TC37. |
| frt-03 | supported → cannot_tell | 4 / 4 / 4 / 2 / 2 | Reasoning | The appointment window and the on-time definition were reached and judged "does not address". |
| fin-08 | contradicted → cannot_tell, supported | 7 / 7 / 7 / 6 / 6 | Reasoning | The evidence was decisive; the override between the amended filing and the release cannot be used (the roles are not ranked and the edges miss the clashing statement), so the answer is "documents disagree". |
| aipm-05 | contradicted → one part cannot_tell | 7 / 7 / 7 / 4 / 4 | Reasoning | Three reached requirement statements were judged "does not address" ("GA launch shall not proceed until SR-7 verification has passed", "GA locales: … pt-BR", the Closed-only-when-Passed rule). |
| frt-07 | mixed → cannot_tell, supported | 8 / 7 / 5 / 3 / 3 (of 8; one email date header was not extracted) | Both | Two statements were never reached (the "Copy. Driver was going to roll at 5am" email, the "supersedes any Carrier tariff" clause); two reached ones were judged "does not address"; the override target does not match ("accessorial schedule"). |
| frt-01 | mixed → two parts cannot_tell | 10 / 10 / 8 / 7 / 7 | Both | Two table rows read from an image page ("APPT 10/08/2025 08:00", "BILLS SIGNED …") were never reached; the quarter-hour rule was reached but not shown. |
| frt-05 | mixed → cannot_tell, contradicted | 8 / 7 / 6 / 5 / 5 | Both | One declared-value statement was not extracted; the concealed-damage notice email was never reached; the "unless the consignee gives written notice" limit was reached and judged "does not address". |
| fin-07 | supported ×3 → cannot_tell | 5 / 5 / 5 / 4 / 4 | Both | One reached statement was not shown; part 4 had no linked entity at all. |
| leg-02 | supported ×3 → cannot_tell, weakened | 9 / 9 / 8 / 5 / 5 | Both | "Section 4.2 is not amended" was never reached; the "this Amendment prevails" clause and the amendment clause were reached and judged "does not address"; the override edge is unclear because "Agreement" names more than one entity. |

## Totals

| Class | Cases |
|---|---|
| Graph missed only | 1 (TC10) |
| Reasoning misjudged only | 9 (TC12, TC17, TC18, TC27, TC37, TC38, frt-03, fin-08, aipm-05) |
| Both | 5 (frt-07, frt-01, frt-05, fin-07, leg-02) |

Reasoning is involved in 14 of the 15 wrong cases and the graph's reach in 6 of the 15.

## Limits of this table

- Counts of gold evidence are per case, not per part, so in the "Both" cases they do not say which of the two causes flipped a given part.
- Seven suite cases (TC10, 12, 17, 18, 27, 37, 38) have gold without quoted evidence spans, or with one long span; their class is read from the traces in `results/run2-analysis.md`, not computed.
- "Reached" counts a statement reached by the typed walk, the full read, a card or the decision. A relation is carried by a statement sharing at least half of the gold quote's words (the scorer's rule).
- This is a description of the 29 suite cases after error analysis; it does not test a fix.
