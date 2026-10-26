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
- **16 bundles** in `examples/freight/bundle_NN/`, each with `rate_confirmation.pdf`, `pod.jpg`, `dock.jpg`, `invoice.pdf` and `key.json`.
- **Mix:** 6 correct; 6 wrong (3 detention errors, 3 carton-count errors); 4 smudged or ambiguous (2 smudged departure times, 2 cluttered carton photos). The correct answer for the smudged ones is UNRESOLVED for the affected line.
- **Content:** fictional carrier and shipper names only. Rate confirmation line: "Detention: $75.00/hour after 2 hours free time" (vary the rates and free time across bundles). POD: printed form with handwritten "Arrived" and "Departed" times. Dock photo: 10–30 clearly separated cartons. Invoice: "Cartons delivered: N", "Detention: $X".
- **How:** generate PDFs from a template (`scripts/make_freight_pdfs.py`), print the POD form, handwrite the times, and photograph everything with a phone.
- **`key.json`:** `{"verdict": "...", "lines": {"detention": "...", "cartons": "..."}, "truth": {"arrived": "07:40", ...}}`.
- Presented as a **demonstration with an honest label**, never as a benchmark.

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
