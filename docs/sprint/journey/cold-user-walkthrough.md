# Cold-user walkthrough (TC17 main, TC40 short)

Persona: someone at a company in a dispute, never seen ProofGraph. Page http://localhost:8502, desktop pane (~800x600, then emulated 1400x900) and 375px. Claim TC17: "Connors was continuously authorized to act as Interim CMO from May 7, 2026." plus 3 PDFs. Cached, $0 spent. Screenshots (9, 0.5 scale): docs/sprint/journey/cold/.
Method notes: PDFs attached by JS DataTransfer, served from a temporary CORS file server outside the repo (killed afterwards; a first attempt using a temp app/static folder failed because the running server did not serve it, and I deleted that folder). The first failed attempt submitted non-PDF bytes and got "No /Root object" errors; that was my harness, not the product. I read the result text through the iframe DOM as well as screenshots, because the result is a 2.5 MB iframe the page-text tool cannot see.

## Think-aloud log

### 1. Landing (01-landing.jpg)
Expected: a product name, one line saying what it does. Saw: left menu "New review" / "Packet app"; fields "Passcode", "Claim", "Evidence packet" ("Upload", "200MB per file • PDF, PNG, JPG"), button "Check the claim". Understood: I type a claim and attach files. Confused: no product name on the page (tab says "ProofGraph"), no sentence about what "checking" means, no example of a good claim, "Packet app" is unexplained. Next: type passcode, claim.

### 2. Entering claim
Textarea says "Press Cmd+Enter to submit form" only after clicking in; the button is still the obvious thing. Fine. No character guidance (one claim? several?). Nothing says a claim with "and" will be split.

### 3. Uploading (02-form-filled.jpg)
Files show as chips with truncated names ("IHP_Boa...026-14.pdf", "IHP_Byl...ficers.pdf", "IHP_GC_...cation.pdf"). Truncated names are a small problem: with real packets, filenames starting alike will be indistinguishable. Typing into the page while a rerun is happening duplicated my claim text once (typed text doubled) and the page reset the claim at one point. A real slow typist could hit this.

### 4. Waiting (03-after-submit-chips.jpg)
Cached, so it took ~5 s and I barely saw it. The button greyed out, then three green bars appeared: "IHP_Board_Resolution_2026-14.pdf: text PDF, 2 pages" (and the other two). Then the claim appeared with two small coloured tags, "Weakened Connors was continuously authorized to act as Interim CMO" and "Contradicted from May 7, 2026." Understood: the claim was cut into two pieces and each got a tag. I did not see any "working..." message, progress, or time estimate; I cannot say how a 2-minute live wait would feel.

### 5. Result top (04-result-top-narrow.jpg)
Order on the page: green file bars, the two tags, a "Download as one HTML file" button, then a dark panel starting with a big bold paragraph: "Claim part 1: 16 passages back it up and 1 casts doubt (IHP_Bylaws_Excerpt_Article_V_Officers.pdf, p1, no date found, second check confirmed). Claim part 2: 12 passages back it up and 1 goes against it (...p2, no date found, second check not sure)."
Then the heading "Goes against the claim", my claim repeated, then "Claim part 1 of 2: Casts doubt on the claim by 1 passage: ...pdf, p1" and "Claim part 2 of 2: Goes against the claim by 1 passage, second check not sure: ...pdf, p2".
First conclusion: "Goes against the claim", so my claim is NOT ok. But then 16 + 12 passages BACK it up and one each doubts. I cannot tell why 1 passage beats 28. The "One passage that goes against a claim is enough to count against it" sentence is far down in a footnote under the map, so I only learned the rule later. At the very top the tags say "Weakened" and "Contradicted" while the heading says "Goes against". Three different words for the verdict in three places.
Also: the "against" passage in part 2 is "Ratification shall be effective upon adoption of the ratifying resolution." The "doubt" passage is a general bylaw about board approval. As a layperson I cannot tell if that really contradicts "continuously authorized from May 7" without being told which date the board adopted the resolution (14 May) and that May 7 to 14 would then be unauthorized. The page never says that in a sentence. That reasoning is the whole answer and it is missing.

### 6. The map (05-desktop-map-cards-page.jpg, 08-mobile375-map.jpg)
Three rows: "Goes against it (0) none found", "Casts doubt (1) No date found [orange triangle]", "Backs it up (16)" with dates "7 May 2026 / 13 May 2026 / 14 May 2026" and circles, some solid green, some hollow, some with small numbers (5, 3, 4, 2). A dashed box: "Mentioned but not uploaded letter dated May 7, 2026 (cited in 4 places)". A legend sits UNDER the map: "Circle = backs it up, triangle = casts doubt, diamond = goes against it. Solid = second check confirmed, hollow = second check not sure. Dashed row = documents mentioned but not uploaded...". So without a legend: rows are readable by their titles; shapes are guessable (triangle = warning); solid vs hollow means nothing until you read the legend; the little numbered badges are never explained in the legend (they look like counts of stacked passages); dates on top suggest a timeline but the footnote says "Days run in order, not to scale", so the gaps between circles mean nothing. "Second check" is never defined for a newcomer: who did the first check? In part 1 the map has "Goes against it (0) none found" as the top row, which is the heaviest row, an empty line wasting prime space, and the actual problem passage is in the middle row with no date, off the timeline. The "No date found" lump is separated from the dated column, so the contradiction visually floats nowhere in time even though the whole dispute is about dates.
The most useful item, "Mentioned but not uploaded: letter dated May 7, 2026 (cited in 4 places)", is the real hole in the evidence (the appointment letter itself), but it is a small dashed line with no "you should upload this" message.

### 7. The cards
Under the map: collapsed groups "Casts doubt (1): 1 confirmed by the second check." (open), "Backs it up (16): 6 confirmed by the second check, 10 not sure." (open, with nested "Show all 16", "Also 2 similar passages on the same page", "10 not sure after the second check"). Each card: the quote in italics, a one-line paraphrase ("appointment require approval by resolution of Board"), then a grey mono line "IHP_Bylaws_Excerpt_Article_V_Officers.pdf p1 · condition · Depends on a condition · box pinned · Second check: confirmed." Words I cannot parse: "condition", "box pinned", "scope", "time". The two labels "Depends on a condition" and "Only true for a time period" are the actual reasoning but look like footer metadata. Cards for the same passage appear under part 1 and again under part 2, so the same document shows up twice and I wonder if I double-count.
Nested collapsed items inside collapsed groups ("Also 2 similar passages...") mean I must open three levels to see 16.

### 8. Finding the one passage that matters (06-click-link-highlight.jpg)
Good: clicking the file link "IHP_Bylaws_Excerpt_Article_V_Officers.pdf, p1" in the verdict opened the card and showed the real PDF page on the right with one orange highlighted block. That is the best moment in the product: I could see the exact sentence on the actual page. But: clicking a circle in the map first (a "backs it up" mark) lit up the board-resolution page where about 20 red/orange boxes covered nearly the whole page, so the highlight told me nothing. On desktop the PDF page is a small column (barely legible at my pane size) and I did not see a zoom or "open the PDF" control. The page image only appears on desktop; at 375px I saw no page image in the stretch I scrolled.
The link text is the filename plus ", p1": I can find the page, but it does not show the quote itself in the verdict block, so I must click to learn what the problem sentence is.

### 9. The end
Last things: "Mentioned but not uploaded: letter dated May 7, 2026 (cited in 3 places: ...)" for part 2, and "Text pages only; 32 passages in 3 documents examined; scans/images not read; may be incomplete. 15 matched passages were judged not to bear on this part by the labelling step." No "what should I do next" (upload the letter? talk to counsel?). "Download as one HTML file" button sits above the verdict, ahead of anything to read, and is unexplained.

### Mobile 375 (07, 08)
The result lives in an iframe about 343px wide inside the page, with its own scrollbar, plus content slightly wider than the frame (scrollWidth 359 vs 343): long filenames clip ("Officers.pd"). Double scrolling (page and iframe). The big first paragraph at this width is eight lines of filenames. A ">>" icon sits top left. Map stays readable. Dark panel inside a light page.

### Dark/light
The result panel was dark with an orange outline in one run and light in the TC40 run, same machine, no switch by me except toggling the emulation. The page shell stayed light in both. I could not tell what controls it; the surprise of a black box on a white page felt unfinished.

### TC40 (09-tc40-result.jpg)
Claim "The Bosch NDA allows ... outside consultants without written authorization." Result top: "0 passages back it up and 2 go against it (01_Bosch-Automotive-Service-Solutions-Mutual-Non-Disclosure-Agreement-7-12-17.pdf, p1, no date found, second check confirmed; 01_Bosch-...-17.pdf, p1, ...)" then "Goes against the claim". This one is clear: a red "Goes against the claim" pill, one diamond with a "2" badge, two empty rows. The sentence is shorter in meaning but the filename is printed twice, 85 characters each, making the first paragraph almost unreadable. The first card quote ("Recipient agrees to limit disclosure ... to employees and employees of Affiliates having a specific need to know") is labelled "Covers only part of what is claimed", which is a weak reason; I would need to be told in one line "the NDA lets you share only with employees and affiliates, not consultants".

## The 7 answers

1. In 10 seconds can I say whether the evidence backs the claim and why? Partly. I can say "against" (the heading says so) in 3 seconds. I cannot say why: the first paragraph is a pile of counts and filenames, and it says 16 and 12 passages BACK the claim, which reads as the opposite of the verdict. The reason (one bylaw passage says effective only upon adoption of the resolution, adopted 14 May, so May 7-14 is not covered) is nowhere in plain words.

2. Can I read shapes/rows/fill/columns without a legend? Rows: yes, titles are literal. Shapes: triangle/diamond/circle only by guess. Solid vs hollow: no. Numbered badges: no (and not in the legend either). Date columns: they look like a timeline but are not to scale, and "No date found" is a separate lump. The legend exists but is below the map in small grey type and also contains the single most important rule ("One passage that goes against a claim is enough").

3. Can I tell which documents the findings come from and open the exact passage? Yes, mostly. Each card names the file and page, the verdict links jump to the card, and the right-hand PDF page shows a highlighted box. Weaker: the verdict block gives only the filename, not the sentence; clicking a "backs it up" circle highlighted so many boxes that it was useless; I never found a zoom or "open PDF".

4. What would I tell my boss after 2 minutes? "The tool says our claim is contradicted. It's not that nobody supports it: documents show Connors was appointed by letter on May 7 and the Board ratified on 14 May, but a bylaw passage says ratification takes effect only when the resolution is adopted, which would leave May 7-14 uncovered. It also notes the May 7 appointment letter itself wasn't in what we uploaded. I'd want legal to look at that and we should find the letter before we say 'continuously'." Honest caveat: I only got that by piecing together the "against" card, the dates on the map and the 'not uploaded' note myself; the page did not say it.

5. Words I didn't understand: "Weakened", "Contradicted" (vs "Goes against" vs "Casts doubt"); "second check" / "second check not sure" / "confirmed"; "box pinned"; "condition", "scope", "time" tags; "labelling step"; "matched passages" and "not about this part are hidden"; "Packet" ("Packet app"); "text PDF"; "Claim part 1 of 2" (why did my sentence become two claims?); "passages" (vs quotes/sentences); "similar passages on the same page"; "inferred from the text".

6. Expected but missing: one plain sentence of the reasoning under the verdict; which claim part is which (the two parts are never shown as their own words, only "Claim part 1 of 2"; the split fragments are just "Connors was continuously authorized to act as Interim CMO" and "from May 7, 2026" with no explanation); a "what to do next" (upload the missing letter); a product name/explanation on the landing; a clear confidence or how sure the tool is; ability to zoom/open the original PDF; an obvious order "verdict, why, evidence".

7. Untrustworthy / cluttered / misordered: (a) The verdict heading is below the file bars and tags and above a long bold block of counts: the counts come BEFORE the plain sentence, and the heading "Goes against the claim" comes after the counts. Reading order is numbers, then verdict, then claim parts, then map, then cards: I want verdict, why, map, cards. (b) Three vocabularies for the same verdict in the same screen. (c) The map is above the cards but its legend is below it and the cards' tags (condition/time) that carry the reasoning are tiny footers. (d) The empty row "Goes against it (0) none found" is shown first in part 1, so the thing that matters is the middle row. (e) "16 back it up" next to "against" feels like a contradiction; it reads untrustworthy until the one-passage rule is found in a footnote. (f) Long filenames printed in full in the headline paragraph (especially Bosch, twice). (g) Dark panel in light shell, internal scrollbar, clipped text at 375px. (h) Download button before any content.

## Ranked problems

P1 (H) Verdict has no plain reason.
Text: "Claim part 1: 16 passages back it up and 1 casts doubt (...)" then "Goes against the claim".
Newcomer lost: numbers say the claim is mostly supported but the heading says against; no sentence explains which fact breaks it. I can only get there by reading cards and map dates.
Wished: one plain sentence under the verdict: what is established, what breaks it, and which dates.

P2 (H) Counts and filenames lead the page, the verdict comes second.
Text: bold block beginning "Claim part 1: 16 passages back it up..." sits above "Goes against the claim".
Lost: first thing I read is a string of numbers and a long filename; headline is third. TC40 prints an 85-character filename twice.
Wished: verdict first, short; evidence counts and filenames as supporting detail.

P3 (H) The "one passage is enough" rule is buried.
Text: "One passage that goes against a claim is enough to count against it." inside the small legend under the map.
Lost: this single rule explains why 16 supporting passages lose; I only found it by reading all the small print.
Wished: said next to the verdict, in normal-size type.

P4 (H) Conflicting verdict words.
Text: "Weakened" / "Contradicted" (tags above), "Goes against the claim" (heading), "Casts doubt on the claim" (part 1 tag).
Lost: is part 1 doubtful or contradicted? Are "weakened" and "casts doubt" the same? Which one is the verdict?
Wished: one vocabulary, one overall verdict, each part's verdict labelled the same way.

P5 (H) Map legend is below the map and does not cover everything.
Text: "Circle = backs it up, triangle = casts doubt, diamond = goes against it. Solid = second check confirmed, hollow = second check not sure."
Lost: shapes/fills meaningless first; the small numbered badges (5, 3, 4, 2) are not explained at all; "Days run in order, not to scale" kills the timeline reading.
Wished: legend before or with the map; every symbol explained; badges explained.

P6 (H) Highlight on the page image can cover the whole page.
Text: clicking a "backs it up" circle shows the Board Resolution page with ~20 boxes over nearly all text.
Lost: "open the exact passage" turns into "here's the page, good luck". The single-passage highlight on the Bylaws link did work.
Wished: only the clicked passage highlighted; others toned down.

P7 (M) "Second check" is never explained.
Text: "second check confirmed", "second check not sure", "Not sure means the second check, which sees only the quote and the part, did not reach the same label."
Lost: who/what ran a second check, and does "not sure" mean I should ignore the finding? In part 2 the single "against" passage is "not sure", which should alarm me but doesn't say so.
Wished: say in one line what it means for my decision.

P8 (M) Map ordering and an empty row up top.
Text: "Goes against it (0) none found" is the first row in part 1.
Lost: the key finding is the middle row and is undated, floating away from the dated timeline.
Wished: put what matters first, hide empty rows or compress them, show why a passage has no date.

P9 (M) Card footers carry the reasoning but look like metadata.
Text: "... p1 · condition · Depends on a condition · box pinned · Second check: confirmed."
Lost: "condition/time/scope" and "box pinned" are jargon; "Depends on a condition" and "Only true for a time period" are the actual reasons.
Wished: reasoning as a readable line; drop internal words.

P10 (M) "Mentioned but not uploaded" is understated.
Text: dashed row "Mentioned but not uploaded letter dated May 7, 2026 (cited in 4 places)".
Lost: this is the biggest gap in my evidence and the page doesn't say what I should do.
Wished: a clear "missing document: upload it" line near the verdict.

P11 (M) Claim splitting is unexplained.
Text: "Claim part 1 of 2", "Claim part 2 of 2" and the tag fragments "Connors was continuously authorized to act as Interim CMO" / "from May 7, 2026."
Lost: why did my one sentence become two, and what exactly is part 2? The fragments show only as coloured tags.
Wished: show each part as its own labelled sentence with its own verdict.

P12 (M) Landing explains nothing.
Text: "Passcode / Claim / Evidence packet / Check the claim", menu "New review", "Packet app".
Lost: product name, purpose, what makes a good claim, what "Packet app" is.
Wished: a sentence and an example.

P13 (M) Mobile 375: iframe inside page, double scroll, clipped filenames.
Text: "(IHP_Bylaws_Excerpt_Article_V_Officers.pd" cut off; content wider than the frame.
Wished: one scroll, text wraps, filenames shortened.

P14 (L) Dark panel inside light shell, and theme inconsistency.
Text: black result block with orange outline on a white page (TC17 run); light result for TC40.
Lost: looks unfinished; I wasn't sure it was the same product.

P15 (L) "Download as one HTML file" button above everything.
Lost: appears before any content, unexplained.

P16 (L) Truncated file chips and a typing glitch.
Text: "IHP_Boa...026-14.pdf"; typing during a rerun doubled my claim text once.
Lost: can't tell similar files apart; a claim can get garbled.

P17 (L) Duplicate cards for the same passage under part 1 and part 2.
Lost: do I count it twice?
