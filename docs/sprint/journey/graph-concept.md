# Graph concept: what Proof Graph can show as a graph

Customer job: see at a glance whether the evidence supports, weakens or contradicts the claim, trust it, and jump to the exact passage. Basis: product-review.md, journey.md, sprint note, scope, screenshots 06, 07 and 12.

## 1. Recommendation
- Build a **stance map** per claim part: three lanes (Contradicts, Weakens, Supports; strongest finding on top), one mark per card or merged group, a dated axis plus its own **Undated** column.
- It is a graph in the data sense (evidence plotted against the claim), not a node-link diagram. The lane position is the finding; the date axis only adds "when", and undated evidence is never hidden.
- Every mark is a button that reveals its card (sprint task 5). Marks never change status; code computes it. It replaces the sprint "timeline strip" (task 4) and is the same size of work.
- MVP is 2 to 3 days on the existing `_strip`/`reveal` plan. Later: a document lane view and a cross-part layout.
- Reason: with 30 cards where the 1 contradiction is last (about 7,600 px down), the customer needs the minority finding visible in the first screen. Lanes do that; a count chart or a tangled graph do not.

## 2. Concepts compared
| Concept | Customer value | Honesty risk | Effort | Fit with constraints |
|---|---|---|---|---|
| A. Stance map (lanes x date + Undated column) | High: verdict evidence and where it sits, one glance, every mark jumps to a card | Low if Undated is a visible column and inferred dates are marked | M, 2-3 days | Good: inline SVG, keyboard, no colour-only |
| B. Pure timeline of passages by date | Medium: good for "was X before Y" claims, weak for stance | High: about half the cards are undated, so it either drops them or invents a place | M | OK, but fails the honesty test alone |
| C. Claim-centred node-link (claim hub, spoke per passage) | Low: edges carry only one fact (the relation), so it is a star with no structure to read; research favours node-link only for topology and path tasks, which this is not | Medium: length and clustering look like weight | L (layout, labels at 375 px) | Poor: no dependency-free layout, hard on mobile |
| D. Evidence balance (bars or scale of counts) | Medium: fast, familiar | Highest: 16 supports visually outvote 1 contradiction; invites vote counting | S | Easy, but it breaks the product rule that one contradiction can decide |

## 3. Wireframes (TC17 part 2, schematic)
Desktop (width about 800 px). Shapes: square = supports, triangle = weakens, diamond = contradicts. Filled = second read confirmed, hollow = not settled.
```
Part 2  from May 7, 2026.                       [Contradicted]
1 contradicts, 0 weakens, 12 supports, 20 irrelevant (hidden)
                 Apr 2026   May 2026   Jun 2026 | Undated (not placed)
Contradicts  (1)                                 |   ◇o  <- hollow
Weakens      (0)   none                          |
Supports    (12)          ■ ■  ■4   ■            |   ■ ■o ■o 3
                          ^ day with 4: count    |
  - - ┆ referenced, not supplied: letter dated May 7, 2026 (cited in 4 places)
Dates are inferred from the text, not legal dates.
[click or Enter on a mark -> card opens, scrolls to centre, box highlights]
```
Mobile (375 px): the same lanes, but the date axis becomes compressed ranks (no fixed px per day) and the Undated column drops under the lanes as a fourth lane row.
```
Part 2 [Contradicted]
Contradicts 1  ◇o
Weakens     0  none
Supports   12  ■ ■ ■4 ■
Undated     5  ◇o ■o ■o ■ ■
 dashed: letter dated May 7 (x4)
 ◇ contradicts  ▲ weakens  ■ supports
 hollow = not settled by 2nd read
Marks are at least 32 px tall; tap opens the card.
```

## 4. Data mapping (existing fields only)
| Card field | Mark |
|---|---|
| relation | Lane (rows, fixed order Contradicts, Weakens, Supports) and shape (diamond, triangle, square); colour as a third cue, plus the lane label |
| date (explicit) | x position on a dated axis, ticks by month; marks on the same day stack with a count |
| date inferred | Same x, but the mark gets a dotted outline and the axis caption "inferred from the text" |
| date missing ("Undated") | Own column at the right edge, separated by a rule; labelled "No date found in this passage", never positioned in time |
| second read: confirmed / not settled | Filled / hollow. Neutral ink for both, no red and no score |
| referenced, not supplied | Dashed marker in a footer row, one per distinct reference, "cited in N places" |
| merged near-duplicate cards (task 1) | One mark with a count badge; the click opens the primary and the `also:` list stays reachable |
| source doc + page | Mark label on focus or hover and in `aria-label`: "Contradicts, Bylaws p2, no date, not settled" |
| card id | `data-card-id`; click or Enter calls `reveal(card)` and it also works from the lane header ("show 12") |

Chart header stays code-built: counts, documents, date span (task 2/10 strings). No model text.

## 5. What it must not imply
- No false precision: inferred dates are dotted and captioned; undated marks never sit on the axis; no connecting lines between marks (no implied sequence or causation).
- No vote counting: lane heights are equal, a lane with 1 mark is as prominent as one with 16 (count in the lane label, "Supports (16)"; marks of a big lane wrap into a grid rather than stretching). Caption: "One contradicting passage is enough to contradict a claim."
- No confidence: hollow means "second read alone did not settle it", not "less true". No size, opacity or position encodes strength.
- No hidden evidence: the 15 or 20 irrelevant passages are counted in the header, and not-settled cards stay on the map.
- No verdict from the chart: the chip stays the code's verdict; a pending state shows lanes empty with "Pending".
- A weak sole contradiction stays visible and is labelled as such (hollow diamond, "1 passage, not settled") rather than hidden.

## 6. MVP vs later
**MVP (flag-on, 2-3 days):** per-part stance map as inline SVG (or flex grid) following sections 3-4; shape + fill + label + colour; Undated column; dashed reference row; count badges; `reveal` on click, Enter and Space; `aria-label` on each mark; focus ring; dark mode through CSS variables; 375 px layout via lane rows; sits above the relation groups; legend of 3 shapes and hollow/filled; test: marks equal cards, every `data-card-id` resolves, greyscale distinguishes shapes, no banned words, flag-off golden unchanged.
**Later:** overall map above all parts (parts as bands) with "why this verdict" jump links; document lane view (rows by file) to show coverage and "bylaws uploaded, nothing relevant"; hover preview of the pinned quote; keyboard arrow navigation across marks; print/download of the chart; pending marks while checks run (task 6).

## 7. AI / backend need
Nothing for the MVP. Later-version limits that only AI/backend can fix (see product-review P6, P12, P17): part-scoped relevance so parts do not repeat the same supports, self-contained parts, and precision of labels so "supports" that the second read says do not mention the part do not fill the Supports lane. A better date extractor (more explicit dates) would shrink the Undated column; the chart does not need it.

## 8. Open questions for the owner
1. Is the stance map (A) the right answer to "graph", or do you want a node-link picture for demo appeal? (My advice: A, and keep node-link out; it adds no information.)
2. Should the Undated column be allowed to be the larger part of the chart (TC17: about half the cards)? It is honest; the alternative hides evidence.
3. May the chart caption state "One contradicting passage is enough to contradict a claim" (product-review Q1)?

## Sources
- Kialo pro/con trees overview: https://en.wikipedia.org/wiki/Kialo
- Node-link vs matrix readability (Ren et al., large online experiment): https://www.cambridge.org/core/journals/network-science/article/understanding-nodelink-and-matrix-visualizations-of-networks-a-largescale-online-experiment/C293136C4761F09D4C2C328E2BC19287
- Node-link vs matrix, topology tasks (Okoe et al.): https://arxiv.org/pdf/1709.00293.pdf
- Matrices or node-link diagrams, directed graphs: https://repository.tudelft.nl/record/uuid:10b6c65a-82eb-434f-86a6-0e30e512129c
- Legal chronology tools handling uncertain and undated events: https://www.aeontimeline.com/solutions/chronology-research-tool and https://www.vaquill.ai/features/chronology-builder
