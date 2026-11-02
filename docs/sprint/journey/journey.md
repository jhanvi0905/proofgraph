# Customer journey, evidence map flag on (PROOFGRAPH_EVIDENCE_MAP=1), wave 1 state

Captured 2 Nov 2026, branch feat/evidence-map-ui at b244aae, page "New review" (the default page), desktop pane about 800x600, scale 0.5-0.6 screenshots (JPEG).
Inputs: TC17 claim "Connors was continuously authorized to act as Interim CMO from May 7, 2026." with the 3 PDFs of its Evidence Packet (live review, about $0.032); TC40 Bosch NDA claim with its 1 PDF (cache hit, $0).
Files were attached by a JS DataTransfer into the uploader (the browser tool cannot open a native file dialog); PDFs were served same-origin from a temporary app/static folder, since deleted. Passcode was a made-up test value.
Not built yet (so absent): grouped or collapsed layout, timeline strip, Pending chip, stage strip. Everything is one long flat list of cards inside an iframe.

## 1. Landing and passcode
File: 01-landing-passcode-form.jpg
Sees: sidebar "New review" / "Packet app"; one form: "Passcode" (password box), "Claim" (text area), "Evidence packet" (uploader: "Upload", "200MB per file - PDF, PNG, JPG"), button "Check the claim".
Must do: type passcode, claim, attach files, press the button. No title, no one-line explanation of what the tool does, no hint of what a good claim looks like.
Friction: first screen has no heading or purpose line (the packet-app page has a JOB_LINE; this page does not). Passcode sits above the claim, so the first thing asked is a secret. Sidebar "Packet app" is unexplained. The form is only the top 55% of the screen; the rest is empty until a run.

## 2-3. Writing the claim and adding files
File: 02-03-claim-and-files-filled.jpg
Sees: claim in the text area with hint "Press Cmd+Enter to submit form"; three file chips with truncated names ("IHP_Boa...026-14.pdf", "IHP_Byl...ficers.pdf", "IHP_GC_...cation.pdf") and sizes (107.3KB, 142.6KB, 92.6KB).
Must do: nothing further; the form submits as one.
Friction: names are truncated, so three similar files are hard to tell apart. No check that the files were read until after submit. Typing the claim triggers no feedback; the file-ingest lines only appear after pressing submit.

## 4. Waiting while the review computes
Files: 04-waiting-parts-checking.jpg, 05-parts-resolved-chips.jpg
Timeline (TC17, live): click, about 1 s nothing visible (page greys the button); at about 3 s three green boxes appear: "IHP_Board_Resolution_2026-14.pdf: text PDF, 2 pages", "IHP_Bylaws_Excerpt_Article_V_Officers.pdf: text PDF, 3 pages", "IHP_GC_Memo_Appointment_Ratification.pdf: text PDF, 3 pages", plus two grey "Checking" chips, one per part: "Connors was continuously authorized to act as Interim CMO" and "from May 7, 2026.". Chips flip to "Weakened" and "Contradicted" together at roughly 15-20 s (not seen between 8 s and about 17 s; screenshots were at about 3, 8, 21 s). The result viewer appeared about 25 s after click. TC40 (cached) finished in under 10 s with the same pattern.
Friction: the wait text is only the grey "Checking" chip. No stage names, no count ("7 of 19"), no "Results fill in as checks finish". The claim was split into two parts without telling the customer; the second part "from May 7, 2026." reads as a fragment. The only progress indicator is Streamlit's tiny top-right "Running" state. Nothing says the result is not final while chips are grey. Chips for both parts flipped at once, so the staging is not meaningful to the viewer.

## 5. Results, top of page
File: 06-results-top-verdict-part1.jpg (page scrolled so the viewer is at the top)
Sees, outside the viewer: a "Download as one HTML file" button above an iframe 900 px tall (scrolls inside itself).
Inside: heading "Contradicted", claim text; then part 1 chip "Weakened Connors was continuously authorized to act as Interim CMO"; part summary line "16 supports, 0 contradicts, 1 weakens, 15 irrelevant (hidden), from 3 of 3 documents; 1 document referenced, not supplied"; coverage note "Text pages only; 32 passages in 3 documents examined; scans/images not read; may be incomplete. 15 matched passages were judged not to bear on this part by the labelling step. Dates are inferred from the text, not legal dates."; then card 1 open in full (about 20 lines of resolution text).
Friction: overall verdict "Contradicted" and part 1 "Weakened" with 16 supports sit together and look inconsistent until you read down to the contradicting card at the end (part 2 holds the single contradicts). The verdict is not explained anywhere near the chip. Two scroll containers (page and iframe) fight on trackpad. Part 1 summary says "1 weakens" but the weakens card is near the bottom of part 1, 4,000 px down.

## 6. Second-read badges, referenced-but-unsupplied markers
File: 07-results-badges-referenced-marker.jpg
Sees per card: relation label and date ("Supports  May 7, 2026 - inferred from in passage"), italic quote, a short phrase, then source line "0-IHP_Board_Resolution_2026-14.pdf p1 - box pinned - Second read of this quote alone: confirmed." or "...: not settled." followed by a bordered note "The second read of this quote alone found it does not mention this part, while this card is labelled as support. It sees only the quote and the part."
Referenced marker: dashed box "Referenced, not supplied: letter dated May 7, 2026 (cited in 0-IHP_Board_Resolution_2026-14.pdf p1)".
Counts, part 1: 17 cards; 7 "confirmed", 10 "not settled"; 4 referenced markers, all the same "letter dated May 7, 2026" (cited at Board Resolution p1, GC Memo p3, p2, p2: the duplicate p2 is shown twice). Part 2: 13 cards; 11 confirmed, 2 not settled; same 4 markers repeated.
Friction: badge wording is the new neutral copy, no red; but 10 of 17 cards in part 1 carry the long explanatory paragraph, which doubles card height and repeats nearly verbatim. "not settled" with "does not mention this part" can read as the card being wrong. Date label glitch: "inferred from in passage" (a word is missing). Filenames carry a numeric prefix ("0-", "2-") that is not the customer's name. The same unsupplied letter marker appears 4 times in each part, 8 times total.

## 7. Undated handling and part boundary
File: 08-results-undated-separator-part-boundary.jpg
Sees: a bare "Undated" separator line, then the card "Weakens  Undated" (bylaws quote about approval by resolution of the Board, "Second read of this quote alone: confirmed."). Part 2 starts with a red "Contradicted" chip, "from May 7, 2026.", the line "Sources disagree on this part.", then its own summary "12 supports, 1 contradicts, 0 weakens, 20 irrelevant (hidden), from 3 of 3 documents; 1 document referenced, not supplied".
Friction: "Undated" is a bare word with no explanation (the explanation is only in the coverage note far above). The sole contradicting card for the whole claim is the last card of part 2 (an "Undated" card, "Ratification shall be effective upon adoption of the ratifying resolution.", bylaws p2, "not settled") at about 7,600 px down, so the evidence behind the red verdict is last. Part 1 and part 2 repeat nearly the same 12-16 supporting quotes.
File: 09-results-part2.jpg (part 2 first card, a repeat of the board resolution quote, in full).

## Scroll length (TC17)
Desktop (iframe 900 px high; pane 768 px): viewer content 8,592 px total = 9.5 iframe heights = about 11 pane viewports. Part 1 4,493 px (5.0 iframe heights, about 5.9 viewports), part 2 3,286 px (3.7 / 4.3). 30 cards in all, 0 collapsible sections, 0 `<details>`. Inside a 900 px box the person scrolls the box, then the page.
Mobile 375 px (13: 12903 px): total 12,903 px; part 1 7,314 px (about 9.0 viewports of 812), part 2 5,031 px (about 6.2). No horizontal overflow (viewer width 343 px, content 343 px). Nested iframe scroll continues to be a trap on touch.
TC40 (cached): 1,505 px total, 2 cards (both "Contradicts", "confirmed"), 0 referenced markers, 38 irrelevant hidden; fits in about 1.7 iframe heights.

## 8. Dark mode
Files: 10-dark-part2-cards.jpg, 11-dark-results-top.jpg
Result: the viewer iframe follows prefers-color-scheme (body rgb 22,22,22) but the Streamlit page around it stays light (config pins base = "light"), so a dark panel sits inside a light page with the light sidebar. Contrast inside the viewer is readable; coloured card borders (green/orange) and red chip hold. Friction: mixed light/dark page; the "Download as one HTML file" button and chips stay light.

## 9. 375 px mobile
Files: 12-mobile375-results-top.jpg, 13-mobile375-card-badges.jpg
Result: the form and viewer reflow, no horizontal scroll. Friction: sidebar collapses to ">>" with a large empty top band; part chips wrap; the source line breaks awkwardly ("2-" then the filename on the next line); each card is about 1.2 viewports with the badge note, so reading 17 cards is long. The 900 px iframe is taller than the screen, so there are two nested vertical scrolls.

## 10. TC40 result
File: 14-tc40-results-top.jpg
Sees: a green box "01_Bosch-Automotive-Service-Solutions-Mutual-Non-Disclosure-Agreement-7-12-17.pdf: text PDF, 4 pages", a "Contradicted" chip, the claim, the download button, then the viewer: heading "Contradicted", summary "0 supports, 2 contradicts, 0 weakens, 38 irrelevant (hidden), from 1 of 1 documents", the same coverage note, then 2 cards. Short and clear; both cards "Second read of this quote alone: confirmed." The part chip and the page heading repeat the claim three times.

## Cost
Spent $0.0315 (ledger 2.71144 -> 2.74298), all TC17 live. TC40 was cached ($0). Cap used: SPEND_LIMIT_USD=2.81.
