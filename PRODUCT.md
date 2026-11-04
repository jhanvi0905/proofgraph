# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Primary audience for this build: hackathon judges, who watch a three-minute demo and open the public URL once. Long-term buyer the copy speaks to: in-house contract managers and legal-ops leads (the persona "Maya") who sign off on claims someone else wrote about what contracts, NDAs, amendments and governance documents allow. Second audience: the sender who receives a shared review link.

## Product Purpose
Checks a claim against every document in a packet and says whether the documents support it, contradict it or say nothing, showing the exact words on their page. Success: a reviewer reaches a trustworthy per-part answer in seconds and can check it themselves.

## Positioning
Claim verification for document packets, by a span-grounded evidence graph. Beyond citations: a citation points at text that agrees with a claim, while ProofGraph shows the text that decides it, including the clause that disagrees, which document overrides which, and what the documents do not say. Never name or compare other tools.

## Operating Context
A claim arrives as a sentence to trust (summary, memo, message) with documents attached. The reviewer pastes the sentence, drops in the packet, watches the packet being read, then opens the answer on its page. A second claim on the same packet reuses the already-read graph.

## Capabilities and Constraints
Answers per claim part: Supported, Contradicted, Qualified, Not in these documents, Not mentioned anywhere (the documents-disagree answer is not produced by the backend yet). Every statement opens on its page with its box, with a tier mark (read from the page, model's reading, unclear; unclear never decides). Two routes must agree (graph walk and full read). Reads with Muse Spark; Muse Spark Open is the independent second reader. Stack already exists: FastAPI with server-sent events, one HTML page, vanilla JS and CSS, no build step. Everything graph-related sits behind PROOFGRAPH_GRAPH=1 and the flag-off page must stay byte-identical. Pricing tiers and video are out of scope.

## Brand Commitments
The name is ProofGraph. Somewhere on the site, in the product's own words and without naming other tools: a citation points at text that agrees; ProofGraph shows the text that decides, including what disagrees.

## Evidence on Hand
No real packets may appear on the page or in public screenshots; only synthetic or redacted fragments. No customers, testimonials, logos or usage counts exist and none may be invented. A results report is not yet available, so any measured figure must read "Runs pending".

## Product Principles
1. Show the work, then the verdict: the path is the explanation.
2. Say plainly when the documents are silent; never fill a gap.
3. Quotes are always distinguishable from interpretation.
4. No unmeasured claim, and no overclaim of any kind.
5. The first step costs nothing: a first check needs no account.

## Accessibility & Inclusion
WCAG AA contrast at minimum. Meaning never rests on colour alone. Reduced-motion users get the same content without animation. Progress is announced through a polite live region.
