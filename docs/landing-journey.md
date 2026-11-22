# Landing page journey

A working note for the layout of `app/web/index.html`. Copy and framing are fixed. This note decides only presentation: order, components, and the next step offered at each point.

## Who arrives

Most visitors come from a link (README, a message, a profile), and they read before they act.

| Visitor | Job to be done | What makes them stay |
|---|---|---|
| **CTO** (insurtech, claims, document AI) | "Is this a real problem, and can I trust the output enough to embed it?" | A verdict that can refuse, a citation for every value, honest limits, a component shape |
| **Hiring leader** | "In two minutes, does this person build rigorous AI systems?" | One run that works, visible judgment about where the model stops, a link to decisions and results |
| **AI engineer** | "How is the model constrained, and how would I check it?" | What the model saw, what code decided, replayable runs, the code |

The buyers behind the product (insurers, reinsurers and MGAs; then claims operations; then reinsurance and broking review; as an embedded component) explain why the examples are insurance packets. They are not page copy.

## Journey

| Stage | Touchpoint | Visitor action | Emotion | Pain point (before this pass) | Opportunity |
|---|---|---|---|---|---|
| Arrive | Hero | Reads the headline | Curious, sceptical | None in the copy | Keep it |
| Grasp | Hero sheet | Reads one real result | Interested | Only the case where a rule decides is offered. The refusal, the product's point, needs scrolling. | Offer both examples side by side: a rule decides, and documents disagree |
| Try | "Run an example" | Clicks | Expectant | The button appears only after a fetch, with a long label in brackets | Two plainly named buttons |
| Watch | Run, step 1 | Reads how the documents were read | Confused | Leftovers from the old system: page checklists that never tick, a "Name a person, office…" key, empty threads | A table of what the model was allowed to see: each document, its kind, the policy it describes, how we know, and the passages admitted |
| Watch | Run, step 2 | Reads the claim's result | Neutral | "One value for one slot" (an internal word), and the governing document shown as an id | Name the passes and the boundary; name the governing document |
| Aha | Result page | Checks a boxed line on its page | Convinced | Weakest step already named | Keep it |
| Probe | After the result | Wants the opposite case, or the code | Ready to judge | Dead end: the only way out is "New check" | A next-step row: run the other example, read the code, check another claim |
| Verify | Nav, close | Looks for the repository | Deciding | No code link anywhere on the page | "Code" in the nav, plus a link in the close |
| Act | Form | Picks a packet and a question | Engaged | Duplicate id: the form's mapping table and the run view's map shared `id="map"` | Separate ids |

## Moments

- **Aha:** a rule names the governing document, and the cited line is boxed on its page.
- **Moment of truth:** the same system, on another packet, says the question can't be settled and shows why. Both need to be one click away.
- **Drop-off:** the run view's first screen, if it looks unfinished, and the end of the result, if nothing comes next.

## Priorities

1. Run view step 1 shows what the model was allowed to see, and the dead v1 parts are removed. (Highest: it is the first screen after the click.)
2. The hero offers both examples.
3. A next step after every result.
4. A code link in the nav and in the close.
