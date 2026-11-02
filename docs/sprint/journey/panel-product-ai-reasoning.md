# Panel: show the AI's reason on an opened row?

Panel: PM, UX writer, trust/risk. Read-only review. Inputs: sprint doc (Goal, Product decisions), redesign-from-scratch (reader questions, section 10), cold-user-walkthrough, `_row`/`_passage`/`_second_line`/`_position_note` in `app/viewer/render.py`.

## Recommendation: YES, WITH CONDITIONS (narrow)

Add one labelled "AI's reading" sentence inside the opened panel only. Do NOT swap it for the source line: document and page stay. Remove the date line when there is no date, the duplicate source line, and shrink the second-check paragraph.

## What we are overriding, explicitly

The sprint doc cut "per-card re-explanation" for 4 Nov, and redesign section 10 says no model-written sentences. Those were owner calls and they were right for the closed list: a page of model prose would bury the verbatim quote and the verdict. We override only this slice: one sentence, opened panel only, never in a row, summary, counts line or the verdict band. The "no model text in any summary" rule stands. Why override: the cold reader asked for the reason six times (walkthrough items 6 and 7; "one passage beats 28", "covers only part of what is claimed is a weak reason"). Today the only "why" is a tiny tag, and the walkthrough calls those tags "footer metadata". The owner must sign this override; it is not ours to assume.

## (1) Is it wise?

| Risk | Verdict |
|---|---|
| Reader need ("why does this count?") | Real, repeated in the cold log. |
| Fluent text outruns a "not sure" second check | Real. Solved by rules below, not by hoping. |
| Hallucination beyond the quote | Real. The model writes `Card.why` before the second check sees it. Mitigate with a cap and a code check (below). |
| Legal/audit | Reasoning is not evidence. Keep quote first, large, quoted; AI line smaller, labelled, never in the downloadable "evidence" sense without the label. |
| Code owns the verdict | Unchanged. The line never feeds the verdict, counts or order. |
| Clutter | Fine if one sentence, opened panel only. |

## (2) How, exactly

- Place: in the opened panel directly under the quote's source line, above the page image. Closed row stays quote plus source plus second check badge.
- Label: "AI's reading:" in muted small text. Quote stays the primary type. Never inside quotation marks, never styled like evidence.
- Length: one sentence, max about 140 characters. Code hides anything longer, empty, or that restates the quote word for word. No truncation with an ellipsis (a clipped reason misleads).
- Only where it adds something: hide it when it merely repeats the relation ("This backs up the claim").
- Second check agrees: show "AI's reading: ...".
- Second check not sure or could not run: do NOT show the reading. Show the short check line instead: "Second read of this quote alone: not settled. It does not name this part." Fluent reason plus doubt on one screen is the contradiction to avoid.
- Goes against / Casts doubt rows: show the reading even more readily, but only when the check is confirmed, because these rows decide the verdict and are where a wrong sentence costs most. If not settled, the check line alone, and the quote still speaks for itself.
- Banned in the line: confidence words ("clearly", "strongly"), percentages, verdict words ("fails", "proves"), anything not traceable to the quote (dates, names not in the quote). A code check: every number and capitalised name in the line must appear in the quote or part text, else hide.

## (3) Compact layout

Source info kept: document name and page (how to find it), plus the date only when it exists. "No date in this passage" disappears from the panel (the closed row keeps the undated separator already built). Duplicate source line removed (the row already carries it).

Supporting row, closed:
```
(+) "Recipient shall deliver the goods to the consignee at site." 
    POD 7713 signed scan · p1 · Second check: confirmed        [Open]
```
Supporting row, opened, second check confirmed:
```
(+) "Recipient shall deliver the goods to the consignee at site."
    POD 7713 signed scan · p1
    AI's reading: Signed delivery receipt for the same goods and site.
    [page image, one box]
    The box is an estimate because this page is a photo or scan.      [Close]
```
Supporting row, opened, second check not sure (the owner's case):
```
(+) "<verbatim quote>"
    POD 7713 signed scan · p1
    Second read of this quote alone: not settled. It does not name this part.
    [page image]
    The box is an estimate because this page is a photo or scan.      [Close]
```
Goes-against row, TC17 Bylaws, opened, confirmed:
```
(x) "...effective only upon adoption of the resolution by the Board..."
    IHP Bylaws Excerpt Art. V · p2 · 14 May 2026
    AI's reading: Authority starts at the resolution, not on 7 May.
    [page image, one box]                                              [Close]
```
Same row if not settled: reading omitted, line "Second read of this quote alone: not settled. Other passages are needed to settle it." The old 3-sentence paragraph is gone (the "sees only the quote and the part" explanation moves to one footer line, once per page).

Check the Bylaws line itself against the rule: "14 May" and "7 May" are in the part/claim text, so it passes the traceability check only if the dates appear in quote or part; otherwise it would be hidden. Good, that is the test working.

## (4) Acceptance checks

1. Every panel keeps document and page; no panel shows the source twice; "No date in this passage" appears nowhere inside a panel.
2. The AI line renders only when `check == "agrees"`, is under 140 characters, is one sentence, and carries the "AI's reading:" label in a muted, smaller style than the quote (computed font size and colour test).
3. For any row where `check != "agrees"`, no `Card.why` text is in the DOM (assert on the rendered HTML), and the short check line is present.
4. Numbers and capitalised names in the line all occur in the quote or part text; otherwise it is absent (unit test with a hallucinated date).
5. Verdict, counts line, row order and summaries are byte-identical with and without the feature (golden test); the flag-off output is unchanged.
6. No banned words (confidence, percent, "disagrees", "failed", "wrong") in any AI line or check line; cold reader on TC40 can say in one sentence why the NDA row goes against the claim without opening a second source.

## Owner must decide

1. Sign the override of the 4 Nov cut (opened panel only).
2. Whether a hidden-when-not-sure rule is acceptable even though it hides the reason on exactly the rows readers most want explained (we say yes: honesty over completeness).
3. Whether to constrain `Card.why` in the labelling prompt (one sentence, quote-grounded) and regenerate, or rely on code filtering alone (we recommend both; the prompt change needs a separate go-ahead and eval cost approval).
