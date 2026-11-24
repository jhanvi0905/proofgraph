# Family tax: US federal tax documents, domain layer unchanged

Preregistered in `data/family_tax/preregistration.json` (commit `9a876e6`) before any run. Three packets, seven US government PDFs (2023 US Code sections, an IRS notice, page extracts of Pub. L. 119-21; URLs, page ranges and hashes in the preregistration). The packets went through the product path only: upload, propose, a person confirms each document, 12 typed claims, every candidate line confirmed (nothing set aside), decide. Two runs, each with an empty response cache, so every model call was live. No file in `proofgraph/`, `app/` or `data/` changed apart from the new `data/family_tax/`. Run records: `data/family_tax/run1_results.json`, `run2_results.json`, `uploads_confirmed.json`; harness in `data/family_tax/harness/`.

Scoring against the real world: **right** means the verdict is the real answer. **No answer** means refused, unresolved, no lines or quoted (quoted is never an answer). **Wrong** means the opposite verdict. Claims that name no year are graded as of 2026.

## T-SALT: 26 U.S.C. 164(b)(6), policy label "IRC 164(b)(6)"
USC 2023 §164 (policy_form): $10,000 ($5,000 MFS), 2018-2025. Pub. L. 119-21 §70120, extract pp. 99-100 (endorsement): $40,000 (2025), $40,400 (2026), +1%/yr to 2029, $10,000 after 2029, floor $10,000.

| Claim | Real world | Predicted | Run 1 | Run 2 | Why |
|---|---|---|---|---|---|
| S1 phasedown floor $10,000 | supported | unresolved (governing_instrument_absent) | **supported** | **supported** | Act p.1 "(iii) LIMITATION ON REDUCTION ... less than $10,000", one line from the Act; endorsement_over_base over the Code's cap line (p.2). Right answer, but the rule overrode a line about the cap, not about the floor. |
| S2 cap $10,000 | contradicted | unresolved (governing_instrument_absent) | refused (value_ambiguous) | refused (value_ambiguous) | The Act's strike line "(2) by striking ''$10,000 ($5,000 ...)''" came back twice: once with a $10,000 pointer, once with no pointer. Preregistered rule: no pick on a strike line. **Diagnostic (not scored), with that one line set aside: supported, which is wrong.** The struck figure was read as the Act's amount. |
| S3 2026 cap $40,400 | supported | unresolved (governing_instrument_absent) | **supported** | **supported** | Act p.1 "(ii) ... calendar year 2026, $40,400," was the only line from the Act; endorsement_over_base. |
| S4 2026 cap $40,000 | contradicted | unresolved (governing_instrument_absent) | **contradicted** | **contradicted** | The same line (against side); governing $40,400. Support did not return the 2025 "$40,000" line. |

## T-1099K: 26 U.S.C. 6050W(e), policy label "IRC 6050W(e)"
USC 2023 §6050W (policy_form): $600. IRS Notice 2024-85 (correspondence): $5,000 (2024), $2,500 (2025), $600 (2026 on). Pub. L. 119-21 §70432, extract p.173 (endorsement): $20,000 and 200 transactions, "as if included in section 9674" of ARPA.

| Claim | Real world | Predicted | Run 1 | Run 2 | Why |
|---|---|---|---|---|---|
| K1 threshold $20,000 | supported | unresolved (governing_instrument_absent) | **supported** | **supported** | Act p.1 "exceeds $20,000"; the Code's "$600" (p.3) and the Notice's $600 and $20,000 background lines (pp.3, 6) are bases; endorsement_over_base. |
| K2 threshold $600 | contradicted | unresolved (governing_instrument_absent) | refused | refused | Atomize returned no atoms: "not about an insurance instrument's coverage ... no predicate in the closed set fits." |
| K3 2025 threshold $2,500 | contradicted | unresolved (governing_instrument_absent) | **contradicted** | **contradicted** | Notice p.7 "For calendar year 2025 ... exceeds $2,500" against the Act's $20,000; the rule put the statute over the notice only because the notice was confirmed as a non-endorsement. |
| K4 as K1, typed "Under IRC 6050W(e)" | supported | refused (more_than_one_value) | refused (more_than_one_value) | refused (more_than_one_value) | "IRC 6050" was read as a second amount. No model call. |

## T-BONUS: 26 U.S.C. 168(k), policy label "IRC 168(k)"
USC 2023 §168, extract pp.16-17 (policy_form): 40% (2025), 20% (2026). Pub. L. 119-21 §70301, extract pp.118-120 (endorsement): 100%, property acquired after January 19, 2025.

| Claim | Real world | Predicted | Run 1 | Run 2 | Why |
|---|---|---|---|---|---|
| B1 100 percent | supported | unresolved (governing_instrument_absent) | refused | refused | Atomize: "a tax code provision ..., not an insurance instrument". |
| B2 40 percent | contradicted | unresolved (governing_instrument_absent) | quoted (Act p.2) | quoted (Act p.2) | Read as wording (no currency). Quoted the transitional election "substituting '40 percent' for '100 percent'". No verdict. |
| B3 acquired after Jan 19, 2025: 100 percent | supported | refused (dates_not_supported) | refused (dates_not_supported) | refused (dates_not_supported) | A printed date and no money amount. No model call. |
| B4 2026: 20 percent | contradicted | unresolved (governing_instrument_absent) | no lines | quoted (Code p.2) | Run 2 quoted the superseded Code as the controlling clause ("... before January 1, 2027, 40 percent", the long-production schedule), because the Act returned no clause. Not a verdict, but the quote shown is old law. |

## Score

**Against the real world, each run: 5 right (S1, S3, S4, K1, K3), 0 wrong, 7 no answer.** Both runs gave the same verdict on all 12 claims. B4 differed only in form: no lines in run 1, quoted in run 2. One wrong answer was one set-aside away: S2's diagnostic decide returned supported for $10,000.

**Against predictions: 2 of 12 claim predictions matched (K4, B3), in both runs.** The other ten all predicted `governing_instrument_absent`, which never occurred. Of the named predictions:
- **Wrong:** T-A and T-D. T-D said no year claim would be answered right; S3, S4 and K3 were.
- **Not exercised:** T-R. The Act yielded one line every time it asserted, so rule 1 always fired.
- **Untestable:** T-E. The proposer quoted no effective-date line on any Act.
- **Held:** T-P, T-V and T-K (the proposer left the kind blank on all seven files). T-W held on scored results only. T-0 held.

## What broke, exactly

1. **The proposer reads every upload as an insurance document** (b). `proofgraph/propose.py`, `SYSTEM` ("one insurance document"):
   - For the two Act extracts with page 1 mid-statute (pp.118-120, p.173) it quoted nothing. Both came back unplaceable, and the person had to type a row through `/api/upload/{id}/rows`.
   - On all seven files it gave no kind, no amends line and, for the Acts, no effective-date line. The two Act dates in the record were typed at confirmation.
   - So no amends route exists, and the D10 missing-document check never ran. Prediction T-A (a form-number mismatch) assumed the proposer would quote the amends line; it never did.
2. **Atomize refuses tax claims as off-domain, intermittently** (b). `proofgraph/atomize.py`, `SYSTEM` ("a claim about insurance documents"). It returned `no_predicate_fits` for K2 and B1 in both runs, while near-identical claims (K1, K3) passed. The server then shows "couldn't be turned into one checkable statement" (`app/server.py`, `claim_gather`).
3. **A section number reads as an amount** (b). `proofgraph/grouping.py`, `read_claim` / `_AMOUNT_RE` with `numbers.CLAIM_CURRENCY_TOKEN`: three capitals before a digit is a currency, so "IRC 6050" is refused as a second value (K4).
4. **Amending text is read as stating the amount** (d). Support quoted "by striking ''$10,000 ...''" with a $10,000 pointer. `assertions.assert_from_evidence` reads it as the Act stating $10,000, and nothing marks struck text. Under the endorsement rule that is exactly the figure the Act removed (S2 diagnostic: wrong).
5. **Percentages are not amounts** (d). `grouping._AMOUNT_RE` needs a currency mark, digit grouping or a scale word, so every bonus-depreciation claim is wording: quoted or refused, never compared (B1, B2, B4).
6. **The as-of-date break** (a), smaller than expected:
   - B3 was refused at the claim reader (`read_claim`, `dates_not_supported`).
   - S3, S4 and K3 were answered right, but code never read the year. The reads happened to return only the line for the claim's year from the Act; the 2025 / after-2029 lines were not returned. Had they been, `arbiter._endorsement_over_base` would not fire ("more than one in-scope endorsement"), and `_later_effective_date` ties lines from one document, giving documents_disagree (T-R).
   - Rightness on year claims therefore rests on what the model chose to quote, not on any rule.
   - B4 (run 2) shows the same gap: with no clause from the Act, the superseded Code line was quoted as controlling.
7. **Kinds** (b). There is no kind for a statute, an Act or IRS guidance. The confirmer mapped them to policy_form / endorsement / correspondence (`schema.InstrumentType`), and that mapping, not the documents, made the statute beat the notice in K3.

No parsing/layout break (c) was seen: every quote verified, including two-column Code pages.

## What held

- **Never a wrong verdict** in 24 scored decisions. Every no-answer was named:
  - value_ambiguous;
  - more_than_one_value;
  - dates_not_supported;
  - an atomize refusal;
  - quoted, not checked.
- **Every quote verified against the PDF**, with its page. Both runs gave the same verdict on all 12 claims.
- **The model never picked the winner.** All five right answers came from the one rule, endorsement over base, applied by code.
- **D13 item 2 held as designed.** The multi-figure strike line was not resolved by code; it stopped the decide and asked the person.

## Judgments made as the confirming person

- **Kinds:** chose a kind for all seven files; the proposer proposed none.
- **Policy labels:** typed all three (for example "IRC 164(b)(6)"); how = judgment throughout.
- **Typed rows:** typed the rows for the two unplaceable Act extracts, each with one printed line (the section heading). This was not in the preregistration; it is the app's documented fallback.
- **Effective dates:** typed for the SALT and bonus Acts (2024-12-31, 2025-01-19) with reasons, recorded `typed_at_confirmation`. They never decided anything, because rule 1 fired first.
- **Figure picks:** none. The one multi-figure line was a strike line, which gets no pick by rule. The diagnostic set-aside was mine and is not scored.

## Cost

119 live calls, 462,117 input and 38,223 output tokens: **$2.61** at $4 / $20 per million (Opus 5.5). That is:
- proposals: 7 calls, $0.16;
- a one-claim trial run before run 1: $0.11;
- run 1: 53 calls, $1.15;
- run 2: 54 calls, $1.19.

To rerun: set `PROOFGRAPH_TAX_WORKDIR` to a scratch folder holding the downloaded PDFs (URLs and hashes in the preregistration), then run the scripts in `data/family_tax/harness/`.
