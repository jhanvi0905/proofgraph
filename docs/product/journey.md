# Journey map: one ProofGraph session

Sources: `docs/product/icp.md`, section 3 of `docs/sprint/2026-10-29-mvp.md`. Scope is one web-app session, from landing on the screen to opening a source quote. Awareness, signup, marketing and advocacy are out of scope.

**Persona:** the hackathon ICP, a PM deciding whether the export button ships this week. They hold a usage note, a support-cost note and a release note that disagree.
**Job:** see what supports the claim, what contradicts it and what is still open before committing.
**Emotion scale:** 1 = frustrated, 3 = neutral, 5 = confident.

## Steps

| # | Action | Screen element | User question | Emotion | Pain if done badly | UI requirement |
|---|---|---|---|---|---|---|
| 0 | Land on the screen | Empty state | "What do I put in, and is this for me?" | 3, unsure | A freight-only form that suggests the tool isn't for them | Name the job in one line; offer the PM packet and the detention packet as examples to load |
| 1 | State the claim | Claim field | "Will it take my sentence as I wrote it?" | 3 | The field rejects a ship-or-not sentence | Free-text claim, no domain picker |
| 2 | Attach both sides | Evidence items, one per note | "Does the cost note stay in the packet?" | 3, wary | A single summary box merges the notes and the contrary line is lost before the run | One item per note, each with its own label and text, all visible before running |
| 3 | Run | Check button, then stage strip | "Is this actually checking?" | 2–3, impatient | A stamp appears instantly with no engine call | Stages light up in order: propose, ground, check, combine. The verdict appears only after combine |
| 4 | Read the split | Result: verdict, then one row per link | "What held, what broke, what is open?" | 4–5, the aha | Only the word CONTRADICTED is shown and the 40% line disappears | Supporting, contradicting and unresolved links shown together on one screen, each with its reason line and check type |
| 4b | Compare | "Direct Muse said" panel beside the result | "Would a plain model answer have told me this?" | 4, convinced | The comparison is hidden, or it looks like a second verdict | Direct Muse's one-breath answer shown verbatim, clearly labelled as the alternative, never merged into the verdict |
| 5 | Open the source | Source panel with the quote highlighted | "Can I check the citation myself?" | 5, can defend the call | A reason with no source id and no text | Every link row is clickable and opens its note with the exact quote highlighted |

## Moment of value

Step 4. Three rows are on screen at once, and each opens its highlighted quote:
- **SUPPORTS:** the 40% usage line.
- **CONTRADICTS:** the $4,200/month support line against the claimed $1,000, shown with the executed check.
- **UNRESOLVED:** the release note never mentions "this week". The row says what to fetch.

The verdict word alone is not the value. If they only see a stamp, they are back to the model summary they already had.

## States

| State | What the user sees | Requirement |
|---|---|---|
| Empty | Claim field, evidence slots, example packets | No result area until a run starts; nothing looks pre-decided |
| Running | Stage strip: propose → ground → check → combine | Show the current stage; keep the claim and evidence readable while it runs |
| Result | Verdict, label, link rows, "Direct Muse said" panel | All three link outcomes visible without scrolling past the verdict |
| Error | Which stage failed, in plain words | Never show a verdict after a failed stage; keep the inputs so they can rerun |
| Spend cap hit | Run stopped, with the stage it reached | Say it stopped on the cost limit, not that the claim failed; show no verdict and keep the inputs |

## Critical moments

- **Moment of truth:** step 3. A result that appears with no visible checking reads as a stamp, and trust ends there.
- **Churn trigger:** step 4 shows only CONTRADICTED, or the 40% line is gone. That is no better than Direct Muse.
- **Second churn trigger:** step 5 opens a reason with no source text, so the PM can't defend the call.

## Prioritized improvements

1. **Must have:** three link rows visible together, each clickable to its highlighted quote (steps 4–5).
2. **Must have:** visible stages, and no verdict before combine, on error or at the spend cap (step 3, states).
3. **Quick win:** load the PM packet as an example in the empty state, so a judge reaches the aha in one click.
4. **High payoff:** the "Direct Muse said" panel, which shows the alternative dropping the contrary line.

The detention reviewer journey stays: `live_case()` and the existing button keep the detention claim. The PM case is a second packet on the same screen, not a replacement.
