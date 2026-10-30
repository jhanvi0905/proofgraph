# Value proposition: ProofGraph

Sources: `docs/01-product-brief.md`, section 2 of `docs/sprint/2026-10-29-mvp.md`.

## For anyone who must back a claim with evidence from documents

1. **Who:** People who sign off on a conclusion drawn from documents, where a confident wrong answer costs more than "I can't confirm this": billing and freight reviewers, auditors and finance teams, contract and compliance reviewers, PMs deciding what to ship, and AI agents that need a check before they act.
2. **Why:** Know whether the evidence actually supports the conclusion, whether an AI or a person reached it, without a contrary line disappearing into one confident summary.
3. **What before:** Reread the documents, keep a spreadsheet, or ask a model. Direct Muse answers in one breath, cites a real line, and drops the line that disagrees. A citation shows where a fact came from. It does not show that the conclusion follows from it, or that the arithmetic, scale or meaning is right.
4. **How:** Muse Spark breaks the claim into links, each tied to its source quote. The engine checks every link with the strongest independent method and never with the model that proposed it: executed code for numbers and dates, Muse Spark Open as a blind second reader for wording (one quote, one statement, never the proposer's answer), and SAM 3.1 counting for images. Fixed rules combine the checks, and the weakest link sets the verdict: SUPPORTED, CONTRADICTED or UNRESOLVED.
5. **What after:** The reviewer can point to the line that holds, the line that breaks the claim, and the gap no document fills, each tied to source text and to an executed or blind check. UNRESOLVED says what to fetch next.
6. **Alternatives:** Direct Muse (decision D26) is faster and hides the weak link. A spreadsheet or a manual reread is slow and has no independent check. ProofGraph is the check you run before trusting the answer.

## Lead demo: a PM deciding whether to ship the export button this week

- The 40% usage line supports the claim.
- The $4,200/month support line contradicts the claimed $1,000.
- The release note never mentions "this week", so that link stays UNRESOLVED.

The same path, with no domain-specific branch, runs on SEC filings, contract late fees and freight invoices.

## Value proposition statement

For anyone who must stand behind a conclusion drawn from documents, ProofGraph is a verification workflow that checks every link against its source and trusts only the weakest one. Unlike asking a model directly, it keeps the contrary line visible and never lets the AI that proposed a step decide whether that step passes.

## Reusable statements

- **Marketing:** Citations you can check, down to the pixel.
- **Sales:** See which line holds, which line breaks the claim, and which question no document answers, before you sign off.
- **Onboarding:** Paste one claim and its documents. Read the verdict, then open the link that set it.

**Not claimed here:** fewer wrongly approved claims than a direct model answer. That is the North Star in the brief, and this sprint does not test it.
