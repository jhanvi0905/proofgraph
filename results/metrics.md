# Evaluation metrics

Computed by `scripts/metrics.py` over every recorded run set. The tables below are that script's output, pasted unedited (the 2026-11-24 state of the repo). Nothing here is a new run: no model call was made.

## Reproduce

```
ANTHROPIC_API_KEY= uv run python scripts/metrics.py
```

Needs no network or key once the pinned local embedding model (all-MiniLM-L6-v2) is in the Hugging Face cache, and `data/raw/` holds the source files (`pgrun fetch`; the ISO forms are not redistributed). Family A, family B and D11 are replayed from `data/recorded/model` (all 51 recorded responses are used; a call with no stored response is skipped and named, never sent). Tax outcomes come from `data/family_tax/run{1,2}_results.json`. Family C and IRS have no machine-readable run record, so their rows are transcribed by hand in `load_family_c_irs()` from `results/family_c.md` and `results/live_irs.md`; check them against those files.

## Run sets and what each label means

- **Dev:** family A (the Gillette retention claim).
- **Holdouts (clean):** family B against its preregistered labels (`B-pre`), the tax holdout against real-world labels (`Tax-real`), Family C original run 1 (`C-orig1`).
- **Not clean:** family B against the D9 expectations (`B-D9`, written after the rules, by their author; 3 packets added after seeing the system), D11 (a regression of family A/B claims typed as text), Family C original run 2 and the two D12 runs (fixes made after seeing Family C output), IRS (not preregistered), and the tax predictions used as labels (`Tax-pred`, the author's guesses at the system's output, not the right answer).
- **Pools.** *Holdouts pooled, clean* = B-pre, Tax-real run 1 and run 2, C-orig1. *All sets pooled* = A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS. Left out of pools because they re-score the same claims: B-pre (B-D9 is in), Tax-pred, C-orig2, D11. The tax claims enter twice, once per run.
- One observation is one (run, claim). Quoted is an answer type, never a refusal.

## Definitions

1. **Bucket accuracy.** Per expected category (supported, contradicted, unresolved split by reason, not_found, quoted, refuse before a verdict, and "any refusal" for Family C's C5, whose label is "not_found or refused"): n, and the share where the system's category equals the expected one. Table 1 is category only; Table 1b also requires the reason to match where the label gives one (for supported, no_conflict vs resolved_by_rule counts as a reason).
2. **Refusal precision and recall.** A system refusal is any output that is not supported, contradicted or quoted: unresolved, not_found, or a refusal before a verdict (claim unreadable, atomize refused, no lines, value_ambiguous, ...). An expected refusal is an expected unresolved, not_found or refuse. TP = refusal where a refusal was expected. FP = refusal where an answer (supported, contradicted or quoted) was expected: **over-refusal**. FN = no refusal where one was expected: **under-refusal**. Precision = TP/(TP+FP). Recall = TP/(TP+FN). A system that refuses everything has recall 100% and precision equal to the share of expected refusals (here 5 of 56 pooled = 9%; 1 of 37 in the clean holdout pool = 3%). A system that never refuses has precision undefined and recall 0. Neither rate means anything without the other.
3. **Precedence accuracy.** Items = those where the label names a governing document or rule, or where a rule fired in the output. Match = the output's governing document equals the label's (family B, D11: also the rule). For the tax holdout the label names no rule and the governing document is derived by the script's author from each claim's `real_world_why` (always the Public Law); only the document is scored. Family C, IRS and the tax predictions carry no governing-document label, so the metric is not scored there.
4. **Derivation validity.** Of the evidence items the model returned (passage id, quote, value pointer), the share the checker accepted as an Assertion or Clause. Two stages are shown: the pass check (id was shown, quote occurs exactly once, citation verifies in its region) and the assertion step (one amount read, or a valid pointer; otherwise `InvalidAssertion`). Counts come from the replayed traces and `PacketRun.assertions/clauses/invalid`. The tax run records keep only the lines shown to the person, so only the second stage is visible there. Family C has no line-level record.
5. **Cost and latency.** Tokens times $4 per 1M input and $20 per 1M output (claude-opus-5-5). Replayed packets use the recorded token counts and count every call as if live; the distinct-response line counts an identical prompt once. For tax and Family C only the totals in the results docs exist. The embedding model is local and free. Latency is only in a live trace's `latency_ms`; replays record 0.

## Caveats

- **n is small everywhere.** Family A is one claim. Family B has 8 (or 11) packets, 4 of which are single-instrument. Tax has 12 claims, run twice, so 12 claim-level facts and not 24. Family C and IRS have 5. No per-set rate here is an estimate; sets with n below about 30 should be read as counts. Pooled rates mix sets with different difficulty and are not a population estimate. Refusal recall rests on 1 to 5 expected refusals in every row.
- **Family A is n=1, not 12.** `data/SOURCES.md` planned 12 Gillette dev packets and the README repeated it; only one labelled claim (`data/claims.json`), three slots and six retrieval queries were built. Both files were corrected when this was found.
- **B-pre is replayed under the current rules.** It scores 5 of 8 on reason (the three endorsed packets were labelled `resolved_by_rule`, which D9 calls a mislabel) and 8 of 8 on category. The as-run table (`results/family_b.md`) was 8 of 8 at `eeb9a2f`.
- **The tax refusals count as over-refusals against real-world labels.** The real answer existed and the system declined, so by the definition they are false refusals, even though each was a named refusal and none was a wrong verdict. Against the preregistered predictions, the same outputs score as under-refusals, because the author predicted `governing_instrument_absent` and it never occurred. Both views are shown, not netted.
- **Wrong verdicts.** None in any set (no supported where contradicted was expected, or the reverse). The tax diagnostic with the S2 line set aside (supported, wrong) is not a scored run and is not in the tables.
- **IRS.** Row 4's refusal reason is not recorded in the results doc (recorded as `unresolved`); row 5 has a line set aside by a person. Not preregistered.
- **Tax derivation validity** is over lines shown to the person, so it excludes pass-level rejects and overstates validity. In family A, B and D11 every proposal passed both stages (31 of 31): the pass check and assertion step have not yet rejected anything in a replay. The rejects that exist are in live runs (tax: value_ambiguous on the strike line; Family C: value_not_in_verified_span on an exclusion line, no count given) and only the tax count is in a record.
- **Latency was not recorded for any claim run.** The tax, Family C and IRS live traces were not committed. The only latencies in the working tree are 6 document-proposal calls in gitignored `data/uploads`, not claim runs, and they are not reproducible from the repo.
- **Cost.** Replay cost counts duplicated prompts that the cache would have saved. The live cost of family B was 20 real calls as run, not 32. Per-claim max cost is only available for replayed sets; tax and Family C give a mean from the run total.
- **Label sources not preregistered:** B-D9, D11 (written from earlier replays), the Family C original run 2, the D12 runs, IRS, and the derived governing-document labels in tax.

## Tables (output of scripts/metrics.py)

## Run sets

| id | set | status | n | note |
|---|---|---|---|---|
| A | Family A, Gillette D&O retention (dev set) | dev | 1 |  |
| B-pre | Family B, preregistered labels (labels.json) | holdout | 8 | replayed under the current (post-D9) rules; the as-run table in results/family_b.md was 8 of 8 |
| B-D9 | Family B, D9 expectations (labels_d9.json) | not clean | 11 | labels written after the rules were built, by the person who built them; 3 packets added after seeing the system |
| D11 | D11 regression, typed claims (regression_d11.json) | not clean | 5 | regression fixture written from earlier replays; re-runs the family A claim and four family B claims as typed text |
| Tax-real-1 | Tax holdout run 1, real-world labels | holdout | 12 | labels = the real answer from the law; governing document label (the Public Law) derived by this script's author from each claim's real_world_why |
| Tax-real-2 | Tax holdout run 2, real-world labels | holdout | 12 | labels = the real answer from the law; governing document label (the Public Law) derived by this script's author from each claim's real_world_why |
| Tax-pred-1 | Tax holdout run 1, preregistered predictions as labels | holdout | 12 | labels are the author's predictions of what the system returns, not the right answer |
| Tax-pred-2 | Tax holdout run 2, preregistered predictions as labels | holdout | 12 | labels are the author's predictions of what the system returns, not the right answer |
| C-orig1 | Family C (Chubb cyber), original run 1, parser as frozen | holdout | 5 | preregistered; one live run per claim |
| C-orig2 | Family C, original run 2 (watermark glyphs dropped), C4 not re-run | not clean | 4 | parser fix made after seeing run 1 |
| C-D12-1 | Family C under D12, run 1 | not clean | 5 | D12 fixes made after seeing Family C output |
| C-D12-2 | Family C under D12, run 2 | not clean | 5 | D12 fixes made after seeing Family C output |
| IRS | IRS live runs (results/live_irs.md) | not clean | 5 | not preregistered; row 5 has one line set aside by a person; the reason for row 4's refusal is not recorded |

### 1. Bucket accuracy by expected category (category match, k/n)

| set | supported | contradicted | unresolved: documents_disagree | unresolved: governing_instrument_absent | unresolved: amounts_not_comparable | not_found | quoted | refuse | refusal_any | all |
|---|---|---|---|---|---|---|---|---|---|---|
| A | - | - | 1/1 | - | - | - | - | - | - | 1/1 (100%) |
| B-pre | 8/8 | - | - | - | - | - | - | - | - | 8/8 (100%) |
| B-D9 | 8/8 | 1/1 | - | 1/1 | - | - | 1/1 | - | - | 11/11 (100%) |
| D11 | 4/4 | - | 1/1 | - | - | - | - | - | - | 5/5 (100%) |
| Tax-real-1 | 3/6 | 2/6 | - | - | - | - | - | - | - | 5/12 (42%) |
| Tax-real-2 | 3/6 | 2/6 | - | - | - | - | - | - | - | 5/12 (42%) |
| Tax-pred-1 | - | - | - | 0/10 | - | - | - | 2/2 | - | 2/12 (17%) |
| Tax-pred-2 | - | - | - | 0/10 | - | - | - | 2/2 | - | 2/12 (17%) |
| C-orig1 | 1/2 | 0/1 | - | - | - | - | 0/1 | - | 1/1 | 2/5 (40%) |
| C-orig2 | 1/2 | 0/1 | - | - | - | - | - | - | 1/1 | 2/4 (50%) |
| C-D12-1 | 2/2 | 1/1 | - | - | - | - | 1/1 | - | 1/1 | 5/5 (100%) |
| C-D12-2 | 2/2 | 1/1 | - | - | - | - | 1/1 | - | 1/1 | 5/5 (100%) |
| IRS | 2/2 | 2/3 | - | - | - | - | - | - | - | 4/5 (80%) |
| Holdouts pooled, clean (B-pre, Tax-real x2 runs, C-orig1) | 15/22 | 4/13 | - | - | - | - | 0/1 | - | 1/1 | 20/37 (54%) |
| All sets pooled (A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS) | 21/28 | 9/19 | 1/1 | 1/1 | - | - | 3/4 | - | 3/3 | 38/56 (68%) |

#### 1b. Same, requiring the reason to match where the label gives one

| set | supported | contradicted | unresolved: documents_disagree | unresolved: governing_instrument_absent | unresolved: amounts_not_comparable | not_found | quoted | refuse | refusal_any | all |
|---|---|---|---|---|---|---|---|---|---|---|
| A | - | - | 1/1 | - | - | - | - | - | - | 1/1 (100%) |
| B-pre | 5/8 | - | - | - | - | - | - | - | - | 5/8 (62%) |
| B-D9 | 8/8 | 1/1 | - | 1/1 | - | - | 1/1 | - | - | 11/11 (100%) |
| D11 | 4/4 | - | 1/1 | - | - | - | - | - | - | 5/5 (100%) |
| Tax-real-1 | 3/6 | 2/6 | - | - | - | - | - | - | - | 5/12 (42%) |
| Tax-real-2 | 3/6 | 2/6 | - | - | - | - | - | - | - | 5/12 (42%) |
| Tax-pred-1 | - | - | - | 0/10 | - | - | - | 2/2 | - | 2/12 (17%) |
| Tax-pred-2 | - | - | - | 0/10 | - | - | - | 2/2 | - | 2/12 (17%) |
| C-orig1 | 1/2 | 0/1 | - | - | - | - | 0/1 | - | 1/1 | 2/5 (40%) |
| C-orig2 | 1/2 | 0/1 | - | - | - | - | - | - | 1/1 | 2/4 (50%) |
| C-D12-1 | 2/2 | 1/1 | - | - | - | - | 1/1 | - | 1/1 | 5/5 (100%) |
| C-D12-2 | 2/2 | 1/1 | - | - | - | - | 1/1 | - | 1/1 | 5/5 (100%) |
| IRS | 2/2 | 2/3 | - | - | - | - | - | - | - | 4/5 (80%) |
| Holdouts pooled, clean (B-pre, Tax-real x2 runs, C-orig1) | 12/22 | 4/13 | - | - | - | - | 0/1 | - | 1/1 | 17/37 (46%) |
| All sets pooled (A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS) | 21/28 | 9/19 | 1/1 | 1/1 | - | - | 3/4 | - | 3/3 | 38/56 (68%) |

### 2. Refusal precision and recall

| set | n | TP | FP | FN | precision | recall | over-refusals (=FP) | under-refusals (=FN) | system refusals | expected refusals |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 1 | 1 | 0 | 0 | 1/1 (100%) | 1/1 (100%) | 0 | 0 | 1 | 1 |
| B-pre | 8 | 0 | 0 | 0 | n/a (no refusals) | n/a (none expected) | 0 | 0 | 0 | 0 |
| B-D9 | 11 | 1 | 0 | 0 | 1/1 (100%) | 1/1 (100%) | 0 | 0 | 1 | 1 |
| D11 | 5 | 1 | 0 | 0 | 1/1 (100%) | 1/1 (100%) | 0 | 0 | 1 | 1 |
| Tax-real-1 | 12 | 0 | 6 | 0 | 0/6 (0%) | n/a (none expected) | 6 | 0 | 6 | 0 |
| Tax-real-2 | 12 | 0 | 5 | 0 | 0/5 (0%) | n/a (none expected) | 5 | 0 | 5 | 0 |
| Tax-pred-1 | 12 | 6 | 0 | 6 | 6/6 (100%) | 6/12 (50%) | 0 | 6 (of which quoted: 1) | 6 | 12 |
| Tax-pred-2 | 12 | 5 | 0 | 7 | 5/5 (100%) | 5/12 (42%) | 0 | 7 (of which quoted: 2) | 5 | 12 |
| C-orig1 | 5 | 1 | 3 | 0 | 1/4 (25%) | 1/1 (100%) | 3 | 0 | 4 | 1 |
| C-orig2 | 4 | 1 | 2 | 0 | 1/3 (33%) | 1/1 (100%) | 2 | 0 | 3 | 1 |
| C-D12-1 | 5 | 1 | 0 | 0 | 1/1 (100%) | 1/1 (100%) | 0 | 0 | 1 | 1 |
| C-D12-2 | 5 | 1 | 0 | 0 | 1/1 (100%) | 1/1 (100%) | 0 | 0 | 1 | 1 |
| IRS | 5 | 0 | 1 | 0 | 0/1 (0%) | n/a (none expected) | 1 | 0 | 1 | 0 |
| Holdouts pooled, clean (B-pre, Tax-real x2 runs, C-orig1) | 37 | 1 | 14 | 0 | 1/15 (7%) | 1/1 (100%) | 14 | 0 | 15 | 1 |
| All sets pooled (A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS) | 56 | 5 | 15 | 0 | 5/20 (25%) | 5/5 (100%) | 15 | 0 | 20 | 5 |

### 3. Precedence accuracy

| set | n items | governing document matches | rule matches (labelled items) | note |
|---|---|---|---|---|
| A | 0 | - | - | - |
| B-pre | 3 | 3/3 (100%) | 3/3 (100%) | rule fired on 3; of those governing (+rule where labelled) match 3/3 |
| B-D9 | 5 | 5/5 (100%) | 5/5 (100%) | rule fired on 5; of those governing (+rule where labelled) match 5/5 |
| D11 | 4 | 4/4 (100%) | 4/4 (100%) | rule fired on 3; of those governing (+rule where labelled) match 3/3 |
| Tax-real-1 | 12 | 5/12 (42%) | no rule labels | rule fired on 5; of those governing (+rule where labelled) match 5/5 |
| Tax-real-2 | 12 | 5/12 (42%) | no rule labels | rule fired on 5; of those governing (+rule where labelled) match 5/5 |
| Tax-pred-1 | no labels | - | - | rule fired in output on 5 |
| Tax-pred-2 | no labels | - | - | rule fired in output on 5 |
| C-orig1 | no labels | - | - | - |
| C-orig2 | no labels | - | - | - |
| C-D12-1 | no labels | - | - | - |
| C-D12-2 | no labels | - | - | - |
| IRS | no labels | - | - | rule fired in output on 4 |
| Holdouts pooled, clean (B-pre, Tax-real x2 runs, C-orig1) | 27 | 13/27 (48%) | 3/3 (100%) | rule fired on 13; of those governing (+rule where labelled) match 13/13 |
| All sets pooled (A, B-D9, Tax-real x2, C-orig1, C-D12 x2, IRS) | 29 | 15/29 (52%) | 5/5 (100%) | rule fired on 15; of those governing (+rule where labelled) match 15/15 |

### 4. Derivation validity

| set | claims with lines / packet runs | evidence items proposed by the model | passed pass-level check | of those: became Assertion/Clause | end to end: accepted / proposed | invalid assertions | repairs |
|---|---|---|---|---|---|---|---|
| A | 1 | 4 | 4/4 (100%) | 4/4 (100%) | 4/4 (100%) | 0 | 0 |
| B | 11 | 16 | 16/16 (100%) | 16/16 (100%) | 16/16 (100%) | 0 | 0 |
| D11 | 5 | 11 | 11/11 (100%) | 11/11 (100%) | 11/11 (100%) | 0 | 0 |
| Tax-real-1 (shown lines only) | 8 | not recorded | not recorded | 18/19 (95%) | not recorded | 1 | not recorded |
| Tax-real-2 (shown lines only) | 8 | not recorded | not recorded | 20/21 (95%) | not recorded | 1 | not recorded |

Reject reasons:

| set | pass-level rejects (reason: count) | assertion-level rejects (reason: count) |
|---|---|---|
| A | none | none |
| B | none | none |
| D11 | none | none |
| Tax-real-1 | not recorded | states several amounts; the reads did not say which is the c: 1 |
| Tax-real-2 | not recorded | states several amounts; the reads did not say which is the c: 1 |

### 5. Cost and latency

| set (replayed) | packets | model calls | calls per packet mean / max | input tokens | output tokens | cost if every call were live | mean per packet | max per packet |
|---|---|---|---|---|---|---|---|---|
| A | 1 | 3 | 3.0 / 3 | 5,066 | 886 | $0.038 | $0.038 | $0.038 |
| B | 11 | 45 | 4.1 / 5 | 64,452 | 4,219 | $0.342 | $0.031 | $0.043 |
| D11 | 5 | 23 | 4.6 / 5 | 33,015 | 2,430 | $0.181 | $0.036 | $0.039 |

Distinct model responses used by all replays: 51 ({'recorded': 51}); 70,638 input and 5,584 output tokens = $0.39. Total calls made across replays: 71.

| live run (transcribed from the results doc) | calls | input tokens | output tokens | cost at $4/$20 | per call | per unit (mean; max not recorded) |
|---|---|---|---|---|---|---|
| B as run (results/family_b.md) | 20 real of 32 | 27,643 | 1,620 | $0.14 | $0.007 | $0.018 (8 packets) |
| B D9 packets (results/family_b.md) | 10 real calls | 13,901 | 1,230 | $0.08 | $0.008 | $0.027 (3 packets) |
| Tax, everything: 2 runs + 7 proposals + 1 trial (results/family_tax.md) | 119 live calls | 462,117 | 38,223 | $2.61 | $0.022 | $2.613 (1 total) |
| Tax run 1 (cost stated, tokens not) | 53 calls | not given | not given | $1.15 | $0.022 | $0.096 (12 claims (2 made no model call)) |
| Tax run 2 (cost stated, tokens not) | 54 calls | not given | not given | $1.19 | $0.022 | $0.099 (12 claims (2 made no model call)) |
| Family C, 3 live runs under D12 (results/family_c.md) | 47 live calls | 122,068 | 9,706 | $0.68 | $0.015 | $0.045 (15 claim-runs) |

Latency: replays record 0 ms (no call is made). The repo holds no latency for any claim run (tax, Family C, IRS and family B live traces were not committed). Local, uncommitted, gitignored data/uploads/*/propose.trace.jsonl holds 6 live document-proposal calls (not claim runs): min 2.8 s, median 3.1 s, max 6.7 s.

## Mismatches (expected vs got, reason-strict)

| set | item | expected | exp reason | got | got reason |
|---|---|---|---|---|---|
| B-pre | B-jewelry-endorsed | supported | resolved_by_rule | supported | no_conflict |
| B-pre | B-firearms-endorsed | supported | resolved_by_rule | supported | no_conflict |
| B-pre | B-silverware-endorsed | supported | resolved_by_rule | supported | no_conflict |
| Tax-real-1 | S2 | contradicted | None | refuse | value_ambiguous |
| Tax-real-1 | K2 | contradicted | None | refuse | atomize_refused |
| Tax-real-1 | K4 | supported | None | refuse | more_than_one_value |
| Tax-real-1 | B1 | supported | None | refuse | atomize_refused |
| Tax-real-1 | B2 | contradicted | None | quoted | None |
| Tax-real-1 | B3 | supported | None | refuse | dates_not_supported |
| Tax-real-1 | B4 | contradicted | None | refuse | no_lines |
| Tax-real-2 | S2 | contradicted | None | refuse | value_ambiguous |
| Tax-real-2 | K2 | contradicted | None | refuse | atomize_refused |
| Tax-real-2 | K4 | supported | None | refuse | more_than_one_value |
| Tax-real-2 | B1 | supported | None | refuse | atomize_refused |
| Tax-real-2 | B2 | contradicted | None | quoted | None |
| Tax-real-2 | B3 | supported | None | refuse | dates_not_supported |
| Tax-real-2 | B4 | contradicted | None | quoted | None |
| Tax-pred-1 | S1 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-1 | S2 | unresolved | governing_instrument_absent | refuse | value_ambiguous |
| Tax-pred-1 | S3 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-1 | S4 | unresolved | governing_instrument_absent | contradicted | None |
| Tax-pred-1 | K1 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-1 | K2 | unresolved | governing_instrument_absent | refuse | atomize_refused |
| Tax-pred-1 | K3 | unresolved | governing_instrument_absent | contradicted | None |
| Tax-pred-1 | B1 | unresolved | governing_instrument_absent | refuse | atomize_refused |
| Tax-pred-1 | B2 | unresolved | governing_instrument_absent | quoted | None |
| Tax-pred-1 | B4 | unresolved | governing_instrument_absent | refuse | no_lines |
| Tax-pred-2 | S1 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-2 | S2 | unresolved | governing_instrument_absent | refuse | value_ambiguous |
| Tax-pred-2 | S3 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-2 | S4 | unresolved | governing_instrument_absent | contradicted | None |
| Tax-pred-2 | K1 | unresolved | governing_instrument_absent | supported | None |
| Tax-pred-2 | K2 | unresolved | governing_instrument_absent | refuse | atomize_refused |
| Tax-pred-2 | K3 | unresolved | governing_instrument_absent | contradicted | None |
| Tax-pred-2 | B1 | unresolved | governing_instrument_absent | refuse | atomize_refused |
| Tax-pred-2 | B2 | unresolved | governing_instrument_absent | quoted | None |
| Tax-pred-2 | B4 | unresolved | governing_instrument_absent | quoted | None |
| C-orig1 | C1 | supported | None | refuse | no_lines |
| C-orig1 | C2 | contradicted | None | refuse | no_lines |
| C-orig1 | C4 | quoted | None | refuse | atomize_refused |
| C-orig2 | C2 | contradicted | None | refuse | no_lines |
| C-orig2 | C3 | supported | None | refuse | no_lines |
| IRS | 401k $23,000, all lines confirmed | contradicted | None | unresolved | None |
