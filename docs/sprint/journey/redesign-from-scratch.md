# Evidence view, redesigned from scratch

Status: proposal, no code. Facts: TC17 and TC40 from `cold-user-walkthrough.md`; data shape from `tests/test_evidence_map.py`.

## 1. The reader's six questions, in order

| # | Question | The one region that answers it |
|---|---|---|
| 1 | Is my claim OK? | **Verdict band** (once, top) |
| 2 | Which part of it fails, and on what exact words? | **Parts**, worst first, the deciding passage open |
| 3 | What backs it up? | **Backs it up** column of each part |
| 4 | What is missing? | **Not uploaded** block (after the parts) |
| 5 | Where exactly does that come from? | **Open passage**: quote plus the page with one box |
| 6 | Can I trust it, what was read? | **Footer** (scope, text pages only) |

Nothing else is on the page. The verdict word appears once, in the band. Parts carry their own word on their own header (same three words: Backs it up, Casts doubt, Goes against).

## 2. Three structurally different concepts

**A. Argument ledger (tree).** Claim at the top, its parts as branches, each branch splits into *Goes against / Casts doubt* on the left and *Backs it up* on the right. Every passage is one text row. Idea borrowed from Kialo: thesis on top, pros and cons hang beneath, position tells direction ([Kialo layout](https://blog.kialo-edu.com/?p=5482), [Kialo colour/position](https://feeldothink.org/p/colour-coded-discussion-diagrams-in-kialo/)). Kialo's known weakness is lost context deep in the tree; we stop at depth 2 (claim, part, passage).

**B. Evidence matrix.** Rows = documents, columns = claim parts, cell = stance glyph. Standard in legal practice: issues against exhibits, support/undermine marked in cells, gaps flagged ([Nextpoint chronology and evidence](https://support.nextpoint.com/hc/en-us/sections/17155307762189-Litigation-Chronology-and-Evidence), [fact matrix](https://gotranscript.com/en/blog/fact-matrix-from-transcripts-evidence-grid-example)). Strong for "which document says what". Weak here: a cell holds many passages, so it shows a count or a glyph and the count starts to decide; the exact sentence is two clicks away; 3 documents by 2 parts is an almost empty grid.

**C. Coverage timeline.** The claim's period against the dates the documents cover, so gaps show. It would make the TC17 story (7 to 14 May) visible. Rejected as the base: only date claims have a period (TC40 has none), about half the passages are undated or unconfirmed so half the evidence sits off the axis, and dates are inferred, not legal dates. It is the old map's mistake in a nicer coat.

### Comparison

| Test | A Ledger | B Matrix | C Timeline |
|---|---|---|---|
| Structured, logical, easy to follow (owner's words) | Claim, part, passage reads like the claim itself | Reads as a grid, not as reasoning | Reads only for date claims |
| Needs a legend | No: column titles are the words | Yes: glyphs in cells | Yes: axis, marks |
| One passage is enough, visible | Yes: the against row sits first and open | Hidden in a cell | Hidden among marks |
| Counts stay proportional | Equal columns, list is capped | Cell counts dominate | Cluster size dominates |
| Works at 375px | Stacks to one column | Needs horizontal scroll | Needs scroll |
| Honest with undated passages | Row says "No date" | Fine | Off-axis lump |
| 10-second cold read | Passes (see section 4) | Fails: "what is this grid?" | Fails |

## 3. Decision: A, the argument ledger

Why: it is the only structure whose shape is the product's logic (a claim stands or falls part by part, and one passage against is enough), so no legend or rule-reading is needed. It uses the full width, collapses to one column on a phone, and every item is a text row that opens one passage.

Keep from the current page: the card (quote, document, page), the pinned quote, the page image with exactly one box, the "referenced but not supplied" data, and the scope footer text. **Delete:** the lanes-and-marks map, shapes, fill, numbered badges, date columns, the legend, the loose red sentence, the verdict in three places, the bold counts paragraph, nested collapsed groups, the "Download" button above the verdict (move to footer), and the two-column page-image-beside-chart split. Dates stop being an axis and become words on a row.

### Rules of the page
1. One word per concept: **claim**, **part**, **passage**, **Backs it up / Casts doubt / Goes against**, **Not uploaded**, **Second check** (explained once, where first used, not in a legend).
2. Meaning never by colour alone: each stance has its word, a glyph (check, !, cross) and its column position; colour is a bonus.
3. Parts sorted worst first (Goes against, Casts doubt, Backs it up), numbered by their claim order ("Part 2 of 2"), so the top of the page is where the problem is. Tradeoff: order differs from the claim; the number and the part's own words keep it clear.
4. The deciding rule is said once, beside the verdict, in body size: "One passage that goes against a claim is enough."
5. Columns are equal width. The Backs it up list is capped (first 4 rows, grouped by document, then "Show 12 more"). The against column is never capped and its first row is open.
6. A row with no date says "No date". A row the second check did not confirm says "Not confirmed". Within a list: confirmed and dated first, then the rest under a plain subhead.
7. Empty side collapses to one line ("None found"), never an empty half.

## 4. Wireframe, desktop (about 1200px wide, full width), TC17

```
ProofGraph  ·  Review                                                  
=============================================================================================
Your claim   "Connors was continuously authorized to act as Interim CMO from May 7, 2026."
+-------------------------------------------------------------------------------------------+
|  X  GOES AGAINST YOUR CLAIM                                                               |
|  One passage that goes against a claim is enough. It is in Part 2, below.                 |
|  1 document the passages cite was not uploaded  (see Not uploaded)                        |
+-------------------------------------------------------------------------------------------+

PART 2 of 2   "from May 7, 2026"                                      X  Goes against
+--------------------------------------------+----------------------------------------------+
| GOES AGAINST IT (1)                        | BACKS IT UP (12)                             |
| X "Ratification shall be effective upon    | v Board Resolution 2026-14 (7)               |
|    adoption of the ratifying resolution."  |   v "...resolved 14 May 2026..." p1  14 May  |
|    Bylaws Excerpt . p2 . No date           |   v "...effective 13 May..."  p1     13 May  |
|    Not confirmed (second check not sure)   |   v "..."                    p2  No date     |
|    [ Open this passage ]                   |   v "..."                    p2  No date     |
|                                            |   Show 3 more                                |
|                                            | v Bylaws Excerpt (5)   Show                  |
|                                            |   Not confirmed (4) - the second check did   |
|                                            |   not reach the same label   Show            |
+--------------------------------------------+----------------------------------------------+

PART 1 of 2   "Connors was continuously authorized to act as Interim CMO"   !  Casts doubt
+--------------------------------------------+----------------------------------------------+
| CASTS DOUBT (1)                            | BACKS IT UP (16)                             |
| ! "...appointment requires approval by     | v Board Resolution 2026-14 (9)  ... first 4  |
|    resolution of the Board..."             |   rows, then  Show 12 more                   |
|    Bylaws Excerpt . p1 . No date           | No date found (6)   Not confirmed (10)       |
|    Confirmed                               |   each a collapsed subhead, one line         |
|    [ Open this passage ]                   |                                              |
+--------------------------------------------+----------------------------------------------+

NOT UPLOADED   (documents the passages cite but you did not give us)
+- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -+
 ?  Appointment letter dated May 7, 2026 - cited in 4 passages        [ Show the 4 passages ]
 Add it to the packet and run the review again.
+- - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -+

Text pages only. 32 passages in 3 documents read. Scans and images not read. May be incomplete.
Dates are inferred from the text, not legal dates.                         [ Download as HTML ]
```

Opened passage (replaces nothing, expands under the row, full width of its column on phone, left half of the part on desktop):

```
| X "Ratification shall be effective upon adoption of the ratifying resolution."            |
|   Bylaws Excerpt . page 2 . No date found . Not confirmed                                 |
|   +----------------------+                                                                |
|   |  page 2 image        |   one box, only this passage                                  |
|   |  [=== boxed ====]    |   [ Close ]  [ Next passage > ]                               |
|   +----------------------+                                                                |
```

## 5. Wireframe, mobile (375px, one scroll, no iframe)

```
+-------------------------------------+
| Your claim                          |
| "Connors was continuously           |
|  authorized to act as Interim CMO   |
|  from May 7, 2026."                 |
| X GOES AGAINST YOUR CLAIM           |
| One passage that goes against a     |
| claim is enough. It is in Part 2.   |
| 1 cited document not uploaded       |
+-------------------------------------+
| PART 2 of 2  "from May 7, 2026"     |
| X Goes against                      |
| GOES AGAINST IT (1)                 |
| X "Ratification shall be effective  |
|   upon adoption of the ratifying    |
|   resolution."                      |
|   Bylaws . p2 . No date             |
|   Not confirmed                     |
|   [ Open this passage ]             |
| BACKS IT UP (12)                    |
| v Board Resolution (7)  [Show]      |
| v Bylaws (5)            [Show]      |
+-------------------------------------+
| PART 1 of 2  ...  ! Casts doubt     |
| ...same two blocks, stacked...      |
+-------------------------------------+
| ? NOT UPLOADED                      |
|   Appointment letter, May 7, 2026   |
|   cited in 4 passages  [Show]       |
+-------------------------------------+
| Text pages only. 32 passages ...    |
+-------------------------------------+
```
File names wrap or show a short form (first 24 characters plus the page); full name on open. Block order is the same as desktop, so there is nothing to relearn.

## 6. Wireframe, TC40 (one part, nothing backs it)

```
Your claim  "The Bosch NDA allows ... outside consultants without written authorization."
+-------------------------------------------------------------------------------+
| X  GOES AGAINST YOUR CLAIM                                                    |
| One passage that goes against a claim is enough. It is below.                 |
+-------------------------------------------------------------------------------+
PART 1 of 1   (the whole claim)                                  X Goes against
| GOES AGAINST IT (2)   Bosch NDA 7-12-17.pdf                                   |
| X "Recipient agrees to limit disclosure ... to employees and employees of     |
|    Affiliates having a specific need to know"  p1 . Confirmed  [Open]         |
| X (second passage, p1)                                         [Open]         |
| Nothing in the documents backs it up.                                         |
Text pages only. ...
```
A one-part claim hides the "Part 1 of 1" line when it adds nothing. The long file name appears once, as the group name.

## 7. Data to visual

| Data | Visual |
|---|---|
| Overall verdict (code) | Band word and glyph, once |
| Claim part text | Part header, quoted in full |
| Part verdict (code) | Word and glyph at the right of the part header |
| Card.relation | Which column; glyph and word at row start |
| Card.quote | The row text (first line); full on open |
| Card.doc, page | Row meta "Bylaws . p2"; group name when grouped |
| Card.date or none | Words ("14 May 2026") or "No date"; never an axis |
| Second-check state | "Confirmed" or "Not confirmed" at row end; "Not confirmed" rows sit in a collapsed subhead on long lists |
| Merged duplicates | One row, "Same passage on 2 pages" is not shown; the row says "x2 same passage" only if merged on one page, and opens one box |
| Referenced but not supplied | Dashed "Not uploaded" block; count = how many passages cite it; "Show the 4 passages" lists their verbatim quotes |
| Passage in two parts | Row in each part; opens the same single box |
| Scope text | Footer |

## 8. Honest handling, summarised
- **Undated:** each row says "No date"; long lists get a "No date found (n)" subhead. No mystery column, no scale.
- **Not confirmed:** a word on the row, never hidden; for the one against passage it is shown right under the quote.
- **Missing letter:** its own block with the action sentence, plus a one-line flag in the band so it is seen first.
- **16 and 1:** equal columns, capped list, against first and open; the rule sentence says once why 1 is enough. Counts appear only in column titles, never in the band.

## 9. Acceptance checks
1. Cold read: a stranger, 10 seconds, says "My claim goes against the documents because one passage says ratification only takes effect on adoption of the resolution." No explanation given.
2. The verdict word appears exactly once outside part headers; no other verdict vocabulary exists on the page.
3. The page has no legend, no tooltip needed, no shape or colour-only meaning (grayscale screenshot still readable).
4. Every row opens its passage; the page image shows exactly one box; keyboard: Tab to row, Enter opens, Escape closes.
5. At 375px: one scroll, no horizontal scroll, no clipped file name; at 1440px: no column narrower than 400px, no empty half.
6. Dark mode: all text 4.5:1, glyph and word survive.
7. Part 2's against passage is visible without scrolling at 1440x900 and within one scroll at 375px.
8. Verdict, the rule sentence and counts are identical to code output: UI test that no verdict word is derived in JS and that the against-first rule is in the markup, not computed by the view.

## 10. Must NOT be shown
No confidence or percentage; no filters; no AI or model-written sentences (the only sentences are the fixed rule, fixed labels and verbatim quotes); no timeline or "not to scale" axis; no marks with numbered badges; no internal words (condition, scope, box pinned, labelling step, matched passages); no count in the verdict band; no duplicate verdict; no full-page highlight of many boxes; no nested collapses beyond one level.

## 11. Pre-mortem (what could go wrong)
- "16 vs 1 feels unfair": the rule sits next to the verdict; the against column is first and open.
- Worst-first order confuses: numbered "Part 2 of 2" and quoted part text.
- "Not confirmed" read as "ignore it": the footer and the subhead say what it means; the against row shows it without hiding the passage.
- Quote rows are truncated badly: first line plus ellipsis, full on open.
- Lost date story (7 to 14 May): see backend note; until then the two dated passages are readable in rows.
- A mislabelled relation: the reader sees the exact passage and judges for themselves.

## 12. Notes for AI/backend (not this sprint)
- A code-built "dates in play" line (claim date versus the dates found on the deciding and nearby passages, e.g. 7 May vs 14 May) would carry the TC17 reasoning without a model sentence; needs date extraction with a source passage per date.
- Return the deciding passage id and part order from code, so the view sorts nothing.
- A `referenced` item should carry the list of citing card ids (quote shown on "Show the 4 passages").
- Short display name for documents; part text as the user's own words for each split.
- Later: a dated sort toggle, once most passages carry dates.

## Sources
[Kialo](https://blog.kialo-edu.com/?p=5482), [Kialo layout](https://feeldothink.org/p/colour-coded-discussion-diagrams-in-kialo/), [Nextpoint](https://support.nextpoint.com/hc/en-us/sections/17155307762189-Litigation-Chronology-and-Evidence), [fact matrix](https://gotranscript.com/en/blog/fact-matrix-from-transcripts-evidence-grid-example), [fact-check presentation study](https://ar5iv.labs.arxiv.org/html/2308.10220). Search found no authoritative verdict-first fact-check layout standard; this part rests on the cold-user log.
