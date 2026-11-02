# Trust and engagement plan (journey view)

Think-only. Facts come from the journey docs (TC17 live run, cold walkthrough, product-fear note, redesign, backend lane). Principle: we show where to look, the reviewer decides. We say the limits first and plainly.

## 1. Journey map

| Stage | User goal | Feels | Trust risk | Shown today (docs) | Moment of truth |
|---|---|---|---|---|---|
| Arrive | Learn what this is, is it safe | Wary, time-poor | Asked for a secret before purpose | No title or purpose line; passcode first; "Packet app" unexplained | Can I say what it does in 5 s? |
| State claim | Put my claim in | Unsure what a good claim is | Claim silently split into fragments ("from May 7, 2026.") | No example, no hint on splitting | Parts shown back as readable sentences |
| Upload | Hand over sensitive files | Anxious about data | No word on storage, retention, who sees it | Truncated names; 200MB/PDF,PNG,JPG; no "files read" check until submit | Is it safe to put this in? |
| Wait | Know it is working | Anticipation or doubt | Silence reads as broken; grey "Checking" looks final | Green file lines at ~3 s, grey chips, flip at ~15-20 s, result ~25 s; no stages or count | Does the wait feel purposeful? |
| First result | Is my claim OK, why | Wants one answer, 10 s | Verdict word differs in 3 places; 16 backs vs "Contradicted" looks wrong; reason missing | Redesign: one verdict band, rule said once, worst part first | Can I state the result in one sentence? |
| Verify a finding | See the exact words and box | Sceptical, hunting a flaw | Box covers half the page; box missing on scans | Quote plus page with one box (best moment); some scans "unpinned" | First passage opened: exact box found |
| Handle uncertainty | Know what "not settled" means | Alarm: "tool doubts itself" | Reads as grade; "not run" confused with "not settled" | 31% of rows carry it; new copy "Quote alone: not settled" | First "not settled" does not break belief |
| Decide / act | Know what to do next | Liability fear | No next step; missing letter is a small dashed line | "Not uploaded" block; scope footer | I know my next action |
| Share | Show boss, auditor, counsel | Fear of blame | Export shows doubt without context; download above verdict | One HTML file, unexplained | Export stands on its own |
| Return | Re-check after fixing gap | Low motive unless closed loop | No accounts, no saved runs; no resume | Re-run means retype | Add document, re-run, see what changed |

## 2. Trust moments and the move that earns each

1. **First 10 seconds (arrive).** Move: heading, one purpose line, one example claim, and three plain "what it does not do" lines: it does not decide for you; reads text pages only unless stated; verdict is a fixed rule, not a model's opinion. Passcode last, with one line on who holds it. Lane HOST. Principle: say limits early.
2. **Data handling at upload.** Move: one sentence beside the uploader (what is stored, how long, who can see, not used for training) linking to a short "how we check" page. Must be true; get the facts from the owner before writing. Lane CONTENT/POLICY plus HOST. Principle: assurance at the point of fear.
3. **First passage opened.** Move: the deciding passage comes first and open; one box, quote and page together; "Open the page and read it in place". If no box can be drawn, say so in words, never imply a box. Lane UI. Principle: verifiable evidence; the user is the verifier.
4. **First "not settled".** Move: one code-built line under the verdict ("Every passage was re-read on its own; N confirmed; M did not settle because a quote alone often needs the page; all still count"), the row label "Quote alone: not settled", and a distinct "did not run". No score words. Lane UI. Principle: calibrated honesty.
5. **The weakest finding and the surprising verdict.** Move: when the deciding row is undated or not settled, say so beside the verdict in plain words ("This rests on one passage; read it first"), and say the rule once: one passage against is enough. Do not defend the verdict; point to the evidence. Lane UI plus CONTENT. Principle: no overclaiming, and the owner open decision (should the band stay red when the only contradiction is not settled) is made by code, not copy.
6. **A missing document.** Move: "Not uploaded" is a call to action: names the document, how many passages cite it, "Add it and run again". Lane UI plus HOST. Principle: graceful failure.

## 3. Engagement (no scores, filters, or AI summaries)

- **Verify in 2 minutes path:** verdict band, the deciding passage open, "Open this passage", then scope footer. Everything else is optional depth.
- **Next action per verdict** (fixed strings chosen by code from status): Goes against, read this passage and check it with the owner of the document; Casts doubt, read the doubting passage, then decide; Backs it up, still check the not-uploaded list and scope; Not uploaded present, add it and re-run.
- **Shareable result:** move the one-file download below the verdict, label it "Download this review (one HTML file)", and make it carry the claim, rule, scope and the not-settled line, so it never shows doubt without context.
- **Resume / re-run:** keep the claim and file list in session after a run so adding the missing document is one click (HOST). No accounts this sprint, so "return" means re-run within a session and a re-opened download.
- **Plain language and wait state:** name stages from real events (reading files, checking part N of M, results fill in), keep "not final" visible while chips are grey. This builds anticipation without invention.

## 4. Recommendations (impact vs effort)

| # | Move | Lane | Size | Impact |
|---|---|---|---|---|
| 1 | Verdict band with the rule said once, deciding passage first and open, one verdict word | UI | M | Highest |
| 2 | Landing purpose line, example claim, "what it will not do", data-handling sentence, passcode last | HOST + CONTENT | S | Highest |
| 3 | Row label and one counts line for "not settled" / "did not run", plus "still counts" | UI | S | High |
| 4 | "Not uploaded" as call to action plus keep claim/files so re-run is one click | UI + HOST | M | High |
| 5 | Staged wait text from real events; "results fill in" | HOST | S | Medium |
| 6 | One-paragraph "how we check" page and retention statement | CONTENT/POLICY | S | Medium |
| 7 | Download moved to footer, labelled, with scope in the file | UI + HOST | S | Medium |
| 8 | Nested iframe scroll and theme match | HOST | M | Medium |
| 9 | Pipeline notes: self-contained claim parts, support precision, scan boxes, second-read reason class | PIPELINE/AI | L | Notes only |

**Do first:** 1, 2, 3. They cover the first 10 seconds, the first result, and the first doubt.

## 5. Signals (no new analytics) and test script

Signals from usability sessions and the saved HTML: (a) seconds from result to first passage opened; (b) % who state the result in one sentence unprompted; (c) % who say they would act, and what act; (d) passages opened (observer tally); (e) % who correctly say what "not settled" means; (f) % who add the missing document and re-run when invited; (g) any tester who finds a wrong box (severity-one).

**Script, 5 people (2 legal/compliance, 2 audit/finance, 1 screen-reader user), 30 min each, think aloud throughout.**
1. Landing: "Tell me what this is and whether you would upload a real file." Q: what do you expect it to do? what would stop you uploading? who sees the file?
2. Run TC17 yourself (cached). Q: what do you think is happening while you wait? what would you do if it took two minutes? is the result final?
3. "Tell me the result in one sentence." Q: why? which passage decides? how sure are you, and why?
4. "Show me the evidence for the deciding point." Q: did you find the exact words and box? what would convince you? what is missing?
5. Find a "not settled" row. Q: what does it mean? does it change how you read the finding? what would you do next?
6. "What would you do now, and what would you send to someone?" Download it. Q: would you show this export to your boss? what is missing? would you come back, for what?
Screen-reader pass (the fifth tester, plus a keyboard-only run for all): complete tasks 3-5 by audio only; record what is announced first for a row, whether state precedes quote, and whether "still counts" is heard.

## 6. Risks: where reassurance backfires

- Calling the second read a "verification" or "confirmed correct": it re-reads a quote alone and can miss context. Say "re-read", never "validated".
- "Still counts" without the action line reads as dismissal; always pair it with "open the page".
- Data-handling claims we cannot prove (retention, no training): a false line is worse than none. Verify before publishing.
- Over-polishing a red verdict resting on one undated, not-settled passage: the reader will check it, and a weak basis found after a confident band destroys trust. Say it is the deciding passage and invite the check.
- Next-action text that sounds like legal or financial advice. Keep it to "read, check with the document owner, add the missing file".
- Hiding irrelevant passages (15 and 38 hidden) without saying so: always state counts, scope and "may be incomplete".
