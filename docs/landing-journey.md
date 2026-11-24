# Landing page journey

Working note for `app/web/index.html` and the result screen, set from the one-page spec (23 Nov). It decides order, components and the next step at each point. Copy comes from the spec.

## Readers, and what each needs within two minutes

| Reader | Question in their head | What has to be on screen |
|---|---|---|
| CTO | Can I trust the output, and does it fit into a claims workflow? | The answer and its evidence on one screen; what the model does versus what code does; what it refuses |
| Hiring manager | Does this person build rigorous AI systems that know their limits? | A real run that works, a refusal that works, and a link to the code, the decisions and the results |
| Non-technical reader | What does it do, and for whom? | One sentence on what it is, three plain answers, who it saves time for |
| Legal or claims reader | Which document governs, and could I defend this file? | Governing document, clause, page and quote; the rule that decided; "not legal advice" |

Users in the product (the spec's, not page copy): the adjuster or coverage analyst who answers, and the claims manager who signs off.

## Rules that outrank layout (spec)

1. The answer appears in the first screen, before anything explains how it works.
2. Two doors above the fold: worked packets, and your own documents. Neither hidden.
3. What it will not do is said plainly near the top.
4. Refusals look like results, because they are.
5. A report, never a chat box.

## Page order

| # | Section | Job | Component |
|---|---|---|---|
| 1 | Hero | What it is, two doors, a real answer | Headline, one sentence, two buttons, a result card with three tabs: right, wrong, can't be settled |
| 2 | Won't do | Set scope before trust is asked for | One ruled line under the hero |
| 3 | Why it matters | Business value | The differentiator line, then two columns: the person answering, the person signing off |
| 4 | The three answers | The whole output space | Ruled list on the rail, each "can't be settled" reason named |
| 5 | Every answer can be checked | Precision | The boxed page images, read in order |
| 6 | What it refuses | Trust | The four refusals, styled as results |
| 7 | Check a claim | Act | Two tabs: worked packets (packet, mapping, question) and your documents (upload, propose, confirm, run) |
| 8 | Questions | Objections | Short answers, including legal advice |
| 9 | Close | Next step | Run one, read the code |

## Result screen (spec)

Question, claim with the amount in bold, the answer large, then why: governing document by name, clause, page and quote, or the named refusal reason. Then the chain, collapsed: what the model was allowed to see, the two passes, the rule that fired. Footer: file hashes, extractor version, commit, re-run link. The live progress steps no longer sit above the answer.
