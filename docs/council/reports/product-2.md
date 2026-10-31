# ProofGraph product report 2: domain, variations, process, frontend

Product team, read-only. Sources: the human's facts, docs/04 lines 1 to 24, and prior knowledge. No web research was done in this pass, so dataset and competitor facts are marked UNVERIFIED. Labels: [E] evidenced (brief, docs/04 or a stated human fact), [A] assumed, [U] unverified prior knowledge for the data agent to confirm.

Skills applied as methods: beachhead-segment, identify-assumptions-new, lean-canvas, metrics-dashboard, outcome-roadmap, job-stories, pre-mortem, customer-journey-map.

---

## 1. Domain decision

### Scoring (1 to 5 per criterion, weighted to a score out of 100)

Weights: utility and frequency 15, cost of a miss 10, public data and realistic packets 15, theme fit 20, demo drama 15, Meta model fit 15, judge legibility 10.

| Criterion (weight) | Freight | Finance | Legal | AI PM | Hybrid: freight claim dispute (freight docs + contract terms + invoice money) |
|---|---|---|---|---|---|
| Utility and frequency (15) | 4 | 4 | 4 | 5 | 4 |
| Cost of a miss (10) | 4 | 5 | 5 | 3 | 4 |
| Public data, realistic packets (15) | 2 | 5 | 4 | 4 | 2.5 |
| Theme "Build for Your World" (20) | 5 | 4 | 4 | 3 | 5 |
| Demo drama in 3 min (15) | 5 | 4 | 3 | 3 | 5 |
| Meta model fit (15) | 5 | 3 | 3 | 2 | 5 |
| Judge legibility (10) | 3 | 5 | 4 | 4 | 4 |
| **Weighted score /100** | **82** | **84** | **76** | **68** | **85.5** |

Reasons behind the key scores [A, from the builder's stated background]:

- **Freight wins on Meta fit and drama.**
  - Packets are naturally scans and photos: bills of lading (BOL), signed proof of delivery (POD) with handwritten exceptions, and delivery photos.
  - SAM 3.1 counting pallets or cartons is a real job here, not decoration.
  - Muse Spark boxes on a handwritten "2 short" note make the strongest visual in any domain.
- **Freight loses on public data.**
  - Real BOLs and PODs are private.
  - Packets must be synthetic but realistic, built from public templates such as standard straight BOL forms and carrier rules tariffs [U].
- **Finance wins on data and legibility.**
  - SEC filings on EDGAR are public and huge.
  - Datasets such as FinQA, TAT-QA and FinanceBench exist [U].
  - Judges understand "the 10-K says otherwise" instantly.
  - It is weaker on Meta fit, because most filings are digital text, so boxes on scans matter less.
- **Legal has the best ready benchmark.**
  - ContractNLI labels entailment, contradiction and "not mentioned" for NDA clauses [U].
  - CUAD covers clause types [U].
  - But contract review is visually flat and crowded with competitors.
- **AI PM is the most frequent job but the weakest standalone demo.**
  - It works best as the frame: the claim comes from an AI.

### Recommendation

- **Primary demo domain: the freight claim dispute hybrid.**
  - Pitch story: "I worked freight. When a load arrives short or damaged, someone writes a claim, now often drafted by an AI, and someone else must check it against the BOL, the POD, the photos, the rate confirmation and the liability terms. Missing one exception notation or one liability clause costs thousands."
  - It earns three things:
    - the theme points (firsthand world)
    - the Meta points (scans, handwriting, photo counts, independent check)
    - the drama (red box on a handwritten exception, a SAM count of 22 against a claimed 24)
- **Secondary domain: finance (public-company filings).**
  - Pitch story: "Same engine, different world. An AI analyst note says revenue grew 20% across all regions. The 10-K segment table says 18%, excluding discontinued operations, with one region down."
  - It earns generality, judge legibility, and honest numbers on public data.
- **Legal is used as the evaluation benchmark, not as a demo domain.** ContractNLI's "not mentioned" label tests our absence reporting [U].
- **AI PM is the framing for every claim.** Each demo claim is shown as AI-drafted ("Drafted by an assistant"). This is the Impact story: AI writes, humans sign.

**Disagreement inside the panel.**
- Strategy wanted finance as primary, for data and legibility.
- UX and hackathon strategy wanted freight, for theme, Meta fit and drama.
- **Resolved for freight**, because:
  - theme fit is a Stage 1 pass/fail gate
  - Meta tooling is 25% of the score
  - finance stays as a 20-second generality cut and as the public-data eval
- Condition: if engineering finds handwriting or photo counting unreliable on synthetic scans, swap the primary to finance with scanned exhibits.

### Five highest-utility claim types per domain [A, builder expertise to confirm]

**Freight**

| Claim type | Example claim | Evidence needed |
|---|---|---|
| Quantity and condition at delivery | "All 24 pallets were delivered short by 2 and 3 were damaged." | BOL (piece count), signed POD with exception notes, delivery photos |
| Carrier liability amount | "The carrier is liable for the full $48,000 invoice value." | BOL released-value notation, carrier rules tariff (liability cap), commercial invoice |
| Accessorial and detention charges | "6 hours of detention are billable at $75 per hour." | Rate confirmation (free time, rate), gate or ELD timestamps, facility check-in log |
| Invoice matches agreed rate | "The freight invoice matches the rate confirmation." | Rate confirmation, carrier invoice, fuel surcharge table |
| Claim filed on time | "Our claim is within the 9-month filing window." | POD delivery date, claim notice date, BOL terms or contract |

**Finance**

| Claim type | Example claim | Evidence needed |
|---|---|---|
| Growth or metric claim | "Revenue grew 20% across all regions in FY25." | 10-K MD&A, segment note, prior-year 10-K |
| Guidance claim | "Management raised full-year guidance." | Earnings release, call transcript, prior release |
| Covenant compliance | "The company is in compliance with its leverage covenant." | Credit agreement definitions, 10-Q debt note, compliance certificate |
| Debt and maturity | "No debt matures before 2028." | Debt footnote, 8-K on refinancing |
| Litigation or risk absence | "There is no material pending litigation." | 10-K legal proceedings, contingencies note, recent 8-Ks |

**Legal**

| Claim type | Example claim | Evidence needed |
|---|---|---|
| Termination right | "We can terminate for convenience on 30 days' notice." | Master agreement, amendments, order form |
| Liability cap and indemnity | "Our liability is capped at fees paid in 12 months." | Limitation of liability clause, carve-outs, indemnity section |
| Assignment and change of control | "The contract survives an acquisition without consent." | Assignment clause, definitions |
| Renewal dates | "The contract auto-renews on 1 Jan unless notice is given by 1 Oct." | Term clause, amendments, notice clause |
| Confidentiality scope | "We may share their data with subcontractors." | NDA or DPA, definitions, permitted disclosures |

**AI product management**

| Claim type | Example claim | Evidence needed |
|---|---|---|
| Support answer faithfulness | "Refunds are available within 60 days." | Refund policy, terms of service, regional exceptions |
| Benchmark claim | "Model A beats Model B by 5 points on X." | Paper tables, eval run export, setup notes |
| Release note claim | "SSO is available on all plans." | Pricing page, changelog, plan matrix |
| Data handling claim | "We never store customer prompts." | Privacy policy, DPA, retention schedule |
| Launch metric claim | "Activation rose 12% after the launch." | Dashboard export, experiment readout, definitions doc |

---

## 2. Variation decision table

This table tells the pack builders what to vary and engineering what to measure. Each axis exists because its result changes a product decision.

| Axis | Values to produce | Product decision it informs | Result that would change the decision |
|---|---|---|---|
| Relation mix | Pure support; pure contradiction; mixed; all weakeners; nothing relevant | Verdict banner logic, and whether contradictions lead the list | If mixed packets give unstable verdicts across runs, show a per-part status only and drop the overall verdict |
| Weakener type | Qualifier, exception, condition, scope, time or superseded, magnitude, definition, source strength | Whether cards show a typed weakener badge or a plain "Weakens" | If type accuracy is under 70% [A threshold], show "Weakens" with the qualifying words quoted, not a type |
| Claim compoundness | 1, 2 to 3, and 4+ atomic parts; parts joined by "and", "all", numbers or dates | Whether the claim-part chips and tree ship as Must | If the split is unstable (different parts on reruns) or users must edit it often, let the user confirm the split before analysis |
| Modality | Digital text, numeric tables, scanned typed pages, handwriting, photos | Whether boxes on scans are the hero; whether SAM is in the demo | If box overlap with the true span is poor on scans, fall back to page highlight plus quote; if SAM count is not better than Spark's count, drop SAM from the hero moment |
| Numeric precision | Exact match, rounding, unit change (lb/kg, $k/$m), percent against percentage points | Whether magnitude weakeners are a separate type | If numeric errors dominate misses, add a visible "numbers checked" line per card |
| Packet size | 1 document; 3 to 5; 10+; 50+ pages | Packet limits in the UI; when the tree navigator appears | If quality drops past N documents or pages, set a hard limit with a clear message |
| Conflict and supersession | An amendment overrides the original; a later POD corrects the earlier one; two sources disagree | Whether "Superseded" is a supported state and the dates shown | If the system misses supersession, show "Documents disagree" without picking a winner |
| Distractors | Near-miss passages (same entity, other date; same number, other metric) | Precision threshold for showing a card | If precision is under target, raise the bar and show fewer cards |
| Absence | A claim part with no evidence; an evidence page deleted; the claim about a topic the packet omits | Whether "No evidence" is stated firmly or as "not found" | If false "No evidence" exceeds 10% [A], word it as "Not found in this packet" and show which documents were read |
| Wording tricks | Negation, double negation, hedges ("up to"), "all" or "only", passive voice, synonyms | Microcopy for weakener explanations; demo claim choice | If negation flips are common, avoid them in the live demo and report them honestly in the eval |
| Unreadable input | A blurry photo, a skewed scan, a page over the model's page limit [E: PDF text read for the first 100 pages, images for the first 50] | Unreadable-page state design | Always required; the result decides how often it appears |
| Claim origin | Human-written against AI-drafted (fluent, confident, slightly wrong) | Whether to frame the product as checking AI output | If AI-drafted errors are mostly fabrication with no evidence, absence reporting becomes the hero instead of contradiction |

**Pack builder minimum** [A]:
- **Freight:** 12 primary-domain packets.
- **Finance:** 8 packets.
- **Legal:** a ContractNLI slice for absence and contradiction.
- **Every axis value appears at least twice.** Each packet has gold labels:
  - claim parts
  - relation per passage
  - weakener type
  - the exact span with page number

---

## 3. Remaining product process

### (a) Lean canvas

| Block | Content |
|---|---|
| Problem | 1. AI-drafted and second-hand claims are signed off without checking every source. 2. Caveats, exceptions and handwritten exceptions are buried in scans. 3. Citation tools show agreement, not disagreement or absence. |
| Customer segments | Beachhead: freight claims and audit staff at shippers, brokers and 3PLs. Next: finance analysts, contract managers, AI product teams checking assistant answers. |
| Unique value proposition | "See where your own documents disagree with a claim, pinned to the exact spot on the page, before you sign." |
| Solution | Claim split into parts; evidence cards typed by relation and weakener; boxes on the original page including scans and photos; independent second check; exportable review. |
| Channels | Hackathon demo and repo; freight and logistics communities; AI tooling communities; later, plugins for TMS and claims tools [A] |
| Revenue streams | Per-seat SaaS for claims and audit teams; usage per packet; later, an API for AI teams to check their outputs [A] |
| Cost structure | Model calls per claim (Muse Spark, SAM 3.1, Muse Spark Open); storage of documents; labelling for eval |
| Key metrics | Contradiction and weakener recall with correct location; card precision; time to verdict; override rate |
| Unfair advantage | The builder's firsthand freight, finance and legal knowledge for packets and labels; a falsification-first design; Meta grounding on scans. It is honest to say this is thin and copyable. |

### (b) Evaluation plan without interviews

**Desirability (does anyone want this?)**

| Method | What it gives | Change-course threshold [A] |
|---|---|---|
| Builder-as-expert walkthrough: the builder reviews 5 freight packets manually, then with the product, timing both | Time saved, misses caught | If the product doesn't cut time by at least 50% or catch a miss the builder made, the freight story weakens; consider finance as primary |
| Synthetic users: 3 persona prompts (claims analyst, finance analyst, contract manager) review the UI screenshots and list confusions | A cheap usability lint, not real desirability | Any confusion raised by 2 of 3 personas gets fixed before freeze |
| Public signal: scan forum threads on freight claim disputes and AI hallucination in finance (data agent) | Evidence that the pain exists, with quotes | If no public evidence of the "missed exception" pain exists, soften the Impact claim |
| Fake door in the demo: a "Try with your packet" button that counts clicks (post-hackathon) | Real intent | Not decision-relevant this week |

**Quality (does it work?)**
- **Gold set:** the pack builders' labelled packets, split into a dev set and a held-out test set. The builder looks at the test set only once, before the video.
- **Public benchmark slice:** ContractNLI (contradiction and not-mentioned) and a FEVER-style or financial claim set if the data agent confirms one exists [U].
- **Metrics and thresholds:**

| Metric | Definition | Target to ship as is | If below |
|---|---|---|---|
| Contradiction recall (north star, with weakeners) | Gold contradicting or weakening spans found with the correct relation and an overlapping location | ≥ 0.80 | Below 0.6: reposition as "first-pass reviewer"; never say "catches" in the pitch |
| Card precision | Shown contradict or weaken cards that are correct | ≥ 0.80 | Raise the threshold; show fewer cards |
| Location accuracy | Box overlaps the gold span (IoU or line match) | ≥ 0.75 on scans, ≥ 0.9 on digital | Fall back to page plus quote |
| Absence accuracy | "No evidence" parts that truly lack evidence | ≥ 0.85 | Reword as "Not found" |
| Verdict agreement with second check | Spark against Muse Spark Open | Report as is | Under 0.6 makes the badge noisy; show only disagreements |
| Time to first contradicting card | From upload | ≤ 30 s typical [A] | Stream results, pre-run for the demo |
| Cost per claim | Dollars | ≤ $0.50 typical [A] | Cap pages, cache |

- **Honesty rule:** the video shows the test-set table, including at least one miss.

### (c) 3-minute demo storyboard (freight primary)

**Demo packet (synthetic, realistic, disclosed as synthetic):**
- the BOL scan: 24 pallets, released value "not exceeding $0.50 per lb"
- the signed POD scan with a handwritten note "2 short, 1 dmg"
- the delivery photo
- the rate confirmation
- the commercial invoice: $48,000

**Claim**, labelled "Drafted by an assistant": "Carrier delivered 22 of 24 pallets, 3 of which were damaged. The carrier is liable for the full $48,000 invoice value."

| Time | Screen | Voice-over (summary) |
|---|---|---|
| 0:00 to 0:15 | Builder's face or a title card; a pile of freight paper | "I worked in freight. Every short or damaged load becomes a claim, and now AI drafts them. Someone still has to check it against the paperwork." |
| 0:15 to 0:30 | The claim text, then the packet dropped in (5 files, 2 scans, 1 photo) | "Here is a real-format claim and its packet." |
| 0:30 to 0:50 | Streaming: claim splits into 3 chips; the first red card appears | "ProofGraph splits the claim and looks for what disagrees first." |
| 0:50 to 1:20 | **Hero moment.** Click the red card: "Contradicts: liability is limited by released value." The right pane jumps to the BOL scan with a box on the released-value line. Chip 3 turns red. | "The invoice is $48,000, but the bill of lading limits liability to 50 cents a pound. That's about $9,600, not $48,000." |
| 1:20 to 1:45 | Amber card: "Weakens (magnitude): POD notes 1 damaged, not 3." Box on the handwritten POD note. | "The driver's signed delivery receipt says 1 damaged, not 3." |
| 1:45 to 2:00 | Green card: "Supports: 22 pallets." The photo with SAM masks over each pallet, count 22. | "Meta's SAM 3.1 counts 22 pallets in the delivery photo, matching the shortage." |
| 2:00 to 2:15 | Second-check badge: "Independent check agrees: 2 of 3 parts; disagrees on damage count." Click to show why. | "A second, open-weight Meta model checks each verdict without seeing the first one's reasoning." |
| 2:15 to 2:30 | Generality cut: a finance 10-K packet, "Revenue grew 20% across all regions" turns amber and red on the segment table | "Same engine on public filings." |
| 2:30 to 2:45 | Eval table: recall, precision, location accuracy on the held-out set, one miss shown | "Measured on labelled packets. Here's what it still misses." |
| 2:45 to 3:00 | Export view; repo URL; "Built 27 Oct to 4 Nov" | "One click to a signed review. Built this week on Muse Spark, SAM 3.1 and Muse Spark Open." |

**Demo arithmetic:** $0.50 per lb is illustrative and needs a stated weight. Example: 24 pallets at 800 lb is 19,200 lb, which gives a $9,600 cap. The pack builder must make the numbers consistent [A].

**Q&A prep sheet**

| Likely question | Answer |
|---|---|
| Isn't this RAG? | No chat and no top-k answer. The input is a claim, and the output is typed relations, including contradiction and absence, located on page images, with an independent check and a measured score. |
| Are the packets real? | Real formats, synthetic content, built from public templates and my freight experience; finance packets use real public filings. |
| What happens when it's wrong? | Every card shows the quote and the page; the user accepts or rejects. The second check flags disagreement. "Can't tell" is allowed. |
| Why SAM if Spark can count? | SAM gives an independent pixel-level count with masks the user can see; we report where they disagree. Say only what engineering confirmed. |
| What's the accuracy? | Point to the held-out table; name the weakest category. |
| Cost and speed? | Per-claim cost and latency from the eval run. |
| Who pays? | Claims and audit teams at shippers, brokers and 3PLs first; then finance and AI teams. |
| What existed before the hackathon? | Point to the commit history and the README disclosure. |
| Does it work on my documents? | PDFs and photos up to the stated page limit; unreadable pages are named, not skipped. |
| Why not ask ChatGPT? | It answers and agrees; this hunts disagreement, types it, pins it to the scan, and shows what's missing. |

### (d) Updated PRD summary and 12 job stories

**Goal:** a reviewer reaches a defensible verdict on an AI-drafted claim in under 2 minutes, seeing every contradiction, weakener and gap located on the original page.

**Scope:** the three-pane review, one claim at a time, a packet of up to N documents [engineering sets N].

**Out of scope:** chat, open-web search, accounts, free-form graph, multi-user.

| # | Job story | Acceptance criteria | Priority |
|---|---|---|---|
| 1 | When I start, I want to load an example packet in one click, so I see value before uploading anything. | 3 examples (freight, finance, legal) on the start screen; each opens a finished review in under 3 s (pre-computed allowed, and labelled as such) | Must |
| 2 | When I paste a claim and drop files, I want analysis to start right away. | PDF, JPG and PNG accepted; per-file status; the limit is stated before upload | Must |
| 3 | When the claim is compound, I want to see its parts. | Left pane lists the parts with chips; each card names its part | Must |
| 4 | When parts are split wrongly, I want to fix them. | Edit, merge and split before or after the run; a rerun updates only the affected parts | Could |
| 5 | When something contradicts the claim, I want to see it first. | Contradicts group first, then weakens, then no evidence, then supports | Must |
| 6 | When a passage weakens the claim, I want to know how. | Weakener badge from the taxonomy plus the qualifying words in bold within the quote | Must |
| 7 | When I select a card, I want the exact spot on the page. | Right pane opens the page with a coloured box; works on scans and photos | Must |
| 8 | When I look at the page, I want to find its card. | Clicking a box scrolls to and focuses its card | Should |
| 9 | When a part has no evidence, I want it said plainly. | "Not found in this packet" row under that part; lists the documents searched | Must |
| 10 | When the system is unsure or a page is unreadable, I want to know. | "Can't tell" chip state with a reason; unreadable pages named with a thumbnail | Must |
| 11 | When I doubt the AI, I want an independent check. | Agree or disagree badge per part; a disagreement opens both rationales | Should |
| 12 | When I'm done, I want to record my judgment and export it. | Accept, reject or relabel per card; export (HTML or PDF) shows the claim, verdict per part, cards, page thumbnails with boxes, overrides and a timestamp | Should (accept and reject are Must) |

### (e) Outcome roadmap (product level)

| Horizon | Outcome | Signals |
|---|---|---|
| Now (hackathon) | Judges and a domain reviewer believe the product finds what disagrees, on real-format scans, and say so honestly | Recall and precision table; the hero moment works live or cleanly recorded; Stage 1 passes |
| Next (1 to 3 months) | Freight claims staff use it on real packets weekly | Packets per user per week; override rate falling; time to verdict |
| Next | AI teams use it to check their assistant answers against their docs | API calls; disagreement findings acted on |
| Later | Packets and verdicts become a reusable record: claims history, audit trail, supersession tracking across shipments or contracts | Repeat packets; exports shared with managers |
| Later | Self-hosted, open-weight-only mode for confidential packets | Enterprise pilots |

### (f) Risks and pre-mortem update (domain-specific)

| # | Failure | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Judges don't know freight terms (BOL, POD, released value) | High | Medium | One-line plain-language glossary on screen; claim in plain words; the finance cut for legibility |
| 2 | Synthetic packets look fake or too easy | Medium | High | Use real public form layouts, realistic noise (stamps, skew, handwriting); include distractors; disclose that they are synthetic |
| 3 | Handwritten POD exception not read | Medium | High | Engineering test first; fallback to a typed exception notation |
| 4 | SAM count wrong on stacked or wrapped pallets | Medium | Medium | Choose clear photos; show the masks so errors are visible; drop it if unreliable |
| 5 | Liability arithmetic in the demo is wrong or legally oversimplified | Medium | High (credibility) | Builder checks the numbers; say "illustrative terms"; no legal advice framing |
| 6 | The domain looks niche, so Impact scores low | Medium | High | Frame as "AI drafts, humans sign" across freight, finance and legal; show market breadth in one line |
| 7 | The frontend ambition eats engineering time before freeze | High | High | Must list only; Could items cut Sunday night |
| 8 | The eval set is too small to be credible | Medium | Medium | Report n and confidence honestly; add the ContractNLI slice |
| 9 | The "basic RAG" perception persists | Medium | High | No chat box anywhere; say the three differences in the first 30 s |
| 10 | Live latency during the recording | Medium | Medium | Pre-run with a cached result and an honest "replayed run" label, or record live with retries |

---

## 4. Frontend product spec

### Information architecture

1. **Start**
   - example packets (3 cards)
   - New review (claim box plus drop zone)
   - Recent reviews (local only)
2. **Review**, the three panes:
   - top bar: claim text, verdict banner, relation counts, filters, export
3. **Export view**, a printable review record
4. **About and method**:
   - how it works
   - the eval table
   - the "built during the hackathon" note
   - model credits

### Layout and responsive behaviour

| Width | Behaviour | Priority |
|---|---|---|
| ≥ 1280 px | Three panes: left 22%, centre 33%, right 45%; resizable splitters | Must (fixed widths), Could (resizable) |
| 960 to 1279 px | Left pane collapses to a narrow chip rail (icons and part numbers); centre and right side by side | Should |
| < 960 px | Single column with tabs: Claim, Evidence, Page; choosing a card switches to Page | Could |

### Claim-part chips

Each part shows its short text, a status chip and counts (✕2 !1 ✓3).

| Status | Meaning | Visual | Priority |
|---|---|---|---|
| Contradicted | At least one accepted contradicting card | Vermilion fill, ✕ icon, solid border | Must |
| Weakened | Weakener cards, no contradiction | Amber fill, ! icon, dashed border | Must |
| Supported | Supports only | Blue fill, ✓ icon | Must |
| Not found | No relevant evidence | Grey hatch, ? icon | Must |
| Can't tell | Conflicting, unreadable or low confidence | Grey outline, ~ icon, reason on hover | Must |
| Checking | Still streaming | Shimmer skeleton | Should |
| Overridden | User changed the status | Small pen icon plus the original status in the tooltip | Should |

The overall verdict banner takes the worst part status, in this order: contradicted, weakened, can't tell, not found, supported. The banner says which part drives it.

### Evidence card anatomy

| Element | Content | Priority |
|---|---|---|
| Relation stripe | Left border colour plus icon plus word ("Contradicts") | Must |
| Weakener badge | Qualifier, Exception, Condition, Scope, Time, Superseded, Magnitude, Definition, Source strength | Must (or a generic "Weakens" if engineering says type accuracy is low) |
| Quote | The exact span, max 3 lines with expand; qualifying words in bold | Must |
| Claim part | "Part 3: full $48,000 liability" | Must |
| Source | Document name, page, and a thumbnail on hover | Must |
| Why line | One sentence: "Released value caps liability at $0.50/lb, about $9,600." | Must |
| Confidence cue | Three levels as words: Clear, Likely, Uncertain (no percentages) | Should |
| Second-check badge | Agrees or Disagrees | Should |
| Actions | Accept (A), Reject (R), Relabel (L, menu of relations) | Accept and Reject Must, Relabel Should |

### Filters and keyboard

- **Filter chips** by relation, by claim part (click a chip on the left), and by document. Must.
- **Keyboard** (Should):
  - J and K: next and previous card
  - [ and ]: next contradicting card
  - A, R and L: card actions
  - O: open the original at the page
  - E: export
  - ?: shortcut sheet

### Linked highlighting

- Hovering or focusing a card flashes its box on the page for 600 ms and scrolls the page if needed. Must for click, Should for hover.
- Clicking a box on the page scrolls to and focuses its card. Should.
- Several boxes on one page are numbered to match the card order. Should.
- Photo evidence from SAM shows outlined masks plus a count label. Could; it becomes Should if SAM is in the demo.

### Shallow tree navigator

- **When it appears.** Shown in the left pane only when the claim has 3 or more parts or the packet has more than 3 documents. Otherwise the left pane is a flat chip list.
- **Structure.** Claim, then parts, then evidence entries (icon plus document and page).
- **Default collapse.** Parts with contradictions start expanded; supported parts start collapsed.
- **Collapse control.** A single toggle "Tree / List".
- **Priority.** Could. The flat chip list is Must.

### States

| State | What the user sees | Priority |
|---|---|---|
| Empty (first run) | Three example packet cards and a drop zone; one line on what the product does | Must |
| Loading / streaming | Steps shown in order ("Reading 5 documents", "Splitting the claim", "Looking for contradictions", "Second check"); cards appear as found, contradictions first | Must (step text), Should (true streaming) |
| No relevant evidence | Every part "Not found"; message plus the list of documents read | Must |
| Unreadable page | Banner: "2 pages could not be read" with thumbnails; affected parts become Can't tell | Must |
| Over page limit | "Only the first 50 pages of images and 100 pages of text were read in report.pdf" [E docs/04 limits] | Must |
| Error | Plain message, retry button, nothing lost | Must |
| Spend cap reached | "This run stopped at the spending limit. Results so far are shown and are incomplete." | Must |
| Can't tell | Chip plus reason (conflicting documents, unreadable, low confidence) | Must |
| Checker unavailable | Badge reads "Second check unavailable" | Should |

### Export view

A printable page containing:
- the claim, with the "AI-drafted" tag if set
- the verdict and the status of each part
- each card's relation, quote, document and page
- page thumbnails with boxes
- the user's overrides, marked, and any reviewer note
- models used and a timestamp
- footer: "Generated by ProofGraph. Review decisions are the reviewer's."

Delivery: HTML with print CSS is Must; PDF download is Could.

### Accessibility

- Never colour alone: every relation has an icon, a word and a border style.
- WCAG AA contrast for text on chips and cards.
- Full keyboard path; visible focus rings.
- ARIA live region announces new cards politely during streaming.
- Boxes have text alternatives: the card's quote.
- Respect reduced motion: no flashing; outline the box instead.

### Visual design principles

| Meaning | Colour (Okabe-Ito based, colour-blind safe) | Icon | Pattern |
|---|---|---|---|
| Contradicts | Vermilion #D55E00 | ✕ | Solid |
| Weakens | Amber / orange #E69F00 | ! | Dashed |
| Supports | Blue #0072B2 | ✓ | Solid thin |
| Not found / unresolved | Neutral grey #7A7A7A | ? | Hatched |
| Can't tell | Grey outline | ~ | Dotted |

Use blue, not green, for supports, so red and green confusion can't occur.

**Trust feel:** calm, document-like, closer to a legal redline or audit workpaper than a chatbot:
- neutral off-white canvas, serif or high-legibility text for quotes, monospace for numbers
- quotes always verbatim, with a "verbatim" marker
- no exclamation, no "AI magic" sparkles, no confidence percentages
- the original page is always one click away
- dark mode is Could

### First-run experience

- **Three example cards** (Must):
  - "Freight: short and damaged delivery claim"
  - "Finance: AI analyst note against a 10-K"
  - "Legal: NDA sharing claim"
- **Pre-computed results.** Each opens a finished review instantly, labelled "Example result, precomputed".
- **Rerun option.** A "Run it live" button reruns that example.
- **Coach marks.** A 3-step tour (Should):
  1. "Parts of the claim"
  2. "What disagrees, first"
  3. "Click to see it on the page"

### Microcopy for the 10 most important strings

| Where | String |
|---|---|
| Start headline | "Check a claim against your documents. See what disagrees first." |
| Claim box placeholder | "Paste the sentence you need to check, for example from an AI draft." |
| Drop zone | "Drop the evidence: PDFs, scans or photos. Up to N files." |
| Streaming | "Looking for what contradicts or weakens the claim…" |
| Not found | "Not found in this packet. Searched: BOL.pdf, POD.jpg, invoice.pdf." |
| Can't tell | "Can't tell: the documents disagree. The later one is dated 16 Oct." |
| Unreadable | "We couldn't read page 2 of POD.jpg. Parts that depend on it are marked Can't tell." |
| Second check disagrees | "An independent model disagrees on this part. Look at both reasons before deciding." |
| Spend cap | "Stopped at the spending limit. These results are incomplete." |
| Export footer | "Highlights are suggestions. The decisions in this record are the reviewer's." |

### Must / should / could summary

- **Must:**
  - start screen with the example packets
  - three-pane review
  - chips with the five states
  - card anatomy (minus confidence and second check)
  - click card to box
  - filters by relation
  - all Must states
  - accept and reject
  - HTML export
  - colour-blind-safe semantics
- **Should:**
  - box to card linking
  - hover flash
  - keyboard navigation
  - second-check badge
  - confidence cue
  - relabel
  - streaming
  - mid-width layout
  - coach marks
- **Could:**
  - tree navigator
  - SAM mask overlay (Should if in the demo)
  - claim-part editing
  - resizable panes
  - mobile tabs
  - PDF export
  - dark mode

---

## Questions for engineering

1. What is the box accuracy of Muse Spark perception grounding on typed scans, handwriting and photos at line level [E: 0 to 1000 grid]? This decides whether the hero is a box or a page highlight plus quote.
2. Can handwritten POD exceptions ("2 short, 1 dmg") be read reliably? This decides whether freight stays primary.
3. Does SAM 3.1 count pallets or cartons better than Spark's own count on realistic photos? This decides whether SAM is in the hero moment.
4. What is weakener-type accuracy by type? This decides typed badges versus a generic "Weakens".
5. How stable is the claim split across reruns? This decides whether claim-part editing is needed.
6. How do we distinguish true absence from a miss, and what is the false "Not found" rate? This decides the wording of the absence state.
7. Can the system detect supersession by date across documents? This decides whether "Superseded" ships.
8. What are latency to the first contradicting card and the total per claim, and can results stream? This decides the streaming UI and a live versus replayed demo.
9. What are cost per claim and the behaviour at the spend cap? This decides the spend-cap state and packet limits.
10. Can Muse Spark Open take images, or only extracted text, and what is its agreement rate? This decides the second-check badge and the open-weight bonus pitch.
11. What packet size (documents and pages) keeps quality within target, given the 100-page text and 50-page image limits [E]? This decides the stated limits on the drop zone.
12. Can examples be precomputed and replayed exactly, with an honest label? This decides the first-run design and the demo recording.
