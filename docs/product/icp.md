# Ideal customer profile: ProofGraph

Source: `docs/product/value-prop.md` only. No survey, interview or usage data exists yet, so this ICP is a hypothesis to test, not a finding.

## ICP for the hackathon story: the PM making a ship call from notes that disagree

- **Who:** A product manager at a software company who owns a ship-or-hold decision this week and holds a usage note, a support-cost note and a release note that do not agree.
- **Behavior:** Decides alone or with a small group, under time pressure. Already asks a model for a quick read, so the habit exists. Adopts whatever fits in one run, with no setup.
- **Functional job:** Know whether the evidence backs "ship the export button this week" before saying yes.
- **Emotional job:** Not get caught out later by a line they never saw.
- **Social job:** Defend the call to leadership by pointing at source text, not "the AI said so".
- **Pains:** Rereading notes takes time they don't have. Direct Muse cites a real line and drops the one that disagrees. A spreadsheet has no independent check. A citation doesn't show that the conclusion follows.
- **Success looks like:** One run shows the line that holds (40% usage), the line that breaks the claim ($4,200/month vs the claimed $1,000), and the gap no document fills ("this week" never appears).
- **Why this one leads:** A judge understands it in seconds, it needs no domain training, and it shows all three verdicts in one run.

## Adjacent ICPs (same engine, no new branch)

1. **Billing and freight reviewers** checking invoices against rate confirmations and delivery proof. Pain: overcharges on charges like detention. Highest stakes per mistake, and the documents mix photos, handwriting and print.
2. **Auditors and contract reviewers** checking report figures and what an agreement allows. Pain: a model cites the right row and still gets the arithmetic, scale or meaning wrong, or treats "not mentioned" as yes.

## Not a fit

- People who want a model to give advice or make the decision for them. ProofGraph checks a claim; it doesn't give advice.
- Questions with no documents behind them, or where a fast confident answer is worth more than "I can't confirm this".

## Go-to-market implication

Lead the demo and README with the PM run, then show the same path on an invoice and a filing to prove the engine isn't PM-specific.
