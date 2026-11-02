# Product review of the captured journey (TC17, wave 1, flag on)

Basis: journey.md, screenshots 05, 06, 07, 08, the sprint note (Goal, Product decisions), the copy spec, first 40 lines of docs/02-scope.md. Not re-run; no code read.

## 1. Verdict
**Partly.** The engine is right but the screen does not yet answer the customer's job.
- The customer's question is "does my evidence support, weaken or contradict this claim, and where is the passage?" The answer exists but is spread across 30 flat cards in 8,592 px; the one contradicting card is last, about 7,600 px down.
- The top of the page shows "Contradicted" beside part 1 "Weakened" with 16 supports (06). With no reason shown, a careful customer will think the tool is broken, and trust is the product.
- Pinned quotes and boxes are a real strength: every card links to its exact page. That is the "find the passage" half, and it works.
- 10 of 17 cards in part 1 carry a long "not settled" note, which reads as "this card may be wrong" and undercuts the evidence the customer needs to trust.
- TC40 (2 cards, 1,505 px) shows the target feel: short, clear. TC17 shows the problem: multi-part claims, repeated quotes, no hierarchy.

## 2. Per-stage decisions
**Entry.** First thing seen: a one-line title and purpose ("Check a claim against your documents. Every finding links to the exact passage."), then Claim, then Evidence packet, then Passcode last (or collapsed, if the host allows). A short example claim as placeholder. Reason: today the first ask is a secret and nothing says what the tool does (01).
**Claim.** Placeholder shows a good claim: one checkable sentence with a date or amount. No new logic.
**Upload.** Show full file names (wrap, not truncate) and a "3 files, 342 KB" line. Customers cannot tell three similar IHP files apart (02-03).
**Wait.** Replace grey "Checking" chips with the sprint stage strip plus "Results fill in as checks finish. Nothing is final until every check is done." Chips say "Pending", never a verdict colour. Show parts as "Part 1 of 2" so the split of the claim is not a surprise; the fragment "from May 7, 2026." must be labelled as a part, not a second claim. About 25 s is tolerable only if progress is visible.
**Results top.** One verdict banner, then one code-built sentence that says why, e.g. "Contradicted because part 2 has 1 contradicting passage (Bylaws p2). Part 1: weakened." plus a jump link to that passage. Verdict, jump link, then parts. Sprint rule is kept: counts and names only, no AI text.
**Part.** Chip, claim text, counts line, then groups in this order: Contradicts, Weakens, Supports. Contradicts open first, so the red evidence is at the top of its part. Supports collapsed to the counts line (sprint decision kept).
**Cards.** Quote first, source and page link second, relation and date third. The second-read badge stays neutral and short; the long note moves into a tooltip or one line per class, not per card. "Undated" becomes "No date found in this passage". Strip the "0-" and "2-" prefixes from displayed file names. One referenced-not-supplied marker per distinct letter ("cited in 4 places") and one per packet, not per part.
**Bottom.** End with one footer: coverage note (text pages only, scans not read), the date caveat, and the download button. Nothing decisive may live down here.
**Cross-cutting.** Make the viewer theme match the page (light) and give it one scroll container: let the viewer grow with the page on desktop and mobile.

## 3. Pointer table
| id | Pointer | Impact | Lane | Sprint task |
|---|---|---|---|---|
| P1 | Contradicting card buried at ~7,600 px; collapse, Contradicts first | H | UI | 3 (decisions: 3/2/0 open) |
| P2 | Verdict vs part 1 "Weakened" looks inconsistent; add "why" sentence and jump link | H | UI | NEW |
| P3 | Wait shows only grey "Checking"; stage strip, Pending, no-final line | H | UI | 11 / 6 |
| P4 | Part verdict itself unexplained; "Sources disagree on this part." is visible and uses a banned word | H | UI | 9 (extend ban list check to part notes) |
| P5 | 10 of 17 "not settled" notes repeat near-verbatim; shorten to a class line | H | UI | 9, 3 |
| P6 | Part 2 repeats the same ~12 supports as part 1 | M | AI/backend (part-scoped relevance) plus UI (dedupe across parts) | 1 (within a part only), NEW |
| P7 | Same unsupplied marker 4 times per part, 8 total | M | UI | 1 |
| P8 | Date label "inferred from in passage" (word missing) | M | UI | NEW (S) |
| P9 | Bare "Undated" separator | M | UI | 7 (rewrite, not delete) |
| P10 | Landing has no title, purpose line or example claim; passcode first | M | UI | NEW |
| P11 | Truncated file names; numeric "0-" prefix shown | M | UI | NEW |
| P12 | Claim split into parts silently; fragment part reads oddly | M | AI/backend (splitter) plus UI label | NEW |
| P13 | Nested scroll (900 px iframe) on desktop and mobile | M | UI | NEW |
| P14 | Dark viewer in light page | L | UI | 7 |
| P15 | Mobile: source line breaks, large empty top band | L | UI | 7 |
| P16 | Claim repeated 3 times (TC40) | L | UI | NEW |
| P17 | Part 1 "supports" cards the second read says do not mention the part | H | AI/backend (labelling precision) | none |
| P18 | Verdict-combination rule across parts | H | Product-decision | none |

## 4. Contradiction / verdict-consistency problem
Observed: part 1 Weakened (16 supports, 1 weakens), part 2 Contradicted (1 contradicts, 12 supports); overall Contradicted. The rule is plausibly right (worst part wins) but the customer sees no reason.
**UI-only fix (status untouched):** under the overall chip, add a code-built line: "Overall is the strongest finding across parts. Part 2 is Contradicted by 1 passage: [doc, page]. Part 1 is Weakened by 1 passage: [doc, page]." Each name is a link that opens its card. In each part, show the 16 or 12 supports as "Supports (16)", collapsed, so a pile of supports does not look like it outvotes one contradiction. Add a neutral one-line note on the verdict: "One contradicting passage is enough to contradict a claim."
**AI/backend would need:** (a) precision on part 1 supports: the second read says several do not mention the part, so some supports may be mislabelled; (b) a part splitter that yields self-contained parts, so "from May 7, 2026." is not a fragment; (c) the sole contradicting card is "Undated", "not settled", a bylaws sentence about effectiveness on adoption. Whether that is a true contradiction is a labelling-quality question, not a UI one. If it is weak, the red verdict rests on one weak pin, and the product should say so ("1 passage, second read not settled") rather than hide it.

## 5. Open questions for owner
1. Is "worst part wins" the intended overall rule, and may the UI state it in one sentence?
2. Where should the passcode live (last field, or host-level gate)? It is a hackathon gate, but it is the first thing a judge sees.
3. When the only contradicting card is "not settled", should the verdict stay red? (Product decision; code owns status.)
4. Is cross-part dedupe of repeated supports (P6) in scope, or part-scoped relevance an AI-lane item for after 4 Nov?
