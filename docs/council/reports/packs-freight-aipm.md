# Freight and AI-PM evidence packets

SYNTHETIC. Every company, person, number and document in these packets is invented for testing ProofGraph. Every rendered page also has a small footer that says "Synthetic sample for software testing". No quoted span includes that footer.

Root: `scratchpad/packs/` (absolute path: `<scratchpad>/packs/`)

Each packet folder `packs/<domain>/<id>/` contains:
- `upload/`: the files a user drags in. These are real PDFs, JPGs and PNGs. There is no Markdown in this folder.
- `claim.txt`: the claim to paste.
- `pack.json`: the gold annotation. Every relation has a file, a page and a bounding box.
- `README.md`: the on-screen demo path, the moments to click, and the failure cases to watch.
- `ground_truth/<doc>.txt`: a text twin made from the layout record. Every gold quote is an exact substring of it.
- `_debug/`: verification output only. It holds the clean pre-scan PDFs and pages with each gold box drawn in red. It is not for upload.

Build, all reproducible: `packs/build/fa/fa_build_all.py`, with the content modules `fa_content_*.py` and the layout engine `fa_render.py`. The finance and legal builder uses `packs/build/render.py`, which belongs to them. I moved my scripts into `packs/build/fa/` after the two files collided. To run:
`cd <main-checkout>/.claude/worktrees/proofgraph-meta-hackathon-e83833 && uv run --with reportlab --with pillow python <scratchpad>/packs/build/fa/fa_build_all.py`

## 1. Index

| id | title | claim | gold | rels | tags (main) | diff |
|---|---|---|---|---|---|---|
| frt-01-detention-amended-rate | Detention bill after a rate amendment and an early arrival | INV-55821 correctly bills 3.5 h detention at $85/h for $297.50 | contradicted | 11 | amendment, later email, distractor, computation, screenshot | 4 |
| frt-02-lumper-buried-cap | Lumper reimbursement vs long contract and receipt scan | Copperline paid $275 lumper and can recover the full amount | partly_supported | 10 | long doc (1,643 words, key clause on p5 of 6), JPG scan, absence, exception | 3 |
| frt-03-on-time-true | On-time delivery that really was on time | Load 7713 was delivered on time | supported | 6 | true claim, no cry wolf, handwritten POD scan | 1 |
| frt-04-bol-weight-pallets | Weight and pallets: BOL vs scale ticket | Weighed 18,450 lb across 22 pallets, as shown on the BOL | partly_supported | 7 | near-miss 18,540, table wrong cell (22 drums), 2 scans, photo placeholder | 3 |
| frt-05-carmack-released-value | AI summary overstates Carmack liability | Carrier liable for full $48,000; 18 months to file | contradicted | 10 | AI hallucination, released value, "shall not ... unless" | 4 |
| frt-06-lane-rate-respectively | Lane rate: "respectively", amendment, fuel table | Bills contracted $2,150 linehaul, 28% FSC, total $2,752 | contradicted | 8 | respectively trap, signed amendment scan, table band | 4 |
| frt-07-tonu-injection | TONU with cancellation exception and planted AI instruction | Owed $250 TONU because shipper cancelled | contradicted | 9 | prompt injection, "No TONU shall be paid if" | 3 |
| frt-08-demurrage-cannot-tell | Demurrage with only the terminal schedule | 7 days beyond free time at $150/day = $1,050 | cannot_tell | 6 | 1 doc, 2-page scan, per-TEU scale trick, silent | 3 |
| aipm-01-ab-segment-lift | A/B lift quoted from one segment | Ranker v7 improved task success by 12% | partly_supported | 6 | table wrong row, relative vs pp, distractor, PNG | 2 |
| aipm-02-latency-requirement | Latency PASS against an outdated PRD target | We met the PRD's latency requirement | contradicted | 8 | later email supersedes, 1.71 s unit trick, PNG | 3 |
| aipm-03-eval-no-regression | "No regression" true on headline, narrowed in methods | v4.2 eval shows no regression vs v4.1 | partly_supported | 7 | 1 doc, long (1,561 words, 5 pages), headline vs fine print | 3 |
| aipm-04-postmortem-cause | AI incident summary blames the wrong change | Caused by 14:02 config push, rolled back 14:20, no data lost | contradicted | 11 | AI hallucination, postmortem supersedes status page, 2 PNGs | 3 |
| aipm-05-safety-launch | "Safe for launch" with an open P0 and an untested locale | Review complete, all P0 closed, red team covered every locale | contradicted | 10 | 5 docs, distractor, modality, cross-doc join, PNG tracker | 4 |
| aipm-06-model-card-data | Model card claim vs training data sheet | Licensed and public-domain only, no user data, March 2025 cutoff, 12 bias groups | contradicted | 9 | 4 parts, "except" trap, definition trap, silent part | 3 |

There are 118 gold relations in total. By relation: contradicts 38, supports 34, weakens 16, conditions 14, irrelevant 11, not_enough 5. By weakener: time 16, magnitude 14, scope 14, condition 9, definition 7, weak_source 6, absence 5, qualifier 5, exception 4. Absence entries appear in 4 packets. Overall gold: supported 1, partly_supported 4, contradicted 8, cannot_tell 1.

## 2. File types per packet

| packet | native PDF (text layer) | image-only scan PDF | JPG scan | PNG screenshot | photo placeholder | multi-page with buried key |
|---|---|---|---|---|---|---|
| frt-01 | RateCon_RC-40917.pdf (2p), email_detention_rate_change.pdf, Invoice_INV-55821.pdf, Reefer_FSC_bulletin_wk1006.pdf | | | YMS_gate_events_BPL-118204.png | | RateCon p2 clock rule |
| frt-02 | Halvorsen_Copperline_TSA_2025.pdf (6p), Invoice_CT-77310.pdf | | lumper_receipt_scan.jpg | | | TSA p5 cap, p6 approval rule |
| frt-03 | Appointment_confirmed_Ref7713.pdf | POD_7713_signed_scan.pdf (handwritten times, stamp) | | | | |
| frt-04 | | BOL_30552_signed_scan.pdf, Scale_ticket_028841_fax.pdf | | | PLACEHOLDER_trailer_photo.png | |
| frt-05 | ACX_100-F_Rules_Tariff.pdf (4p), email_thread_concealed_damage.pdf | BOL_LKW-55190_scan.pdf | | | | Tariff p3-4 |
| frt-06 | MTA_Schedule_A_Pemberly_Lonestar.pdf, Schedule_A-1_Fuel_Surcharge.pdf, Invoice_LT-2025-1187.pdf | Amendment_2_Schedule_A_signed.pdf (handwritten signatures) | | | | |
| frt-07 | RateCon_Load_88412.pdf, email_thread_cancel_88412.pdf, Tallgrass_dispute_letter_TC-1049.pdf | | | | | |
| frt-08 | | PGCT_import_demurrage_schedule_scan.pdf (2p, stamp, handwritten note) | | | | Exceptions on p2 |
| aipm-01 | Q4_2025_OKRs_Search.pdf | | | EXP-2291_readout_dashboard.png | | |
| aipm-02 | PRD_Summarize_API_v2_v1.2.pdf (2p), email_PRD_v1.3_latency_change.pdf | | | k6_load_test_summary.png | | PRD p2 NFRs |
| aipm-03 | MQR-2025-41_v4.2_vs_v4.1.pdf (5p) | | | | | p2 section 5.6/5.7, p4 glossary |
| aipm-04 | Postmortem_INC-4471.pdf (2p) | | | slack_inc-4471-auth.png, status_page_oct3.png | | Data loss on p2 |
| aipm-05 | Launch_readiness_checklist.pdf, Red_team_summary_round2.pdf, Launch_plan_v4.pdf, Marketing_brief_SmartReply.pdf | | | safety_tracker_SMARTREPLY.png | | |
| aipm-06 | Atlas-7B_model_card.pdf, Atlas-7B_data_sheet.pdf (2p) | | | | | Data sheet p2 exception |

Totals: 26 native PDFs, 6 image-only scan PDFs, 1 JPG scan, 6 PNG screenshots, and 1 photo placeholder. Scans are rotated 0.6 to 1.8 degrees and carry paper tint, an edge shadow, a vignette, Gaussian noise, specks, blur and JPEG artefacts. Some also have rubber stamps, Bradley Hand handwriting, and Snell Roundhand signatures. Only frt-04 depends on a photo, and that photo is optional. Its README has a capture sheet, and the gold count is 21 pallets.

## 3. Variation coverage matrix

| requirement | packets |
|---|---|
| weakener: qualifier | frt-02, frt-05, aipm-03, aipm-06 |
| weakener: exception | frt-02, frt-07, frt-08, aipm-06 |
| weakener: condition | frt-01, frt-02, frt-05, frt-07, frt-08, aipm-02, aipm-05 |
| weakener: scope | frt-04, frt-05, frt-06, frt-07, aipm-01, aipm-03, aipm-04, aipm-05, aipm-06 |
| weakener: time (superseded or different time) | frt-01, frt-02, frt-05, frt-06, aipm-02, aipm-04, aipm-05 |
| weakener: magnitude | frt-01, frt-02, frt-04, frt-05, frt-06, frt-07, frt-08, aipm-01, aipm-02, aipm-06 |
| weakener: definition | frt-01, frt-03, frt-08, aipm-04, aipm-05, aipm-06 |
| weakener: weak_source | frt-01, frt-04, frt-06, frt-07, aipm-04 |
| weakener: absence | frt-02, frt-08, aipm-05, aipm-06 |
| relation: supports | 13 of 14 (all except aipm-05) |
| relation: contradicts | 12 of 14 (all except frt-03, aipm-03) |
| relation: weakens | frt-04, frt-05, aipm-01, aipm-02, aipm-03, aipm-04, aipm-05, aipm-06 |
| relation: conditions | frt-01, frt-02, frt-05, frt-06, frt-07, frt-08, aipm-02, aipm-05 |
| relation: not_enough | frt-02, frt-08, aipm-05, aipm-06 |
| relation: irrelevant | frt-01, frt-03, frt-04, frt-05, frt-06, frt-07, aipm-01, aipm-05 |
| claim with 1 part | frt-03, aipm-02, aipm-03 |
| claim with 3+ parts | frt-01, frt-02, frt-04, frt-05, frt-06, frt-07, aipm-04, aipm-05, aipm-06 (4 parts) |
| numeric documents | frt-01, frt-04, frt-06, frt-08, aipm-01, aipm-02 |
| textual documents | frt-02, frt-05, frt-07, aipm-03, aipm-06 |
| table documents | frt-01, frt-02, frt-04, frt-06, frt-08, aipm-01, aipm-05 |
| scan-like documents | frt-02 (JPG), frt-03, frt-04, frt-05, frt-06, frt-08 |
| packet of 1 / 2 / 3 / 4 / 5 docs | 1: frt-08, aipm-03. 2: frt-03, frt-04, aipm-01, aipm-06. 3: frt-02, frt-05, frt-07, aipm-02, aipm-04. 4: frt-06. 5: frt-01, aipm-05 |
| irrelevant distractor document | frt-01 (reefer bulletin), aipm-01 (OKRs), aipm-05 (marketing brief) |
| conflicting documents | frt-01 (email supersedes RateCon), frt-06 (amendment overrides schedule), aipm-02 (email supersedes PRD), aipm-04 (postmortem supersedes status page) |
| claim true and well supported | frt-03 |
| true on headline, weakened by fine print | aipm-03 (also frt-02 "At cost" row, aipm-02 PASS badge) |
| documents silent on part of the claim | frt-08, aipm-06 (P4), aipm-05 (pt-BR), frt-02 (approval) |
| near-miss number | frt-04 (18,540 vs 18,450), aipm-02 (1.71 s vs 1,500 ms), frt-08 (per TEU), aipm-01 (relative % vs pp), frt-01 (quarter-hour rounding) |
| table value in another row or column | frt-04 (22 is drums), frt-06 (28% row), aipm-01 (Desktop row), aipm-05 (Mitigation vs Verification column) |
| "respectively" / list alignment | frt-06 |
| negation or modality trap | frt-05 ("shall not be liable ... unless", condition met), frt-07 ("No TONU shall be paid if"), aipm-05 ("shall not proceed until", "may proceed"), aipm-06 ("except") |
| AI-generated claim with plausible hallucination | frt-05 (18 months comes from a records-retention item), aipm-04 (14:20 decision read as rollback; cause taken from a Slack guess) |
| embedded instruction aimed at AI | frt-07 (dispute letter) |
| long documents, 1,500+ words, key clause buried | frt-02 TSA (1,643 words, 6 pages, cap on p5), aipm-03 eval (1,561 words, 5 pages, caveats on p2 and p4). frt-05 tariff is 1,223 words over 4 pages |

## 4. Annotation guideline I followed

1. Split the claim into parts that can each be checked against one fact or rule. Amounts, counts, dates, causes and scope words each get their own part.
2. For each part, record every span a careful reviewer would want to see. That includes spans that look supportive but should not decide the verdict.
3. The `relation` field says what the span says about the part on its face: supports, contradicts, weakens, conditions, not_enough or irrelevant.
4. `weakener_type` gives the reason when a span changes the force of the evidence.
   - It uses the closed list: qualifier, exception, condition, scope, time, magnitude, definition, weak_source, absence.
   - When a supports span carries weak_source or time, the support is self-serving or superseded. The invoice or letter written by the claimant counts as weak_source. A PRD text that a later email replaces counts as time.
5. Superseded evidence is kept and labelled with the reason "time". The note says which document controls. The verdict uses only controlling evidence.
6. Irrelevant is used only for tempting spans: a lookalike number, a different program, the source of a hallucination, or an injected instruction. It is never used for random text.
7. Absence is anchored to the place the fact would normally appear: a blank field, an "N/A", a pointer to a missing invoice, or the list that omits a locale. It is also listed in `absence`.
8. Overall labels:
   - supported means every part is supported by controlling evidence.
   - contradicted means the claim, read as the user would act on it, is false: an amount, date, cause or decision it asserts is wrong.
   - partly_supported means the main assertion holds in some form, but a part is false or materially narrowed.
   - cannot_tell means a needed fact is missing and nothing contradicts the claim.
9. `part_status` gives a per-part verdict, so a scorer can grade parts as well as the whole claim.
10. Quotes are exact substrings of the rendered text twin.
    - Table-row quotes are the cells joined by single spaces in reading order.
    - Markdown markers and handwriting markers are removed.
    - Each quote occurs exactly once in its document.
11. Boxes are computed from the layout record of each drawn text run, not estimated by eye. Each box is the union of the runs the quote touches, padded by 1.5 points. Units are normalised 0 to 1000, origin top-left. For scans, the box corners are rotated by the same skew as the page image.

## 5. Ten observations for how to build the product

1. **Show the controlling clause first.** In 9 of 14 packets, a span that looks supportive sits next to the span that decides the verdict. Examples: $65 vs $85, PASS vs v1.3, the status page vs the postmortem. Each part card needs a "controls" marker, and superseded evidence should appear greyed with a pointer to what replaced it. Ordering by date and by amendment language is a core feature.
2. **Arithmetic is evidence.** frt-01, frt-06 and frt-08 cannot be decided without a calculation across 2 or 3 files: clock start, rounding, rate band and per-TEU pricing. A reviewer needs to see the computed value with each input linked to its box. A verdict chip alone is not enough.
3. **Evidence often spans documents.** In frt-07, an email timestamp is checked against a rate confirmation cutoff. In aipm-05, a launch plan locale list is checked against the red-team list. In frt-01, a yard screenshot row is checked against a page-2 clause. The evidence card has to hold a "because" chain of two or three spans from different files.
4. **The killer clauses share few words with the claim.** "Detention time begins at the later of...", "not to exceed $250.00 per stop" and "carried over from v4.1" barely overlap the claim text. Retrieval that ranks only by similarity to the claim will miss the buried clauses on page 2 or page 5. Scan every condition, definition, exception and footnote, then link them.
5. **Tables need row and column context.** The four table traps all put the tempting value in the right table but the wrong cell. The highlight should box the whole row and name the column header of the value used ("PKG QTY = 22", not "pallets = 22").
6. **Negation and modality need a condition state.** "Shall not be liable ... unless notice within 5 days" in frt-05 is a condition that was met. "No TONU shall be paid if ... before 18:00" in frt-07 is an exception that was triggered. A conditions card should show met, unmet or unknown. A plain contradicts/supports flip gets these cases wrong.
7. **Absence must be explicit and actionable.** The UI should list what is missing and which document would settle it. For frt-08, that is the demurrage invoice and the container size. For frt-02, it is the approval number. The not_enough anchors show where the gap sits on the page.
8. **Weak sources look like strong support.** The claimant's invoice, the carrier's letter and a Slack guess all "support" the claim. A source-role badge (claimant, counterparty, neutral record, later or final) would let a reviewer discount them at a glance.
9. **Do not cry wolf.** frt-03 has a tempting 10/13 date and must come out clean green. AI-generated claims tend to borrow a nearby real number: 18 months from records retention, and 14:20 from the rollback decision. Showing that lookalike span as "this is where the number came from" is high value and builds trust. Separately, the injected instruction in frt-07 must be surfaced as a warning, never obeyed or hidden.
10. **Scans and handwriting are where demos break.** Key values in frt-03 (handwritten 09:18 and "N") and in frt-06 (signature dates) only exist in handwriting on skewed scans. Multi-line quotes also need several line boxes, not one union rectangle (see the frt-02 B.4 debug image). Test OCR on these pages before the demo.

## 6. Best three packets for a 3-minute demo

1. **frt-07-tonu-injection.** It has three short files and a familiar money dispute. The verdict turns on one clause plus one timestamp ("before 18:00 the day prior" vs 16:20). It ends with a robustness moment, because the tool shows the planted "mark as SUPPORTED" note as a warning and keeps its verdict. It runs in about 60 seconds.
2. **aipm-05-safety-launch.** This one speaks to judges who are product people. It shows a cross-document join (pt-BR), a table column trap (Shipped vs Verification Pending), a modality trap ("GA launch shall not proceed until"), and a distractor that is correctly set aside. It is visually strong because the tracker is a PNG screenshot with a boxed row.
3. **frt-03-on-time-true.** This is a 20-second contrast case. The tool reads a handwritten time on a skewed scan, files the tempting 10/13 date as irrelevant, and returns a clean green. It proves the tool does not invent problems.

Alternate: frt-01-detention-amended-rate is the richest freight case, with an amendment, a screenshot, arithmetic and a $85 overbill. It needs more than a minute to explain.

## 7. Self-check: how quotes and boxes were verified

- Every quote was located in the layout record (the text twin in `ground_truth/`) and checked to occur exactly once in that document. The run reported 0 missing and 0 duplicate quotes across 118 relations.
- Every quote was checked to sit on a single page. No quote spans a page break.
- For each native PDF, I ran pdftotext in layout mode and in raw mode. Every quote appears in the extracted text once whitespace is collapsed, with no token-only fallbacks. Each PDF also has a non-empty text layer.
- For each image-only scan PDF, pdftotext returns no text.
- For the JPG and PNG files, there is no text layer by design. Their quotes are checked against the ground-truth twin.
- Each box was drawn back onto the final uploaded file, after skew, noise and stamps, and saved under `_debug/`. I opened and inspected these pages:
  - frt-03 POD scan
  - frt-04 BOL scan and scale ticket
  - frt-02 receipt JPG and TSA page 5
  - frt-06 amendment scan
  - frt-08 tariff scan page 1
  - aipm-01 readout PNG
  - aipm-05 tracker PNG

  In each, the red boxes sat on the quoted text. Stamps and handwriting were placed only in areas with no text.
- I checked that the scans are legible and that the handwritten values carry the quoted information (09:18, N, signature dates).
- I checked that the "Synthetic sample for software testing" footer is outside every quote.
