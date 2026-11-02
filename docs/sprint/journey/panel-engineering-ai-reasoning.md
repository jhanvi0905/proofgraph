# Panel (engineering): should an opened ledger row show AI reasoning?

Evidence: cached runs (cost $0, ledger unchanged) of FRT-03, TC17, TC40 through `run_review`; code read of `prompts/label.md`, `proofgraph/review/label.py`, `app/viewer/render.py`.

## What the model already writes
`Card.why` comes from the labelling call (`label.md`, reasoning effort low). The prompt asks for "a reason of at most 12 words tying the passage to the part". Code hard-cuts it at 120 chars (`WHY_MAX`, can cut mid-word; observed max 72). The model sees the whole candidate text plus the claim part, and is told "Never use text outside the candidates", but nothing in code checks that. Candidates are fenced as data and an injected instruction goes to `injection_quote`/banner; `why` itself is not filtered. `render.py` HTML-escapes it (`_e`), so no markup risk. The ledger (`_passage`/`_row`) dropped it on purpose; `card.why` is still rendered only on the old card path (line ~676). The blind second check never sees `why`.

## Real examples (29 cards; 12 shown)
| Run | Relation | 2nd check | Quote (60) | why |
|---|---|---|---|---|
| FRT03 c1 | supports | not sure | Late? N | Late N marks delivery not late |
| TC17 c1 | supports | confirmed | RATIFICATION OF INTERIM CHIEF MEDICAL OFFICER... | Ratifies appointment effective May 7 with full authority |
| TC17 c2 | supports | not sure | The foregoing Resolution was duly adopted... May 13 | Shows unanimous board adoption with quorum present |
| TC17 c5 | supports | not sure | Dr. Connors assumed the duties... | States she exercised full authority continuously since appointment |
| TC17 c9 | supports | not sure | The Corporation's governance record is complete... | States no compliance gap in authorization |
| TC17 c11 | weakens | confirmed | Adopted: May 13, 2026 | Shows board adoption occurred May 13 not May 7 |
| TC17 c18 | supports | not sure | The appointment... could have authorized... on or before May 7 | Confirms board could have authorized on or before May 7 |
| TC17 c22 | supports | not sure | The Board's intent... recitals acknowledge... service since May 7 | Confirms service timeline since May 7 |
| TC17 c26 | contradicts | not sure | Ratification shall be effective upon adoption... | Makes ratification effective upon adoption, which was May 13 |
| TC17 c21 | supports | confirmed | By specifying May 7, 2026, as the effective date... | Explains May 7 date shows intent to relate back |
| TC40 c1 | contradicts | confirmed | Recipient agrees to limit disclosure... | Limits disclosure to employees, excluding outside consultants |
| TC40 c2 | contradicts | confirmed | Recipient will not disclose... | Requires written authorization for disclosing to consultants |

## Counts
- Style: short (37-72 chars), plain, restates the quote. It usually says what the passage says, not how it bears on the claim part.
- Stays within quote: 27 of 29. Two reach outside it: TC17 c26 adds "which was May 13" (true in the packet, not in the quote); c11 adds an inference ("not May 7").
- Second check "not sure": 9 of 29 (31%): TC17 8 of 26, FRT03 1 of 1, TC40 0 of 2. In all 9 the `why` is a faithful paraphrase that does NOT say the quote entails the part. A reader sees a confident sentence next to "not sure", so the label looks stronger than the evidence. No `why` outright says the opposite of the check, but 8 of 9 (e.g. c2: adoption is not authorization since May 7) read as support when the checker says the quote does not state the part.
- Not reproduced: the owner's POD signature row (R. Okafor 10/14/2025 10:58) is not in the cached FRT-03 run (1 card, "Late? N"). Judged from the pattern, not that row.

## Cost and effort to show it
- Zero model cost; no pipeline change; `why` is already in saved review JSON (`Card.why: str`), so old saves load.
- `_passage`: add one `<p>` from `card.why`. Flag-off path unaffected (ledger code only), byte identity safe if the flag-off render does not change. Tests: add 3 in `tests/test_viewer_render.py` (shown when confirmed, hidden/replaced when not, escaped).
- Layout: replaces or sits beside the `meta` line; the doc/page/date info is already on the row, so little is lost.

## Risks
Model text next to verbatim evidence can read as evidence; mismatch with the check (31%); injected text could be echoed into `why` (not sanitised); 120-char cut can end mid-word; it paraphrases the quote and mostly adds no information.

## Options
- A (as-is, "AI's reading"): cheap but shows the 31% mismatch; it is the highest-risk choice.
- B (only when check confirmed, else the existing check note): cheap, about 1 hour with tests. Hides the weak cases, so the explanation shows exactly where the evidence is strong.
- C (code-built reason: shared terms, dates, numbers, entity): safest and verifiable, but the pipeline lacks per-card match facts and it is more work (about 1 day); also less fluent.
- D (nothing): defensible; the quote is the evidence.

## Recommendation: B
Show `why` only when `relation` is supports/contradicts/weakens, `check == "agrees"`, and no injection banner is raised for that document. Conditions: (1) label it "AI's reading", styled apart from the quote (muted, never inside the quote block); (2) truncate on a word boundary; (3) when check is not "agrees", show only the existing check note; (4) never let `why` feed status or verdict logic (stays in `status.py`); (5) HTML-escape, keep the 120-char cap; (6) tests: confirmed shown, not-sure hidden, injection hidden, markup escaped, flag-off bytes unchanged; (7) re-measure the mismatch rate on 2 more packs, plus the owner's FRT-03 POD row, before shipping. Prompt change (asking for a reason that links the quote to the part) is a later, paid step.
