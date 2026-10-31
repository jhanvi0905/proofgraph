# Council session: evidence tree, and whether we hold up against Direct Muse (31 Oct 2026)

Inputs: `docs/01-product-brief.md` (rubric, theme, bans), `docs/02-scope.md`, `docs/product/journey.md`, `docs/sprint/2026-10-31-final.md`, the percent-tolerance fix on `fix/percent-tolerance`, and the five Direct-Muse-approved FinDVer claim packets in `examples/claim-packets/`. Nothing in this memo is built yet except the tolerance fix.

## 1. Product council

**Alignment with the hackathon (from docs/01, verified 26 Oct).** Theme "Build for Your World". Rubric: Impact 30, Meta AI tooling 25, Demo 25, Technical depth 20. Stage 1 bans basic RAG apps. The brief's own promise is "the proof graph drawn on the documents" and its Meta story is "Citations you can check, down to the pixel". `docs/02-scope.md` lists the proof graph under "Never cut".

**Gap.** The engine already emits a DOT graph (`proofgraph/engine/graph.py`, `ClaimRun.graph`), but the Streamlit app does not draw a tree. The journey doc asks for three link rows with a highlighted quote. A name like ProofGraph makes a judge expect to see a graph. Today they see a verdict and rows.

**Positions**
- Product & Hackathon Strategy Lead: the evidence tree is the demo. It carries Demo 25 and Impact 30 together, because it shows why a verdict can be trusted, which Direct Muse cannot. Lead with the tree on `ship-export-this-week`, not with a score.
- Impact view: the user is someone who signs off on a number. The tree should answer three questions in order: what did you claim, what does the document actually say, where does it break.
- Demo view: one claim, one screen, three seconds to the aha. The tree must fit on one screen with the verdict at the root.

**Proposed evidence tree (one claim)**
```
CLAIM  "support cost is $1,000 a month"                    CONTRADICTED · COMPUTED
├─ ✓ usage 40%           wording · CHECKED        usage_note  "…used by 40%…"
├─ ✗ cost $1,000         compute · COMPUTED       (4,200 − 1,000)… quote: "$4,200 a month"
│     computed $4,200, claim says $1,000   → claim would hold as "$4,200"
└─ ? "this week"         not mentioned            release_note — fetch: a dated release plan
```
- Root: claim and verdict. Children: required links, ordered contradicts, unresolved, supports.
- Each link shows its check type and strength, the substituted arithmetic, and the source quote. Clicking opens the source text with the quote marked.
- A fact node shows its value and how it was grounded (quote, box, blind re-read, SAM count).
- The weakest required link is marked, since the label is defined by it.

**Product asks of engineering**
1. Surface the computed value next to the claimed value in the link result (today: "expression does not hold").
2. Offer the corrected claim when a compute link fails and the grounded facts are sound.
3. Order and colour the tree by weakest link.

## 2. Engineering council

**Staff Applied AI Engineer (creative options, ranked by cost/benefit)**
1. *Corrected claim.* When a compute link fails, return the value the grounded facts compute. Turns "no" into "here is the true number". Small: `check_compute` already evaluates both sides.
2. *Audit the Direct Muse answer.* Direct Muse writes its steps out. Show them beside the tree and mark which cited numbers are grounded. On the working-capital claim its own step computed 38.39% and then wrote "approximately 38.33% as claimed", which the tree makes visible. Needs only the recorded Direct Muse text, no new call.
3. *Disagreement flag.* Where Direct Muse says entailed and ProofGraph does not, mark it as the place to look. Cheap, and it frames ProofGraph as a second opinion rather than a rival.
4. Not recommended before submit: a second proposer vote, or any new model call per tree node.

**Verification & Reasoning Engineer (will it hold up?)** Honest answer: ProofGraph does not beat Direct Muse on FinDVer accuracy, and we should not say so. Evidence:
- Recorded 28 Oct slice: on the first 30 false claims ProofGraph approved 0, Direct Muse 5. On 50 true claims ProofGraph approved 2, rejected 25, declined 23 (right on 2 of 27 answered). A tool that rejects half of true claims is not more accurate; it is stricter.
- The "0 of 5" was partly an accident. Before the fix, the percent tolerance depended on how the proposer wrote the expression (see the findings brief). After the fix, the same five claims run live give 3 CONTRADICTED, 1 UNRESOLVED, 1 SUPPORTED. The supported one is `-404.40%`: the grounded figures compute to −404.3956%, which is −404.40% at two decimals, so the arithmetic is right and the gold "false" comes from something the graph did not check. So on this slice it is 1 versus 5, not 0 versus 5.
- The first 30 gold labels are all false, the dev file's 50 are all true. There is no mixed slice and no confidence interval. n is too small to rank two systems.
- Structural risk: a quote can ground and still be the wrong line item (a revenue row read as net income). Wording links are the defence, and in this run the checker is blind but the proposer chose the quote.

**What does hold up**
- A verdict that shows its work. Direct Muse returns text; ProofGraph returns links a reviewer can reject one by one.
- Asymmetric failure: it declines instead of guessing (23 of 50 true claims declined, not approved).
- Determinism: the engine is code, the same facts give the same verdict.

**Principal Engineer on scope.** The tree is a presentation of data the engine already produces, plus one new field (computed value). It does not need a new dependency: `st.graphviz_chart` plus nested expanders. Next.js (draft D30) is not needed for it.

## 3. Recommendation

1. Do not claim a FinDVer win. Claim the tree, the audit trail, and the abstain behaviour. This matches D26 ("not a FinDVer win") and the brief's "Not claimed" list.
2. Build the evidence tree on the existing Streamlit screen, fed by `ClaimRun`, with the computed value and the corrected claim. Use `ship-export-this-week` as the lead and one FinDVer claim as the second example.
3. For D26, use the working-capital claim only with the audit view (Direct Muse's own arithmetic against its own verdict). Do not use `-404.40%`.
4. Restate the scoreboard sentence after the fix, from a rerun, before it goes in the README or video.

## Decisions for the human
1. Approve building the evidence tree and the computed-value field (AGENTS.md: feature work needs approval and the feature workflow).
2. Approve a rerun of the 30 false claims (about 25 live proposes, under $1) so the "0 versus 5" sentence can be restated. It is a FinDVer run, so it needs a yes against D29's gate.
3. Share, if you have it, the official judging guidelines and the Agents 102 notes. Only the rubric in `docs/01` is in the repo, and I cannot tell whether the judges weight "verifiable" or "agentic" use.
