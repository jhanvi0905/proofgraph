# D11 regression: five claims typed as text, no question key

Run 2026-11-24 against `data/regression_d11.json` (written and hashed before any D11 code, commit `0282a99`).
Each claim's text was read by code (`read_claim`), its policy number found in the text, the for and against reads run on the text alone (no key from `slots.json`, so retrieval saw a different query and the model was called live: 18 calls), and every candidate line confirmed. No line was set aside, so no human judgment helped the answers match. The responses are recorded in `data/recorded/model`; `tests/test_d11.py` replays them with no key.

| Claim | Expected | Typed, no key | Cited |
|---|---|---|---|
| retention (FD960228) | unresolved, documents_disagree | same | same 4 documents and values; one quote wider (below) |
| fb_money | supported, HO 00 03, $200 | same | same page |
| fb_jewelry | supported, HO 00 15, $1,000, endorsement over base, nothing differed | same | same pages |
| fb_firearms | supported, HO 00 15, $2,000, same rule | same | same pages |
| fb_silverware | supported, HO 00 15, $2,500, same rule | same | same pages |

**Answers: 5 of 5. Citations: 4 of 5 identical, 1 differs.** The FD960229 cover note's quote now starts at "POLICY NO: FD960228" (character 79,787) instead of "RETENTION:" (79,877): the same block, the same figure (USD 1,000,000), two lines wider. Recorded as found, not tuned (D11, fix 3).

Documents with nothing found are now reported: ACE and CNA binders on the retention, HO 00 15 on money (it does not restate item 1).
