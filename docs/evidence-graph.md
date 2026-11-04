# The evidence graph

How ProofGraph reads a packet of documents, links what it finds and decides a claim. The graph is on when `PROOFGRAPH_GRAPH=1`.

## How it works

Paste a claim and drop in its documents. ProofGraph reads the packet once into a graph of who must, may or must not do what, with every statement pinned to its page. It then checks each part of the claim by walking from the things the claim names to the rules that govern them.

1. **Read.** Each document is read once, before any claim arrives. Every rule is written down with who it binds, whether it is a must, a may or a must-not, what it covers, its date, and its exact quote. Exceptions ("unless...", "provided that...") become their own linked statements.
2. **Connect.** Statements about the same thing join one node, through definitions, party names and section numbers. A person links to her office, an office to its class, and an amendment to the section it changes. Look-alike names never merge.
3. **Ask.** The claim splits into parts, and each part attaches to things that really exist in the graph.
4. **Walk and read.** The graph walks typed paths from those things to the rules that govern them. At the same time, one full read of the packet looks for anything the walk might miss.
5. **Decide.** The model judges two statements at a time. Code decides the answer from the structure, which document takes precedence, and the dates. Every answer shows its proof path, how each link was made, and what kind of reasoning it needed.

### Two real cases

**TC17: two documents, a rule on a class.** Claim: "Connors was continuously authorized to act as Interim CMO from May 7, 2026."

- The resolution says the CEO appointed her on May 7 and the Board ratified it on May 13, "effective as of May 7".
- The bylaws never mention Connors. They do say a Chief Medical Officer is a principal officer (§5.1), that no principal-officer appointment is effective until the Board approves it (§5.2), and that ratification is effective on adoption (§5.9).
- The path runs Connors → CMO (interim) → principal officer → §5.2, then to the resolution's own record of adoption on May 13. Bylaws take precedence over a resolution, so authority runs from May 13, not May 7.
- The CEO's May 7 letter is cited but not in the packet, and the answer says so.

**TC40: one document, a rule with an exception.** Claim: "The Bosch NDA allows the recipient to share confidential information with outside consultants without written authorization."

- §2 forbids disclosure to consultants unless the Disclosing Party authorizes it in writing.
- The claim denies exactly that condition, so the claim is contradicted.
- §5.4 (information "independently developed by... a consultant") and §14 (the parties as "independent contractors") share the claim's words but not its meaning, so they are set aside.

### What the graph holds

| Piece | What it is |
| --- | --- |
| Entity | A person, organisation, office, section, concept or dated event |
| Rule statement | Who it binds, must / may / must-not / is, the action, the value and whether it is stated or left blank, its date, its exact quote |
| Exception | A separate statement linked to the rule it carves out |
| Document | Its role (contract, amendment, bylaws, resolution, memo) and date |
| Claim part | One checkable piece of the claim, attached to its entities |

| Link | Meaning | Made by |
| --- | --- | --- |
| mentions | A statement is about this entity | Code |
| same as | Two names are one thing (a definition, the parties clause, a section number) | Code |
| is a / holds office | Connors holds the CMO office; the CMO is a principal officer | The model lists them, code checks each one against the quote |
| defined by / refers to section | A term's definition; a clause pointing at another section | Code |
| excepts / conditions / carves out | An exception or condition on a rule | The model extracts it, code links it |
| supersedes / precedence | An amendment replaces a section; one document outranks another | Code finds candidates and ranks documents; the model labels the effect |
| cites | A document refers to one that is not in the packet | Code |

### The six answers

| Answer | When |
| --- | --- |
| Supported | Statements match the part, nothing conflicts, no exception applies; more documents agreeing makes it stronger |
| Contradicted | A rule or statement clashes with the part, including a claim that denies an exception's condition |
| Qualified | Support exists, but an exception or condition is attached |
| Not found | The documents discuss the thing but never say this, and the full read found nothing either |
| Unknown | No document mentions the thing at all |
| Documents disagree | Two documents clash and nothing decides which one wins |

### Why people can trust it

- **Every statement opens on its page**, with a tier: read from the page, the model's reading, or unclear. An unclear link never decides an answer, and each answer is only as strong as its weakest link.
- **Two independent routes** to the evidence (the walk and the full read) must agree on what matters. When they don't, the screen says so.
- **Nothing is dropped silently.** Every rejected statement is counted, and "not found" needs both routes to come up empty.
- **The model judges only small, local things**, two statements at a time, which a person can check at a glance. Code does all the combining.
- **Reliability is measured on gold cases**, broken down by tier, not asserted.

## The flow at a glance

&#91;embedded content: ProofGraph flow: built once per packet, run for every claim\]

Only the filled boxes call a Meta model. The walk, the merges, the links and the decision are code, so every step can be replayed and checked.

## Scenarios we cover

A claim is classified by the shape of the proof path that decided it, read off by code. That one tag is shown on screen and used to break down the results. Thirteen scenarios are covered; three are out of scope and say so.

| # | Scenario | Example | Mechanism | Covered |
| --- | --- | --- | --- | --- |
| S1 | Direct statement | Bosch §18: Michigan law governs | One-hop path | Yes |
| S2 | Rule with exception or condition | TC40: consultants need written authorization (§2) | Exception as its own statement; a claim that denies the condition is a conflict | Yes |
| S3 | Hinges on a definition | Bosch §16: "Affiliate" means 51% control | defined-by link | Yes |
| S4 | Rule on a class, claim names an instance | TC17: Connors → CMO → principal officer → §5.2 | is-a and holds-office; a third hop allowed only along class links | Yes |
| S5 | Override or precedence across documents | TC17: §5.9 against the resolution; amendments in memo packs | overrides edges from the documents' own words, then the later document of the same role, then a declared governance order | Yes |
| S6 | Timing and sequence | TC17 "continuously from May 7"; TC18 "before she began" | effective\_from dates compared by code; "continuously" judged by the model | Mostly |
| S7 | Not mentioned | The governing-law-not-mentioned pack | Walk and full read both empty | Yes |
| S8 | Blank template value | Bosch's empty Period of Confidentiality | value status: blank | Yes |
| S9 | Multi-part claim | Shares with consultants and keeps copies | split.py; the worst part decides | Yes |
| S10 | Evidence cited but not supplied | TC17's CEO letter of May 7 | cites link via referenced\_documents() | Yes |
| S11 | Word-overlap distractor | Bosch §5.4, §14 | Different subject and concept; comparator says irrelevant | Yes |
| S12 | Instruction planted in a page | frt-07, fin-08 | Data marking plus an injection field in extraction | Yes |
| S13 | Scanned page | The service report scan in the worked example | Transcription with line boxes; approximate tier | Yes |
| U1 | Arithmetic across many figures | Summing invoice lines; FinDVer | engine/calc.py path, not the graph | Out of scope for the demo |
| U2 | Depends on law outside the packet | 18 U.S.C. §1833(b) in Bosch §5.6 | Shown as a cites link to a law not supplied | Shown, not decided |
| U3 | Subjective claim | "Reasonable care is strong protection" | Ends as cannot tell | Honest, not solved |
