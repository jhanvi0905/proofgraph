# What a blind first-time reader fears about "Second check: not sure it fits this part"

Sources: `app/viewer/render.py` (`_SECOND`, `_second_line`, `SECOND_CHECK_TEXT`, `CHECK_LABEL`), cold-user walkthrough (P7: "who did the first check? does not sure mean I should ignore the finding?"), redesign reader questions (Q6 "Can I trust it?"), sprint Product decisions (neutral colour, never a score, banned words).

## 1. The fears, ranked (user's voice, trigger words)

1. **"The tool doesn't trust its own finding, so why should I?"** Trigger: "not sure". The word is the tool's own doubt, spoken about its own work, with no owner ("who is not sure?").
2. **"Is my claim wrong, or is the tool broken?"** Trigger: "not sure it fits this part" on the one passage that goes against the claim (cold walkthrough: "should alarm me but doesn't say so"). Money or legal exposure rides on that one row.
3. **"Do I now have to re-check everything myself?"** Trigger: "Second check" with no object, plus "Check the original document yourself" style copy elsewhere. No stated next action.
4. **"If a third of these are unsure, are they all unreliable?"** Trigger: the repeated phrase on about 31% of rows; "not sure" is read as a grade, not a limit.
5. **"Can I show this to my boss or in court?"** Trigger: "the second check was not sure" in a screenshot or export reads as the tool admitting doubt. Fear of blame: "I relied on something the tool itself doubted."
6. **"Did something fail silently?"** Trigger: "could not be run this time" / "not run on this one" sit beside "not sure" in the same slot, so the reader cannot tell "it looked and hesitated" from "it never looked".

Newcomer extra: "Second" implies a first check they never saw; "this part" is undefined until they have met claim parts.

### Screen-reader order for one row (today)
"Backs up, [quote], [file], page 2, No date in this passage, Second check: not sure it fits this part." Then, if opened: "Read alone, the quote does not mention this part, but it is listed as support, so the second check was not sure it fits."
Confusing: (a) verdict-bearing state arrives last, after a long quote; (b) "not sure" has no subject, and "it fits" has no object; (c) "second check" appears twice in two sentences; (d) "listed as support" is jargon (listed by whom?); (e) the filled/hollow mark is aria-hidden or unheard, so the legend ("solid = confirmed, hollow = not sure") means nothing; (f) nothing says "the finding still counts"; that reassurance exists only in the explainer paragraph, which a linear listener may never reach.

## 2. What it actually means (the truthful floor)

A second, independent read looked at the quote alone, with the part, and not the rest of the page. On its own the quote did not clearly say what the first read took it to say. That is a limit of a narrow re-read, usually because a quote loses its meaning without the surrounding page. It is not a finding that the passage is wrong, it did not change the verdict, and the finding still counts. The reader's useful action: open the page and read the passage in place. Never imply the finding is unreliable, never imply it is solid.

## 3. Mitigations, ranked by impact/effort

**Recommended wording set (one):**

- Closed row label: **"Read alone, the quote did not settle this"** (fears 1, 2, 6: names who/what, says "alone", no "not sure"). Short form for the narrow row slot: **"Quote alone: not settled"** (matches the sprint badge decision "not settled").
- Confirmed: **"Quote alone: confirmed"**. Same neutral colour for both.
- Not run: **"Second read did not run on this one"** (separate from not settled; fear 6).
- Opened panel line: **"Read on its own, the quote does not mention this part. The first read counted it as support, and it still counts. Open the page to see it in context."**

Candidate rewrites tested (fears 1-6; plain words, no banned words):
| Candidate | Verdict |
|---|---|
| A "A second read of the quote alone did not settle this part. The finding still counts." | Good panel line; long for a row |
| B "Quote alone: not settled" | Best row label; short, neutral, matches sprint |
| C "Needs the page around it" | Warm, actionable, but over-explains the cause |
| D "Second check: unsure" | Rejected: same fear 1 and 4 as today |

**Wording (impact high, effort S):** use the set above everywhere (row, panel, group counts line, aria). Do not say "confidence", "unreliable", percentages.

**Structure (impact high, effort S/M):**
1. *The one change that matters most:* a single plain line directly under the verdict band, code-built from counts: "Every passage was re-read on its own. 18 were confirmed. 8 did not settle, because a quote read alone often needs the page around it. All 26 still count toward the result." (Counts only; no tone of failure.) Closes fears 1, 4, 5 before they form.
2. Put "still counts" on the panel line, not only in the explainer.
3. Action in the panel: link/button "Open page 2 and read it in place" (fear 3). Reassurance first, action last.
4. On the one deciding passage of a "goes against" verdict, add: "This is the passage that decides the result. Open the page to confirm it." Truthful, gives the reader the check a reviewer would do anyway (fear 2, 5).

**Accessibility (impact high, effort S):**
- Order per row: state of the finding, then part, then the check, then the quote. Do not make the second-read state a trailing afterthought; put it in a fixed second position.
- aria-label pattern: "Backs up the claim. Part 2. Second read of the quote alone did not settle this. The finding still counts. Page 2 of [file]. No date." One idea per sentence, nothing repeated.
- State is always words, never fill or shape; keep glyphs `aria-hidden`, keep the legend as a visible text row for sighted users only.
- Say "second read" once per row; elsewhere say "this".
- Group header announces counts ("8 of 26 did not settle") so a listener knows the scale before the rows.

**AI/backend (notes only, not this sprint):** have the second read return a short reason class ("quote is a fragment", "refers to something elsewhere", "different subject") so the row can say why instead of "did not settle". Also try giving the second read the page, not just the quote, to cut the 31% rate. Model-quality and prompt items; no UI should invent a reason.

## 4. Before -> after

| Where | Before | After |
|---|---|---|
| Closed row | Second check: not sure it fits this part | Quote alone: not settled |
| Confirmed row | Second check: confirmed | Quote alone: confirmed |
| Not run | not run on this one | Second read did not run on this one |
| Could not run | could not be run this time | Second read could not run this time. Try again later. |
| Panel line | Read alone, the quote does not mention this part, but it is listed as support, so the second check was not sure it fits. | Read on its own, the quote does not mention this part. The first read counted it as support, and it still counts. Open the page to see it in context. |
| Explainer | A second look at this passage alone. Not sure means it did not reach the same label; the finding still counts. | Each passage was re-read on its own, without the rest of the page. Not settled means the quote alone was not enough. The finding still counts. |
| Aria-label | (state last, shape-dependent) | Backs up the claim. Part 2. Second read of the quote alone did not settle this; the finding still counts. Page 2, no date. |

## 5. Acceptance checks
1. Cold read (5 people, none briefed): shown one not-settled row, 4 of 5 say in their own words "it still counts" and "I should look at the page."
2. Ask "what would you do next?": at least 4 of 5 answer "open the page and read the passage", none answer "ignore it" or "rerun everything".
3. Ask "is the claim wrong, or the tool broken?": none say "tool broken" after reading the verdict-adjacent counts line.
4. Screen-reader pass (VoiceOver and NVDA): one row heard once from top; the listener can state the finding, the check result, and that it counts, without seeing shapes. No sentence repeats "second check".
5. Test: no banned word (disagree, failed, unverified, wrong, flagged, confidence, percent sign) in any rendered string or aria-label; confirmed and not-settled badges share one colour class; "still counts" appears in every not-settled panel and in the counts line.
