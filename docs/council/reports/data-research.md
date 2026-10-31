# ProofGraph data research: sources for claim and evidence packets

Date: 31 Oct 2026. Author: data research agent. Web search and fetch were available.

How to read the verification labels:
- **VERIFIED** means I opened the source, or a search result quoted the official card or page.
- **PARTLY VERIFIED** means only secondary sources confirmed it.
- **UNVERIFIED** means it comes from memory. Check it before you rely on it, especially licences.

None of this is legal advice. Before committing any third-party file to a public repo, re-check its licence file.

## 0. Bottom line

1. **Finance and legal have strong public data, and freight has almost none.**
   - Finance and legal have good public claim-evidence data and an unlimited free supply of real documents, because SEC EDGAR filings and the contracts filed as exhibits are free to reuse (SEC webmaster FAQ).
   - Freight has no public annotated dataset of rate confirmations, bills of lading, PODs or freight invoices. Public labelled bills of lading are scarce enough that practitioners ask for 10 samples on vendor forums.
   - The real freight documents you can lawfully ship are government rules: FMC 46 CFR 541 (detention and demurrage invoicing), FMCSA 49 CFR 373.101 (bills of lading), and US military and GSA freight tariffs. The transactional documents themselves must be synthetic.
2. **No public dataset has a "weakens" label with a weakener type.**
   - The closest are VitaminC (contrastive revisions), ContractNLI (contradiction and not mentioned, with spans), WiCE (partial support per sub-claim) and SEC comment letters (the regulator challenging a company's assertion in a real document).
   - Your weakener taxonomy must be hand-labelled. Borrow structure from these sets.
3. **Use public datasets for three things:** schema inspiration, eval sanity checks, and seeding claims. Do not use them as your demo corpus.
   - Many have share-alike, non-commercial or no-derivatives terms that complicate a public repo.
   - Build the 30 packets from public-domain or CC BY documents plus clearly labelled synthetic ones.
4. **Recommended top-3 domains for the first 30 packets:** Finance (EDGAR), Legal (EDGAR contracts and CUAD), and Freight (public rules plus synthetic operational documents). AI product management comes fourth. It has decent real documents (GOV.UK service assessments, model cards), but its claims are softer and harder to label consistently.

## 1. Candidate datasets and corpora

Column key:
- **Rel** is the relation labels.
- **Evid** is the evidence granularity.
- **Verdict:** U = use as is, A = adapt, I = inspiration only.
- **Hrs** is the estimated hours to convert 10 to 30 items to the pack schema (claim, parts, documents with pages, gold relations with quote, page and weakener type, absence notes, variation tags).

### 1.1 Finance

| Name and URL | Size | Record | Rel | Evid | Licence | Maintained | Verdict | Hrs |
|---|---|---|---|---|---|---|---|---|
| FinDVer https://github.com/yilunzhao/FinDVer | Paper versions disagree: 2,400 (arXiv v1) or 4,000 (EMNLP 2024). Three subsets: FDV-IE, FDV-MATH, FDV-KNOW | `statement`, boolean `entailment_label`, `explanation`, `relevant_context` (indices into the report), and `report` (a 10-K or 10-Q file) | Entailed or refuted (binary) | Paragraph and table indices in long hybrid filings | MIT (VERIFIED on repo) | Repo README notes a July 2026 release of test-split labels (VERIFIED) | **A**. Best finance seed. Real filings, real claims, explanations | 6 to 10 (map context indices to page numbers, add parts, label weakener types for the refuted items) |
| FinanceBench https://github.com/patronus-ai/financebench | 150 public of 10,231 | Question, answer, evidence text, page number, document link (EDGAR PDF) | QA, not NLI | Page-level evidence quote with page number | Hugging Face card says CC BY-NC 4.0. Secondary sources conflict (PARTLY VERIFIED). Treat as non-commercial | Static since 2023 | **I or A**. Page-number evidence is exactly our format. Turn answers into claims, then perturb them | 5 to 8 |
| FinQA https://github.com/czyssrs/FinQA | About 8.3k QA pairs | Pre-text, table, post-text, question, program | QA with numeric programs | Table plus surrounding text, one page | MIT (UNVERIFIED) | Static since 2021 | **I**. Use for numeric perturbation recipes | 4 |
| TAT-QA https://nextplusplus.github.io/TAT-QA/ | About 16.5k questions over 2.7k contexts | Table plus paragraphs, question, answer, **scale** (thousand, million, percent) | QA | Table plus paragraph | CC BY 4.0 (UNVERIFIED) | Static, TAT-DQA adds PDF pages | **I**. The scale field is a must-copy idea | 3 |
| ConvFinQA https://github.com/czyssrs/ConvFinQA | About 3.9k conversations | Multi-turn numeric QA over FinQA | QA | Table | MIT (UNVERIFIED) | Static | I | 2 |
| SEC EDGAR full text https://www.sec.gov/edgar/search/ | Unlimited | 10-K, 10-Q, 8-K, earnings releases (EX-99.1), 10-K/A amendments | None | Raw documents | SEC says EDGAR public filing content is free to access and reuse (VERIFIED, webmaster FAQ). Third-party copyrighted material inside a filing may still be protected | Live | **U for documents** | n/a |
| SEC staff comment letters (CORRESP and UPLOAD filings on EDGAR) | Thousands per year | SEC letter questioning a disclosure, and the company's reply | Implicit challenge and response | Paragraph | Same as EDGAR (UNVERIFIED that the SEC treats correspondence identically) | Live | **A, high value**. Real weakeners written by an expert adversary | 2 to 3 per packet |
| 8-K Item 4.02 non-reliance and restatements | Hundreds | "Previously issued financials should no longer be relied upon" | Implicit supersession | Paragraph | EDGAR | Live | **A**. A real "time or superseded" weakener | 2 per packet |
| SEC XBRL Financial Statement Data Sets https://www.sec.gov/dera/data/financial-statement-data-sets | All filers, quarterly | Tagged numeric facts with period and unit | None | Fact level | Public (UNVERIFIED) | Live | **U for gold numbers**. Lets you auto-check figure claims | 1 |

### 1.2 Legal

| Name and URL | Size | Record | Rel | Evid | Licence | Maintained | Verdict | Hrs |
|---|---|---|---|---|---|---|---|---|
| ContractNLI https://stanfordnlp.github.io/contract-nli | 607 NDAs, 17 fixed hypotheses each | Contract text, hypothesis, label, evidence span ids (sentence or list item) | Entailment, Contradiction, NotMentioned. Spans exist only for the first two (VERIFIED) | Span level, discontinuous, multi-span | CC BY 4.0 (VERIFIED via project page) | Static since 2021 | **A, best legal seed**. NotMentioned maps to our absence notes | 4 to 6 (spans to pages need PDF rendering, add weakener types) |
| CUAD https://github.com/TheAtticusProject/cuad | 510 EDGAR contracts, 41 clause types, more than 13k labels | Contract plus clause-type answers (spans), PDFs included | Extraction, not NLI | Span plus original PDF | CC BY 4.0 (PARTLY VERIFIED) | Static | **A**. Clause labels such as cap on liability, termination for convenience, exclusivity and anti-assignment are ready-made qualifier and exception hunting targets | 3 to 5 |
| MAUD https://github.com/TheAtticusProject/maud | 152 merger agreements, about 47k labels (UNVERIFIED) | Deal point questions with answers | Multiple choice | Span | CC BY 4.0 (UNVERIFIED) | Static | I | 3 |
| LegalBench https://hazyresearch.stanford.edu/legalbench/ | 162 tasks | Varies by task | Some tasks are entailment-like | Short passages | Per-task licences, mostly CC BY (UNVERIFIED) | Static | I. Mine task definitions such as "definition" and "rule exception" | 2 |
| LEDGAR (LexGLUE) https://huggingface.co/datasets/lex_glue | About 60k provisions | Provision text plus label | Classification | Clause | CC BY-SA (UNVERIFIED) | Static | I | 1 |
| SEC EDGAR EX-10 material contracts and amendments | Unlimited | Credit agreements, supply agreements, amendments | None | Full documents | EDGAR reuse | Live | **U for documents**. Amendment chains give real supersession | n/a |
| CourtListener opinions https://www.courtlistener.com | Millions | Court opinions, sometimes with exhibits | Narrative findings | Page | Opinions are public domain. Exhibit contracts vary (UNVERIFIED) | Live | A. A court ruling that a clause did not cover X is a gold weakener | 2 per packet |

### 1.3 Freight and logistics

| Name and URL | What it is | Licence | Verdict | Notes |
|---|---|---|---|---|
| FMC D&D billing rule, 46 CFR 541 https://www.govinfo.gov/content/pkg/FR-2024-02-26/pdf/2024-02926.pdf | Required invoice contents. Missing required information eliminates the obligation to pay (541.5). 30-day issuance windows. 541.4 was set aside by the D.C. Circuit and later removed (VERIFIED, secondary) | US federal government work, public domain | **U** | Perfect for absence claims such as "invoice is payable" when the free-time start date is missing. Also has a real superseded-rule example in 541.4 |
| FMCSA 49 CFR 373.101 bills of lading https://www.ecfr.gov/current/title-49/part-373 | Required BOL contents for for-hire carriers. Household goods are covered separately at 375.505 (VERIFIED) | Public domain | **U** | Use as the rule document in BOL completeness packets |
| 49 CFR 371.3 broker records, and 41 CFR 102-118 (federal transportation payment and audit) | Broker record rules, and how the GSA audits freight bills | Public domain (UNVERIFIED cite numbers) | U | Real audit rules |
| SDDC Freight Traffic Rules Publication (MFTRP No. 1) and the Defense Transportation Regulation Part II | Military domestic freight tariff with accessorials such as detention, stop-off and layover, with free-time definitions | US government, likely public domain (UNVERIFIED) | **U, high value** | The only real, freely reusable accessorial and detention tariff I know of. It reads like a real carrier tariff |
| Public port authority tariffs (for example Port of Los Angeles Tariff No. 4, Port of NY/NJ, Port of Oakland) | Demurrage, wharfage, free time | Public-agency documents. Reuse terms vary by state (UNVERIFIED) | A | Quote excerpts with attribution, or link out |
| Ocean carrier D&D tariffs and carrier terms (Maersk, MSC and others, on their websites) | Free time, rules, exceptions | Copyrighted | I only | Paraphrase their structure into synthetic tariffs |
| NMFC (NMFTA) | Freight classification | Copyrighted and licensed | Avoid | |
| Incoterms 2020 (ICC) https://iccwbo.org/business-solutions/incoterms-rules/incoterms-rules-trademark-and-copyright-policy/ | Trade terms | ICC owns the copyright. Any reproduction in part or in whole needs permission. Incoterms is a trademark (VERIFIED) | **Avoid the text** | Name a rule ("FOB") but never paste its wording. Write your own plain-language summaries |
| Roboflow "freight invoice" https://universe.roboflow.com/saad-lachhab-bj5tz/freight-invoice | Small community computer-vision set. Contents unknown | Varies (UNVERIFIED) | I | Check it before using |
| UiPath Bills of Lading ML package docs https://docs.uipath.com/document-understanding/automation-suite/2.2510/user-guide/bills-of-lading-ml-package | Field list (date of issue, place of issue, B/L type, PO number) | Docs only | I | Use as a field checklist for templates |
| STB and FMC decisions, and court cases on detention disputes | Real disputes with findings | Public domain | A | Source of realistic adversarial claims |

**Verdict for freight: no annotated data exists.** Rules are public domain and usable as is. All rate confirmations, BOLs, PODs, invoices and emails must be synthetic.

### 1.4 AI product management

| Name and URL | What it is | Licence | Verdict |
|---|---|---|---|
| GOV.UK Service Standard assessment reports https://www.gov.uk/service-standard-reports | Real product reviews: "met / not met" per point, with reasons, for named services | Open Government Licence v3 (UNVERIFIED for every report, but the GOV.UK default is OGL) | **U, best PM source**. Real PM-style claims with explicit qualified verdicts |
| 18F and GSA TTS product docs and blog https://18f.gsa.gov | US government product method docs, research write-ups | Public domain or CC0 (UNVERIFIED) | U |
| Meta Llama model cards https://github.com/meta-llama | Model cards with benchmark tables and limits | Llama community licence. The repos are public, but check redistribution of the card text (UNVERIFIED) | A. Very on-theme for a Meta hackathon. Quote short spans and link out |
| Hugging Face model cards (librarian-bots/model_cards_with_metadata) https://huggingface.co/datasets/librarian-bots/model_cards_with_metadata | Mass dump of community cards. The card warns content is unreviewed and may contain personal data (VERIFIED). Licence not confirmed | Per-model licences | A. Filter to Apache or MIT models |
| arXiv eval reports and model papers under CC BY | Benchmark tables, ablations | Per-paper licence, shown on arXiv | A. Pick only CC BY papers |
| danluu/post-mortems https://github.com/danluu/post-mortems | List of links to public postmortems | Repo licence not found. The linked posts are owned by their authors | I. Link-only. Write synthetic postmortems in the same style |
| AI Incident Database https://incidentdatabase.ai | Incident reports with citations | CC BY-SA 4.0 (UNVERIFIED) | A |
| Public A/B test write-ups (Microsoft ExP, Booking, Netflix tech blogs) | Experiment readouts | Copyrighted | I only |
| Public PRDs | Almost none real. GOV.UK discovery and alpha reports come closest | | Synthetic |

### 1.5 General claim verification, attribution and document NLI

| Name and URL | Size | Rel | Evid | Licence | Verdict | Why it matters |
|---|---|---|---|---|---|---|
| FEVER https://fever.ai | About 185k claims | Supports, Refutes, NotEnoughInfo | Wikipedia sentences | CC BY-SA 3.0 (UNVERIFIED) | I | Known claim-only bias: models can score well without reading evidence |
| FEVEROUS https://huggingface.co/datasets/fever/feverous | About 87k | Same three labels | Sentences **and table cells** (VERIFIED) | CC BY-SA 3.0, following Wikipedia terms (VERIFIED) | I | Table-cell evidence format |
| VitaminC https://github.com/TalSchuster/VitaminC | More than 400k pairs from more than 100k Wikipedia revisions (VERIFIED) | Supports, Refutes, NEI, plus **contrastive pairs** where a small evidence edit flips the label | Sentence | CC BY-SA 3.0 (VERIFIED) | **I, design-critical** | The closest thing to our "time / superseded" and "magnitude" weakeners |
| TabFact https://tabfact.github.io | About 118k statements over about 16k tables | Entailed, Refuted | Table | CC BY 4.0 (UNVERIFIED) | I | |
| SciFact https://github.com/allenai/scifact | About 1.4k claims | Support, Contradict, NEI with rationale sentences | Abstract sentences | CC BY-NC 2.0 (UNVERIFIED) | I | Expert-written claims, rationale-span format |
| HoVer https://hover-nlp.github.io | About 26k | Supported, Not supported, multi-hop | Multi-document | CC BY-SA 4.0 (UNVERIFIED) | I | Multi-document evidence |
| WiCE https://github.com/ryokamoi/wice | About 1.9k claims | Supported, **Partially supported**, Not supported, per **sub-claim** | Cited web article sentences | CC BY-SA (UNVERIFIED) | **I, design-critical** | Matches our claim-parts idea. Decomposition helps |
| RAGTruth https://github.com/ParticleMedia/RAGTruth | About 18k responses | Span-level hallucination types (evident or subtle conflict, baseless info) | Span | MIT (UNVERIFIED) | I | Span-level conflict taxonomy |
| ALCE https://github.com/princeton-nlp/ALCE | 3 QA sets | Citation recall and precision | Passage | MIT code (UNVERIFIED) | I | Citation-quality metrics we can reuse |
| AttributionBench https://huggingface.co/datasets/osunlp/AttributionBench | 7 merged sources | Attributable or not | Passage | Apache-2.0 (VERIFIED card metadata) | I or eval | Shows models miss fine-grained, partial-support details |
| LLM-AggreFact https://huggingface.co/datasets/lytang/LLM-AggreFact | About 11 sub-datasets | Supported or unsupported per sentence | Grounding docs | CC BY-ND 4.0, **evaluation only, no training** (VERIFIED) | Eval only | Benchmark for a cheap checker (MiniCheck) |
| DocNLI, ContraDoc, FActScore, FactBench (UNVERIFIED) | | Document-level NLI, self-contradiction, atomic facts | Document | Various | I | |
| FUNSD https://guillaumejaume.github.io/FUNSD/ | 199 scanned forms | Key-value linking | Scan | Research and non-commercial terms. Images come from the tobacco litigation archive (UNVERIFIED) | I | Scan noise reference |
| SROIE https://github.com/zzzDavid/ICDAR-2019-SROIE | About 1k receipts | Field extraction | Scan | Unclear (UNVERIFIED) | I | |
| CORD https://github.com/clovaai/cord | About 1k public of 11k Indonesian receipts | Field parsing | Scan | CC BY 4.0 (UNVERIFIED) | A, for a receipt-noise style reference | |
| DocVQA https://www.docvqa.org | About 12k industry document images | QA | Page image | Research terms (UNVERIFIED) | I | Shows OCR and layout failure modes |

## 2. Top-3 real-document sources per domain

**Finance**
1. EDGAR 10-K, 10-Q and EX-99.1 earnings releases from companies with a restatement or a large guidance change.
2. EDGAR CORRESP and UPLOAD comment letter threads.
3. FinDVer reports and claims (MIT), which provide the claims and the gold binary label.

**Legal**
1. CUAD PDFs (CC BY 4.0, EDGAR contracts).
2. ContractNLI NDAs (CC BY 4.0) with their NotMentioned and Contradiction spans.
3. EDGAR EX-10 contracts plus their later amendments (supersession chains).

**Freight**
1. 46 CFR 541 (FMC D&D invoicing) and the Federal Register preamble.
2. 49 CFR 373.101, 371.3 and 41 CFR 102-118.
3. SDDC MFTRP No. 1 / DTR Part II accessorial rules, or a public port authority tariff.

All operational freight documents are synthetic.

**AI product management (fourth domain)**
1. GOV.UK service assessment reports (OGL).
2. Meta Llama or Apache-licensed Hugging Face model cards.
3. CC BY arXiv eval papers.

Postmortems, PRDs and A/B readouts are synthetic.

## 3. Plan for the first 30 packets

Every packet carries a `provenance` field per document:
- `real:<url>` for a real document;
- `real-excerpt:<url>` for an excerpt of one;
- `synthetic:<template_id>` for a made-up document.

Each document also carries a visible "SYNTHETIC" footer if it is synthetic. Every packet carries `variation_tags`. Target mix per domain:
- 4 supported-with-weakener packets;
- 3 contradicted packets;
- 2 absence packets;
- 1 fully supported control.

### Finance (10, about 90% real)

- **F1 to F4.** Start from FinDVer statements on 4 different companies.
  - Take 2 entailed claims and 2 refuted ones.
  - Download the source 10-K PDF from EDGAR so page numbers are real.
  - Add the weakener the model is likely to miss. Examples: "excluding the impact of the divestiture" (scope), "non-GAAP" (definition), a footnote with a segment restatement (time).
- **F5 to F6.** Take an 8-K earnings release claim ("revenue grew 12%") plus the 10-Q that shows constant-currency or an acquisition-driven explanation.
  - Weakener types: magnitude, scope.
- **F7 to F8.** Use a restatement chain: the original 10-K, the 8-K Item 4.02, and the 10-K/A. The claim quotes the original figure.
  - Gold: contradicted by the later document (time / superseded).
- **F9.** Use a comment-letter thread. The claim is the company's assertion. The SEC letter weakens it (weak source / definition), and the reply qualifies it.
- **F10.** Absence. Example claim: "the company disclosed a going-concern doubt". Search the packet and record a scoped absence note listing the pages searched.
- **Synthetic part:** only the claim sentences that you write yourself. Label them `claim_origin: authored`.

### Legal (10, about 90% real)

- **L1 to L4.** Use 4 ContractNLI NDAs.
  - Pick hypotheses where the label is Contradiction or where the Entailment depends on an exception, for example "Receiving party may share with employees" with a "provided that they are bound by..." condition.
  - Rewrite each hypothesis as a natural-sounding user claim.
- **L5 to L7.** Use CUAD contracts.
  - The claim is "Customer can terminate at any time without penalty".
  - The gold evidence is the CUAD "termination for convenience" span plus a notice-period or fee clause. Weakener types: condition, qualifier.
  - Use the CUAD "cap on liability" spans for magnitude.
- **L8 to L9.** Use an EDGAR contract plus its amendment. The claim cites the original term. Gold: superseded.
- **L10.** Absence via a ContractNLI NotMentioned hypothesis.
- **Synthetic part:** a cover email or AI summary that states the claim. Label it.

### Freight (10, about 25% real by page)

Each packet uses one real rule document and 2 to 4 synthetic operational documents.

- **R1 to R3. Detention.**
  - Documents: a synthetic rate confirmation stating "detention $75/hr after 2 hrs free", a synthetic POD with in and out times, and a synthetic carrier invoice.
  - Claims such as "Carrier is owed 4 hours detention". Weakeners:
    - in-time later than the appointment (condition);
    - a "must be reported within 24 hrs" clause (condition);
    - free time counted from appointment rather than arrival (definition).
- **R4 to R5. Ocean D&D invoices against 46 CFR 541.**
  - The claim is "this demurrage invoice must be paid".
  - Gold: contradicted, because the invoice omits a required element, for example the free-time end date (absence plus rule).
- **R6. BOL completeness against 373.101.** A field is missing or mismatched across the BOL and the rate confirmation (pieces or weight).
- **R7. Accessorial.**
  - Claim: "lumper fee is reimbursable".
  - Evidence: a rate confirmation that says "lumper requires receipt", and no receipt in the packet (absence).
- **R8. Rate dispute.** A rate confirmation, a revised rate confirmation sent the same day, and an invoice billed at the original rate (superseded).
- **R9. Tariff against invoice.** A detention line uses the SDDC or port tariff free time, and the invoice applies a different free time (magnitude).
- **R10. Scan-noise packet.** A POD photo with a skewed stamp and a handwritten out-time. Tests OCR confidence and "needs review".
- **Real part:** the CFR and tariff pages only.

### AI PM (optional 5 as a stretch)

- 2 from GOV.UK assessments. Example claim: "the service met user research needs", where the report has a "met with conditions" qualifier.
- 2 model-card claims. Example: "the model beats X on MMLU", where the card footnote shows a different shot count or eval setup (definition, scope).
- 1 synthetic experiment readout. Example claim: "the variant lifted conversion 4%", where the readout shows the result was not significant and was limited to one segment.

**Estimated build effort:** about 1.5 to 2.5 hours per real-document packet and about 3 hours per synthetic freight packet, including templates once. That is about 70 hours total for 30 packets. Templates are the main one-off cost (about 8 hours). If time is short, do 6 per domain first.

## 4. What must be synthetic, and how to make it realistic

**Must be synthetic:**
- Freight rate confirmations, BOLs, PODs, freight invoices, lumper receipts and dispatcher emails.
- PRDs, A/B readouts and most postmortems.
- Any document containing personal data.
- Incoterms wording, which you must write yourself.

**Realism recipe:**

1. **Templates from field lists, not from copied forms.**
   - Build each template from the regulatory required-field list (373.101, 541) plus vendor field lists such as the UiPath BOL fields.
   - Vary the layout across 3 to 4 template families per document type, the way different brokers produce different rate confirmations.
2. **Entities.**
   - Use fake company names checked against FMCSA SAFER so you do not collide with real carriers.
   - Use real city pairs with plausible mileage and rates, consistent MC/DOT-like formats marked "000000", and plausible appointment windows.
3. **Cross-document consistency with planted defects.**
   - Generate a single "truth" record, then render every document from it.
   - Introduce exactly the planned discrepancy, and log it as gold.
4. **Boilerplate density.**
   - Real rate confirmations bury the key clause in a block of 20 to 40 terms (fuel surcharge, TONU, layover, claims, factoring).
   - Write a terms bank and sample from it, so weakeners do not sit alone in an obvious place.
5. **Scan artefacts.**
   - Render to PDF, rasterise at 150 to 200 dpi, then apply random rotation (±2°), JPEG compression, slight blur, a stamp overlay, handwritten times (use a handwriting font), and fax-style banding.
   - Keep a clean twin of each scanned document for debugging.
6. **Adversarial claims.**
   - For each packet, write the claim the way a busy user or an LLM would: overconfident, rounded numbers, missing scope.
   - Write minimal pairs: the same claim with evidence edited by one fact (VitaminC style), and the same evidence with the claim edited by one qualifier.

**Synthesis pitfalls:**
- **Label leakage.** The weakener is the only odd-looking clause, or it uses the word "except" every time.
- **Templated tells.** All synthetic invoices share fonts and layout, so a model learns the template rather than the task.
- **Arithmetic that is too clean.** Real totals include fuel surcharge percentages, rounding and partial hours.
- **LLM-written documents** sound uniform and polite. Real emails are terse and contain typos.
- **No hard negatives.** Every packet has a problem, so "supported" never appears. Keep about 15% clean controls.
- **Real names or real MC numbers** slip into synthetic documents.
- **Absence that is not really absent.** The fact sits on a page outside the packet, or appears in a different unit.
- **Unlabelled synthetic content** in a public repo, which misleads judges. Label it in the data and in the UI.

## 5. Minimum gold annotation guideline (single annotator)

1. **Claim parts.**
   - Split the claim into atomic, independently checkable parts: one subject, one predicate, one quantity or date each.
   - Keep the original wording. Store character offsets back into the claim.
   - Each part names its type: `entity`, `quantity`, `time`, `condition`, or `attribution`.
2. **Per-part status.** Exactly one of:
   - `supported`;
   - `supported_with_weakener` (true but qualified);
   - `contradicted`;
   - `not_found` (absence);
   - `needs_review` (unreadable or ambiguous scan).

   The claim-level status is derived by rule, never labelled directly: any contradicted part makes the claim contradicted; otherwise any not_found part makes it not_found; otherwise any weakener makes it supported_with_weakener.
3. **Relations.** Each relation records:
   - the part id;
   - the relation, one of `supports`, `contradicts`, or `weakens`;
   - the document id and page;
   - the verbatim quote (shortest span that carries the meaning, at most 2 sentences or one table row with its header);
   - the bounding box if available.

   Multi-span evidence gets multiple relations with a shared `group_id`. The quote must match the document text exactly after whitespace normalisation, and a script checks this.
4. **Weakener type.** Exactly one primary type per `weakens` or `contradicts` relation, in this order of precedence: `time_superseded`, `condition`, `exception`, `scope`, `definition`, `magnitude`, `qualifier`, `weak_source`.
   - Decision tests:
     - Does it apply only if X happens? Then `condition`.
     - Does it carve out a case? Then `exception`.
     - Does it limit who, where or which items? Then `scope`.
     - Does it change what a term means? Then `definition`.
     - Is a number different or bounded? Then `magnitude`.
     - Is there hedging language? Then `qualifier`.
     - Is the source unaudited, an estimate, or a third party? Then `weak_source`.
     - Is the claim replaced by a later document? Then `time_superseded`.
   - Absence is a status, not a weakener type.
5. **Absence notes.** For `not_found`, record:
   - what was searched for, as 2 to 4 search terms or synonyms;
   - which documents and pages were checked;
   - what would have counted as evidence.

   Never mark not_found if any document is unreadable. Use needs_review instead.
6. **Variation tags.** Tag each packet with the conditions it tests: `numeric`, `table`, `scan`, `multi_doc`, `long_doc` (more than 50 pages), `supersession`, `minimal_pair`, `negation`, `unit_scale`, `synthetic`.
7. **Consistency tools.**
   - Keep a decision log of edge cases.
   - Re-label 10% of packets blind after 3 days and compute self-agreement. If it falls below 85% on weakener type, merge or redefine types.
   - Have the model pre-label, then correct it, but record `label_source: human_corrected`.

## 6. What the data tells us about how to build: 8 design implications

1. **Decompose claims, then judge per part.**
   - WiCE shows that partial support is common and that sub-claim decomposition improves entailment judgments. FActScore-style atomic facts give the same lesson.
   - Show partial support explicitly per part. The part chips in the left panel are the right design.
2. **Assume models ignore evidence until proven otherwise.**
   - FEVER has a known claim-only bias, and VitaminC shows that models trained on static evidence fail when one fact in the evidence changes. Contrastive training improves robustness.
   - Build minimal pairs into the eval set, and check that the verdict flips when the evidence flips.
3. **Do arithmetic in code, not in the model.**
   - FinQA, TAT-QA and FinDVer errors cluster on multi-step numeric reasoning and scale or unit mistakes (thousands against millions, percent against percentage points). TAT-QA needed a separate scale field.
   - Extract number, unit, scale, period and basis (GAAP or non-GAAP), and compare them deterministically.
4. **Retrieval is the bottleneck on long documents.**
   - FinanceBench's reported results show retrieval-based setups failing most questions, while giving the right pages helps a lot. FinDVer is built around long hybrid filings for the same reason.
   - Index by page. Run a second retrieval pass that hunts specifically for weakeners: "except", "provided that", "subject to", "excluding", footnotes, amendments, and later-dated documents.
5. **Make "not found" a first-class, scoped answer.**
   - ContractNLI keeps NotMentioned separate and gives it no evidence spans. NEI is the hardest class in FEVER and SciFact.
   - Say "not found in pages searched", list the pages, and never turn absence into "false" unless a rule says absence voids the claim, as in 46 CFR 541.5.
6. **Evidence is discontinuous and multi-span.**
   - ContractNLI spans are sentence or list-item sets, and contract exceptions often sit far from the main clause.
   - AttributionBench shows models are insensitive to fine-grained partial mismatches.
   - Support grouped quotes. Verify every quote verbatim against the source before showing it, and reject quotes that cannot be matched.
7. **Time and supersession need explicit document dates.**
   - VitaminC is built from revisions. Restatements and contract amendments are routine in finance and legal.
   - Capture each document's effective date and amendment chain, and rank later documents as able to override earlier ones.
8. **Tables and scans need their own path and an honest "needs review".**
   - FEVEROUS keeps table cells as evidence units. DocVQA, FUNSD and SROIE show OCR and layout errors dominate on scans.
   - Keep table cells with their row and column headers. Carry OCR confidence through to the UI, and route low-confidence spans to needs_review instead of guessing.
   - A small dedicated checker (the MiniCheck results on LLM-AggreFact) can verify each quote-part pair cheaply after a larger model proposes it.

## Sources consulted (opened or seen in search results)

- https://github.com/yilunzhao/FinDVer (opened)
- https://arxiv.org/abs/2411.05764
- https://github.com/patronus-ai/financebench
- https://huggingface.co/datasets/PatronusAI/financebench
- https://stanfordnlp.github.io/contract-nli
- https://arxiv.org/abs/2110.01799
- https://huggingface.co/datasets/theatticusproject/cuad-qa
- https://huggingface.co/datasets/tals/vitaminc
- https://huggingface.co/datasets/fever/feverous
- https://arxiv.org/pdf/2106.05707
- https://huggingface.co/datasets/osunlp/AttributionBench
- https://huggingface.co/datasets/lytang/LLM-AggreFact
- https://arxiv.org/abs/2404.10774
- https://www.sec.gov/os/webmaster-faq
- https://www.govinfo.gov/content/pkg/FR-2024-02-26/pdf/2024-02926.pdf
- https://www.hfw.com/insights/fmcs-new-demurrage-and-detention-regulations-become-effective-may-2024
- https://public-inspection.federalregister.gov/2025-23920.pdf
- https://www.law.cornell.edu/cfr/text/49/373.101
- https://iccwbo.org/business-solutions/incoterms-rules/incoterms-rules-trademark-and-copyright-policy/
- https://universe.roboflow.com/saad-lachhab-bj5tz/freight-invoice
- https://forum.uipath.com/t/bill-of-lading-samples/724828
- https://docs.uipath.com/document-understanding/automation-suite/2.2510/user-guide/bills-of-lading-ml-package
- https://github.com/danluu/post-mortems
- https://huggingface.co/datasets/librarian-bots/model_cards_with_metadata
- https://guillaumejaume.github.io/FUNSD/ (licence UNVERIFIED)
- https://github.com/zzzDavid/ICDAR-2019-SROIE (licence UNVERIFIED)
- https://www.docvqa.org (licence UNVERIFIED)

Everything else above is marked UNVERIFIED and comes from memory.
