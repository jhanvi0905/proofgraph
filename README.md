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

## What the model gets wrong, and what the system does about it

The model reads and proposes; code decides. Each row is a way a language model fails on this task, and the change that makes the failure visible or impossible.

**Observed in runs on this packet**

| Failure | Evidence | Response | Status |
|---|---|---|---|
| **Coerces a phrase into the nearest allowed value.** Given "each claim", atomize returned the basis `any_one_claim`, silently treating two bases as one. | first atomize run | Bases on evidence are read by code from the cited text. `each_claim` and `each_loss` stay distinct, and no equivalence is allowed without a cited span ([D6](DECISIONS.md)). | Evidence side done; the claim side still takes the model's enum ([DEFERRED](DEFERRED.md)) |
| **Copies vocabulary from its prompt examples.** With a family-A example, the slot came back as `corp_reimbursement`, matching the example. After the example changed, the same claim gave `corporate_reimbursement`. | atomize runs before and after `e46957a` | Examples are outside insurance, so they teach the format, not the holdout's words. A test checks that model-facing text holds no packet's literals. | Done |
| **Names the same thing differently from run to run.** The slot drift above means an exact match between a claim and its evidence would silently miss. | same runs | Logged, not yet fixed: needs slot resolution that does not trust the model's spelling. | Open |
| **States an interpretation as if it were a reading.** The passes wrote "Insuring Clause I.B (company reimbursement)" and "the third figure is the company reimbursement retention". The packet says neither. | `pgrun passes`, `bc3a413` | Every route to a slot has a strength: read, derived or judgment. A judgment must write out its reasoning, and the report shows the weakest route each assertion rests on. | Done for routes; pass readings get the same treatment when evidence becomes assertions |

**Designed against before it could happen**

| Failure | Response |
|---|---|
| Arithmetic or unit errors | The model never compares numbers. Code parses amounts to integer minor units and compares integers; `NIL` is not comparable rather than zero. |
| Paraphrased or invented quotes | The quote must occur exactly once in the span; code builds the citation from the span's position, and one verifier checks it against the file. One repair, then the pass fails. So far: 0 rejects in 4 quotes. |
| Citing a passage it was not given | Span ids are an enum in the output schema, and an id outside the input is a hard failure. |
| The attack pass anchoring on the support pass | Separate prompts, and attack never sees support's output (tested). |
| Forcing a claim into the nearest predicate | "No predicate fits" is an outcome, not a repair target. |
| Filling a field it cannot source | A field with no source is "not stated", never filled ([D1](DECISIONS.md)). |
| Picking a winner when documents disagree | The arbiter has no model in it. The answer stays `unresolved` unless a precedence rule, scoped to the slot's policy, fires. Counterfactual tests show each rule can flip a verdict. |
| Run-to-run variation | Current models reject `temperature`. Instead, the prompt template's hash is in the trace and every response is cached, so a rerun replays exactly. |

## Status

Rebuilding from scratch on this branch. What exists so far:

- [`data/SOURCES.md`](data/SOURCES.md): the two document families, with everything recorded read from the files themselves.
- [`data/predicates.json`](data/predicates.json): the closed predicate set, frozen as data.
- [`DECISIONS.md`](DECISIONS.md): numbered design decisions; the arbiter cites them.
- [`DEFERRED.md`](DEFERRED.md): what was found and deliberately left, with reasons.

Dataset: 20 packets. 12 come from family A (Gillette 1996 D&O exhibit, the dev set), and 8 come from family B (ISO HO 00 03 04 91, a holdout run once at the end with no code changes after). n = 20 demonstrates the design. It does not estimate a rate.

The earlier version (an evidence graph over ContractNLI contracts, with an accuracy headline) is in git history up to commit `14264f0`. Why it was retired is in the commit that removed it.
