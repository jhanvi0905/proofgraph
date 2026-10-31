# Council brief: claim packets for the Direct Muse comparison (31 Oct 2026)

Status: findings and recommendations. Nothing here changes a rule. Per AGENTS.md, rule changes need the human.

**Update after the fix (branch `fix/percent-tolerance`):** see `2026-10-31-council-session.md`. Live rerun of the same five: 3 CONTRADICTED, 1 UNRESOLVED, 1 SUPPORTED (ASSUMED). The table below is the result before the fix.

## What was done
- Recovered the 28 Oct Direct Muse run from the model cache: 31 cached calls, 5 answered `entailed`. D26 says all FinDVer rows in that slice are gold false.
- Built the 5 approved claims into claim packets (copies kept locally under `data/handoff-2026-10-31/claim-packets/` in the main checkout, because the real filing excerpts have an unverified licence). Each carries the real SEC excerpts and a recorded propose reply, so `uv run python -m proofgraph <file>` replays with no network.
- Ran all 5 through `run_claim` with a live propose (about $0.11 in total, ledger $0.112, well under the cap).

## Result
| Claim (short) | Direct Muse | ProofGraph | Link that failed |
|---|---|---|---|
| Working capital deficit +38.33% | entailed | CONTRADICTED / COMPUTED | `(f_dec - f_mar)/f_mar*100 == 38.33` |
| R&D decrease ~59.98% | entailed | CONTRADICTED / COMPUTED | `... == 59.98` |
| Partners' capital ~-9.63% | entailed | CONTRADICTED / COMPUTED | `... == -9.63` |
| Net profit margin ~-404.40% | entailed | CONTRADICTED / COMPUTED | `... == -404.40` |
| Fund mgmt net income -52.1% | entailed | CONTRADICTED / COMPUTED | `... == 52.1` (also UNGROUNDED_QUOTE on a header fact) |

ProofGraph rejected all five. The result is real, but finding 1 shows it is partly an accident of how the proposer phrased the expression.

## Finding 1 (high): the percent verdict depends on how the proposer writes the number
`engine/calc.py` attaches a tolerance to a literal only when the expression's literal equals a literal found in the claim. `engine/numbers.py` stores a claim literal written with `%` as a fraction (38.33% becomes 0.3833). The proposer wrote `38.33`, so no tolerance attaches and the comparison is exact.

Reproduced offline with `check_compute` on the working-capital figures (84,255 to 116,603, true change 38.3925%):

| Claim text | Expression | Result |
|---|---|---|
| "approximately 38.33%" (false) | `... * 100 == 38.33` | fail (rejected, as gold says) |
| "approximately 38.33%" (false) | `... == 0.3833` | **pass: "compute to 0.4, matching the claimed 38.33%"** |
| "38.39%" (true) | `... * 100 == 38.39` | **fail: a true claim is rejected** |
| "38.39%" (true) | `... == 0.3839` | pass |

- A true claim written the way the proposer usually writes it is rejected. This is a plausible cause of the 25 rejected true claims on the dev file. I have not tested that on the 50 rows.
- Written as a fraction, the "approximately" band (2% of the value) applies, and the false claim is approved. By arithmetic all five false claims sit inside 2%: relative errors are about 0.16%, 0.03%, 0.09%, 0.001% and 0.05%. I ran only the first through the engine.
- So "ProofGraph approved 0 of 5" is not yet a property of the rule. It is a property of one phrasing.

Recommendations:
1. One tolerance rule, independent of phrasing: normalize percent literals so `38.33` and `0.3833` match the claim's `38.33%`.
2. "Approximately" should widen the band by about one unit of the last printed digit, not 2% of the value. A 2% band approves every near-miss FinDVer writes.
3. Add tests for both phrasings of the same claim, true and false, so the verdict cannot depend on them.

## Finding 2 (medium): the plain reason carries no numbers
The verdict reason is "expression does not hold". D26 promises "one plain reason". Recommend: "Computed 38.39%; the claim says 38.33%." The pass message also prints "compute to 0.4" for a 0.3839 result, which is a display rounding bug.

## Finding 3: pick for D26 still stands, with a caveat
Direct Muse's own reasoning computed 38.39% and still wrote "approximately 38.33% as claimed". That is the clearest on-screen failure. The caveat is that the miss is 0.06 points, so the reason in Finding 2 matters more than the verdict word.

## Finding 4: the freight packet is not a baseline-failure case
`examples/packets/ship-export-this-week.direct.json` shows Direct Muse answering `refuted` correctly. It cannot be the "Direct Muse approves a false claim" picture. A freight claim with a subtle trap (a figure that matches only after a unit or period change) could be built and tested live for about $0.01 per claim. Not done.

## Not verified
- Gold labels. The fund-management claim (52.1%) is arithmetically right for the cited cells (928/1782 = 52.08%), and the cited row sits under a revenue schedule, so it may be false for a different reason (wrong line item). I did not check the filing.
- The 25-of-50 explanation in Finding 1.
- Anything about the other 25 Direct Muse `refuted` answers; they were not run.

## Decisions asked of the human
1. Approve a fix to the percent tolerance (Finding 1) as a `fix/` branch with the tests above.
2. Approve the reason wording change (Finding 2).
3. Choose D26 source: this FinDVer claim after the fix, or a freight claim built to fail Direct Muse.
