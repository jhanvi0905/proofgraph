# Results page arrangement v2 (product team decision)

Reader's question, in order: What is the answer? Why? Where exactly is the passage? Everything below serves that order. Source: cold-user-walkthrough.md (P1..P17). Facts below are from that log only.

## 1. The single hierarchy (top to bottom)

1. **Verdict block** (first thing; nothing above it but the claim text): claim in the reader's words, ONE verdict chip, one rule line.
2. **Why line**: the deciding passage as a verbatim quote, document short name, page. Code picks it: the strongest opposing passage (if several, the first by confirmed-then-page order); for "backs up", the first confirmed backing passage. The quote is a link that opens the card and the page image.
3. **Gap line** (only if a mentioned-but-not-uploaded document exists): facts only.
4. **Parts**: one row per claim part, each part shown as its own words plus its own chip. Collapsed to one line if only one part.
5. **Legend (one line + marks key), then the stance map** per part.
6. **Cards**, opened by the map or "Show all".
7. **Footer detail**: counts, hidden-passage count, "text pages only" caveat, Download.

After 10 seconds: chip + why line. After 1 minute: click the quote, see the one boxed passage on the page.

**Names:** display name = code-derived, deterministic (strip extension and shared prefix, e.g. `IHP_Bylaws_Excerpt_Article_V_Officers.pdf` shows as `Bylaws Excerpt Art. V`; Bosch shows as `Bosch NDA 7-12-17` style truncation in the middle, never at the end). Full filename in `title` and in the card. Same rule for file chips (P16). No counts and no filename-lists in the verdict block.

## 2. One vocabulary

| Concept | Only words used | Appears in |
|---|---|---|
| Verdict | **Goes against the claim / Casts doubt on the claim / Backs up the claim**; states: Nothing found about this, Not enough to decide, Still checking | page title chip, per-part chip, lane header uses the short form "Goes against it / Casts doubt / Backs it up", card badge |
| Rule | "One passage that goes against a claim is enough to count against it." | plain 16px line directly under the verdict chip, only when the verdict is Goes against; removed from the caption |
| Second check | "Second check: confirmed / not sure", defined once in the key as "A second look at this passage alone. Not sure means it did not reach the same label; the finding still counts." | key + card badge |

Removed everywhere: Weakened, Contradicted, Supported (the old tags above the verdict), "box pinned", condition/scope/time as footer words, "labelling step", "matched passages", "Packet", "text PDF".

## 3. Legend and map

- The key sits **above** the map in normal-size type, three short rows: Shapes (circle backs it up, triangle casts doubt, diamond goes against it); Fill (solid = second check confirmed, hollow = not sure); Number on a mark = "N passages on that day, click to see them"; Dashed row = "mentioned in your documents but not uploaded"; Columns = "Dates are in order, not to scale. Dates come from the text."
- Lane order: **Goes against it, Casts doubt, Backs it up** (strongest first). An empty lane collapses to one grey line "Goes against it: none found" under the other lanes, never first.
- Columns: dated columns, then "No date found" with one line: "These passages state no date." The deciding passage always carries a ring (outline, not colour only) so it is findable.
- Cited-not-supplied row stays in the map, and is also promoted to the gap line (section 4).

## 4. Gap line

Fact sentence, code-built: `Not uploaded: letter dated May 7, 2026. Your documents mention it 4 times. It is the document that would settle this.` The last clause appears only when the missing document's date or name matches the claim's date or subject by code; otherwise omit it. No "you should" advice, no legal advice. Sits directly under the why line.

## 5. Click behaviour

One mark = one card = one boxed passage. A mark with a number badge opens a small list of its N cards; each item highlights one box. The page image shows only the clicked passage's box at full strength; any others on that page are not drawn (or 20% outline only if the engineer needs them). **Defect for the frontend engineer (P6):** repro from the log: run TC17, in part 1 click a solid green "Backs it up" circle dated 13 or 14 May; the Board Resolution page loads with about 20 red/orange boxes covering nearly the whole page. Expected 1 box. Check whether the click highlights every box on the page rather than the card's own box, or whether the passage's box coordinates are page-wide. Clicking the Bylaws p1 link in the verdict gave a correct single box; use that as the working reference.

## 6. Mobile order (375px)

Verdict chip, rule line, why quote (wraps, no clipping), gap line, parts, key (collapsed to a "How to read this" toggle is NOT allowed; show it, 4 lines), map stacked as lanes with "No date found" as a fourth row, cards. One scroll: render the result in the page, not an iframe (P13); `overflow-wrap:anywhere`. Marks and links at least 44px tap targets. Download sits last.

## 7. Cut

Cut from the top: bold counts paragraph, Download button, the Weakened/Contradicted tags, file bars (move to footer as one line "3 documents read"). Cut: duplicate cards for a passage under both parts (show once, labelled "also used for part 2"), nested collapsed groups deeper than one level (P17). Not this sprint: confidence, filters, AI summary, zoom control.

**Must NOT be shown:** any model-written sentence, a score or percentage, "likely/probably", advice on what to decide, the old words above, a green or "backs up" look while Still checking, a count in place of the verdict, a lane height or mark size that implies strength.

## 8. Problem table

| P | Decision | Lane |
|---|---|---|
| P1 | Why line: verbatim quote + doc + page under the verdict | UI |
| P2 | Verdict first; counts and filenames to footer; short names | UI |
| P3 | Rule sentence under the chip | UI |
| P4 | One verdict set (section 2) | UI + product-decision (done here) |
| P5 | Key above map, covers badge, second check, not to scale | UI |
| P6 | One box per click; defect to investigate | UI (engineer) |
| P7 | Second check defined once; says finding still counts; sole-opposer "not sure" gets a ringed mark and the line "Only one passage goes against it, and the second check was not sure" (code-built) | UI |
| P8 | Strongest lane first, empty lanes collapsed; No date found explained | UI |
| P9 | Card reasoning line = existing label text ("Depends on a condition") in body type, above the source line; drop internal words | UI |
| P10 | Gap line (section 4) | UI |
| P11 | Each part shown as its own words and chip; one line "We split your claim into parts" | UI |
| P12 | Landing sentence and example claim | product-decision (copy by UX writer), UI |
| P13 | Single scroll, no iframe, wrap | UI |
| P14 | One theme from system preference, shell and result match | UI |
| P15 | Download to footer, labelled "Download this result as one HTML file" | UI |
| P16 | Middle-truncated names with full-name title; block input edits during rerun | UI |
| P17 | Show a shared passage once | UI |

## 9. Wireframes (real facts from the log)

**TC17 desktop**
```
Claim: Connors was continuously authorized to act as Interim CMO from May 7, 2026.
[ GOES AGAINST THE CLAIM ]  One passage that goes against a claim is enough to count against it.
Why: "Ratification shall be effective upon adoption of the ratifying resolution."
     Bylaws Excerpt Art. V, p2 (no date found, second check: not sure)  <- link
Not uploaded: letter dated May 7, 2026. Cited 4 times. It is the document that would settle this.
Part 1  Connors was continuously authorized to act as Interim CMO   [Casts doubt on the claim]
Part 2  from May 7, 2026                                            [Goes against the claim]
How to read: o backs up  ^ casts doubt  <> goes against | solid=confirmed hollow=not sure
            number = passages that day | dashed = not uploaded | dates in order, not to scale
 Goes against it   (none found)  [part 1]
 Casts doubt (1)                  ^ No date found
 Backs it up (16)  7 May o  13 May o  14 May o(5)      ... dashed: letter May 7 (4)
[cards: Casts doubt open (1), Backs it up collapsed "Show all 16"]   [page image: one box]
Footer: 3 documents read. 32 passages examined, 15 hidden as not about this part. Download.
```
**TC17 mobile:** chip; rule line; why quote (wrapped); gap line; Part 1 row + chip; Part 2 row + chip; key; lanes stacked (Goes against none found / Casts doubt / Backs it up / No date found); cards; footer.

**TC40 desktop**
```
Claim: The Bosch NDA allows ... outside consultants without written authorization.
[ GOES AGAINST THE CLAIM ]  One passage that goes against a claim is enough to count against it.
Why: "Recipient agrees to limit disclosure ... to employees and employees of Affiliates
     having a specific need to know"  Bosch NDA, p1 (second check: confirmed)
Map: <>(2) Goes against it | Casts doubt: none found | Backs it up: none found
Cards: 2 open. Footer: counts, Download.
```
(Verdict word is the log's; no "consultants not allowed" sentence is written by us, the quote is the evidence. The card label "Covers only part of what is claimed" stays as code text.)

## 10. Acceptance checks (pytest or headless browser)

1. First visible element in the result (DOM order) is the verdict chip; no digit-run counts or `.pdf` precede it.
2. Exactly one verdict word set: the strings Weakened, Contradicted, Supported, "box pinned", "labelling step" appear 0 times in the result HTML.
3. Under the chip, for a Goes-against verdict, the rule sentence is present at font-size >= 16px and not inside the legend or footer.
4. The why line contains a quote that is a verbatim substring of the extracted source text of the cited page, plus the display name and page number.
5. The key precedes the map in DOM order and mentions every mark type: circle, triangle, diamond, solid, hollow, number, dashed, "not to scale", second check.
6. Lane order is against, doubt, backs; an empty lane is never first.
7. If a not-uploaded document exists, a gap line appears before the first part row and contains its name or date; with the flag off the output is byte-identical to the baseline.
8. Clicking any mark draws exactly 1 box on the page image (assert box count == 1); regression for the 20-box repro.
9. At 375px: `document.documentElement.scrollWidth <= 375`, no iframe in the result, no horizontal clipping; dark and light render with the same theme for shell and result; every mark and link reachable and activated by keyboard (Tab, Enter).
10. Cold-read test: show the top screen (no scroll) to 3 readers who have never seen the product; each states the result in one sentence that names "goes against / against" and the deciding document or quote. Pass at 3 of 3.
Also: meaning is never colour alone (shape + word + ring).

## 11. Notes for AI/backend (no work assumed)

- Code, not a model, should select the deciding passage and expose a "sole opposing passage" flag plus its second-check state; the line in P7 is built from it.
- If the missing document's date matches the claim's date, expose that match as a boolean for the gap line's last clause.
- Optionally expose per-claim-part text spans so part rows show their own words (P11); the log shows the fragments exist.
- Check that a passage's box coordinates are per-passage, not per-page (supports the P6 investigation).
