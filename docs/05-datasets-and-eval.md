# 05 · Datasets, adapters and evaluation

## The adapter idea
One pipeline; every test set plugs in through an adapter in `proofgraph/adapters/` that yields `Case` objects (see `03-architecture.md` §2). An adapter is about 50 lines. Changing mode (`passage` or `whole`) is a flag, not new code.

| Adapter | Mode(s) | Size | Answer key from |
|---|---|---|---|
| `findver.py` | `passage` (gold passages given), `whole` (entire filing) | 250 numeric + 250 fact-lookup (passage); 50 numeric (whole) | Outside experts (FinDVer) |
| `contractnli.py` | `whole` | ~300 statement–contract pairs | Outside experts (ContractNLI) |
| `traps.py` | `passage` | 50 | Built by us (by construction) |
| `freight.py` | `whole` | 16 bundles | Built by us |

## FinDVer (MIT)
- **Get it:** `git clone --depth 1 https://github.com/yilunzhao/FinDVer data/FinDVer`
- **Files:** `data/testmini.json` (700: `numeric` 250, `ie` 250, `knowledge` 200) and `data/test.json` (1,700; labels released). Filings are in `financial_reports/<report>.json`.
- **Record fields:** `example_id`, `subset` (`numeric`|`ie`|`knowledge`), `split`, `statement`, `entailment_label` (bool), `relevant_context` (list of passage ids), `report` (filename).
- **⚠ LEAK FIELDS (the adapter must drop these, and a test asserts it):** `explanation`, `explaination` (sic, on numeric testmini), `python_calculation`, `execution_result`, `knowledge`. They contain the answer or the worked solution.
- **Filing format:** `{url, report_type, context: [{id, context, type: "paragraph"|"table"}], html_tables}`. Tables are pipe-delimited and full of `​`; strip them. A filing is ~200K characters on average (max ~400K), about 50K–100K tokens, so it fits in one Muse call.
- **Header lines such as "in thousands" are often missing** from extracted tables. That's why the scale rule exists (`03-architecture.md` §5).
- **Mapping:** `true` → SUPPORTED, `false` → CONTRADICTED. UNRESOLVED counts as an abstention.
- **Splits:** dev = the first 50 `numeric` claims of `test.json` (tune prompts here only). Scored = `testmini` (`numeric` 250, `ie` 250). Whole-filing mode = the first 50 `numeric` testmini claims.
- **Not used:** the `knowledge` subset (it needs outside knowledge code can't check).
- **Worked example:** `numeric-val-0` (Ryman 10-K, passage 107). The claimed 183,479 is the gross row; the net row is 180,996. See the walkthrough page.

## ContractNLI (CC BY 4.0)
- **Get it:** download `contract-nli.zip` from https://stanfordnlp.github.io/contract-nli/ in a browser and unzip it to `data/contract-nli/`. The workspace proxy blocks the download, so this is a manual step. **Don't use Hugging Face mirrors for scored runs** (their licence and provenance differ).
- **Format:** `{documents: [{id, file_name, text, document_type, url, spans: [[start,end],…], annotation_sets: [{annotations: {nda-1: {choice, spans: [span idx…]}, …}}]}], labels: {nda-1: {short_description, hypothesis}, …}}`. There are 17 hypotheses; `choice` is one of `Entailment`, `Contradiction`, `NotMentioned`.
- **Mapping:** Entailment → SUPPORTED, Contradiction → CONTRADICTED, NotMentioned → UNRESOLVED.
- **Sources:** split the document into clause `Source`s using the dataset's `spans`, and send all of them (whole mode).
- **⚠ LEAK FIELDS:** `annotation_sets` (choices and evidence spans). They go only into `Case.answer` and `Case.gold_evidence`.
- **Sample:** ~300 pairs from the test split, stratified by label (fixed seed 7). Dev = 30 pairs from the dev split.
- **Extra metric:** evidence overlap. Did ProofGraph cite at least one of the examiner's spans?
- **Worked example:** Frodsham Town Council NDA, "Receiving Party may retain some Confidential Information…" → Contradiction (clause 6). The trap is clause 7's "right to copy."

## Conflict traps (built by us, automatic)
For 50 `numeric` testmini claims: keep the gold passages and add a copy of one gold passage in which **one number the claim depends on** is changed by +10%. Pick the number by intersecting the numbers in the gold passage with the numbers in FinDVer's worked explanation. That intersection is used **only by the builder script**, and the explanation is never sent to any model. Answer: UNRESOLVED (`CONFLICT`). Script: `scripts/build_traps.py`, seed 7.

## Freight bundles (built by us, Day 5)

**Not this window.** The spec below stays as written. For the window that submits on 4 Nov 2026, follow the 28 Oct data plan in the next section: one demonstration packet at `examples/freight/demo-001/`. The sixteen `bundle_NN` directories are not built in this window.

- **16 bundles** in `examples/freight/bundle_NN/`, each with `rate_confirmation.pdf`, `pod.jpg`, `dock.jpg`, `invoice.pdf` and `key.json`.
- **Mix:** 6 correct; 6 wrong (3 detention errors, 3 carton-count errors); 4 smudged or ambiguous (2 smudged departure times, 2 cluttered carton photos). The correct answer for the smudged ones is UNRESOLVED for the affected line.
- **Content:** fictional carrier and shipper names only. Rate confirmation line: "Detention: $75.00/hour after 2 hours free time" (vary the rates and free time across bundles). POD: printed form with handwritten "Arrived" and "Departed" times. Dock photo: 10–30 clearly separated cartons. Invoice: "Cartons delivered: N", "Detention: $X".
- **How:** generate PDFs from a template (`scripts/make_freight_pdfs.py`), print the POD form, handwrite the times, and photograph everything with a phone.
- **`key.json`:** `{"verdict": "...", "lines": {"detention": "...", "cartons": "..."}, "truth": {"arrived": "07:40", ...}}`.
- Presented as a **demonstration with an honest label**, never as a benchmark.

## 28 Oct data plan

Written 28 Oct 2026. One person. Submit Wednesday 4 Nov 2026, 22:00 IST. Hard stop Thursday 5 Nov 2026, 07:30 IST. This section is the testing data for that window. It does not start an eval. The per-run cap stays $50. D27, D28, and D29 stay as written.

The routes are the ones in `03-architecture.md` and `proofgraph/schema.py`. `Case.dataset` is `findver`, `contractnli`, `traps`, or `freight`. `Source.kind` is `text`, `table`, `pdf`, or `image`. There is no new dataset value.

| Evidence | Method | Grounded when |
|---|---|---|
| Text passage, or a table passage loaded as text | `quote` | The quote is in the source, and the value is in the quote |
| Digital PDF with a text layer | `text_in_box` | The words inside the box contain the value |
| Image of handwriting, a scan, or a clock | `blind_reread` | Muse Spark Open, given only the crop, reads the same value |
| Image of physical goods | `count_agreement` | The SAM 3.1 count for the noun equals the pointed count |

A `compute` or `temporal` link goes to the calculator. Strength is COMPUTED. A `wording` link goes to the blind checker and returns `entails`, `contradicts`, or `not_mentioned`. Strength is CHECKED. A `rule` with `expr` null and `rule_source` `assumed` is ASSUMED.

### On disk tonight

- **FinDVer (MIT)** is at `data/FinDVer`. The adapter loads a numeric passage only. The worked row a judge can be shown beside the score is `numeric-val-0` in `data/testmini.json`: report `RHP-2024-02-23_10-K.json`, passage 107, source id `p107`, kind `table`. The statement is "The net interest expense in 2023, considering debt interest and capitalized interest, was $183,479,000." The gold label is false. In that table, debt interest paid for 2023 is $183,479, and cash paid for interest, net of capitalized interest, is $180,996. Dataset `findver`, mode `passage`. The check is `quote`.
- The 30 false rows and the 50 true dev rows already ran. The scored file is the 250 numeric rows of `testmini`. It waits on the D29 five-box gate, then Tuesday 3 Nov, with `n` omitted, and the fresh estimate at or under $50. Command, when the gate is yes: `python scripts/run_eval.py --dataset findver --mode passage --split testmini --systems pg --seed 7`. This plan does not run it. Do not replace FinDVer with synthetic filings.
- **ContractNLI (CC BY 4.0)** is not on disk. It is 607 real NDAs, 17 hypotheses, labels Entailment, Contradiction, and NotMentioned. The human downloads `contract-nli.zip` in a browser from https://stanfordnlp.github.io/contract-nli/ and unzips it to `data/contract-nli/`. The proxy blocks that download. Hugging Face mirrors stay forbidden for scored runs. A scored sample may run Wednesday 4 Nov morning only under D29. Do not write fictional NDAs and call them ContractNLI. The row a judge can see, once the zip is real, is the Frodsham Town Council NDA: "Receiving Party may retain some Confidential Information…" → Contradiction (clause 6). The trap is clause 7's "right to copy."
- `tests/fixtures/detention_program.json` stays a unit fixture. Three text strings. The claim says the invoice detention charge of $450.00 is correct. The times are 10:00 and 14:12. No files. It is not the demo packet.
- `tests/fixtures/text_span_rate.pdf` is one generated Courier page. `tests/fixtures/sum_program.json`, `tests/fixtures/scale_program.json`, and `tests/fixtures/findver/financial_reports/acme.json` stay unit fixtures.
- `examples/freight/` does not exist. PG-SPIKE-01 is notes only: arrived 07:40, departed 11:55, rate $75, 12 drawn cartons, invoice $450 and 10 cartons. Those times are not the packet. On that drawing, SAM counted 12 when the noun was `cardboard box`, and the noun `carton` returned empty. The packet does not keep `cardboard box` for that reason.

### USE

Outside labels. These rows are not hand-made.

- **FinDVer.** Case id `numeric-val-0`. Show that row beside the score. The 250 is the scored file under D29.
- **ContractNLI.** Only when the official zip is in `data/contract-nli/`. The judge's row is the Frodsham retention clause above. Dataset `contractnli`, mode `whole`. If the zip is not on disk before Sunday 1 Nov 2026, wording has no USE set. The wording demonstration below is the substitute.

### DEMO

One packet. Labeled a demonstration. Never a benchmark. Dataset `freight`, because that is the built-by-us value. Mode `whole`. Case id `freight-demo-001`. Directory `examples/freight/demo-001/`.

The packet has the same roles as a real evidence packet: a digital rate page, a photographed form with a handwritten value, a photograph of countable physical goods, and a digital invoice. Carrier **Northwind Cartage**. Shipper **Harbor Lane Goods**. Fictional names. No logos. No real people's names (guardrail 23).

One timeline. It is not 10:00–14:12, and it is not 07:40–11:55.

| Field | Value |
|---|---|
| Arrived | 08:00, handwritten on the form |
| Departed | 12:30, handwritten on the form |
| Free time | 2 hours, on the rate page |
| Rate | $75.00 per hour, on the rate page |
| Elapsed | 4.5 hours |
| Billable | 2.5 hours |
| Fair detention | $187.50 |
| Invoice detention | $450.00 |

A person recomputes 12:30 minus 08:00, minus 2 hours free, times $75, and gets $187.50. The invoice says $450.00. The claim that $450.00 is correct is false. Verdict CONTRADICTED. Link `l_detention` is `compute`, required, strength COMPUTED:

`(hours_between(f_arrived, f_departed) - f_free) * f_rate == f_invoice`

A `temporal` link uses that same calculator. This claim is `compute`. The packet does not add a second pair of times.

Link `l_same_day` is `rule`, `expr` null, `rule_source` `assumed`, statement "Arrival and departure are on the same calendar day." The form has no date. Strength ASSUMED. It is not in `required`, so the detention verdict stays COMPUTED. The link is on the case so that route is visible.

The goods fact is kind `count`. After the human counts the photo, the invoice states a different count. Link `l_goods` is `compute`, required, strength COMPUTED: `f_goods_count == f_invoice_count`. That line is CONTRADICTED. The grounding method is `count_agreement`.

| Path | Source id | Kind | Method |
|---|---|---|---|
| `examples/freight/demo-001/rate_confirmation.pdf` | `rate_conf` | `pdf` | `text_in_box` |
| `examples/freight/demo-001/pod.jpg` | `pod` | `image` | `blind_reread` |
| `examples/freight/demo-001/goods.jpg` | `goods` | `image` | `count_agreement` |
| `examples/freight/demo-001/invoice.pdf` | `invoice` | `pdf` | `text_in_box` |
| `examples/freight/demo-001/key.json` | | | filled before any model call |

`reportlab` is not in `pyproject.toml`. It is not added. The rate page and the invoice are one-page Courier PDFs with a real text layer, written by `_pdf_pages` in `tests/test_text_span.py`. That writer is already in the repo. `proofgraph/pdf.py` reads an uncompressed or FlateDecode Courier page. The rate page paints `Detention: $75.00/hour after 2 hours free time`. The invoice paints `Detention: $450.00` and a delivered-count line that uses `goods_noun` and `invoice_count` from `key.json`.

**`key.json` fields:** `case_id` (`freight-demo-001`), `dataset` (`freight`), `mode` (`whole`), `demonstration` (true), `benchmark` (false), `carrier`, `shipper`, `claim`, `verdict` (`CONTRADICTED`), `lines.detention` (`CONTRADICTED`), `lines.goods` (`CONTRADICTED`), `truth.arrived` (`08:00`), `truth.departed` (`12:30`), `truth.free_hours` (2), `truth.rate_usd_per_hour` (75), `truth.elapsed_hours` (4.5), `truth.billable_hours` (2.5), `truth.fair_detention_usd` (187.50), `truth.invoice_detention_usd` (450), `truth.goods_noun`, `truth.goods_count`, `truth.invoice_count`, `assumed_rule`, and `sources` for the four files above. `goods_noun`, `goods_count`, and `invoice_count` stay null until step 4. The claim is then filled with those two fields: `The invoice detention charge of $450.00 is correct, and the invoice count of <invoice_count> <goods_noun>s matches the photo.`

**What the human does, in order.** A phone and a pen. No model call.

1. Create `examples/freight/demo-001/key.json` with the timeline, the rate, the fair charge $187.50, the invoice charge $450.00, the two fictional names, and the assumed-rule sentence. Leave the three goods fields null.
2. Write `rate_confirmation.pdf` with `_pdf_pages`. The detention sentence is in the file bytes.
3. On paper, letter the labels Arrived and Departed. Write 08:00 and 12:30 in pen. Photograph the form so the handwriting fills the frame. Save `pod.jpg`. That file is the blind re-read. The crop is the only thing Muse Spark Open sees on this route.
4. Set out real, separated physical goods and photograph them as `goods.jpg`. Count them by hand. The count is at least 4. If the photo shows cartons, `goods_noun` is `carton`. If it shows something else, the noun is the ordinary name of what is in the frame. Write that noun and the hand count into `key.json`. Set `invoice_count` to the hand count minus 2. Write the claim sentence with those words. Report the hand count as the truth. Do not name the photo `cardboard box` because a drawing answered to that noun.
5. Write `invoice.pdf` with `_pdf_pages`, using $450.00 and `invoice_count` from `key.json`. The count line uses `goods_noun`.
6. Stop. Making the packet does not call Muse, the checker, or SAM.

**Checks a person can mark:**

- [ ] The packet has a digital rate page, a phone photo of a handwritten form, a phone photo of countable physical goods, and a digital invoice. The names are fictional. There is no logo and no real person's name.
- [ ] The numbers in `key.json` were written before any model call. They agree with each other. The detention claim is false: 12:30 minus 08:00 is 4.5 hours, minus 2 hours free, times $75 is $187.50, and the invoice says $450.00.
- [ ] The packet has one timeline: 08:00 and 12:30. It does not also carry 10:00–14:12 or 07:40–11:55.
- [ ] `goods_noun` is what the photo shows. A photo of cartons uses `carton`. `goods_count` is the hand count. `invoice_count` is a different number, and that number is the one on the invoice.
- [ ] Both PDFs are Courier pages with a real text layer. `pod.jpg` is a photograph. The handwritten times are not a sentence stored as `Source.kind` `text`.
- [ ] `tests/fixtures/detention_program.json` is still the unit fixture. It was not copied in as this packet.
- [ ] The folder is labeled a demonstration. It is not presented as a benchmark.

### Wording demonstration, only if the zip is still absent

Build this only if `data/contract-nli/` has no official zip at the end of Sunday 1 Nov 2026. Wording then has no USE set. This case is a demonstration. It is not ContractNLI. Dataset `freight`. Mode `passage`. Case id `freight-demo-wording-001`. Directory `examples/freight/demo-wording-001/`.

- `clause.txt`, source id `clause`, kind `text`, method `quote`.
- `key.json`.
- Clause: "Northwind Cartage may use Harbor Lane Goods' lane notes only to move the named load, and must return those notes when that load is delivered."
- Claim: "This agreement is governed by the law of Delaware."
- The clause does not mention Delaware, governing law, or venue. Expected checker output: `not_mentioned`. Answer: UNRESOLVED. Link kind `wording`, strength CHECKED.
- `key.json` fields: `case_id`, `dataset` (`freight`), `mode` (`passage`), `demonstration` (true), `benchmark` (false), `not_contractnli` (true), `claim`, `clause`, `expected_checker` (`not_mentioned`), `answer` (`UNRESOLVED`), `strength` (`CHECKED`).

If the official zip is present before Sunday, skip this directory. The Frodsham row is the wording row the judge sees.

### Checkable packets

`examples/packets/` is the small set a person can open and check. The three compute files include a program, and `tests/test_packets.py` runs them with no network. The two FinDVer files are real filings with the outside label and no program. The governing-law file is a wording demonstration and does not call the checker.

| File | World | What a person can check |
|---|---|---|
| `numeric-val-0.json` | SEC 10-K | Gold CONTRADICTED. Debt interest paid is $183,479. Net cash interest is $180,996. |
| `numeric-test-0.json` | SEC filing | Gold SUPPORTED. Net cost of a cyber incident after insurance recoveries. |
| `detention-overcharge.json` | Detention bill | CONTRADICTED / COMPUTED. 12:30 minus 08:00, minus 2 hours, times $75 is $187.50. The invoice says $450.00. |
| `detention-correct.json` | Detention bill | SUPPORTED / COMPUTED. Same clocks and rate. The invoice says $187.50. |
| `late-fee-overcharge.json` | Contract late fee | CONTRADICTED / COMPUTED. 1.5% of $10,000 is $150. The invoice says $500.00. |
| `governing-law-not-mentioned.json` | Contract clause | Expected UNRESOLVED. The clause is about returning lane notes. It does not mention Delaware. Not ContractNLI. |

These detention and late-fee sources are the lines from those documents, stored as text so the calculator can be checked tonight. They are not the phone photos. The vision packet in `examples/freight/demo-001/` is still the human's photographs, and it uses this same 08:00–12:30 timeline.

### Not built in this window

- The 16 bundles at `examples/freight/bundle_NN/`.
- Synthetic filings in place of FinDVer.
- Conflict traps (`scripts/build_traps.py`, dataset `traps`).
- A general PDF corpus.
- Fictional NDAs labeled ContractNLI.
- A second freight timeline, a drawing counted as `cardboard box`, or a `reportlab` dependency.

## Systems compared
| System | What it is |
|---|---|
| A · Direct Muse | Muse Spark reads the same sources and answers directly |
| B · Direct Muse that may abstain | Same as A, plus a `cannot_tell` option |
| PG · ProofGraph | The full pipeline |
| PG − quote check | The engine with grounding disabled (rerun from cache, no API cost) |
| PG − coverage | The engine with the coverage rule disabled (rerun from cache) |
| PG self-check | The blind checker replaced by the proposer checking its own links (new API calls) |

## Metrics (`scripts/report.py`)
| Name | Formula | Notes |
|---|---|---|
| **Wrongly approved** (headline) | predicted SUPPORTED and answer is CONTRADICTED ÷ all answers CONTRADICTED | Lower is better |
| Answered | committed (not UNRESOLVED) ÷ all | Target ≥ 50% |
| Right when answered | correct ÷ committed, compared with A **on the same cases** | |
| Knows when it can't tell | predicted UNRESOLVED ÷ cases whose answer is UNRESOLVED | ContractNLI NotMentioned, traps, smudged freight |
| Right, by label | correct ÷ verdicts with that label | COMPUTED, CHECKED, ASSUMED |
| Evidence overlap | cited ≥ 1 examiner span ÷ committed | ContractNLI only |
| Grounding invariant | committed verdicts whose required facts are all grounded ÷ committed | **Must be 100%** |

## Success criteria (pre-registered; paste into the README on Day 1 before any run)
1. PG's wrongly-approved rate is lower than A's, on FinDVer and on ContractNLI.
2. PG is right when answered at least as often as A on the same cases, and answers ≥ 50%.
3. PG says UNRESOLVED on clearly more of the can't-tell cases than A and B.
4. COMPUTED verdicts are at least as accurate as CHECKED verdicts.
5. The blind checker beats the self-check.
6. The grounding invariant is 100%.
7. On freight, every smudged or ambiguous value ends UNRESOLVED, never guessed.

If a criterion fails, report it as it is, with reason codes. Never hide or re-define a metric after seeing the results.

## 31 Oct final set (accepted 31 Oct, D31; replaces the 28 Oct data plan and the success criteria above for this window)

Written Sat 31 Oct 2026, evening. The sections above stay as history. The evaluation for the submission is the 29 cases below. Tune only on DEV. Run HELD-OUT once, after the freeze tag, from `scripts/eval_review.py`.

### Sources and citations

| Source | Cases used | Licence status | In the repo |
|---|---|---|---|
| ContractNLI (Koreeda and Manning, 2021, Findings of EMNLP), official test split | 37, 38, 40, 41, 43, 44, 45, 46 | CC BY 4.0; contracts are third-party documents redistributed by the dataset | Pointer: file name, sha256, path in the official zip |
| LegalReasonBench, micro1 public sample, revision `1bfa904c8f255925baf2610c0f86aa7c05d94ed9` | 11, 12, 14, 16, 17, 18, 20, 22 | CC BY 4.0 per source card; documents are expert-authored or adapted | IHP PDF conversions committed with attribution; Braddock by pointer |
| Tobacco800 (Doermann, Tobacco800_1; YACCLAB repackaging, Grana et al., ICPR 2016) | 23, 25, 27 | Unverified for redistribution | Pointer only |
| Company Documents (local `archive (3).zip`; Kaggle listing unverified) | 4, 10 | Unverified | Pointer only |
| Our packs (synthetic, written and labelled during the hackathon) | frt-07, frt-03, fin-08, aipm-05, frt-01, frt-05, fin-07, leg-02 | Ours | Committed |

The human's suite has 46 cases. Excluded with reasons in `final-plan.md` section 1.4: Company Documents 1 to 3 and 5 to 9; LegalReasonBench 13, 15, 19, 21; Tobacco800 24, 26; SD02 28 to 36 (synthesized forms, diagnostic only); ContractNLI 39 (budget) and 42 (annotation dispute on that topic). Unused members of a source-overlap group stay out of every split.

### Split

| Split | Cases |
|---|---|
| DEV (11; demo cases live here) | TC17, TC18, TC20, TC22, TC37, TC40, TC25, frt-07, frt-03, fin-08, aipm-05 |
| HELD-OUT (18; run once) | TC11, TC12, TC14, TC16, TC38, TC41, TC43, TC44, TC45, TC46, TC23, TC27, TC4, TC10, frt-01, frt-05, fin-07, leg-02 |

Held-out reference mix: supported 6, contradicted 7, insufficient evidence 4, conflicting 1. 18 cases form 12 source groups; report both counts.

### Ingestion notes

- The IHP evidence (17 to 22) is DOCX in the suite. Use the exact PDF conversions in the dataset's `Format Conversions/LegalReasonBench/` (hashes in its `provenance.json`). They belong to the same source group as the originals.
- Tobacco800 PNGs are 1-bit with ink stored as white on black. Ingest inverts them.
- Some ContractNLI file names contain `%20` or a leading space. Ingest sanitises display names.
- Several ContractNLI agreements are unsigned templates. Claims concern wording only.

### Gold (`gold-1`)

One JSON per case in `tests/fixtures/gold/`, read only by `scripts/eval_review.py` and `scripts/report_review.py`. Fields: case, pool, source dataset, split, claim, reference verdict with origin (`external_label`, `curated`, `author`), parts with spans and five-way status plus `conflict`, relations with part, relation, weakener type, file, page, verbatim quote, `quote_pdf`, optional boxes and origin.

| Source label | Our label |
|---|---|
| supported / contradicted | same |
| insufficient_evidence | not_found (fact absent after reading) or cannot_tell (judgment missing) |
| conflicting_evidence | contradicted with `conflict: true`; a pass needs a pinned supports and a pinned contradicts card |
| anchor `context_only` | relabelled to weakens (with type), set_aside or not_enough; marked `relabelled` |
| pack weakens / conditions / irrelevant | weakens / weakens (condition) / set_aside |

The suite's `Solutions/`, `_Evaluation/`, annotation files, `.fmt` and `.tab` never enter a model call. A blind relabel of 6 cases (12, 16, 43, 45, 23, 4) by a session without the reference reports agreement before the held-out run.

### Metrics

Kept from the 31 Oct roadmap: contradicts precision and recall, weakens recall, weakener type accuracy, five-way part status accuracy, false red on true claims, set-aside false positives, text-layer and scan box pass rates, pin rate by status, cost and time per claim. New: claim-level agreement with the suite reference verdict; conflict pass rate. Every rate carries n, the source-group count and a Wilson 95% interval, reported per pool.

### Wording we may use

"Measured once on 18 held-out cases: 6 questions on 3 real agreements with labels adapted from ContractNLI, legal benchmark files and historical scans with answers curated by the builder, and 4 synthetic packets we wrote. Relation and weakener labels are ours." Never "benchmark result", "externally validated accuracy" or a win over Direct Muse.
