# Pre-registration: unseen run of quote bounds, cid guard and evidence set

Frozen 2 Nov 2026 before any run. Code under test: branch `test/integration-arms` (merge of `feat/evidence-set` @14788ae and `feat/quote-bounds` @72d2918). No prompt, threshold or code edit after the first run of this protocol; a failed bar means the flags stay off and unmerged.

## Sample (selection rule independent of outcomes)
Unseen = the suite cases not in `examples/suite/manifest.json`. A first seeded draw (seed 20261102) came out mostly scanned images, which cannot test text-PDF behaviour (approximate boxes cannot turn a part red), so it was discarded BEFORE any run. Replacement rule: every unseen case whose Evidence Packet is entirely `.pdf` files. Cases: Test Case 1, 2, 5, 6, 7 (Company archive), 13, 15 (Braddock record), 39, 42 (ContractNLI) = 9 cases. Source groups overlap (Company x5 share one archive, Braddock x2 share one record); report per group. Answer keys (`Solutions/`, `_Evaluation/`, annotation files, `CASE_PRIORITIES.md` Why column) are not used as input or for scoring. No gold comparison, no accuracy claim.

## Arms (same claims, same files, same cache dir)
- A: all flags off (today's path).
- B: PROOFGRAPH_QUOTE_BOUNDS=1 and PROOFGRAPH_CID_GUARD=1.
- C: B plus PROOFGRAPH_EVIDENCE_SET=1 (with retry and single-card fallback).
Run order A, B, C. Hard spend stop: ledger total at start + $1.10 (SPEND_LIMIT_USD). No re-runs. If the cap stops a run, remaining arms are INCONCLUSIVE.

## Bar
Q1 (B vs A, quote hygiene):
- every part with one card in both arms keeps its status, or each change is listed with its cause;
- for cards whose quote changed, the checker answer moves toward not_mentioned on at most 1 in 5 changed pairs (needs at least 5 changed pairs, else INCONCLUSIVE for this item);
- zero new errors or timeouts; every rejected quote is listed.
Q2 (C vs B, evidence set):
- parts that still have one card keep their status, or each change is listed;
- at least 5 parts with 2 or more cards, else INCONCLUSIVE;
- Opus panel read: at most 1 in 6 of the added cards and of the status or conflict events read as padding, fragment or overreach;
- zero parts in error after retry; report how many fell back to the single card;
- median cost per review at most 2x arm A.
Decision: B adoptable as an optional flag only if Q1 passes; C only if Q1 and Q2 both pass and the human says yes. Anything else: stays off and unmerged. Report per source group with n; no accuracy or win claim; the recorded demo path stays single-card.

## Result (run once, 2 Nov 2026; kept here because the throwaway branch that held this file was deleted)
Spend about $0.42 of the $1.10 stop. Neither flag met the bar, so both stay off and unmerged (`feat/quote-bounds`, `feat/evidence-set` are parked).
- Arm B (quote bounds + cid guard, single card): the checker moved toward not_mentioned on 1 of 6 changed pairs (limit 1 in 5), so Q1 passed by the letter, but the short-quote rejection dropped table-row evidence on two of nine cases (one lost a correct contradiction) and the widened quote lost one supported part. Not recommended.
- Arm C (arm B + evidence set): only 4 parts had 2 or more cards (bar needed 5), so Q2 was INCONCLUSIVE; no errors after retry. Not adoptable under the frozen rule.
- No accuracy claim. The sample was later used again only as the unseen pool for the evidence map (see 2026-11-02-evidence-map-unseen-prereg.md).
