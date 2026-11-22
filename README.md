# ProofGraph

> **Read this first: who wrote what.** The claim being checked is written by the author and stored in `data/claims.json` ("The primary corporate reimbursement retention under FD960228 is USD 1,000,000."), together with its canonical slot key. The system does not choose its own question, and the model never names the slot. For the verdict shown by `pgrun verdict`, the three citations and the routes from them to the slot were also labelled by hand (`data/mappings.json`). `pgrun passes` runs the rest automatically: atomize, retrieve, then the support and attack passes. Which text the passes may read is decided in code, from hand-labelled document mappings (`data/document_mappings.json`). Each mapping cites its scope, the narrowest range that supports the attribution: a schedule row, a "primary carrier" section, or the whole document. Only text inside a scope is admitted, and each passage carries its identification and its strength. `pgrun derive` turns the passes' evidence into assertions and gives the verdict from the pipeline alone. In the published run that verdict is the same as the hand-labelled one, **unresolved (documents_disagree)**, but it rests on four assertions instead of three. Support found an asserter the hand labels missed (the FD960229 cover note restating the primary's retention), and attack found Reliance's $500,000, tagged as a judgment identification. Every derived assertion carries a judgment route, because which characters are the value is the model's reading.

ProofGraph takes a packet of versioned insurance documents (a policy, its endorsements, its binders) and one atomic claim. It returns one of four answers: **supported**, **contradicted**, **unresolved** (documents disagree, or agree in a way that was never tested), or **not found**. It names the governing document and the precedence rule that made it govern, and it emits a derivation that a checker verifies against the exact characters of the documents. The model reads and proposes. Code decides precedence, does every comparison of numbers, and checks every citation.

The hard case is two documents that disagree. Most document-AI work quietly assumes one canonical document. Here, an endorsement can replace a schedule, a binder can state a different retention than the policy, and a layer can attach mid-term. ProofGraph refuses to pick a winner unless a named rule picks it. If the governing document is not in the packet, the answer is **not found**, and the reason says which document is missing.

The measure is reviewer trust: does the derivation let a reviewer check the answer without rereading the packet? Bucket accuracy is reported, with its denominator, but it is not the headline.

## What this system demonstrates

Each point is built, and each points at where to check it.

- **Authority between documents, decided by rules rather than the model.** Which instrument governs is a precedence question: an endorsement over its base form, or a later effective date. Both rules are scoped to instruments issued under the policy in question, and where neither fires, the system refuses to pick a winner. Counterfactual tests show each rule flipping a verdict. → [`proofgraph/arbiter.py`](proofgraph/arbiter.py), `pgrun verdict`, [DECISIONS.md](DECISIONS.md) D3, D7
- **Every answer is traceable to exact characters.** A citation is a file hash, a typed locator (raw-file offsets, or a page plus a quote that must occur exactly once), and the expected text. One verifier checks it against the source document, never against this project's own text conversion. → [`proofgraph/checker.py`](proofgraph/checker.py)
- **Identification is part of the record.** Which policy each document describes is recorded with a route, a strength (read, derived or judgment) and a citation. Passages reach the model only from inside a scope mapped to the claim's policy (a schedule row, a section, or a whole document), decided in code, and every piece of evidence carries that strength, so a judgment identification never reads as a read one. → [`data/document_mappings.json`](data/document_mappings.json), `pgrun passes`
- **A semantic model with a closed vocabulary.** The predicates are frozen as data, and slots are canonical keys in a registry. They resolve by exact match only (no aliases, no fuzzy matching), and the model never names one. → [`data/predicates.json`](data/predicates.json), [`data/slots.json`](data/slots.json), [`proofgraph/claims.py`](proofgraph/claims.py)
- **Retrieval owned end to end, and measured.** BM25 plus local embeddings, fused by rank, scoped to admitted documents. Recall@10 is graded automatically on queries labelled before measuring, with design and independent queries reported apart. → [`proofgraph/retrieve.py`](proofgraph/retrieve.py), `pgrun recall`, [`data/retrieval_eval.json`](data/retrieval_eval.json)
- **The model proposes; code decides.** Every model output is checked against the input it was given and the file it cites, and each guard has a counterfactual test showing what gets through without it. → [How the model is used, and how it is kept honest](#how-the-model-is-used-and-how-it-is-kept-honest)
- **A harness you can replay.** One JSON line per stage: the served model, prompt hash, tokens, rejects and verdict. The published run replays from a clean clone with no API key. → `pgrun demo`, `runs/trace.jsonl`
- **A held-out document family, with a frozen domain layer.** Family B (ISO homeowners forms, a different layout and line of business) is reserved for one run. The domain layer (arbiter, comparators, assertions, passes, predicates, slots and family A's labels) is frozen by hash before any family B label is written, and a test fails if any of it changes ([D8](DECISIONS.md)). Parsing may still change, because family B's PDF shaped the column parser twice, so the claim is narrower than "no code change", and testable. → [`data/freeze.json`](data/freeze.json), `tests/test_freeze.py`

## Run it

From a clean clone. You need [uv](https://docs.astral.sh/uv/) and a network connection; no API key.

```bash
git clone https://github.com/jhanvi0905/proofgraph.git && cd proofgraph && git checkout x/proofgraph-v2-arbiter
```

```bash
uv sync
```

```bash
SEC_USER_AGENT="Your Name you@example.com" uv run pgrun demo
```

`pgrun demo` does four things:
1. It fetches the source documents from their public URLs and refuses any whose sha256 differs from the pinned one. No source document is stored in this repository. SEC EDGAR asks automated clients for a contact, hence `SEC_USER_AGENT`.
2. It prints the verdict on the retention slot.
3. It prints retrieval recall@10 on the labelled queries.
4. It replays the support and attack passes from the model responses recorded in `data/recorded/model`, so it gives the same output as the published trace without calling the API.
5. It gives the verdict from the pipeline's own evidence, beside the hand-labelled one.

Set `ANTHROPIC_API_KEY` to make new model calls instead.

The first run downloads the embedding model (`all-MiniLM-L6-v2`, pinned revision, about 90 MB) from Hugging Face, and `uv sync` installs PyTorch. The ISO homeowners form (family B) is not needed for the demo. It is copyrighted, so it is not redistributed: `pgrun fetch` says where to save it and checks its hash.

## The four verdicts and the rules that produce them

| Verdict | Produced when | Code produces it today? (2026-11-22; see the commit that last changed this table) |
|---|---|---|
| supported | carries a reason. `no_conflict`: nothing contradicts the answer, and nothing comparable was left uncompared (one assertion alone is `no_conflict`). `resolved_by_rule`: documents disagree, and a precedence rule picked one; the verdict names the rule and the governing instrument, so a decision never looks like an absence of disagreement. | **At slot level only, and never yet on a real packet.** Tests cover one assertion alone, and a precedence rule picking a governing assertion (synthetic). Comparing against the claim is not built. |
| contradicted | the governing evidence states a different value from the claim | **No.** Nothing compares a slot's verdict with a claim yet. |
| unresolved | no rule picks a winner, and either the numerals differ (`documents_disagree`) or they agree but currency or basis blocked the comparison (`uncompared_agreement`). Only a named rule (`unresolved_conflict`, `untested_agreement`) produces it, never a fallback. ([DECISIONS.md](DECISIONS.md) D7) | **Yes, on one real slot, both ways.** `pgrun verdict` (hand-labelled citations, 3 assertions) and `pgrun derive` (the pipeline's own evidence, 4 assertions) both give `unresolved (documents_disagree)` on `FD960228.corp_reimbursement.retention`. Two of them rest on a **judgment** route. The verdict survives losing the cover note's I.B route. Without Reliance's route it becomes `unresolved (uncompared_agreement)`; both cases are tests. |
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
| **Paraphrases or invents a quote.** | The quote must occur exactly once in the passage; spacing may differ, characters may not. One repair, then the pass fails. | `test_exactly_once_guard_counterfactual`: without the rule, an ambiguous `$0` cites the wrong figure. Live runs: 17 of 17 quotes located, across five runs. |
| **The attack pass anchors on the support pass.** | Separate prompts; attack never sees support's output. | `test_attack_is_blind_to_support` (a marker planted in support's reading is absent from attack's prompt) |
| **Arithmetic or unit errors.** | The model never compares numbers. | `test_numbers.py`: `$10M` equals `USD 10,000,000`; `NIL` vs `$0` is not comparable |
| **Fills a field it cannot source.** | A field with no source is "not stated", never filled ([D1](DECISIONS.md)). | Item VII's assertion has currency and basis `None` (`test_assertions.py`) |
| **Forces a claim into the nearest predicate.** | "No predicate fits" is an outcome, not a repair target. | `test_no_fit_is_an_outcome_not_a_repair` |
| **Picks a winner when documents disagree.** | No model in the arbiter. A precedence rule fires only between instruments issued under the slot's policy. | `test_later_effective_date_flips_the_verdict_when_reliance_is_in_scope`, plus the route-break tests |

### Evaluation hygiene

- **Labels before measuring.** Retrieval queries and their gold quotes were committed (`baf5c04`) before any change was measured against them.
- **Design and independent queries reported apart.** Queries that exposed a miss are marked as not independent evidence for its fix. Field labels improved an independent query (3/6 → 4/6). Plural folding improved only the design queries, and is reported that way.
- **No retrieval tuned to known answers.** A hand-written synonym list was deleted before commit: it was written after reading both document families, so it encoded known answers and holdout vocabulary.
- **A holdout family, with a frozen domain layer.** Family B runs once. The domain layer is byte-identical from the freeze commit to the family B verdict commit (`tests/test_freeze.py`). Only parsing and retrieval mechanics may change.
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

Dataset: 20 packets. 12 come from family A (Gillette 1996 D&O exhibit, the dev set), and 8 come from family B (ISO HO 00 03 04 91, a holdout run once, after the domain-layer freeze ([D8](DECISIONS.md))). n = 20 demonstrates the design. It does not estimate a rate.

The earlier version (an evidence graph over ContractNLI contracts, with an accuracy headline) is in git history up to commit `14264f0`. Why it was retired is in the commit that removed it.
