# ProofGraph

ProofGraph takes a packet of versioned insurance documents (a policy, its endorsements, its binders) and one atomic claim. It returns one of four answers: **supported**, **contradicted**, **documents disagree**, or **not found**. It names the governing document and the precedence rule that made it govern, and it emits a derivation that a checker verifies against the exact characters of the documents. The model reads and proposes. Code decides precedence, does every comparison of numbers, and checks every citation.

The hard case is two documents that disagree. Most document-AI work quietly assumes one canonical document. Here, an endorsement can replace a schedule, a binder can state a different retention than the policy, and a layer can attach mid-term. ProofGraph refuses to pick a winner unless a named rule picks it. If the governing document is not in the packet, the answer is **not found**, and the reason says which document is missing.

The measure is reviewer trust: does the derivation let a reviewer check the answer without rereading the packet? Bucket accuracy is reported, with its denominator, but it is not the headline.

## The four verdicts and the rules that produce them

| Verdict | Produced when |
|---|---|
| supported | the governing evidence states the claim's value |
| contradicted | the governing evidence states a different value |
| documents disagree | two documents bind one slot differently, or cannot be compared, and no precedence rule picks one. Only an explicit `unresolved_conflict` rule produces it, never a fallback. |
| not found | no span addresses the claim, or the instrument that would govern it is not in the packet (`governing_instrument_absent`) |

There are two precedence rules, and each fires only between instruments issued under the policy the slot belongs to ([DECISIONS.md](DECISIONS.md) D3):

1. **Endorsement over base form.** It never fires in family A (the Gillette D&O packet). That packet's only endorsements, Nos. 12 and 13, amend GS-212C, whose base wording is not in the packet, and nothing in it amends any other policy (D5). In family B (ISO HO 00 03) it fires only on packets where a mutation script inserts a superseding endorsement, because the form ships with none. Read that as: rule 1 has no natural test case in either family. It is not evidence that rule 1 has been tested on real documents.
2. **Later effective date over earlier.** This compares instrument effective dates, never coverage periods: overlapping periods have no "later".

When neither rule fires, the arbiter refuses to pick a winner. In family A, the primary corporate-reimbursement retention is stated as $1,000,000 each claim (FD960228 cover note; Item VII in Endorsement 13 gives the bare figure) and $500,000 each loss (Reliance binder). No instrument with authority over FD960228 resolves it, and the bases differ, so the pair is recorded as uncompared and the answer is **documents disagree** (D6).

## Status

Rebuilding from scratch on this branch. What exists so far:

- [`data/SOURCES.md`](data/SOURCES.md): the two document families, with everything recorded read from the files themselves.
- [`data/predicates.json`](data/predicates.json): the closed predicate set, frozen as data.
- [`DECISIONS.md`](DECISIONS.md): numbered design decisions; the arbiter cites them.

Dataset: 20 packets. 12 come from family A (Gillette 1996 D&O exhibit, the dev set), and 8 come from family B (ISO HO 00 03 04 91, a holdout run once at the end with no code changes after). n = 20 demonstrates the design. It does not estimate a rate.

The earlier version (an evidence graph over ContractNLI contracts, with an accuracy headline) is in git history up to commit `14264f0`. Why it was retired is in the commit that removed it.
