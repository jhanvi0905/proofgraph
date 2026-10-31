# ProofGraph final plan: final case set, demo, realignment, sprint

Written Sat 31 Oct 2026, evening IST. Read-only pass. $0 spent, no Meta or Baseten call made. This file UPDATES `roadmap-sprint.md` (called "the roadmap" below). Anything this file does not mention stays as the roadmap says.

Skills used: `pm-execution:sprint-plan` (capacity, buffer, critical path, sprint goal) and `engineering:testing-strategy` (test pyramid per new module, gaps). Prioritisation reuses the roadmap's weighted rubric; the pre-mortem reuses its tiger table, updated in section 4.6.

Inputs read: the dataset `README.md`, `CASE_PRIORITIES.md`, `DATASET_SOURCES.md`, `EVALUATION_GUIDE.md`, `Test Cases/README.md`, `CLAIMS.md`, `_Evaluation/expected_results.json` (all 46), `manifest.json`, `split_groups.json`, one solution file, `Format Conversions/README.md`; evidence of cases 4, 10, 12, 17, 23, 25, 28, 31, 37, 38, 39, 40, 41, 42, 43 opened with `pdfinfo`/`pdftotext`/`textutil` or viewed as PNG; page counts and text layers checked for 14 cases; the roadmap in full; the two pack indexes; the code signatures in `proofgraph/`, `app/streamlit_app.py`; docs 02, 05, 06, 08, 10, 11, 12 and `docs/sprint/2026-10-31-final.md`; diffstats of open PRs 27 to 29.

## 0. What is new, in eight lines

1. The human's suite gives real or externally published documents. The best of it (ContractNLI 37 to 46 and LegalReasonBench 11 to 22) has real support-versus-contradiction structure. Most "weakeners" are hidden inside `context_only` anchors and need relabelling into our vocabulary.
2. **Final set: 29 cases** (21 from the suite, 8 of our packs). 11 DEV, 18 HELD-OUT. Table in 1.4.
3. **Lead demo moves off freight** to LegalReasonBench Test Case 17 (interim CMO governance: a confident General Counsel memo against the bylaws and the board date). Second is ContractNLI Test Case 40 (real Bosch NDA). frt-07 stays as the builder's-world freight beat with the injection. Section 2.
4. **DOCX is not built.** The dataset already ships exact PDF conversions of every IHP DOCX file. The app says "save as PDF" for DOCX. No new dependency.
5. Tobacco800 PNGs are **1-bit images stored with ink as white on black** (YACCLAB packaging). Ingest must invert them, or Muse and the viewer read a negative.
6. **Engineering recommendation stays option B** (new `proofgraph/review/` layer beside the frozen engine), with the numeric bridge demoted to Should, because the final set is mostly wording.
7. The walking skeleton target moves to a ContractNLI page (Test Case 40, 4 pages, clean text layer): the easiest real page in the set.
8. 22 decisions for the human at the end, with costs. Total new Meta spend asked: about $16 across all runs, each run far under the $50 cap.

---

## STAGE 1. DATA PANEL

Panel: dataset curator (DC), annotation lead (AL), eval statistician (ES), legal expert (LX), finance expert (FX), freight expert (FR), ingestion engineer (IE), licensing reviewer (LR).

### 1.1 What we found in the evidence

| Finding | Evidence | Consequence |
|---|---|---|
| ContractNLI packets are one intact, real, text-layer PDF each, 1 to 7 pages, 386 to 2,615 words | `pdfinfo`/`pdftotext` on 37, 38, 39, 41, 42, 43 | Exact boxes by snapping. Easiest real ingestion in the set |
| ContractNLI file names contain `%20` and one has a leading space (`" 064-19 Non Disclosure Agreement 2019.pdf"`, cases 38, 45, 46) | `ls` | Ingest must sanitise display names and never trust names as ids |
| Several ContractNLI documents are unsigned templates (Frodsham has `[NAME OF INDIVIDUAL RECEIVING INFORMATION]`) | text of 43 | Claims concern wording only. Show a "looks like an unsigned template" note |
| LegalReasonBench Braddock files are text-layer PDFs (2 to 4 pages); IHP files are DOCX in packets 17 to 22, except the appointment letter in 21 | listing, `textutil` | DOCX is the only blocker for the IHP group |
| `Format Conversions/LegalReasonBench/` holds exact PDF conversions of all six IHP DOCX files (1 to 3 pages, full text layer), with hashes in `provenance.json` | `pdfinfo`, README | Use those PDFs. No DOCX code needed |
| Test Case 14 has the comparator memo as a 1360x1760 PNG | listing | One real scan route inside the legal group |
| Tobacco800 PNGs are 1-bit grayscale, 1200 to 2560 px wide, and render white text on black | `file`, viewed 25 p1 | Invert before display and before sending to Muse |
| Test Case 23's `MALIBU_study_plan.pdf` is an image-only PDF (ReportLab wrapper, 0 words) | `pdftotext` | Exercises the image-only PDF path |
| Company Documents are PyFPDF/ReportLab renderings of the Northwind sample database (orders 10248, 10249, 11060, Federal Shipping) | text of 4 and 10, PO PNG | Realistic workflow, unrealistic documents. Licence unverified |
| SD02 pages are 2560x3300 1-bit forms; two are wrapped in image-only PDFs | `file`, `pdftotext` | Small handwritten digits need crop re-read; diagnostic only |
| Reference anchors use `supports`, `contradicts`, `context_only` only. There is no `weakens` | `expected_results.json` | The weakener structure must be relabelled by us |
| Anchors give a location sentence ("Page 1, TotalPrice") and a fact, often not a verbatim quote, and no box | all 46 | Gold needs a verbatim quote and page per anchor; boxes come from snapping |

Weakener structure that is real but hidden in `context_only`: Test Case 4 ("Shipped Date: 2016-07-16" is a scope weakener for "received"), 16 (back pay "less the 45-day suspension and less interim earnings" is a magnitude exception), 17 (resolution "effective as of May 7" versus bylaws "No appointment ... shall be effective unless and until approved" is a time/condition weakener), 20 (bylaws require a licence but nothing proves it: absence), 37 (the consent qualifier), 40 (the written-authorisation condition), 46 (the no-use condition), 23 (a plan is not a result). That is the product's core story, and it lives mostly in ContractNLI and LegalReasonBench.

### 1.2 Scores for all 74 candidates

Scale 0 to 3 unless stated. Fit = real support and contradicting or weakening structure. Real = document realism. Lic = licence fit for a public repo (3 committable, 2 committable with attribution, 1 pointer only, 0 unknown). Ing = ingestion difficulty (0 easy, 3 hard). Gold = quality of the existing reference for our vocabulary. Lab = hours to make it scorable in our schema. Drama = 3-minute demo value. Dom = fit to the builder's domains (freight F, finance $, legal L, AI PM A).

**Suite cases (46)**

| Case | Fit | Real | Lic | Ing | Gold | Lab h | Drama | Dom | Note |
|---|---|---|---|---|---|---|---|---|---|
| 1, 2, 5, 6, 7, 9 | 1 | 1 | 0 | 0 to 1 | 2 | 0.2 each | 0 to 1 | $ F | Single lookups, arithmetic or absence on sample-database renderings |
| 3, 8 | 2 | 1 | 0 | 1 | 2 | 0.3 | 1 | $ | Image invoice row match; no double counting |
| 4 | 2 | 1 | 0 | 0 | 2 | 0.3 | 1 | F | Shipped is not received |
| 10 | 2 | 1 | 0 | 1 | 2 | 0.3 | 1 | $F | PO is an image; supported |
| 11 | 3 | 2 | 2 | 0 | 2 | 0.4 | 2 | L | Penalty change is not exoneration |
| 12 | 3 | 2 | 2 | 0 | 3 | 0.3 | 3 | L | Award 45 days vs later summary 40 |
| 13 | 2 | 2 | 2 | 0 | 2 | 0.3 | 1 | L | Supplemental record adds Kucera |
| 14 | 3 | 2 | 2 | 2 | 2 | 0.5 | 2 | L | PNG memo, on duty vs off duty |
| 15 | 2 | 2 | 2 | 0 | 2 | 0.3 | 1 | L | Record timing |
| 16 | 3 | 2 | 2 | 0 | 2 | 0.3 | 2 | L$ | "less the 45-day suspension and less interim earnings" |
| 17 | 3 | 2 | 2 | 1 | 2 | 0.5 | 3 | L | Confident GC memo vs bylaws vs board date |
| 18 | 3 | 2 | 2 | 1 | 2 | 0.4 | 3 | L | Started May 7, approved May 13 |
| 19 | 2 | 2 | 2 | 1 | 2 | 0.3 | 1 | L | Interim, not permanent |
| 20 | 2 | 2 | 2 | 1 | 2 | 0.3 | 1 | L | Licence not proven: abstain |
| 21 | 1 | 2 | 2 | 0 | 2 | 0.2 | 0 | L$ | Direct cross-page reference |
| 22 | 3 | 2 | 2 | 1 | 2 | 0.4 | 2 | L | Principal vs subordinate officer |
| 23 | 2 | 3 | 1 | 2 | 2 | 0.5 | 2 | A | Plan and blank form are not results |
| 24 | 2 | 3 | 1 | 2 | 2 | 0.4 | 1 | A | Groups vs treatments |
| 25 | 2 | 3 | 1 | 2 | 2 | 0.4 | 2 | L | Real 1989 letter: "unauthorized uses" |
| 26 | 1 | 3 | 1 | 2 | 2 | 0.3 | 1 | L | Recall demand, supported |
| 27 | 2 | 3 | 1 | 2 | 2 | 0.4 | 2 | L | Denial is not lab proof |
| 28 to 36 | 1 to 2 | 0 | 1 | 3 | 2 | 0.4 each | 1 | $ | Synthetic 1988 forms, arithmetic and identity diagnostics |
| 37 | 3 | 3 | 2 | 0 | 3 | 0.3 | 2 | L A | Consent qualifies the ban |
| 38 | 2 | 3 | 2 | 0 | 3 | 0.3 | 1 | L | Retention exception |
| 39 | 2 | 3 | 2 | 0 | 3 | 0.3 | 1 | L | Negotiations are confidential |
| 40 | 3 | 3 | 2 | 0 | 3 | 0.3 | 3 | L A | Consultants need written authorisation |
| 41 | 2 | 3 | 2 | 0 | 3 | 0.3 | 1 | L | Survival clause |
| 42 | 1 | 3 | 2 | 0 | 2 | 0.3 | 1 | L | Oral disclosure; source annotation dispute on this topic |
| 43 | 3 | 3 | 2 | 0 | 3 | 0.2 | 2 | L | "except the right to copy ... solely for the Purpose" |
| 44 | 2 | 3 | 2 | 0 | 3 | 0.2 | 2 | L | No notice duty: disciplined abstention |
| 45 | 3 | 3 | 2 | 0 | 3 | 0.3 | 2 | L | Not technical only: PHI and PII listed |
| 46 | 3 | 3 | 2 | 0 | 3 | 0.3 | 1 | L | Independent development with no-use condition |

**Constructed packs (28)** (fit and drama from the pack indexes; Lic 3 = synthetic and committable; Lab is the remaining normaliser review because gold exists)

| Pack | Fit | Real | Lic | Ing | Gold | Lab h | Drama | Dom |
|---|---|---|---|---|---|---|---|---|
| frt-01 | 3 | 1 | 3 | 1 | 2 | 0.1 | 2 | F |
| frt-02 | 3 | 1 | 3 | 2 | 2 | 0.2 | 2 | F |
| frt-03 | 1 | 1 | 3 | 2 | 2 | 0.1 | 1 | F |
| frt-04 | 2 | 1 | 3 | 3 | 1 | 0.3 | 1 | F (placeholder photo) |
| frt-05 | 3 | 1 | 3 | 2 | 2 | 0.1 | 2 | F |
| frt-06 | 3 | 1 | 3 | 2 | 2 | 0.2 | 2 | F |
| frt-07 | 3 | 1 | 3 | 0 | 2 | 0.1 | 3 | F |
| frt-08 | 2 | 1 | 3 | 3 | 2 | 0.2 | 1 | F |
| fin-01 | 3 | 2 | 1 | 0 | 2 | 0.2 | 2 | $ (FinDVer excerpt, licence marked unverified) |
| fin-02 | 3 | 2 | 1 | 2 | 2 | 0.3 | 2 | $ (same) |
| fin-03 | 3 | 2 | 1 | 1 | 2 | 0.2 | 2 | $ (same) |
| fin-04 | 3 | 1 | 3 | 1 | 2 | 0.1 | 2 | $ |
| fin-05 | 2 | 1 | 3 | 2 | 2 | 0.1 | 1 | $ |
| fin-06 | 3 | 1 | 3 | 2 | 2 | 0.2 | 2 | $ |
| fin-07 | 1 | 1 | 3 | 0 | 2 | 0.1 | 1 | $ (true claim) |
| fin-08 | 3 | 1 | 3 | 0 | 2 | 0.1 | 3 | $ |
| leg-01 to leg-06 | 3 | 1 | 3 | 1 to 2 | 2 | 0.1 to 0.2 | 2 | L (leg-02 is a true claim) |
| aipm-01 to aipm-06 | 2 to 3 | 1 | 3 | 1 | 2 | 0.1 to 0.2 | 2 | A (aipm-05 strongest) |

ES ruling: suite cases are stronger on realism and on external provenance; packs are stronger on weakener density, on boxes, on scans we control, and on licence. Mixing both is right, but they must be reported in separate rows because the label origin differs.

### 1.3 Decision (a): the FINAL SET

29 cases. 11 DEV (tune and demo), 18 HELD-OUT (run once after freeze). Every split keeps the dataset's source-overlap groups whole (1.6).

| # | Id | Pool | Domain | Why it is in | Split role | Format | Ingestion needs | Gold work |
|---|---|---|---|---|---|---|---|---|
| 1 | TC17 | Suite, LegalReasonBench | Legal / governance | Supports (GC memo) and contradicts (bylaws 5.2) and a time weakener (resolution "effective as of May 7", adopted May 13) in one claim | DEMO primary 1 (lead) | 3 DOCX; use the curator's PDF conversions (1 to 3 pages each) | Text layer only | Split into 2 parts; quote and page per anchor; map conflicting_evidence |
| 2 | TC40 | Suite, ContractNLI | Legal / AI PM ("bring a consultant in") | Real NDA; one clause flips the claim; condition weakener "unless authorized ... in writing" | DEMO primary 2 | 1 PDF, 4 pages, text layer | Exact snap | Quote, page, weakener type condition |
| 3 | frt-07 | Pack | Freight | The builder's world; cancellation exception; $150 vs $250 computed; planted instruction | DEMO primary 3 | 3 text-layer PDFs | Exact snap; injection banner | Normaliser review only |
| 4 | TC18 | Suite, LRB | Legal / governance | Clean timeline contradiction across 3 docs (letter May 7, email May 8, resolution May 13) | DEMO backup 1 (replaces TC17) | DOCX, use PDF conversions | Text layer | 1 part, dates |
| 5 | TC25 | Suite, Tobacco800 | Legal / trademark | Real 1989 scanned letter: "objectionable, unauthorized uses" contradicts "authorized" | DEMO backup 2 (scan beat) | 2 PNG, 1-bit inverted | Invert, transcribe, approximate box | Quote and approximate box per line |
| 6 | TC20 | Suite, LRB | Legal | Abstention: requirement is not proof of credential | DEV | DOCX→PDF | Text layer | Relabel context_only as absence |
| 7 | TC22 | Suite, LRB | Legal | Rule applied to the right role (5.2 vs 5.3) | DEV | DOCX→PDF | Text layer | 1 to 2 parts |
| 8 | TC37 | Suite, ContractNLI | Legal / AI PM | Same doc as TC40; supported with a qualifier (consent) | DEV | PDF 4 p | Exact | Weakener type qualifier on a supported part |
| 9 | frt-03 | Pack | Freight | True claim, handwritten POD scan: no cry wolf | DEV | PDF + image-only scan PDF | Scan path | Review only |
| 10 | fin-08 | Pack | Finance | Restatement supersedes; weak source; injection | DEV | Text-layer PDFs | Exact | Review only |
| 11 | aipm-05 | Pack | AI PM | Five docs, open P0, untested locale, PNG tracker | DEV | PDFs + PNG | Mixed | Review only |
| 12 | TC11 | Suite, LRB | Legal | Penalty reduced, cause affirmed | HELD-OUT | 3 PDFs | Text layer | Relabel |
| 13 | TC12 | Suite, LRB | Legal | Conflict: award 45 days, PERB summary 40 | HELD-OUT | 3 PDFs | Text layer | Conflict flag |
| 14 | TC14 | Suite, LRB | Legal | Comparators on duty vs off duty, PNG memo | HELD-OUT | 2 PDFs + PNG | Scan path | Approximate boxes |
| 15 | TC16 | Suite, LRB | Legal / payroll | Back pay "less ..." exceptions | HELD-OUT | 2 PDFs | Text layer | context_only → weakens magnitude |
| 16 | TC38 | Suite, ContractNLI | Legal / records | Retention exception supports | HELD-OUT | PDF 6 p | Leading-space filename | Quote |
| 17 | TC41 | Suite, ContractNLI | Legal / ops | Survival after termination | HELD-OUT | PDF 7 p | Exact | Quote |
| 18 | TC43 | Suite, ContractNLI | Legal / IP | Unrestricted licence contradicted, narrow copy exception | HELD-OUT | PDF 1 p, template | Template note | Quote, exception type |
| 19 | TC44 | Suite, ContractNLI | Legal | No notice duty: not found | HELD-OUT | same PDF | Absence receipt | Part status not_found |
| 20 | TC45 | Suite, ContractNLI | Legal / privacy | "Technical only" contradicted by PHI and PII | HELD-OUT | PDF 6 p | Exact | Quote |
| 21 | TC46 | Suite, ContractNLI | Legal / eng | Exception plus no-use condition | HELD-OUT | PDF 6 p | Exact | Two anchors |
| 22 | TC23 | Suite, Tobacco800 | AI PM / research | Plan and blank questionnaire are not results | HELD-OUT | image-only PDF + 3 PNG | Scan path, invert | Absence, weak source |
| 23 | TC27 | Suite, Tobacco800 | Legal / product safety | Denial is not independent lab proof | HELD-OUT | 2 PNG | Scan path, invert | Weak source |
| 24 | TC4 | Suite, Company Docs | Freight-adjacent | Shipment is not delivery | HELD-OUT | 3 PDFs | Text layer | context_only → weakens scope; not_found |
| 25 | TC10 | Suite, Company Docs | Freight-adjacent / procurement | PO authorisation is an image; supported | HELD-OUT | 2 PDFs + PNG | Scan path | Quote per row |
| 26 | frt-01 | Pack | Freight | Amended rate, early arrival, computation | HELD-OUT | PDFs + PNG | Mixed | Review only |
| 27 | frt-05 | Pack | Freight | AI summary overstates Carmack liability | HELD-OUT | PDFs + scan | Mixed | Review only |
| 28 | fin-07 | Pack | Finance | True claim, "respectively" correct | HELD-OUT | PDFs | Exact | Review only |
| 29 | leg-02 | Pack | Legal | True claim, amendment overrides | HELD-OUT | PDFs + scan | Mixed | Review only |

Held-out reference mix: supported 6 (38, 41, 46, 10, fin-07, leg-02), contradicted 7 (11, 14, 16, 43, 45, frt-01, frt-05), insufficient 4 (44, 23, 27, 4), conflicting 1 (12). Six true claims let us measure false reds. Formats in held-out: text-layer PDF, PNG scans, image-only PDF, 1-bit inverted PNG.

Labelling budget: 21 suite cases at 0.2 to 0.5 h of agent drafting each, about 7 agent hours, about 2 builder hours of review; 8 packs at about 0.1 h each. Inside budget.

### 1.4 Decision (b): EXCLUDED, with reasons

| Excluded | Reason |
|---|---|
| Suite 1, 2, 3, 5, 6, 7, 8, 9 | Company Documents: simplified renderings of a sample database; licence unverified; mostly single-row lookups or arithmetic; 4 and 10 already cover the two useful patterns. Re-add 3 or 8 only if held-out needs more image rows |
| Suite 13, 15 | Same Braddock group; P2 (13) or narrow (15); budget |
| Suite 19, 21 | Same IHP group; direct extraction with little weakener structure |
| Suite 24, 26 | Tobacco P2; overlap groups with 23 and 25 |
| Suite 28 to 36 | SD02: synthesized 1988 forms, OCR and arithmetic diagnostics, small handwritten digits beyond our scan budget, NIST SRD redistribution terms unverified. Report separately after submission if wanted |
| Suite 39 | Good case, cut for budget only. First to re-add |
| Suite 42 | The dataset flags a source annotation on oral information that disagrees with the clause; single supporting span; little drama |
| frt-02, frt-06, frt-08 | Good freight packs; cut for labelling and run budget; frt-08 is a one-scan cannot_tell already covered by suite abstentions |
| frt-04 | Photo is a placeholder; SAM is cut from the demo |
| fin-01, fin-02, fin-03 | FinDVer excerpts, licence marked UNVERIFIED in the footers; keep local |
| fin-04, fin-05, fin-06 | Budget; finance covered by fin-07, fin-08 |
| leg-01, leg-03 to leg-06 | Legal is now covered by real documents; leg-02 kept as a true-claim control |
| aipm-01 to 04, aipm-06 | Budget; aipm-05 kept as the strongest |

### 1.5 Decision (c): covering freight honestly

FR: the suite has no freight cases. Company Documents 3, 4, 5, 8, 10 are order, invoice, PO and shipping records of a sample trading database; they are logistics-adjacent, not carrier paperwork. Only 4 (shipped is not received) and 10 (billed versus authorised PO image) carry freight-like reasoning, and both are in held-out. They are not freight evidence and must not be called that.

Freight is therefore covered by our own synthetic packs only: frt-07 (demo), frt-03 (dev, true claim), frt-01 and frt-05 (held-out). The README says: "Freight examples are synthetic packets we wrote; no public labelled freight packet set was available to us."

Should the lead move? Yes. Rationale:
1. Judges score Impact on credibility. A real contract and an externally published legal benchmark case read as real; a synthetic rate confirmation reads as staged.
2. TC17 shows all three card types in one claim (supports, contradicts, weakens), which is exactly the product. frt-07 shows contradicts and one exception.
3. ContractNLI's labels are externally published, which is the only external reference in the set.
4. The builder's world is freight, finance, legal and AI product management. Legal and AI PM are in the lead cases, so the theme still holds. Freight keeps one 30-second beat in the builder's own voice.

What would change this: if the probe P3 on TC17 misses the bylaws clause after one prompt revision, frt-07 returns as lead and TC40 stays second.

### 1.6 Decision (d): overlap and split rules

1. Source-overlap groups from `split_groups.json` stay inside one split. Our assignment: group_05 (IHP: 17, 18, 20, 22) and group_07 (25) and group_13 (37, 40) are DEV; group_04 (Braddock: 11, 12, 14, 16), group_14 (38, 45, 46), group_18 (43, 44), group_16 (41), group_06 (23), group_08 (27), group_01 (4), group_03 (10) are HELD-OUT. Unused members of a group (13, 15, 19, 21, 24, 26) stay out of every split, so they cannot leak.
2. A format conversion is the same source as its original. IHP PDF conversions belong to group_05.
3. Packs: each pack is its own group, except that frt-07 and fin-08 share the injection pattern; both are DEV.
4. Tuning only on DEV. HELD-OUT ids are a frozen list; the held-out run checks the prompt hashes against tag `v0.9-freeze` (the roadmap's rule, kept).
5. Report per pool and per source group, not only per case: 18 held-out cases form 12 source groups, so intervals are wide. Say n and the group count.

### 1.7 Decision (e): gold normalisation plan

One schema, `gold-1`, for both pools. One JSON per case, under `tests/fixtures/gold/` (new path, decision), read only by `scripts/eval_review.py` and `scripts/report_review.py`.

```json
{"case": "TC17", "pool": "suite|pack", "source_dataset": "LegalReasonBench", "split": "dev",
 "claim": "...",
 "reference": {"verdict": "conflicting_evidence", "origin": "curated|external_label|author"},
 "parts": [{"id": "P1", "text": "...", "span": [0, 42],
            "status": "supported|weakened|contradicted|not_found|cannot_tell",
            "conflict": false, "origin": "derived|curated"}],
 "relations": [{"part": "P1", "relation": "supports|contradicts|weakens|set_aside|not_enough",
                "weakener_type": "exception|condition|qualifier|scope|time|magnitude|definition|weak_source|absence|null",
                "file": "IHP_Bylaws_Excerpt_Article_V_Officers.pdf", "page": 1,
                "quote": "No appointment of a principal officer shall be effective unless and until approved",
                "quote_pdf": "...", "boxes": null, "box_origin": "snapped|authored|none",
                "anchor_ref": "expected_results anchor 2", "origin": "external|curated|relabelled"}],
 "unacceptable": ["Treat shipment as delivery"]}
```

Mapping into our vocabulary:

| Source label | Our label |
|---|---|
| suite `expected_verdict` supported / contradicted | part and overall status supported / contradicted |
| suite insufficient_evidence | not_found when the packet was read and the fact is absent; cannot_tell when a judgment is missing (23, 27) |
| suite conflicting_evidence (12, 17) | contradicted with `conflict: true`; a pass requires both a pinned supports and a pinned contradicts card |
| anchor supports / contradicts | same |
| anchor context_only | relabelled by AL into weakens (with type), set_aside, or not_enough; each relabel marked `origin: relabelled` |
| pack weakens and conditions | weakens (condition type for conditions) |
| pack irrelevant | set_aside (must not appear as supports or contradicts) |
| pack part_status free text | the roadmap's five-way map (kept) |

Who labels what:
- AL (an agent session, no Muse calls) drafts suite gold: split the claim into parts with spans, turn each anchor into a verbatim quote plus page from `pdftotext` of the exact file, relabel `context_only`, add weakener types. Boxes are not hand-drawn: text-layer boxes come from snapping `quote_pdf` with pdfplumber; scan boxes are drawn on the 0 to 1000 grid only for the five scan cases (14, 23, 25, 27, 10), about 15 boxes.
- HB reviews all DEMO and backup gold (5 cases) on Sunday and 6 held-out cases on Tuesday before the held-out run.
- Blind relabel check: a fresh agent session with only claim and evidence (no reference, no solutions) labels 6 cases (TC12, TC16, TC43, TC45, TC23, TC4). ES reports raw agreement on relation per anchor and on part status. If agreement on relation is under 0.7, the scorer reports relation metrics as "provisional" and leads with part status.
- The normaliser and the pack-gold fixes from the roadmap (quote_pdf, per-line boxes, part status map) apply unchanged to packs.

What we may claim:
- ContractNLI cases: "reference label adapted from ContractNLI's published NLI label (Koreeda and Manning, 2021), checked against the clause by the curator."
- LegalReasonBench, Tobacco800, Company Documents: "reference answers curated by the ProofGraph builder for these claims, from public benchmark or archive documents." They are not external labels. The LRB task rubrics grade different, broader work.
- Packs: "documents and labels written by us; synthetic."
- Relation types, weakener types and part splits on every case: ours.
- Never: "externally validated accuracy", "benchmark result", or any accuracy win over Direct Muse.

### 1.8 Decision (f): licence plan for the public repo

| Source | Committed to repo | Shown in public video | How the reader gets it |
|---|---|---|---|
| Our packs frt, fin-04 to 08, leg, aipm | Yes (only the 8 in the set plus demo zip) | Yes | `examples/demo-packs/` |
| fin-01 to 03 (FinDVer excerpts) | No | No | Local only until the human verifies |
| LegalReasonBench IHP and Braddock files (CC BY 4.0 per the source card, pinned revision `1bfa904c`) | Yes, the PDF conversions of the IHP group, with attribution and a "converted from DOCX, wording unchanged" note | Yes | `examples/demo-packs/tc17/`, `tc18/` with `SOURCE.md` |
| ContractNLI 37 to 46 (CC BY 4.0; underlying contracts are third-party documents redistributed by the dataset) | No by default: commit file name, sha256, path inside the official zip, and a script to copy them into `data/` | Yes, with citation on screen | `scripts/fetch_suite.sh` (extend `download_data.sh`, existing path) |
| Tobacco800 (YACCLAB repackaging; licence handling unverified) | No | Only if the human verifies the terms on the TC11 collection page (10 minutes). Otherwise TC25 is not in the public video | Local pointer with sha256 |
| Company Documents (Kaggle listing unverified) | No | No | Local pointer |
| SD02 | No | No | Not in the set |
| Solutions, annotations, `_Evaluation` | Never, and never in model input | No | Gold derived from them lives in `tests/fixtures/gold/` and is read only by scripts |

The suite manifest committed to the repo lists, per case: id, claim, file names, sha256 (from the dataset manifest), source dataset, citation, split, licence status. No evidence bytes for pointer-only sources. Results for pointer-only cases are reported, and a reader can reproduce them by obtaining the same files and checking the hashes.

---

## STAGE 2. PRODUCT TEAM

### 2.1 Demo cases: journey, aha, failure modes, rubric

**TC17 (lead).** Claim: "Connors was continuously authorized to act as Interim CMO from May 7, 2026."
- Journey: drag three PDFs (GC memo, bylaws excerpt, board resolution), paste the claim. Left: two parts, "authorized to act as Interim CMO" and "continuously ... from May 7, 2026". Part 1 Supported, part 2 Contradicted with a "sources disagree" note. Centre for part 2: red card on bylaws 5.2 "No appointment of a principal officer shall be effective unless and until approved by the Board"; amber card (time) on the resolution "Adopted: May 13, 2026" next to "effective as of May 7, 2026"; blue card on the GC memo "the ratification relates back to May 7, 2026 ... no compliance gap exists", tagged weak source (interested party). Right: the bylaws page with the clause boxed.
- Aha: the confident legal memo says "no gap"; one sentence in the bylaws, boxed, says there was one.
- Live risk: the model treats the memo as controlling and returns Supported; the time card is missed; the bylaws page needs scrolling. Mitigation: probe P3 on this case first; the conflict rule shows both sides rather than choosing.
- Rubric: Impact (governance sign-off is a real risk), Meta (Muse Spark reads all pages per part; Spark Open checks each card blind), Demo (one boxed clause), Depth (part split, conflict flag, blind check).

**TC40 (second).** Claim: "The Bosch NDA allows the recipient to share confidential information with outside consultants without written authorization."
- Journey: one real 4-page NDA. One part. Red card: "Recipient will not disclose or permit access to Confidential Information to contract workers, consultants or contractors ... unless authorized by Disclosing Party in writing", condition type. A set-aside or supports-context card shows employee need-to-know access, which is what a skim would rely on.
- Aha: on a real public contract, the exact sentence is boxed in under a minute, and the employee clause that looks permissive is shown as not covering consultants.
- Live risk: low. Text layer, short, well-known clause. Risk is the model returning the employee clause as supports; the blind check and the status rule (pinned contradicts wins) handle it.
- Rubric: Impact (AI PM teams ask this weekly), Depth (exact snap), Demo (real document, credited on screen).

**frt-07 (third, builder's world).** Claim: Tallgrass is owed a $250 TONU because the shipper cancelled.
- Aha: "No TONU shall be paid if ... before 18:00" boxed, the 16:20 email boxed, "Computed $150 flat; the claim says $250", and the injection banner on the dispute letter.
- Live risk: computed line needs the numeric bridge (Should). If cut, the card still shows the $150 quote.
- Rubric: Impact and theme (the builder's freight past), Depth (injection, computation).

**TC18 (backup 1).** "The IHP board approved Connors' appointment before she began performing CMO duties." Three dated documents, contradicted. Replaces TC17 if P3 misses the bylaws clause or if the conflict display is not ready.

**TC25 (backup 2, scan beat).** "Philip Morris authorized Sega's use of MARLBORO branding in SUPER MONACO GP." Real 1989 scan; "objectionable, unauthorized uses" in a dashed approximate box. Used as a 10-second beat only if P1 scan accuracy is at least 40% and the Tobacco800 terms are verified. Otherwise frt-03 (synthetic handwritten POD) is the scan beat.

### 2.2 The demo decision

Smartest, quickest, top-tier: **upload real documents on screen.** Lead with TC17 (multi-document legal file, all three relations), then TC40 (real contract, external label), then frt-07 (the builder's freight world with injection and a computed number). No SAM. Scan beat only if probes allow.

Positioning sentence: **"Paste the conclusion an AI or a colleague wrote, upload the documents behind it, and ProofGraph shows, part by part, the exact sentences that support it and the ones that contradict or weaken it, boxed on the original page."**

Claims to avoid: more accurate than Muse or than any baseline; legal advice or legal validity; "catches every contradiction"; exact boxes on scans; that a template contract was signed or executed; independence of Muse Spark Open from Muse Spark beyond what it sees; any number not in `results/report.md`; calling Company Documents freight data; calling LegalReasonBench documents real case files (they are expert-authored or adapted).

### 2.3 Video, second by second (3:00)

| Time | Screen | Voice-over | Rubric |
|---|---|---|---|
| 0:00 to 0:12 | Title; a memo saying "no compliance gap exists" | "AI and colleagues write confident conclusions. Someone still has to sign them." | Impact |
| 0:12 to 0:30 | Drag 3 IHP PDFs, paste TC17 claim; two parts go grey, then chips appear | "Here is a governance claim and the three documents behind it, uploaded now." | Demo |
| 0:30 to 1:05 | Part 2 red. Click the red card: bylaws 5.2 boxed. Amber card: resolution adopted May 13, "effective as of May 7". Blue card: the GC memo, tagged weak source | "The memo says the appointment was valid from May 7. The bylaws say no appointment is effective until the board approves. The board approved on May 13. Both sides are shown; nothing is hidden." | Impact, Depth |
| 1:05 to 1:20 | Hover: "Second check agrees", Muse Spark Open | "Every card is re-read blind by Meta's open-weight Muse Spark Open. It sees only the quote and the part." | Meta, open-weight bonus |
| 1:20 to 1:50 | Upload the real Bosch NDA (citation on screen), TC40 claim; consultant clause boxed | "A real public contract from ContractNLI. Can we bring in a consultant? Only with written authorisation, boxed on page one." | Demo, Depth |
| 1:50 to 2:20 | frt-07: exception and 16:20 boxed, computed $150, injection banner | "I worked in freight. A TONU fee is owed only after 18:00 the day before. The shipper cancelled at 16:20. One file tells the AI to approve. ProofGraph shows the instruction and ignores it." | Impact, theme |
| 2:20 to 2:30 | Optional scan beat (TC25 or frt-03), dashed box | "Scans get a dashed box: we only call a box exact when the PDF text proves it." | Meta vision, honesty |
| 2:30 to 2:50 | `results/report.md` table: held-out n, groups, intervals, one named miss | "Measured once on 18 held-out cases: real contracts with published labels, benchmark legal files and scans labelled by us, and our own synthetic packets. Here is what it misses." | Depth, honesty |
| 2:50 to 3:00 | Repo, dates, models | "Built this week on Muse Spark and Muse Spark Open." | |

### 2.4 Meta models map

Muse Spark: claim split, whole-packet per-part relation reading, scan transcription with line boxes. Muse Spark Open (Baseten): blind check of every card; blind re-read of scan crops if P2 passes. SAM 3.1: not in the final set or the demo; README says it was built and tested in PR 29 and cut from the product path because no case in the set needs counting. This is honest and loses little: SAM was never central to per-part relations.

### 2.5 Conflicts with the roadmap, resolved

| Roadmap item | New ruling |
|---|---|
| C1 freight lead (frt-07) | Superseded: TC17 lead, TC40 second, frt-07 third |
| Demo packs frt-07, fin-08, frt-03 | fin-08 moves to DEV only; frt-03 is the fallback scan beat |
| Section 6 split (12 dev, 16 held-out packs) | Replaced by the 29-case split in 1.3 |
| Decision 11 domain switch | Replaced: TC17 → TC18 → frt-07 fallback ladder |
| C9 external slices after freeze | The suite brings ContractNLI cases in now, as 8 cases with published labels, not as a 300-pair benchmark |
| C14 SAM Could | Cut from the demo; P4 skipped |
| Wording (section 6) | Rewritten in 1.7 |

---

## STAGE 3. ENGINEERING TEAM

### 3.1 Module, test and screen table

Hours are builder-attention hours (agent typing roughly doubles wall time). Regression risk is the chance of breaking the current 270 tests (302 after PR 29).

| Item | Verdict | Reason | Hrs | Regression risk |
|---|---|---|---|---|
| `proofgraph/schema.py` | KEEP (frozen) | Legacy engine contract; new models live in `review/models.py`; A6 holds | 0 | None |
| `engine/` (`numbers`, `calc` with PR 30, `route`, `combine`, `ground` with PR 29, `spans`, `graph`) | KEEP | `numbers` and `calc` feed split coverage and the numeric bridge through one-link programs; the rest is legacy, off the review path | 0 | None |
| `proofgraph/pdf.py` | CHANGE A LOT, later | Reads only its own Courier PDFs. Do not reimplement now: new ingest lives in `review/ingest.py`; `pdf.py` stays for its tests. Reimplementation moves after freeze | 0 now | None if untouched |
| `propose.py`, `pipeline.py`, `prompts/extract.md` | KEEP, legacy | Claim-program path and `run_claim` for the CLI and old packets | 0 | None |
| `clients/muse.py`, `clients/checker.py`, `cache.py`, `spend.py`, `config.py` | KEEP | `structured`, cache, retries, spend cap, passcode reused; `blind_wording(quote, statement)` for cards and `blind_reread(crop)` for scans, signatures unchanged | 0 | None |
| `clients/sam.py` | KEEP, dormant | Not used in the set | 0 | None |
| `adapters/base.py` | CHANGE A LITTLE | Add pack and suite gold keys to the leak list | 0.3 | Low |
| `adapters/findver.py` | KEEP, dormant | Not run before freeze | 0 | None |
| `proofgraph/direct.py` (PR 28) | CHANGE A LITTLE | Packet mode (page-tagged text, claim-level answer) for the side table | 1 | Low |
| `proofgraph/__main__.py` | CHANGE A LITTLE | `review --claim --files` command | 0.5 | Low (`test_cli.py`) |
| `app/streamlit_app.py` (2,006 lines) | CHANGE A LITTLE now, REWRITE parts after freeze | Add a new review entry function and route beside the old screen; keep passcode, spend refusal, uploader. Do not edit the replay code before freeze | 2 | Medium (`test_app.py`, `test_claim_journey.py`) if old functions are touched; low if only added |
| Replay screen (`_review_groups`, `render_marked_pdf`, `courier_pdf`, `_show_upload`, lead panel) | RETIRE after freeze | Superseded by the viewer | 1.5 (Wed, optional) | Deletes `test_app.py` and `test_claim_journey.py` parts with it |
| `prompts/blind_wording.md`, `blind_reread.md` | KEEP | Used as is | 0 | None |
| `prompts/direct.md` (PR 28) | KEEP | Side table | 0 | None |
| `examples/packets/`, `examples/claim-packets/` | KEEP, legacy | Old tests read them | 0 | None |
| `examples/freight/demo-001` (PR 29) | KEEP | Bundle test fixture | 0 | None |
| `scripts/download_data.sh` | CHANGE A LITTLE | Add suite fetch from a local folder with hash checks | 0.5 | None |
| NEW `proofgraph/review/ingest.py` | BUILD | pdfplumber words, page kind, PNG render, 1-bit inversion, name sanitising, DOCX refusal | 3 | None (new) |
| NEW `review/models.py`, `status.py`, `snap.py`, `relate.py`, `split.py`, `scan.py`, `check.py`, `absence.py`, `numeric.py`, `run.py`, `packs.py` | BUILD | The review layer (roadmap section 7) | see tickets | None (new) |
| NEW `app/viewer/viewer.html`, `render.py` | BUILD | Three panes | 6.5 | None |
| Tests `test_schema.py`, `test_numbers.py`, `test_calc.py`, `test_ground.py`, `test_route.py`, `test_combine.py`, `test_spans.py` | KEEP | Engine unchanged | 0 | None |
| `test_muse.py`, `test_spend.py`, `test_reread.py`, `test_sam.py` | KEEP | Clients unchanged | 0 | None |
| `test_boundaries.py` | CHANGE A LITTLE | Add: `review/**` never imports gold loaders; `review/check.py` passes two strings only; `review/**` never reads `Dataset/Solutions` or `_Evaluation` paths | 0.5 | Low |
| `test_adapters.py` | CHANGE A LITTLE | New leak keys | 0.2 | Low |
| `test_text_span.py`, `test_bundle.py` | KEEP | `pdf.py` untouched now | 0 | None |
| `test_app.py`, `test_claim_journey.py`, `test_ship_export.py`, `test_claim_packet.py`, `test_packets.py`, `test_propose.py`, `test_cli.py` | KEEP until the retire PR | Legacy paths | 0 | Low |

Change from the roadmap: `pdf.py` is no longer reimplemented before freeze. The roadmap's risk 6 disappears, and 1 to 2 hours are saved.

### 3.2 Three options

| | (A) Adapt the claim-program engine | (B) Review layer beside the engine (recommended) | (C) Rewrite around per-part relations, drop the engine |
|---|---|---|---|
| What changes | Map claim parts to links and cards to facts; add relation and weakener fields to `Fact`/`Link`; teach `combine.py` weakens and conflicts | New `proofgraph/review/` with its own models; engine used only for computed numeric cards | Delete engine, propose, pipeline; new package owns everything |
| Rule impact | Breaks A6 (frozen schema) and A5 (new verdicts and kinds); needs approval | A5 vocabulary amendment only (new names in `review/`, not in `schema.py`) | A5, A6, and docs/03 rewritten; D1 to D3 revisited |
| Builder hours to freeze | about 30 | about 24 Must, 28 with Should | about 22 Must |
| Risk | High: the program format forced 25 of 50 true claims to rejection in the old run; weakens has no place in pass/fail links; fact grounding assumes one quote per fact | Medium: two paths to maintain; the bridge is narrow | Medium-high: loses the cap, cache and checker tests only if deleted carelessly; loses the computed-number depth story; deletes about 150 tests of working code |
| Test impact | Many engine tests rewritten; 270 tests at risk | 270 untouched; about 14 new test files | About half the suite deleted; new tests replace fewer of them |
| What the user sees | Same three panes, but cards are derived from links, so weakeners and conflicts are awkward; quotes per fact | Three panes with typed cards, conflict flag, blind check badge, optional computed line | Same as B minus computed numbers |
| Judging story | "Program checked by code" but weaker on wording | "Muse reads every page per part; code pins, checks blind and computes" | "Muse reads every page per part; code pins and checks" |

Recommendation: **B.** It ships the product the judges will see without touching 270 tests, keeps the depth story (computed numbers, frozen engine, boundaries), and costs only about 2 hours more than C. The new final set is mostly wording, so in B the numeric bridge becomes Should, which makes B's Must cost about equal to C's.

Evidence that would change it:
- If P3 shows the per-part whole-packet relation call misses the deciding clause on TC17, TC40 and frt-07 after one prompt revision, while the old `propose` program finds them, move toward A for numeric cases only.
- If by Sun 16:00 there is no end-to-end box, cut B to its smallest form (one part, text layer only, no scan, no blind check), which is C in practice, and keep the engine untouched rather than deleting it.

### 3.3 Ingestion needs from the final set

| Need | Cases | Plan | Hours |
|---|---|---|---|
| Text-layer PDF, 1 to 7 pages | Most | pdfplumber words to the 0 to 1000 grid; PNG via pypdfium2 at 144 dpi, long side up to 1600 px | in R-03 |
| Image-only PDF | 23, frt-03 | Words under 5 per page or `(cid:` over 10% → `image_only`; scan path | in R-03 |
| PNG scans, including 1-bit inverted | 14, 23, 25, 27, 10, aipm-05 | Convert to L; if mean brightness under 100, invert (Tobacco800); then scan path | 0.5 |
| DOCX | 17 to 22 | Not built. Upload of `.docx` returns "Save as PDF and upload again". Eval and demo use the dataset's exact PDF conversions. Optional later: `python-docx` text-only (new dependency, decision) | 0.2 |
| Unsafe names | 38, 39, 42, 45, 46 | URL-decode, strip, keep the original in metadata; doc id is a hash | 0.2 |
| Unsigned template | 43, 44, others | Regex for bracketed placeholders and blank signature lines → doc note "looks like an unsigned template; results describe its wording only" | 0.5 (Should) |
| Multi-document packets | LRB, packs | Page tags `[doc d2 p1]`, datamarked; viewer doc tabs | in R-07 |
| Long documents | Largest: TC38/45/46 at 6 pages, 2,615 words; TC41 7 pages | All fit easily | 0 |

Context fit: the largest packets in the set are about 3,000 words of text (about 4,000 tokens) plus up to 9 page images at about 1,400 tokens each if images are sent for layout. Worst case about 17,000 input tokens per call, under 2% of the 1M context. No retrieval is needed or allowed.

Cost per run (published Spark rates in docs/04: $1.25 per 1M input, $4.25 per 1M output; VERIFY): a 2-part claim makes 1 split call, 2 relation calls (about 10,000 input and 2,000 to 4,000 output tokens with reasoning each), up to 2 transcription calls for scans, and about 4 Baseten checks. Estimate $0.04 to $0.12 per claim. DEV 11 cases × 3 rounds about $3; HELD-OUT 18 once about $2; Direct Muse side table about $0.5; probes under $1; judge sessions capped at $15. Uncertainty: reasoning token counts; the cheapest way to find out is P3, which prints the ledger.

Viewer: unchanged from the roadmap section 5 (one self-contained HTML/JS file in a Streamlit component), plus a conflict note on a part and a template note on a doc.

Deployment: unchanged (Streamlit Community Cloud, private until submit, passcode, `SPEND_LIMIT_USD` 15). pdfplumber and pypdfium2 ship wheels for Linux; no apt packages needed because DOCX conversion is not built. Upload cap 25 MB per file, 40 pages per packet.

### 3.4 Test strategy for the new layer

Pyramid: many unit tests (ingest, snap, status, scorer: table-driven on committed synthetic files), unit tests with fake transports and recorded replies for every model call (request shape, one repair, leak sentinel absent, checker sees two strings), one offline integration run per demo case (recorded replies, no network), and one manual browser check of the viewer. Each ticket in 4.5 names its red test. Gaps: no automated browser test (manual check documented); suite evidence cannot be committed for ContractNLI, Tobacco and Company Docs, so their offline tests use recorded replies plus committed text snippets under fair-use length, or are marked `@pytest.mark.local` and skipped in CI.

### 3.5 Guardrails and docs to amend (decisions for the human)

- docs/02: Tier 1 and never-cut list (decision 14); out-of-scope front end (decision 15). Prepared in `doc-updates/`.
- docs/03: new "Review layer" section with the relation, weakener, part and box vocabularies plus the conflict flag (A5, decision 17). Not prepared, because the vocabulary should be written after P3 confirms it.
- docs/05, 06, 10, 11 (D30 to D37), 12 and the sprint board: prepared in `doc-updates/`.
- docs/08: A5 (decision 17); B8 lexical sweep (16); B9 viewer (15); C12 leak list extended to pack `gold`/`note` keys and the dataset's `Solutions/`, `_Evaluation/`, `.fmt`, `.tab`, `annotation_sets`; C13 only `scripts/eval_review.py` and `scripts/report_review.py` read `tests/fixtures/gold/`; C14 tune only on the 11 DEV cases; E23 data rights extended to LegalReasonBench (CC BY 4.0) and our packs, with Tobacco800 and Company Documents local only (decision 18). Not prepared: guardrails change only after the human approves the wording.

---

## STAGE 4. SPRINT MANAGER

### 4.1 What changes versus roadmap-sprint.md

| Area | Roadmap | Now |
|---|---|---|
| Evaluation set | 28 packs, 12 dev, 16 held-out | 29 cases: 21 suite + 8 packs; 11 dev, 18 held-out |
| Lead demo | frt-07 | TC17, then TC40, then frt-07 |
| Walking skeleton target | frt-07 | TC40 (single 4-page real PDF), then frt-07 |
| `pdf.py` reimplementation | Before freeze | After freeze; new ingest is separate |
| Numeric bridge (S1-17) | Must | Should |
| Scan path | Must | Must, but minimal (transcribe and approximate box); re-read upgrade Should |
| SAM, P4 | Could | Cut |
| Gold work | Pack normaliser | Plus suite drafting, relabelling `context_only`, blind relabel on 6 cases |
| New ingest needs | none | 1-bit inversion, name sanitising, DOCX refusal, template note |
| Conflict | none | Part `conflict` flag and scorer rule |
| Licence | Synthetic only | Plus LRB IHP PDFs with attribution; pointers with hashes for the rest |
| Kept unchanged | Viewer design, contract JSON (plus 2 fields), status rule, blind check, absence receipt, cache replay, deploy, kill rule, merge order | |

### 4.2 Capacity and sprint goal

Capacity: Sat 19:30 to 23:00 (3 h), Sun 08:00 to 22:00 (12 h), Mon 08:00 to 23:00 (13 h) = 28 builder hours; 15% buffer leaves about 24 planned hours. Up to three agent lanes on disjoint files.

Sprint goal (to Mon freeze): **a judge uploads TC17, TC40 or frt-07 on the deployed app and sees per-part statuses and boxed, blind-checked cards in three panes, and the DEV table exists from real runs.**

### 4.3 Day by day

**Sat 31, 19:30 to 23:00 (3 h). Unblock.**

| Task | Owner | Lane | Hrs |
|---|---|---|---|
| Answer decisions 1 to 8 | HB | | 0.5 |
| R-01 merge PRs 30, 27, 28, 29 | HB, PE | | 0.5 |
| R-02 probes P1 to P3 on the new targets | AI | A | 1 |
| R-03 ingest (start) | SWE | A | 0.5 |
| R-04 contract models (two new fields) | PE | C | 0.3 |
| R-05 viewer S1 on a TC40 fixture | SWE | B | start |
| R-09a gold drafting for the 5 demo and backup cases (agent, no Meta calls) | AL | C | 0.2 review |

Exit: main green with four PRs; probe memo with numbers; fixture renders.

**Sun 1, 08:00 to 22:00 (12 h). Walking skeleton by 12:00 on TC40; full Must engine on DEV by night.**

| Task | Owner | Lane | Hrs |
|---|---|---|---|
| R-03 finish ingest; R-06 snap; R-07 relate; R-08 skeleton | SWE, VR, AI | A, B | 3 |
| Skeleton checkpoint 12:00: TC40 uploaded, red card boxed on page 1 | HB | | 0.5 |
| R-09 gold normaliser for both pools; R-09b suite gold drafting (21 cases) | VR, AL | C | 1.5 |
| R-10 split; R-11 status with conflict | AI, VR | A | 1.5 |
| R-12 scorer v0 | VR | C | 1 |
| R-13 scan path with inversion | AI | A | 1.5 |
| R-14 viewer S2 linking and keys | SWE | B | 1 |
| R-15 per-part parallel and chips | SWE | B | 0.5 |
| R-16 blind card check | VR | A | 0.5 |
| HB reviews gold of TC17, TC40, frt-07, TC18, TC25 | HB | | 1 |

Exit: TC17 and frt-07 run locally from uploads; scorer prints a DEV table for at least 8 of 11.

**Mon 2, 08:00 to 23:00 (13 h). All Must done, deployed, frozen.**

| Task | Owner | Lane | Hrs |
|---|---|---|---|
| R-18 absence receipt | VR | A | 1.5 |
| R-19 viewer S3 states, upload status, export and replay badge | SWE | B | 3 |
| R-20 DEV runs, 2 to 3 prompt rounds; typed-badge decision at 12:00 | AI | C | 2 |
| R-21 deploy private, secrets, passcode, cap $15 (by 16:00) | SWE, HB | B | 1 |
| Should, in order: R-22 numeric bridge, R-23 template note, R-24 injection banner, R-25 Direct Muse packet mode, R-26 scan re-read upgrade | all | A, B | 3 |
| R-27 docs amendments and BUILT log | PM | C | 1 |
| Freeze: tag `v0.9-freeze`, prompts versioned | HB | | 0.5 |

Exit: deployed private URL runs TC17 live; `pytest -q` green; all Must merged.

Cut line at freeze: everything through R-21 is above the line. R-22 to R-26 in that order if time remains. Kill rule: any Should unfinished at Mon 20:00 is reverted, not merged.

**Tue 3 (8 h, no features).** HB spot-checks 6 held-out gold (1 h) then R-28 blind relabel report; R-29 held-out run once and `results/report.md` (1 h); README (2 h); video record (4 h).

**Wed 4.** Bug fixes from the video take only; secrets scan; repo public; app public with passcode kept for live calls; tag `v1.0-submission`; submit by 22:00; X post; claim credits.

Parallel lanes: A engine (`proofgraph/review/`, `prompts/`), B viewer and app (`app/viewer/`, `app/streamlit_app.py`), C eval and data (`scripts/`, `tests/fixtures/gold/`, `tests/fixtures/packs/`, `examples/demo-packs/`). `pyproject.toml` and `uv.lock` are touched only by R-03, merged first.

Human-only tasks: decisions (Sat); merges (daily); Tobacco800 terms check (10 min, Sun); demo gold review (Sun, 1 h); held-out gold spot check (Tue, 1 h, before the run); voice and screen (Tue); repo public, form, X post, credits (Wed).

### 4.4 Probe gates

| Probe | Target | Spend | Decision rule |
|---|---|---|---|
| P1 | Muse Spark line boxes on TC40 p1 (text layer, padding check), TC25 p1 (inverted and normalised scan), frt-03 POD, TC14 PNG | about $0.10 | Text layer: fix any constant offset first. Scans: centre-in-box at least 70% → `located` reachable; 40 to 70% → dashed `approximate`; under 40% → page plus quote, no scan box, and TC25 drops out of the video |
| P2 | Muse Spark Open with one image crop (TC25 "unauthorized") | about $0.02 | Works → crop re-read on Spark Open; fails → fallback flagged `checker=fallback`, Spark Open stays text-only checker |
| P3 | Per-part relation call on TC17, TC40, frt-07 with draft `relate.md` | about $0.40 | All three deciding clauses found → plan holds. TC17 bylaws clause missed after one prompt revision by Sun 14:00 → TC18 leads. TC18 also missed → frt-07 leads. Wall time over 90 s per part → reasoning effort low, else replay badge in video |

### 4.5 Ticket list

| # | Title | Owner | Depends | Acceptance criteria | Files | Tests (red then green) | Hrs |
|---|---|---|---|---|---|---|---|
| R-01 | Merge PRs 30, 27, 28, 29 | HB, PE | D1 | Four PRs merged; main green | none | existing | 0.5 |
| R-02 | Probes P1 to P3 on new targets | AI | R-01, keys | Memo with numbers and triggered rulings; ledger under $1 | scratch scripts; `docs/council/2026-10-31-probes.md` | none | 1.5 |
| R-03 | Ingest | SWE | D2 | `ingest(paths)` returns pages with kind, PNG, words on grid; 1-bit dark images inverted; names decoded and stripped; `.docx` returns a per-file "save as PDF" error; corrupt file returns an error, never raises | `pyproject.toml`, `uv.lock`, `proofgraph/review/ingest.py`, `tests/test_ingest.py` | Red: frt-07 p1 has words; generated inverted 1-bit PNG comes out light; `.docx` refusal; truncated PDF error | 3 |
| R-04 | Review contract | PE | none | Roadmap S1-04 plus `parts[].conflict` and `docs[].note` | `proofgraph/review/models.py`, `tests/fixtures/review_tc40.json`, `tests/test_review_models.py` | Red: invalid status rejected; box outside grid rejected | 1 |
| R-05 | Viewer S1 | SWE | R-04 | Roadmap S1-05 on the TC40 fixture; conflict note renders | `app/viewer/viewer.html`, `app/viewer/render.py`, `tests/test_viewer_render.py` | Red: one element per card; no external URL | 4 |
| R-06 | Snap | VR | R-03 | Roadmap S1-06; at least 95% of committed text-layer pack quotes snap with IoU at least 0.7 | `proofgraph/review/snap.py`, `tests/test_snap.py` | Red: pipe-table quote; wrapped quote gives 2 rectangles | 2.5 |
| R-07 | Relate per part | AI | R-03 | Roadmap S1-07; datamarked page tags across documents; leak test against gold sentinel and `Solutions` paths | `prompts/relate.md`, `proofgraph/review/relate.py`, `tests/test_relate.py` | Red with fake transport: every page tag present, no sentinel | 2 |
| R-08 | Walking skeleton | SWE | R-05, R-06, R-07 | New Streamlit route: upload, ingest, one part, relate, snap, viewer; passcode and cap enforced | `app/streamlit_app.py` (new function only), `proofgraph/review/run.py`, `tests/test_review_run.py` | Red: offline TC40-like fixture with recorded reply gives a pinned contradicts card | 2 |
| R-09 | Gold normaliser, both pools | VR | none | `load_gold` returns `gold-1`; packs mapped per roadmap; suite verdict map incl. conflict; boundary test that `review/run.py` never imports it | `proofgraph/review/packs.py`, `scripts/eval_review.py` (stub), `tests/test_packs_gold.py` | Red: all 8 packs and a sample suite gold file validate | 1.5 |
| R-09b | Suite gold drafting (21 cases) | AL (agent), HB review | R-09 schema | Each case has parts, verbatim quotes with page, relabelled context_only, `origin` set; demo five reviewed by HB | `tests/fixtures/gold/*.json`, `docs/council/gold-review.md` | Validated by R-09 loader | 1.5 builder |
| R-10 | Claim split | AI | R-07 | Roadmap S1-10 | `prompts/split.md`, `proofgraph/review/split.py`, `tests/test_split.py` | Red: non-substring span rejected | 1.5 |
| R-11 | Status rule with conflict | VR | R-04 | Roadmap S1-11; pinned supports and pinned contradicts on one part → contradicted with `conflict: true` | `proofgraph/review/status.py`, `tests/test_status.py` | Red: conflict case; unpinned contradicts stays non-red | 1 |
| R-12 | Scorer v0 | VR | R-09 | Roadmap S1-12 plus per-pool and per-group rows; conflict pass rule; Wilson intervals | `scripts/report_review.py`, `tests/test_report_review.py` | Red: run equal to gold scores 1.0 | 2 |
| R-13 | Scan path | AI | R-03, P1 | Roadmap S1-13; inverted scans normalised before transcription | `proofgraph/review/scan.py`, `prompts/transcribe.md`, `tests/test_scan.py` | Red: recorded transcription maps quote to a box centred in gold | 2.5 |
| R-14 | Viewer S2 | SWE | R-05 | Roadmap S1-14 | `app/viewer/viewer.html`, `tests/test_viewer_render.py` | Red: keydown handler and `aria-live` present | 2 |
| R-15 | Per-part parallel and chips | SWE | R-10 | Roadmap S1-15 | `app/streamlit_app.py`, `proofgraph/review/run.py` | Red: events in completion order | 1 |
| R-16 | Blind card check | VR | R-07 | Roadmap S1-16 | `proofgraph/review/check.py`, `tests/test_review_check.py`, `tests/test_boundaries.py` | Red: checker receives two strings only | 1.5 |
| R-17 | Leak and boundary tests | VR | R-09 | Leak keys added; `review/**` never touches gold, `Solutions`, `_Evaluation`, `.fmt`, `.tab` | `proofgraph/adapters/base.py`, `tests/test_adapters.py`, `tests/test_boundaries.py` | Red: a request containing a sentinel fails | 0.5 |
| R-18 | Absence receipt | VR | R-10 | Roadmap E10 | `proofgraph/review/absence.py`, `tests/test_absence.py` | Red: TC44-like fixture gives not_found with pages read | 1.5 |
| R-19 | Viewer S3 and export | SWE | R-14 | Roadmap F3, F4, F6 | `app/viewer/*`, `app/streamlit_app.py` | Red: each state has a fixture render | 3 |
| R-20 | DEV runs and prompt rounds | AI | R-12, R-16 | 11 DEV cases, cost printed before run, under $5 total; prompt versions logged | `runs/review-dev-*.jsonl`, `prompts/*.md` | scorer | 2 |
| R-21 | Deploy | SWE, HB | R-19 | Private URL runs TC17 live; cap $15; passcode | `.streamlit/config.toml`, `README.md` | health check | 1 |
| R-22 | Numeric bridge (Should) | VR | R-07 | Roadmap S1-17 | `proofgraph/review/numeric.py`, `tests/test_review_numeric.py` | Red: frt-07 $150 vs $250 fails | 2 |
| R-23 | Template note (Should) | SWE | R-03 | Placeholder regex → doc note | `proofgraph/review/ingest.py`, `tests/test_ingest.py` | Red: Frodsham-like text flagged | 0.5 |
| R-24 | Injection banner (Should) | AI | R-07 | Roadmap E11 | `prompts/relate.md`, `proofgraph/review/relate.py` | Red: planted line becomes a banner card | 1 |
| R-25 | Direct Muse packet mode (Should) | AI | R-01 | Claim-level answer on page-tagged text; side table only | `proofgraph/direct.py`, `tests/test_direct.py` | Red: packet body contains page tags | 1 |
| R-26 | Scan re-read upgrade (Should) | AI | R-13, P2 | `located` when Spark Open reads the same words | `proofgraph/review/scan.py` | Red: agreement upgrades box status | 1.5 |
| R-27 | Docs and BUILT log | PM | decisions | Apply `doc-updates/` after approval | docs/*, `BUILT_DURING_HACKATHON.md` | none | 1 |
| R-28 | Blind relabel check | ES (agent) | R-09b | 6 cases relabelled blind; agreement table in `docs/council/gold-review.md` | docs only | none | 0.3 |
| R-29 | Held-out run once and report | AI, VR | freeze, R-28 | `results/report.md` generated from `runs/`; per-pool rows; n and groups | `runs/`, `results/report.md` | scorer | 1 |
| R-30 | Suite manifest and fetch script | VR | D6 | Manifest with ids, claims, names, sha256, citation, split; fetch script copies from a local dataset path and checks hashes | `examples/suite/manifest.json`, `scripts/download_data.sh` | Red: hash mismatch aborts | 1 |
| R-31 | Demo packs folder | PM | D6 | `examples/demo-packs/` with frt-07, tc17, tc18 PDFs and `SOURCE.md` attribution; TC40 by pointer | `examples/demo-packs/**` | none | 0.5 |

Must total about 37 ticket hours, about 22 builder hours with agents typing. Should about 6.

### 4.6 Risks and kill criteria

| Risk | Likelihood | Impact | Kill criterion |
|---|---|---|---|
| Relation pass misses the deciding clause on TC17 | Medium | High | P3 rule: TC18, then frt-07 leads |
| Skeleton slips | Medium | High | No box on TC40 by Sun 16:00 → cut scan path to page plus quote; cut R-22 to R-26 |
| Suite gold drafting takes longer than 1.5 builder hours | Medium | Medium | By Sun 20:00, held-out keeps only cases with reviewed gold; minimum 12 held-out |
| Scan boxes wrong | High | Medium | P1 under 40% → no scan boxes; TC25 out of video |
| Conflict display confuses viewers | Low | Medium | Fall back to contradicted with both cards visible |
| False reds on 6 true held-out claims | Medium | High | Reported as measured; any true DEMO claim red on Mon → investigate before video |
| Tobacco800 licence unresolved | Medium | Low | Not in the public video; local results only |
| Deploy fails | Low | High | Not live by Mon 16:00 → Hugging Face Spaces (Streamlit SDK) |
| Scope creep | High | Medium | Kill rule Mon 20:00 |

### 4.7 Decisions for the human (recommended answer, cost)

1. Adopt the 29-case final set and the split in 1.3, frozen now. **Yes.** $0.
2. Lead demo TC17, second TC40, third frt-07; backups TC18 and TC25 (TC25 only if P1 and licence allow). **Yes.** $0.
3. Add `pdfplumber` (D18 already names it; Pillow arrives with PR 29). **Yes.** $0.
4. No DOCX dependency; use the dataset's PDF conversions; app refuses `.docx` with a message. **Yes.** (Alternative `python-docx`, text-only, no boxes: 1.5 h.) $0.
5. New paths: `proofgraph/review/`, `app/viewer/`, `prompts/split.md`, `relate.md`, `transcribe.md`, `scripts/eval_review.py`, `scripts/report_review.py`, `examples/demo-packs/`, `examples/suite/manifest.json`, `tests/fixtures/gold/`, `tests/fixtures/packs/`, `docs/council/gold-review.md`, `docs/council/2026-10-31-probes.md`. **Yes.** $0.
6. Licence: commit our 8 packs and the LRB IHP PDF conversions with CC BY attribution; ContractNLI, Tobacco800, Company Documents as pointers with hashes. **Yes.** $0.
7. Probe spend P1 to P3 on new targets, up to $1. **Yes.** about $0.52.
8. Merge PRs 30, 27, 28, 29 in that order. **Yes.** $0.
9. DEV runs (11 × up to 3 rounds), held-out once (18), Direct Muse side table: approve up to $10. **Yes.** about $6.
10. App cap $15, passcode kept after going public. **Yes.** up to $15.
11. Gold plan in 1.7, including your review of 5 demo cases (Sun, 1 h) and 6 held-out (Tue, 1 h), and the blind relabel on 6 cases. **Yes.** $0 Meta.
12. Claims wording in 1.7 and 2.2; no accuracy win over Direct Muse. **Yes.** $0.
13. Cut SAM from the demo and skip P4. **Yes.** saves $0.10.
14. Amend docs/02 never-cut list and Tier 1 (FinDVer, ContractNLI 300, traps, proof graph, objection loop leave the before-freeze scope). **Yes.**
15. Amend B9 for one vanilla HTML/JS viewer in a Streamlit component. **Yes.**
16. Amend B8 to allow the post-hoc lexical absence sweep. **Yes.**
17. Amend A5 with the review vocabulary including the `conflict` flag, recorded in docs/03. **Yes.**
18. Amend C12, C13, C14 and E23 as in 3.5. **Yes.**
19. Postpone the `pdf.py` pdfplumber reimplementation until after freeze. **Yes.**
20. Labelled cached replay as fallback (amends D25). **Yes.**
21. Check the Tobacco800 terms (10 minutes) before TC25 appears publicly. **Yes, Sunday.**
22. Keep-aside: prior decisions D1 to D29 are kept as history and superseded only where D30 to D37 say so. Hackathon and honesty rules are not revisable. **Yes.**

Total new Meta and Baseten spend requested: about $16 across all runs (probes $0.5, runs $6, judge cap $15 is a ceiling not a forecast). Every single run stays far under the $50 cap.

### 4.8 Unsure, and the cheapest way to find out

| Unsure | Cheapest check |
|---|---|
| Whether the IHP PDF conversions paginate so that bylaws 5.2 sits on page 1 | `pdftotext -f 1 -l 1` on the conversion, 1 minute |
| Whether Muse reads an inverted 1-bit scan correctly without inversion | Not worth testing; invert anyway |
| Real reasoning-token cost per part | P3 ledger |
| Whether Tobacco800 page images may be shown publicly | Read the TC11 collection page terms, 10 minutes |
| Whether ContractNLI permits committing the 6 PDFs | Read the zip's LICENSE and TERMS, 5 minutes; default stays pointer only |
| Whether blind relabel agreement will reach 0.7 | R-28, 0.3 h |
| Whether snapping works on Word-produced PDFs with ligatures (TC41, TC39) | Run R-06 tests on TC41 locally, 10 minutes |
