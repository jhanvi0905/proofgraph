# ProofGraph

ProofGraph takes a packet of versioned insurance documents (a policy, its endorsements, its binders) and one atomic claim. It returns one of four answers: **supported**, **contradicted**, **unresolved** (documents disagree, or agree in a way that was never tested), or **not found**. It names the governing document and the precedence rule that made it govern, and it emits a derivation that a checker verifies against the exact characters of the documents. The model reads and proposes. Code decides precedence, does every comparison of numbers, and checks every citation.

The hard case is two documents that disagree. Most document-AI work quietly assumes one canonical document. Here, an endorsement can replace a schedule, a binder can state a different retention than the policy, and a layer can attach mid-term. ProofGraph refuses to pick a winner unless a named rule picks it. If the governing document is not in the packet, the answer is **not found**, and the reason says which document is missing.

The measure is reviewer trust: does the derivation let a reviewer check the answer without rereading the packet? Bucket accuracy is reported, with its denominator, but it is not the headline.

## The four verdicts and the rules that produce them

| Verdict | Produced when | Code produces it today? (2026-11-22; see the commit that last changed this table) |
|---|---|---|
| supported | nothing contradicts the answer, and nothing that could have been compared was left uncompared. One assertion with no pairs is supported. | **At slot level only, and never yet on a real packet.** Tests cover one assertion alone, and a precedence rule picking a governing assertion (synthetic). Comparing against the claim is not built. |
| contradicted | the governing evidence states a different value from the claim | **No.** Nothing compares a slot's verdict with a claim yet. |
| unresolved | no rule picks a winner, and either the numerals differ (`documents_disagree`) or they agree but currency or basis blocked the comparison (`uncompared_agreement`). Only a named rule (`unresolved_conflict`, `untested_agreement`) produces it, never a fallback. ([DECISIONS.md](DECISIONS.md) D7) | **Yes, on one real slot.** `pgrun verdict` on `FD960228.corp_reimbursement.retention` gives `unresolved (documents_disagree)`. Its three assertions come from hand-labelled citations and routes in `data/mappings.json`, not yet from retrieval or model passes. Two of them rest on a **judgment** route. The verdict survives losing the cover note's I.B route. Without Reliance's route it becomes `unresolved (uncompared_agreement)`; both cases are tests. |
| not found | no assertion addresses the slot, or the instrument that would govern it is not in the packet (`governing_instrument_absent`) | **Partly.** An empty slot returns `not_found (no_addressing_span)` (test). `governing_instrument_absent` is not built. |

There are two precedence rules, and each fires only between instruments issued under the policy the slot belongs to ([DECISIONS.md](DECISIONS.md) D3):

1. **Endorsement over base form.** It never fires in family A (the Gillette D&O packet). That packet's only endorsements, Nos. 12 and 13, amend GS-212C, whose base wording is not in the packet, and nothing in it amends any other policy (D5). In family B (ISO HO 00 03) it fires only on packets where a mutation script inserts a superseding endorsement, because the form ships with none. Read that as: rule 1 has no natural test case in either family. It is not evidence that rule 1 has been tested on real documents.
2. **Later effective date over earlier.** This compares instrument effective dates, never coverage periods: overlapping periods have no "later".

When neither rule fires, the arbiter refuses to pick a winner. In family A, the primary corporate-reimbursement retention is stated as $1,000,000 each claim (FD960228 cover note; Item VII in Endorsement 13 gives the bare figure) and $500,000 each loss (Reliance binder). No instrument with authority over FD960228 resolves it, and the bases differ, so the pair is recorded as uncompared and the answer is **unresolved (documents_disagree)** (D6, D7). Run `uv run pgrun verdict` to see the three assertions, the three pairs (none comparable), both rules not firing, and the verdict. Pull the decision from the trace with:

```bash
grep '"stage": "arbiter"' runs/trace.jsonl | grep -o '"rejects": \[[^]]*\]\|"verdict": "[a-z_]*"'
```

## How the model is used, and how it is kept honest

### Who decides what

The model reads and proposes. Code checks everything the model returns, and code decides.

| Step | The model | Code |
|---|---|---|
| Atomise | splits the claim into atoms in a closed predicate set | validates every field; rejects unresolved references, conjunctions, unparseable amounts; one repair, then fail |
| Retrieve | nothing | BM25 plus local embeddings, fused by rank; picks the ten passages the model may see |
| Support / attack | for each passage it picks: an id, a one-line reading, a verbatim quote | the id must be one it was shown; the quote must occur exactly once in that passage; code builds the citation from the passage's position and verifies it against the file |
| Numbers | nothing | parses amounts to integer minor units; compares integers; `NIL` is not comparable |
| Verdict | nothing | precedence rules scoped to the slot's policy; `unresolved` unless a rule picks a winner |

### Failure modes, and what stops each one

Each row has a test, and the counterfactual tests show what gets through when the guard is removed.

| Failure mode | Guard | Evidence |
|---|---|---|
| **Forces a phrase into the nearest allowed value.** Seen in 1 of 2 atomize runs: given "each claim" when that value was not allowed, it returned `any_one_claim`, treating two bases as one. | Bases are kept as written (`each_claim`, `each_loss`); on evidence, code reads the basis from the cited text, and no equivalence is allowed without a cited span ([D6](DECISIONS.md)). | `test_numbers.py`, `test_arbiter.py` |
| **Copies vocabulary from prompt examples.** In 2 of 2 atomize runs the slot name followed the prompt's example. | Examples are outside insurance, so they teach the format, not the holdout's words. A test checks model-facing text for any packet's literals. | `test_no_family_literals.py` (shown to catch the old prompt) |
| **Cites a passage it was not shown.** | Span ids are an enum in the output schema; an id outside the input is a hard failure, with no repair. | `test_span_id_guard_counterfactual`: without the guard, the citation passes the file verifier, because the passage is real |
| **Paraphrases or invents a quote.** | The quote must occur exactly once in the passage; spacing may differ, characters may not. One repair, then the pass fails. | `test_exactly_once_guard_counterfactual`: without the rule, an ambiguous `$0` cites the wrong figure. Live runs: 4 of 4 quotes located. |
| **The attack pass anchors on the support pass.** | Separate prompts; attack never sees support's output. | `test_attack_is_blind_to_support` (a marker planted in support's reading is absent from attack's prompt) |
| **Arithmetic or unit errors.** | The model never compares numbers. | `test_numbers.py`: `$10M` equals `USD 10,000,000`; `NIL` vs `$0` is not comparable |
| **Fills a field it cannot source.** | A field with no source is "not stated", never filled ([D1](DECISIONS.md)). | Item VII's assertion has currency and basis `None` (`test_assertions.py`) |
| **Forces a claim into the nearest predicate.** | "No predicate fits" is an outcome, not a repair target. | `test_no_fit_is_an_outcome_not_a_repair` |
| **Picks a winner when documents disagree.** | No model in the arbiter. A precedence rule fires only between instruments issued under the slot's policy. | `test_later_effective_date_flips_the_verdict_when_reliance_is_in_scope`, plus the route-break tests |

### Evaluation hygiene

- **Labels before measuring.** Retrieval queries and their gold quotes were committed (`baf5c04`) before any change was measured against them.
- **Design and independent queries reported apart.** Queries that exposed a miss are marked as not independent evidence for its fix. Field labels improved an independent query (3/6 → 4/6). Plural folding improved only the design queries, and is reported that way.
- **No retrieval tuned to known answers.** A hand-written synonym list was deleted before commit: it was written after reading both document families, so it encoded known answers and holdout vocabulary.
- **A holdout family.** Family B (ISO HO 00 03) is reserved, to run once with no code change.
- **Counterfactuals for rules and guards.** Each precedence rule and each model guard has a test showing the outcome changes without it.

### Reproducibility and cost

- Current models reject `temperature`. The trace records the prompt template's hash and the model that actually served each call, and every response is cached on disk, so a rerun replays exactly.
- Cost comes from the trace's token counts, not an estimate. The support and attack passes on the retention atom cost about $0.03 together.

## Status

Rebuilding from scratch on this branch. What exists so far:

- [`data/SOURCES.md`](data/SOURCES.md): the two document families, with everything recorded read from the files themselves.
- [`data/predicates.json`](data/predicates.json): the closed predicate set, frozen as data.
- [`DECISIONS.md`](DECISIONS.md): numbered design decisions; the arbiter cites them.
- [`DEFERRED.md`](DEFERRED.md): what was found and deliberately left, with reasons.

Dataset: 20 packets. 12 come from family A (Gillette 1996 D&O exhibit, the dev set), and 8 come from family B (ISO HO 00 03 04 91, a holdout run once at the end with no code changes after). n = 20 demonstrates the design. It does not estimate a rate.

The earlier version (an evidence graph over ContractNLI contracts, with an accuracy headline) is in git history up to commit `14264f0`. Why it was retired is in the commit that removed it.
