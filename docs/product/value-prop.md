# Value proposition: ProofGraph

Sources: `docs/01-product-brief.md`, section 2 of `docs/sprint/2026-10-29-mvp.md`. One segment for this demo. The product still serves anyone who signs off on conclusions drawn from documents (billing reviewers, auditors, contract reviewers).

## For a PM making a ship decision from notes that disagree

1. **Who:** A product manager under time pressure, holding a usage note, a support-cost note and a release note that do not say the same thing.
2. **Why:** Decide whether to ship the export button this week without a contrary figure disappearing into one confident summary.
3. **What before:** Reread the notes, keep a spreadsheet, or ask a model. Direct Muse answers in one breath, cites a real line, and drops the line that disagrees. A citation shows where a fact came from. It does not show that the conclusion follows from it.
4. **How:** Muse Spark breaks the claim into links, each tied to its source quote. The engine checks every link with the strongest independent method and never with the model that proposed it: executed code for numbers and dates, Muse Spark Open as a blind second reader for wording (it sees one quote and one statement, never the proposer's answer), and SAM 3.1 counting for images. Fixed rules combine the checks, and the weakest link sets the verdict: SUPPORTED, CONTRADICTED or UNRESOLVED.
5. **What after:** After one run the PM can point to three lines:
   - the 40% usage line, which supports the claim;
   - the $4,200/month support line, which contradicts the claimed $1,000;
   - the release note, which never mentions "this week", so that link stays UNRESOLVED and the screen says what to fetch.
   Each line is tied to source text and to an executed or blind check. Before the run they could not see that split.
6. **Alternatives:** Direct Muse (decision D26) is faster and hides the weak link. A spreadsheet is slow and has no check behind it. ProofGraph is the check you run before trusting that answer.

## Value proposition statement

For PMs who must make a call from notes that disagree, ProofGraph is a verification workflow that checks every link in a conclusion against its source and trusts only the weakest one. Unlike asking a model directly, it keeps the contrary line visible and never lets the AI that proposed a step decide whether that step passes.

## Reusable statements

- **Marketing:** Citations you can check, down to the pixel.
- **Sales:** See which line holds, which line breaks the claim, and which question no document answers, before you commit.
- **Onboarding:** Paste one claim and its notes. Read the verdict, then open the link that set it.

## Not claimed here

That ProofGraph wrongly approves fewer claims than a direct model answer. That is the North Star in the brief, and this sprint does not test it.
