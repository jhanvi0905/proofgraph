---
name: ProofGraph
description: Claim verification for document packets, set as audit working papers with tick-and-tie marks.
colors:
  sheet: "#F7F8FA"
  ink: "#0E1A2B"
  cyan-rule: "#CFE3EE"
  stamp-cobalt: "#1636C9"
  pen-red: "#C8222D"
  pen-green: "#1B7F4B"
  amber-pen: "#9A5B00"
  slate: "#4A5668"
  grey: "#5B6678"
  paper: "#FFFFFF"
typography:
  display:
    fontFamily: "Schibsted Grotesk, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: "clamp(2.4rem, 6.2vw, 4.4rem)"
    fontWeight: 700
    lineHeight: 1.02
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Schibsted Grotesk, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: "1.9375rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Schibsted Grotesk, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.4
  body:
    fontFamily: "Schibsted Grotesk, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Schibsted Grotesk, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.55
  document:
    fontFamily: "Source Serif 4, Source Serif Pro, Georgia, Times New Roman, serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
rounded:
  none: "0"
  pencil: "999px"
spacing:
  xs: "0.5rem"
  sm: "1rem"
  md: "1.5rem"
  lg: "2.5rem"
  band: "4.5rem"
components:
  button-primary:
    backgroundColor: "{colors.stamp-cobalt}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "0 1.2rem"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.stamp-cobalt}"
  button-inverse:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.stamp-cobalt}"
    rounded: "{rounded.none}"
    height: "44px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.stamp-cobalt}"
    rounded: "{rounded.none}"
    height: "44px"
  evidence-cell:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.65rem 0.75rem"
  signoff-box:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.55rem 0.8rem"
  pencil-label:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.pencil}"
    padding: "0.2rem 0.7rem"
---

# Design System: ProofGraph

## Overview

**Creative North Star: "The Tied-Out Workpaper"**

ProofGraph looks like an auditor's working paper. A cool white sheet ruled in pale cyan carries blue-black ink; every claim part gets a hand-drawn pencil mark that means one defined thing, backed by a legend and a workpaper reference code (A-1, B-3) that ties to a page. Stamp cobalt is the single saturated field and the primary action. The system is dense, flat and ruled, built for operating a check rather than admiring it.

The system rests on one separation: Source Serif 4 speaks only for what the documents say (quotes, claim text in cells, page excerpts); Schibsted Grotesk speaks for everything ProofGraph says. Colour is never the only carrier of an answer: each answer has a word, a pen colour, a mark shape and an underline style.

**Key Characteristics:**
- Ruled sheet ground (32px cyan baseline rules), squared corners, 1.5-2px ink borders.
- One saturated field (cobalt) per page, on the entrance hero; elsewhere cobalt is action and link only.
- Five pencil marks plus a clash mark, each with a legend entry; gaps written down as open items.
- Tabular figures, no monospace.

## Colors

A cool paper-and-ink neutral set, one cobalt, and four pen colours reserved for answers.

### Primary
- **Stamp Cobalt** (#1636C9): the entrance hero field, primary buttons, links, focus ring. White text only (8.7:1).

### Secondary (pen colours, answers only)
- **Audit-Pen Green** (#1B7F4B): tied out, Supported. Solid underline, tick.
- **Audit-Pen Red** (#C8222D): exception, Contradicted. Solid underline, circle; also the gap line and error text.
- **Amber Pen** (#9A5B00): Qualified. Wavy underline, caret; also the excerpt underline in cells.
- **Slate** (#4A5668): Not in these documents. Dashed underline, bracket.

### Neutral
- **Workpaper Sheet** (#F7F8FA): page ground, ruled with Cyan Column Rule at 45% every 32px.
- **Blue-Black Ink** (#0E1A2B): text, borders, active states (16.5:1).
- **Cyan Column Rule** (#CFE3EE): hairlines, table rows, inactive map pencils.
- **Pencil Grey** (#5B6678): secondary text, Not mentioned anywhere (dotted underline, question mark).
- **Document White** (#FFFFFF): documents and anything that holds them: page images, quotes, cells, sign-off boxes, the pinned sheet.

### Named Rules
**The Four Carriers Rule.** An answer is word + pen colour + mark shape + underline style. Never ship an answer carried by colour alone.
**The Document White Rule.** Pure white means a document (or a box that holds a record). The page ground is the sheet, never white.
**The One Field Rule.** Cobalt fills a field only as the entrance hero; inside the product it is action, link and focus.

## Typography

**Display and UI Font:** Schibsted Grotesk (Helvetica Neue, Arial, system-ui), weights 400, 500, 700.
**Document Font:** Source Serif 4 (Source Serif Pro, Georgia, serif), loaded from Google Fonts.

**Character:** A plain, sturdy grotesk for the examiner; a bookish serif for the evidence. The scale is a 1.25 ratio on 16px: 13 / 16 / 20 / 25 / 31 / 39px.

### Hierarchy
- **Display** (700, clamp(2.4rem, 6.2vw, 4.4rem), 1.02, -0.02em): entrance H1 only. The oversized footer wordmark is the same face, 700, up to 6rem, -0.04em.
- **Headline** (700, 31px, 1.15): section H2s on the entrance.
- **Title** (700, 20px): sub-heads, answer lines, the lede (400).
- **Claim** (500, clamp to 31px on review, 1.3; live reading up to ~31px, 1.35): the claim sentence, at most 40-56rem wide.
- **Answer** (700, 25px; 39px on the shared review): the per-part answer with its mark.
- **Body** (400, 16px, 1.55): copy, max 36-46rem.
- **Label** (400/700, 13px): workpaper reference codes, tier and agree lines, notes, table heads.

### Named Rules
**The Two Voices Rule.** Serif is for quoted document text only; all ProofGraph speech is grotesk.
**The Tabular Rule.** Figures and page references use tabular numerals; no monospace face.

## Layout

Content sits in an 80rem shell (review page: 1320px wrap), 1rem side padding. Entrance is a sequence of bands with 4.5rem top padding: full-bleed cobalt hero (two columns from 960px, 1.1fr / .9fr, 4rem gap), samples, frames, pillars and cases in auto-fit 15rem grids, FAQ and close in a two-column split from 960px. Review page is one column (head, pane, main, foot) until 1100px, then main plus a sticky 24rem page pane on the right with the footer spanning both. Evidence is a columnar grid (documents as columns, parts as rows) from 1440px; below that each part's document cells stack under its text with the document letter and name as a small label, so quotes keep a readable line length. On a narrow screen the page plate sits under the head first and moves inline under whichever quote is tapped. Live reading uses a 13rem checklist beside a column map under 760px stacks. Spacing is rem multiples (.5, 1, 1.5, 2.5, 4.5); targets are at least 44px tall.


## Elevation & Depth

Flat and ruled by default; depth comes from borders (1px cyan, 1.5-2px ink) and the white-on-sheet shift. Soft shadows are used only for things that are physical paper lying on the desk.

### Shadow Vocabulary
- **Pinned sheet** (`0 2px 4px rgba(14,26,43,.25), 0 24px 40px -16px rgba(14,26,43,.5)`, rotated 1.2deg, flat under reduced motion): the entrance example sheet.
- **Page image** (`0 2px 4px rgba(14,26,43,.14), 0 14px 28px -12px rgba(14,26,43,.3)`): the rendered document page.
- **Selected cell** (`inset 0 0 0 2px` ink): the pressed evidence cell is doubled-bordered, not shadowed.

### Named Rules
**The Paper Only Rule.** Shadow belongs to a document or sheet; controls, cells and boxes never cast one.

## Shapes

Square. Buttons, inputs, cells, sign-off boxes and trails have 0 radius. The one curve is the pencil label, an irregular hand-drawn pill (999/1000px mixed radii, 2px ink border) used for map labels. Marks are hand-drawn SVG strokes; the contradiction ring is a drawn red loop around the cell. Evidence cell edge style encodes source: dashed for set-aside, dotted left for model-read, dotted all round for unclear. Highlight boxes on the page image use a 2px pen-colour border with a 12% tint of the same colour, dashed when approximate.

## Components

### Buttons
- **Shape:** square, 44px min height, 2px border, weight 700.
- **Primary:** cobalt fill, white text, 0 1.2rem padding. Hover inverts to white fill with cobalt text.
- **Inverse (on cobalt):** white fill, cobalt text; hover goes ink fill with white text.
- **Quiet:** transparent, cobalt text and border; hover fills cobalt.
- **Link-button:** bold underlined cobalt text, 44px tall.
- **Focus:** 3px cobalt outline, 2px offset (white on the hero). Disabled: 60% opacity.

### Pencil mark and legend
Tick (green), circle (red), caret (amber), bracket (slate), question (grey), and a green/red clash mark for documents-disagree. Always rendered with the answer word and underline style, and always listed in the legend with the tier line.

### Evidence cell
Full-width pressable white cell, 1px cyan border, serif quote, a footer row with mark, relation word, and a bordered reference tag right-aligned. Hover and pressed turn the border to ink. A contradicting cell gets bold footer and the red ring.

### Sign-off box
Bordered 1.5px ink white list: label bold left, value right, cyan row dividers. Carries prepared-by receipt and the second-reader line, on entrance and review.

### Workpaper reference
Small square-bordered box (1.5px ink) with a code like A-1, leading each cell of the review ledger. The entrance sections no longer carry codes: they have plain titles and anchors instead.

### Inputs
Claim textarea and passcode field: white, 2px border (white on cobalt), square, caret in cobalt. The packet drop zone is a 2px dashed white box that turns solid with a 16% white tint on drag-over. The follow-up ask field is a 44px, 2px-ink bordered input beside a button.

### Trail, strip and banner
Trail: bordered white steps joined by arrows showing which document overrides which. Strip: two answers joined by a red gap line with its label. Banner: ink-bordered white note. Open items: dashed ink box listing gaps.

### Bars
Three bars tell the visitor where they are. **Entrance top bar**: one full-width, sticky cobalt bar over the entrance, with the wordmark on the left and four labelled destinations (Check a claim, How it works, What the answers mean, Questions) on the right; every entrance section has an id and a plain title, and the old N-1 to N-4 reference marks are gone. On a phone it is not sticky and wraps. **Run bar**: a sticky sheet bar, shown from the moment a check starts, with a "New check" button, the step the check is on ("Step 1 of 3: Reading the documents", "Step 2 of 3: Checking the claim", "Step 3 of 3: Answer ready", or "Stopped" with the reason), and a "How the documents were read" toggle once reading is done; on a phone the step moves to its own row and the product name is hidden. **Review contents bar**: a sticky bar at the top of a finished review listing Answer, Evidence, Cited not supplied (only when the documents cite something not supplied), How this was checked and Ask another claim (only when the review can take a follow-up); it hides in print, is not sticky on a phone, and anchor targets keep a scroll offset below it. The review's own footer sections carry plain titles ("How this was checked", "Key to the marks").

### Live reading
Under the run bar, a short heading and one sentence say what the columns, labels and lines mean. Checklist of documents and pages with a green tick revealed when read; column map of pencil labels with thin ink threads that go cyan while deciding; the active label turns bold ink.

## Do's and Don'ts

### Do:
- **Do** give every answer all four carriers: word, pen colour, mark, underline style.
- **Do** set quotes and document text in Source Serif 4 on Document White; set everything ProofGraph says in Schibsted Grotesk.
- **Do** tag each ledger cell with a workpaper reference and keep a legend entry for every mark; give every entrance section a plain title and an anchor.
- **Do** write gaps as open items (dashed box), not hide them.
- **Do** keep controls square, at least 44px, with the 3px cobalt focus ring.
- **Do** respect reduced motion: marks and the ring animate only under no-preference; the pinned sheet stays square.

### Don't:
- **Don't** use a chat box, citation chips or a confidence score; answers are per part and tied to a page.
- **Don't** use cobalt as a fill inside the product; it fills only the entrance hero.
- **Don't** put a shadow on cells, buttons or boxes.
- **Don't** use a monospace face or set ProofGraph's own words in the serif.
- **Don't** use colour alone to carry an answer.
