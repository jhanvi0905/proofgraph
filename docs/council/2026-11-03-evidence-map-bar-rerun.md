# Evidence map bar re-run on current code (3 Nov 2026)

Protocol: `docs/council/2026-11-02-evidence-map-unseen-prereg.md`, unchanged. Head `50f18e0` (branch `feat/evidence-map-ui`). Run once, same 9 cases (TC1, 2, 5, 6, 7, 13, 15, 39, 42), same claims and files, flag-off arm (env unset) versus `PROOFGRAPH_EVIDENCE_MAP=1`, shared cache dir. No code, prompt or threshold edits; no re-run. The original runner was not saved, so the arms were driven with `run_review` per case from a throwaway script outside the repo (scratchpad). No answer keys, Solutions or `_Evaluation` files were opened.

**Spend:** ledger before 3.36772880, after 3.36772880 (delta $0.00; cap was before + 0.60). The handoff said about 2.96; the ledger actually read 3.37, and the cap used was 3.37 + 0.60. **Every call in both arms was a cache hit** (each review took 0.1 to 0.3 s and cost $0), so M6 timing and M7 are not a measurement of live cost or latency.

## Metrics vs bar
| Metric | Result | Verdict |
|---|---|---|
| M1 flag-off replay | `replay_compare.py`: G1 0 differences, G2 0 problems | PASS |
| M2 card integrity | 26 cards, all pinned, every quote an exact substring of its page text (whitespace-normalised, text as ordered in map mode), all with a document name, no duplicate within a part and document. Date source spans not individually verified (as in the original). | PASS |
| M3 coverage (reported) | Of 7 cases with 2+ documents, 4 showed 2+ documents: TC1 (2 of 3), TC6 (2 of 2), TC7 (5 of 5), TC13 (3 of 3). Exceptions: TC2 and TC15 one document (other examined passages labelled irrelevant: 1 of 4 and 4 of 22 relevant); TC5 none (0 of 5 relevant). | reported |
| M4 status stability | One change: TC39 cannot_tell to weakened (list below). Not judged here. | for manager |
| M5 label inflation | relevant share per part: median 22.7%, max 50% (TC1) | PASS (<=60%) |
| M6 errors/hangs | 0 errors, 0 banners, slowest review 0.33 s (all cached) | PASS |
| M7 cost/time | median $0.00 and 0.23 s per review (all cached; the 2 Nov figure was $0.024, 18.1 s) | PASS on the numbers, not informative |
| M8 referenced nodes | 0 "referenced, not supplied" items across the 9 cases | reported |

## Per case (flag-off status -> map status)
| Case | Status | Cards off / map | Docs shown / supplied | Box status (map) | Examined / relevant |
|---|---|---|---|---|---|
| TC1 | cannot_tell -> cannot_tell | 1 / 3 | 2 / 3 | 3 pinned | 6 / 3 |
| TC2 | contradicted -> contradicted | 1 / 1 | 1 / 3 | 1 pinned | 4 / 1 |
| TC5 | cannot_tell -> cannot_tell | 0 / 0 | 0 / 3 | none | 5 / 0 |
| TC6 | contradicted -> contradicted | 1 / 2 | 2 / 2 | 2 pinned | 8 / 2 |
| TC7 | cannot_tell -> cannot_tell | 1 / 5 | 5 / 5 | 5 pinned | 22 / 5 |
| TC13 | contradicted -> contradicted | 1 / 5 | 3 / 3 | 5 pinned | 25 / 5 |
| TC15 | contradicted -> contradicted | 1 / 4 | 1 / 3 | 4 pinned | 22 / 4 |
| TC39 | cannot_tell -> **weakened** | 1 / 5 | 1 / 1 | 5 pinned | 12 / 5 |
| TC42 | supported -> supported | 1 / 1 | 1 / 1 | 1 pinned | 10 / 1 |

Box statuses overall: 26 pinned, 0 approximate, 0 unpinned. All 9 packets are text PDFs, so no scanned page was in play and the later scan-line candidate change was not exercised.

## M4 change list (verbatim, for the manager's panel read)
TC39, claim "The Munt sale NDA requires the prospective buyer to keep the existence and status of sale negotiations confidential." cannot_tell -> weakened. Cards (all doc 80e5091b3b0d):
- c1 supports p1: "In consideration of the Sellers agreeing to disclose confidential information (the "Confidential Information") to the Candidate ("Disclosee"), the latter hereby undertakes to the Sellers that as Disclosee, they will keep confidential all and any Confidential Information received at any time."
- c2 supports p1: "Confidential Information shall mean the following: a) all such information, of any kind whatsoever (whether in oral, written or electronic form ... ) pertaining to the Sale of the Munt a..." (quote truncated here)
- c3 weakens (exception) p1: "Confidential Information shall exclude: a) information which had become available to the public prior to the date of disclosure ... " (exclusion for public information)
- c4 weakens (time) p2: "The obligations of the Disclosee under this Agreement shall expire the earlier of (a) three years after the date of this Agreement, or (b) the date the Sale ... is completed."
- c5 weakens (condition) p2: "In the event that the Disclosee ... becomes legally compelled to disclose any of the Confidential Information to a regulatory authority ... the Disclosee shall immediately notify the Sellers before disclosing ..."
The three weakens cards and the status change match the 2 Nov record. No new reds or ambers elsewhere (TC2, 6, 13, 15 were already contradicted; TC42 stays supported).

## Differences vs the 2 Nov result
- Statuses identical in all 9 cases; the only change from flag-off is still TC39. Total cards still 26; M5 median 23% (22.7%) and max 50% unchanged.
- TC6 now shows passages from both documents (original: one document), so M3 is 4 of 7 cases rather than 3 of 7. Per-case card counts were not recorded on 2 Nov, so no other case-level comparison is possible.
- Spend and timing: original $0.20 and 18.1 s median; now $0 and 0.23 s because everything was cached.

## Caveats
- Fully cached run: no live model call was made, so it shows the current code reproduces the same results from recorded answers, and says nothing new about live cost, latency or label stability. A cold run would be needed for M7.
- TC7 cards c3 and c5 have the same quote text (invoice_10249 and purchase_orders_10249); different documents, so not a duplicate under M2.
- Dates from the first-page tier can be unrelated (original caveat, not re-checked); the sample was seen in earlier experiments; no accuracy claim.

**Bar: PASS** (M1, M2, M5, M6 pass; M7 passes only because every call was cached; M3, M4, M8 reported, M4 awaits the panel read).
