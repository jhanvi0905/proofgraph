# ProofGraph

ProofGraph takes a packet of versioned insurance documents (a policy, its endorsements, its binders) and one atomic claim. It returns one of four answers: **supported**, **contradicted**, **documents disagree**, or **not found**. It names the governing document and the precedence rule that made it govern, and it emits a derivation that a checker verifies against the exact characters of the documents. The model reads and proposes. Code decides precedence, does every comparison of numbers, and checks every citation.

The hard case is two documents that disagree. Most document-AI work quietly assumes one canonical document. Here, an endorsement can replace a schedule, a binder can state a different retention than the policy, and a layer can attach mid-term. ProofGraph refuses to pick a winner unless a named rule picks it. If the governing document is not in the packet, the answer is **not found**, and the reason says which document is missing.

The measure is reviewer trust: does the derivation let a reviewer check the answer without rereading the packet? Bucket accuracy is reported, with its denominator, but it is not the headline.

## Status

Rebuilding from scratch on this branch. What exists so far:

- [`data/SOURCES.md`](data/SOURCES.md): the two document families, with everything recorded read from the files themselves.
- [`data/predicates.json`](data/predicates.json): the closed predicate set, frozen as data.

Dataset: 20 packets. 12 come from family A (Gillette 1996 D&O exhibit, the dev set), and 8 come from family B (ISO HO 00 03 04 91, a holdout run once at the end with no code changes after). n = 20 demonstrates the design. It does not estimate a rate.

The earlier version (an evidence graph over ContractNLI contracts, with an accuracy headline) is in git history up to commit `14264f0`. Why it was retired is in the commit that removed it.
