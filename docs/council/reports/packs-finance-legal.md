# Finance and legal claim packets (14)

Root: `scratchpad/packs/finance/<id>/` and `scratchpad/packs/legal/<id>/`. Each packet has:

- `upload/`: the files a user drags into the app (only these).
- `claim.txt`: the claim to paste.
- `pack.json`: the gold annotation. Each relation carries `file`, `page` (1-based) and a `bbox` in 0 to 1000 page coordinates. Scans also carry `quad`, the 4 rotated corners.
- `README.md`: the on-screen run path.
- `ground_truth/`: clean text twins with physical page markers.
- `docs/`: the authoring source.

Build scripts are in `scratchpad/packs/build/fl/` and use the `fl_` prefix. Rebuild with:

```
cd <main-checkout>/.claude/worktrees/proofgraph-meta-hackathon-e83833 && uv run --with reportlab --with pillow python <scratchpad>/packs/build/fl/fl_build.py
```

## 1. Index

| id | title | claim (short) | gold | rel. | key tags | diff. |
|---|---|---|---|---|---|---|
| fin-01-loop-rnd | Loop R&D cut, driver, net loss | R&D down ~59.98%, mainly comp, net loss narrowed | contradicted | 10 | REAL, AI claim, near-miss %, 3m vs 9m table trap, long doc | 4 |
| fin-02-landbay-wc | Landbay working capital deficit | +38.33%, $116.6m, $22,338 from Northern Ifurniture, no GC doubt | contradicted | 8 | REAL, AI claim, scale trick, respectively trap, scan, absence | 4 |
| fin-03-manahl-capital | Man-AHL capital and redemptions | capital $86.7m (-9.6%), profitable, no redemptions after YE | contradicted | 8 | REAL, AI hallucination, 5 docs, master-fund distractor, 2022 column trap, PNG | 3 |
| fin-04-record-revenue | Northwind "record" revenue | record $412m, grew, adj. EBITDA margin ~21% | partly_supported | 9 | headline true / fine print, definition trap, non-GAAP, PNG | 3 |
| fin-05-going-concern | Calder cash runway | cash funds ops through end 2027 | cannot_tell | 6 | 1-part, forecast judgment, scan audit report, subsequent event, absence | 4 |
| fin-06-covenant-waiver | Harbor Lane covenant breach + waiver | breached, waived, back to 4.75x | partly_supported | 11 | step-down row trap, long credit agreement, conditional waiver, distractor, scan, absence | 4 |
| fin-07-segments-true | Altmark segments | IS $1.24bn, grew faster, $186m and $143m respectively | supported | 6 | TRUE claim, no cry wolf, respectively correct, rounding ok | 2 |
| fin-08-restatement-injection | Brightwater restated net income | $58.4m net income, up 12% | contradicted | 8 | restatement supersedes, prompt injection, weak source, column trap | 3 |
| leg-01-nda-carveouts | NDA carve-outs | Kestrel can't share our pricing with anyone | partly_supported | 8 | 1 doc, 1 part, scan, shall not/except/may, definition trap, absence | 3 |
| leg-02-msa-amended-cap | MSA amended LoL cap | 24m-or-$2m cap, 3x data cap, auto-renews | supported | 10 | TRUE claim, amendment overrides original, distractor, scan | 3 |
| leg-03-renewal-order-form | Sable renewal and T4C | exit by emailing by Nov 15; T4C on 30 days | contradicted | 10 | order form overrides terms, sales email weak source, negation, date arithmetic, PNG | 4 |
| leg-04-indemnity-venue | Tessellate indemnity, law, forum | indemnity for any IP claim; NY law; NY courts | contradicted | 11 | governing law vs venue, evidence across 2 docs, scope/exception, scan | 3 |
| leg-05-assignment-coc | Corvid license after acquisition | transfers automatically without consent | contradicted | 10 | AI hallucination, change of control, Affiliate definition, near-name trap, scan | 4 |
| leg-06-sla-dpa | Nimbus SLA credit and breach notice | 25% credit; 24h breach notice | contradicted | 11 | SLA exclusions, credit-table row trap, DPA precedence, 5 docs, distractor, scan, PNG | 4 |

Gold overall: 8 contradicted, 3 partly_supported, 2 supported, 1 cannot_tell. There are 126 relations in total.

| relation | count |
|---|---|
| contradicts | 41 |
| supports | 35 |
| weakens | 22 |
| irrelevant | 14 |
| conditions | 11 |
| not_enough | 3 |

| weakener type | count |
|---|---|
| time | 8 |
| condition | 8 |
| exception | 8 |
| magnitude | 6 |
| definition | 5 |
| weak_source | 5 |
| scope | 4 |
| qualifier | 4 |
| absence | 1 |

The `absence` lists also add 4 more absence notes (fin-02, fin-05, fin-06, leg-01).

## 2. File types per packet

| id | files (kind, pages) |
|---|---|
| fin-01 | Loop_10-Q_Nov2023_MDA_excerpt.pdf (text PDF, 8 p, 3,364 words; key table on p.3) |
| fin-02 | Landbay_10-Q_Dec2023_financial_statements.pdf (text PDF, 7 p, 2,609 words); Landbay_10-Q_MDA_printout_scan.pdf (scan, 2 p) |
| fin-03 | ManAHL_10-K_2023_Items5-6_p10-11.pdf (text, 2 p); ManAHL_MDA_2023_results_screenshot.png (PNG); ManAHL_10-K_F-6_changes_in_partners_capital.pdf (text, 1 p); ManAHL_10-K_Notes_F-10_to_F-12.pdf (text, 2 p); ManAHL_TradingCompany_F-16_F-20.pdf (text, 3 p) |
| fin-04 | NWAN_Q3FY26_earnings_release.pdf (text, 2 p); NWAN_10-Q_Q3FY26_Notes1-4.pdf (text, 2 p); NWAN_nonGAAP_reconciliation_screenshot.png (PNG) |
| fin-05 | Auditor_report_FY2025_signed_scan.pdf (scan, 2 p, stamp + handwritten note); Calder_10-Q_Q2-2026_excerpt_p3-4_p27.pdf (text, 3 p) |
| fin-06 | HarborLane_Credit_Agreement_2025_excerpts.pdf (text, 6 p, 1,902 words; grid on p.3); Compliance_Certificate_Q2-2026_signed_scan.pdf (scan, 2 p); Waiver_letter_Amendment_No2_2026-09-03.pdf (text, 2 p); HarborLane_press_release_2026-08-20.pdf (text, 1 p) |
| fin-07 | Altmark_10-K_FY2025_Note18_segments_p94-95.pdf (text, 2 p); Altmark_10-K_FY2025_MDA_segments_p41.pdf (text, 1 p) |
| fin-08 | BWRC_FY2025_earnings_release_2026-02-26.pdf (text, 1 p); BWRC_10-K-A_FY2025_restatement_excerpt.pdf (text, 3 p); BWRC_Investor_Fact_Sheet_Q1FY26.pdf (text, 1 p, faint injected line) |
| leg-01 | NDA_Lumen_Kestrel_2025_signed_scan.pdf (scan, 3 p; key clause on p.2) |
| leg-02 | MSA_Orbital_Pinecrest_2024_signed.pdf (text, 4 p, LoL on p.3); Amendment_1_to_MSA_signed_scan.pdf (scan, 1 p); Orbital_Partner_Program_Terms_v3.1.pdf (text, 1 p) |
| leg-03 | Sable_Cloud_Subscription_Terms_v4.2.pdf (text, 2 p); Order_Form_SO-2025-1187_signed.pdf (text, 1 p); Email_from_Sable_account_manager_2026-09-08.png (PNG) |
| leg-04 | Tessellate_Platform_Services_Agreement_2025.pdf (text, 3 p); Exhibit_D_Dispute_Resolution_scan.pdf (scan, 1 p) |
| leg-05 | Halvorsen_Corvid_Software_License_Agreement_2023.pdf (text, 2 p); Schedule_4_Competitors_update_2026-01-15_scan.pdf (scan, 1 p); Brightline_to_acquire_Corvid_press_release.pdf (text, 1 p); Corvid_Employee_FAQ_Brightline.pdf (text, 1 p) |
| leg-06 | Nimbus_Master_Subscription_Agreement_excerpt.pdf (text, 2 p); Schedule_2_Service_Level_Agreement.pdf (text, 2 p); Nimbus_October_2026_service_report_scan.pdf (scan, 1 p); Schedule_3_Data_Processing_Addendum.pdf (text, 1 p); Nimbus_News_Autumn_2026_screenshot.png (PNG) |

Totals: 28 text-layer PDFs, 8 image-only scans and 4 PNG screenshots.

Every scan has a skew of 0.5 to 1.8 degrees, noise, a binding shadow, a vignette, JPEG artefacts, a rubber stamp and a handwritten margin note in Bradley Hand. Every signed document has a handwritten signature. Each page carries a discreet footer: "Synthetic sample for software testing..." on synthetic files, or the SEC/FinDVer source with "licence UNVERIFIED" on real excerpts. The footer is never inside a quoted span.

## 3. Variation coverage matrix

| requirement | packets |
|---|---|
| all six relations | supports, contradicts, weakens, conditions, irrelevant: most packets; not_enough: fin-02, fin-05, fin-06 |
| every weakener type | qualifier fin-04, leg-04; exception leg-01, leg-04, fin-06, leg-05, leg-06; condition fin-05, fin-06, leg-02, leg-03, leg-04, leg-06; scope fin-02, fin-04, leg-04; time fin-03, fin-05, fin-08, leg-01, leg-02; magnitude fin-01, fin-02, leg-06; definition fin-04, leg-01, leg-05; weak_source fin-05, fin-08, leg-03, leg-05; absence fin-06 (+ absence lists) |
| 1-part claim | fin-05, leg-01 |
| 3+ part claim | fin-01, fin-02 (4), fin-03, fin-04, fin-06, fin-07, leg-02, leg-03, leg-04 |
| numeric / textual / table / scan docs | numeric+table: fin-01..08, leg-06; textual: all legal; scan: fin-02, fin-05, fin-06, leg-01, leg-02, leg-04, leg-05, leg-06 |
| packets of 1 / 2 / 3 / 4 / 5 docs | 1: fin-01, leg-01; 2: fin-02, fin-05, fin-07, leg-04; 3: fin-04, fin-08, leg-02, leg-03; 4: fin-06, leg-05; 5: fin-03, leg-06 |
| irrelevant distractor document (2+) | fin-03 (master fund), fin-06 (press release), leg-02 (partner terms), leg-06 (newsletter) |
| conflicting documents (2+) | fin-08 (10-K/A vs release), leg-02 (amendment vs MSA), fin-06 (waiver letter vs agreement), leg-03 (order form vs terms vs email), leg-06 (DPA vs MSA) |
| TRUE and well supported | fin-07, leg-02 |
| headline true, weakened by fine print | fin-04, leg-01 |
| documents silent on a part | fin-05, fin-06, fin-02, leg-01 |
| near-miss number | fin-01 (59.98 vs 59.996), fin-02 (38.33 vs 38.39; dollars read as millions) |
| right value in a different row/column | fin-01 (3m vs 9m), fin-03 (2022 column), fin-06 (step-down row), fin-08 (as reported vs restated), leg-06 (credit row) |
| "respectively" / list alignment | fin-02 (trap), fin-07 (correct alignment) |
| negation / modality | leg-01 (shall not ... except ... may), leg-03 (shall not apply), fin-05 (may become available) |
| AI claim with hallucination | fin-03 (no redemptions after year end), leg-05 (transfers to Brightline automatically) |
| definition trap | fin-04 ("Record"), leg-01 (marking + Representatives), leg-05 ("Affiliate" frozen at Effective Date), fin-06 (company "net leverage") |
| embedded AI instruction | fin-08 (faint line in fact sheet) |
| long docs (1,500+ words), buried clause | fin-01 (3,364), fin-02 D1 (2,609), fin-06 D1 (1,902) |
| REAL excerpts (3), at least 2 from the five LLM-approved claims | fin-01 (from 56eea761), fin-02 (919309df), fin-03 (a44776ca) |

## 4. Annotation guideline actually followed

1. **Parts.** Split the claim into independently checkable assertions. A causal clause ("mainly because of", "as a result") is its own part.
2. **Relations.** Annotate a relation for every span that a careful reviewer would want to see, including tempting wrong spans. Those are `irrelevant` with `distractor: true`.
   - `supports`: the span states or entails the part.
   - `contradicts`: the span is incompatible with the part.
   - `weakens`: the part survives but is narrowed, qualified or made less certain.
   - `conditions`: the part holds only if something else is true.
   - `not_enough`: the span is on topic but cannot settle the part.
   - `irrelevant`: a look-alike that must not be used.
3. **Weakener type.** Required on `weakens` and `conditions`, and optional on `contradicts` when the reason is a type: time, magnitude, scope or exception. On `supports` it is used only for `weak_source`, meaning support that comes from a low-authority source such as a sales email, an FAQ or a fact sheet.
4. **Superseded spans.** Annotate them with their literal relation and `superseded: true`, for example the original MSA cap or the pre-restatement figure. The part verdict follows the controlling document, using the precedence clause or the later date.
5. **Part verdict.** Each part gets one of:
   - supported
   - weakened (true as stated but materially qualified or conditional)
   - contradicted
   - not_enough
6. **Overall verdict.**
   - `contradicted` if any part is contradicted.
   - `supported` if all parts are supported.
   - `cannot_tell` if no part can be settled.
   - `partly_supported` otherwise, meaning some parts are weakened or not_enough and none is contradicted.
7. **Numbers.** Recompute every number. A rounding-level miss on an "approximately" claim is `weakens/magnitude`. A wrong scale, period or row is `contradicts`.
8. **Quotes.** Quotes are verbatim, the shortest span that carries the meaning, and a single passage. For tables, the quote is the row as it appears in the text twin; pipes are layout, not words.
9. **Absence.** Add an absence note when the deciding fact is outside the packet. Never infer it from outside knowledge.
10. **FinDVer labels.** The real packets were annotated from the passage text only. FinDVer's labels, explanations and python fields were not used.

## 5. Ten observations for the product

1. **Show the controlling evidence first, not the first match.** In 5 packets the earliest or most prominent span is superseded or overridden: the release before the restatement, the original MSA before the amendment, the Terms before the Order Form, the MSA before the DPA, the 4.75x grid row. The UI needs a "controls / superseded" badge and should order cards by authority and date, not by page order.
2. **Verdicts need the tool's own arithmetic on screen.** Six packets hinge on a recomputed number: 59.996%, 38.39%, the $0.001 par proving whole dollars, 99.13% uptime to the 5% band, 49.1/50.3, and the October 2 deadline. A reviewer will not trust "contradicted" without the formula next to the boxed cells.
3. **Distractors deserve a visible lane.** 14 irrelevant spans are deliberate look-alikes: wrong period, wrong entity, wrong row, wrong plan, similar name. Showing them greyed with a reason ("different entity") builds more trust than hiding them, and it explains why the obvious answer is wrong.
4. **Evidence routinely spans documents.** The forum answer (leg-04) is in an exhibit that the agreement points to. Breach notice (leg-06) needs three spans in two files. The Competitor fact (leg-05) is in a scanned schedule, and the proviso is in the license. Cards need "linked spans", and the page pane should jump between files.
5. **Hardest weakeners to locate: definition and condition.** Definition weakeners sit far from the claim words: footnote (1) on page 2, Note 1 of a different document, clause 1.1 versus clause 3.2. Condition weakeners hide in "Subject to ... paragraph 4" or "if the offering is completed". Retrieval by claim keywords alone will miss them; the engine should follow defined terms and cross-references.
6. **Within-sentence splits matter.** "shall not disclose ... except that ... may disclose" is one sentence carrying both supports and weakens. Boxes and relations need sub-sentence spans, or the UI will paint one sentence both green and amber.
7. **Absence must be a first-class card.** In 4 packets the honest answer depends on something not uploaded: the pricing email, proof the offering closed, the waiver fee paid, an auditor's report. A grey "not in your files" card with a suggested document to add is more useful than a low-confidence verdict.
8. **Scans are where demos break.** 8 of 40 files have no text layer, with skew, stamps over headers, and handwriting near clauses. OCR must keep table rows intact (Schedule 2 lines, Schedule 4 rows). The box must be drawn on the rotated page, which is why scans also carry `quad`.
9. **Judgment is unavoidable in a few places and should be labelled as such.** These are: whether 59.98% counts as "approximately" right, the double "respectively" in Landbay Note 4, whether $4.35m of redemptions is "material", and whether "grew its business" means reported or organic growth. The product should say "judgment call" and show both readings, not hide them inside a confident verdict.
10. **Robustness is a UI feature.** The prompt injection in fin-08 should surface as a banner pinned to its box, not just be ignored silently. Weak sources (sales email, internal FAQ, fact sheet) should carry a badge even when they support the claim. Users will otherwise cite them.

## 6. Judgment or knowledge claims the documents cannot fully settle

| packet | claim element | why | how labelled |
|---|---|---|---|
| fin-05 | "enough cash ... through the end of 2027" | a forecast that depends on an unconfirmed offering | cannot_tell, with conditions and weak_source relations and an absence note |
| fin-04 p2 | "grew its business" | reported +6.7% vs organic -3.1%; meaning depends on the reader | weakened (scope) |
| fin-01 p1 | "approximately 59.98%" | the precision claimed is wrong but the size is right | weakened (magnitude), not contradicted |
| fin-03 p3 | "no material redemptions" | materiality is a judgment; $4.35m is about 5% of capital | contradicted, with the materiality reasoning in the note |
| fin-02 p3 | the double "respectively" | the sentence aligns amounts, years and lenders | contradicted on the plain reading, with ambiguity flagged in the note |
| leg-01 | "can't share with anyone" | depends on whether the email was marked Confidential, a fact outside the packet | partly_supported, plus an absence note |
| leg-06 p2 | 24h vs 72h | could be read as cumulative obligations; the DPA's "sole obligations" sentence settles it | contradicted; observation 9 records the drafting point |

## 7. Best three for a 3-minute demo

1. **leg-06-sla-dpa.** Five files of every kind (text PDF, scan, PNG). One number is wrong for a visible reason (maintenance excluded, 5% row), a tempting newsletter is greyed out, and a precedence clause flips a second part. It shows cross-document linking, distractor handling and arithmetic in under a minute.
2. **fin-08-restatement-injection.** Short, legible, and dramatic. Two documents agree, a later filing withdraws the number, and a file tries to instruct the AI. It demonstrates "controlling evidence first" and robustness in a single screen.
3. **fin-04-record-revenue.** It proves the tool does not cry wolf. Every headline is true, yet the footnote definition of "record", the organic decline and the GAAP loss appear as amber fine print. It pairs well with the two red cases above. The alternative for a "true claim" moment is fin-07, which is shorter but less interesting.

## 8. Verification checklist

- [x] Every gold quote is an exact substring of its source body: `fl_build.py` checks `body.count(quote) >= 1`, and all quotes are unique except where reviewed.
- [x] Every gold quote is an exact substring of its `ground_truth/` twin: 126/126 (`fl_verify.py`). Quotes do not cross physical page markers.
- [x] Text-layer PDFs: `pdftotext` output contains every quote after normalising pipes and whitespace (0 mismatches). It is non-empty for all 28 files.
- [x] Scan PDFs: `pdftotext` returns no text for all 8 files.
- [x] Boxes on text-layer PDFs were checked independently against `pdftotext -bbox` word boxes. The first and last words of each quote fall inside the gold box on the gold page: 94/94.
- [x] Boxes on scans and PNGs were computed from the layout and transformed with the same rotation, crop and window-bar offset used to make the image. Overlay crops for all 126 relations are written to `packs/build/fl/_debug/`. I inspected a sample covering scan tables, scan paragraphs, PNG text, the faint injection line, wide 11-column tables and grid rows, and all sat on the quoted span. On scans, multi-line boxes are slightly taller because of skew, so a `quad` is provided.
- [x] Arithmetic in every synthetic table was re-footed: segments, reconciliations, restatement, covenant schedule, uptime.
- [x] Real excerpts were copied byte-for-byte from FinDVer paragraphs (`scratchpad/tools/make_real_docs.py`). Licence marked UNVERIFIED.
