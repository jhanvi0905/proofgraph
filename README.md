# ProofGraph

[![ci](https://github.com/jhanvi0905/proofgraph/actions/workflows/ci.yml/badge.svg)](https://github.com/jhanvi0905/proofgraph/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.11+-blue)
![license](https://img.shields.io/badge/license-MIT-green)

**Before you approve, pay, or sign on a conclusion, see the sentence in the documents that breaks it.**

An AI or a colleague writes "the NDA lets us brief our consultants" or "the filing puts the incident's net cost at $2.2 million", and someone has to act on it. ProofGraph takes that conclusion and the documents behind it, splits the conclusion into its parts, and shows for each part the exact sentence that **supports**, **contradicts**, or **weakens** it, boxed on the original page. If the documents don't settle a part, it says **Not found** or **Can't tell** instead of guessing.

**Why it needs Meta's models:** Muse Spark reads the *whole packet* for every part of the claim, with no retriever, and reads scanned pages from the image. Meta's open-weight **Muse Spark Open** then re-reads every quote blind. Code, not a model, pins each quote to the page and decides each status.

```
Claim   "The Bosch NDA allows the recipient to share confidential information
         with outside consultants without written authorization."

CONTRADICTED
  "Recipient will not disclose or permit access to Confidential Information to contract
   workers, consultants or contractors unless authorized by Disclosing Party in writing"
   Bosch_NDA.pdf p1 · box pinned to the PDF's own text · second check (Muse Spark Open) agrees
```
<sub>From the review fixture [tests/fixtures/review_tc40.json](tests/fixtures/review_tc40.json) (the real Bosch NDA from the public ContractNLI set). A live Muse Spark call on 31 Oct returned this clause as the contradicting passage: [docs/council/2026-10-31-probes.md](docs/council/2026-10-31-probes.md).</sub>

Built during the [Meta Global AI Developer Hackathon](https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details), Oct 26 to Nov 4, 2026 · Indie track · Build for Your World.

## Demo

- **3-minute video:** `TODO: video link`
- **Live app:** `TODO: app link` (passcode-gated, because every live check spends real money)

The planned demo cases are a governance memo checked against bylaws and a board resolution (LegalReasonBench Test Case 17) and the Bosch NDA above (ContractNLI Test Case 40). Those packets are not committed in this repo, so bring your own contract, policy or filing to the live app.

## How it works: model proposes, code proves, a second model re-reads blind

<p align="center">
  <img src="docs/img/review-architecture.svg" width="100%" alt="ProofGraph review run. The reviewer submits a claim and files. Code ingests pages and checks the spend cap. Muse Spark reads scan images, splits the claim, and reads the whole packet once per part. Code checks the split and pins each quote to the page. Muse Spark Open re-reads each quote against its part, blind. Code applies fixed status rules and the HTML viewer shows boxes and part verdicts.">
</p>

<sub>In text: claim + files → ingest (code) → spend cap (code) → Muse Spark splits the claim → code checks the split → Muse Spark reads the whole packet per part → code pins the quote to the page → Muse Spark Open re-reads quote + part blind → code sets the status → viewer. The diagram follows light or dark mode. Its source is [docs/img/review-architecture.archify.json](docs/img/review-architecture.archify.json), with every node citing its code; [docs/img/review-architecture.html](docs/img/review-architecture.html) is the interactive version (open it locally).</sub>

Parts run in parallel (four at a time), so the app shows each part as a grey "Checking" row that turns into a verdict as it finishes. A whole review downloads as one self-contained HTML file.

## "You're checking AI with more AI. Why trust it?"

Because ProofGraph never asks you to believe a model. It hands you the one sentence that decides each part, boxed on the page, and leaves the deciding to fixed code and your own eyes. **AI finds, code proves, you decide.**

1. **Finding is hard; checking is easy.** The model does the hard part: finding the one sentence in a long packet that breaks the claim. Checking it takes you seconds. Click the card, the page jumps to the box, read the sentence.
2. **No quote on the page, no box.** A solid box is drawn only when code finds the model's quote in the PDF's own words ([snap.py](proofgraph/review/snap.py)). If it can't, there is no box, the card says so in plain words, and that card can never turn a part red ([status.py](proofgraph/review/status.py)).
3. **No model picks the verdict.** Fixed rules in [status.py](proofgraph/review/status.py) turn the evidence into a status, and every review runs the same steps in the same order ([run.py](proofgraph/review/run.py)). A line in a document telling the AI to "approve this" is shown to you as a banner, and it cannot set the verdict, because no model sets the verdict.
4. **The second read is narrow, and it can only make things more cautious.** Muse Spark Open sees one quote and one sentence, never the first model's answer, its reasoning or the page ([check.py](proofgraph/review/check.py)). If it disagrees with all of a part's support, the part drops to **Can't tell**; a disagreement never upgrades anything. Its weights are open, so you can run this check on your own servers.
5. **It says "I can't tell".** **Not found** needs every page read and a plain word sweep that finds no mention the model skipped; otherwise the answer is **Can't tell** ([absence.py](proofgraph/review/absence.py)). A tool that admits when it can't tell is one you can rely on when it does answer.

Every card is on the record: the quote, its document and page, its box, and the second check's answer, all in the one-file HTML export. Tests keep the blind check from importing the reading model's code or seeing the card's reasoning, document or page ([tests/test_boundaries.py](tests/test_boundaries.py)). The one limit to know: a model can still pick the wrong passage, which is exactly why each finding is a sentence you can read on the page, not a score.

## Why this needs Meta's models

| Meta capability | What ProofGraph does with it | What you would lose without it |
|---|---|---|
| **Muse Spark, long context** (1M tokens, [docs/04](docs/04-meta-models.md)) | One call per claim part carries every page of every file, page-tagged, fenced as data ([relate.py](proofgraph/review/relate.py), [prompts/relate.md](prompts/relate.md)). | A retriever ranks passages by how much they look like the claim. The sentence that breaks a claim ("unless authorized in writing", "subject to board approval") often doesn't, so it can be ranked out. Reading whole is how weakeners get found. |
| **Muse Spark vision + Meta Files API** | Pages with no text layer are uploaded with `files.create` and transcribed line by line, each line with a box on a 0 to 1000 grid ([scan.py](proofgraph/review/scan.py), [prompts/transcribe.md](prompts/transcribe.md)). Those lines are then read like any other page. | Scans, photos and stamped copies would stay unread, and a part could never be called Not found while they were. |
| **Structured outputs + reasoning effort** (Responses API `text.format: json_schema`) | Every call returns a schema-validated object, with one repair call on bad JSON ([muse.py](proofgraph/clients/muse.py)). The split must copy each part verbatim and keep every number inside a part, or code rejects it ([split.py](proofgraph/review/split.py)). | Free text you'd have to parse by guesswork. Here every quote and span is something code can check. |
| **Muse Spark Open, open weights** (`muse-spark-open-1026` on Baseten) | The blind second read. It gets one quote and one sentence and answers `entails`, `contradicts` or `not_mentioned` ([prompts/blind_wording.md](prompts/blind_wording.md), [check.py](proofgraph/review/check.py)). | The proposer grading its own work. Because the weights are open, a company can host the checker itself and keep the verification step on its own infrastructure. |
| **SAM 3.1** (built and tested, not yet in the main flow) | Visual evidence. For a claim such as "the photo shows 40 boxes", SAM gets the photo (or the region Muse Spark boxed) and the noun, counts every match, and code accepts the stated number only if SAM's count equals it ([sam.py](proofgraph/clients/sam.py), [ground.py](proofgraph/engine/ground.py)). SAM never sees the claim or the first model's answer. | A count in a photo could only be "checked" by the model that read it. Today this runs only from the older Packet app page, not the New review page or the demo. |

Code does the rest, and that is deliberate. A box is **pinned** only when [snap.py](proofgraph/review/snap.py) finds the model's quote in the PDF's own extracted words; a quote that is not on the page gets no box at all. Status comes from fixed rules in [status.py](proofgraph/review/status.py). Numbers in the offline engine are computed by a safe calculator, never taken from model output.

<details>
<summary><b>Exactly where the boxes come from</b></summary>

- **Text-layer PDFs (solid box).** Muse Spark proposes the exact quote. Code matches it, letters and digits only, against the words `pdfplumber` extracted from that page and draws one rectangle per printed line. No match means no box. Muse does not draw these boxes; it finds the sentence, and code proves where it is.
- **Scans and photos (dashed box).** Muse Spark transcribes the page image and returns a box per line on a 0 to 1000 grid. Code fuzzy-matches the quote to those lines and uses their boxes. A probe found these boxes sit about a line low by a varying offset, so they are marked **approximate**, drawn dashed, and can never turn a part red.
- **Packet app page (second page in the app).** The older claim-level check asks Muse Spark to return a box for each fact it reads from an uploaded PDF, then code confirms the value is printed inside that box at a 2%, 3% or 4% margin ([ground.py](proofgraph/engine/ground.py)). The same page sends a counted object in a photo to SAM 3.1.

</details>

<details>
<summary><b>What SAM 3.1 does here, and what it doesn't</b></summary>

- **Does:** counts instances of one named thing (a noun such as "box" or "person") in a still image. The image goes up as `input_image` with the noun as the only text; the count is the number of boxes SAM returns, and the masks are discarded ([sam.py](proofgraph/clients/sam.py)). If Muse Spark gave a valid box for the fact, only that region is sent ([ground.py](proofgraph/engine/ground.py)).
- **Decides nothing on its own:** code compares SAM's count with the stated whole number. Equal means grounded; anything else, or any SAM error, leaves the fact ungrounded (fail closed).
- **Doesn't:** read text, judge condition or damage, answer open questions about a picture, or run on the New review page.
- **Status:** built and unit-tested with a stubbed SAM response, so `uv run pytest tests/test_sam.py tests/test_bundle.py` runs offline and free. No live SAM result is shown in this README.

</details>

### "Isn't this just RAG?"

No. There is no retriever, no index, no embeddings and no top-k anywhere in the review path. Muse Spark reads every page for every part, and has to answer with a typed relation, so **contradicts**, **weakens** (with a type such as exception, condition or time limit) and **not found** are first-class outputs, not just "here is a relevant chunk". Then code checks that the quote is really on the page before it counts.

### "Isn't the second model just another LLM grading?"

It is narrower than that on purpose. Muse Spark Open never sees the first model's answer, its reasoning, the page, or any other card: only one quote and one part sentence ([check.py](proofgraph/review/check.py)). It is a witness, not a veto. Its answer is shown on the card and never deletes one. Code decides what it changes: if every supporting quote for a part was disagreed with, that part is **Can't tell**, not Supported. It shares lineage with Muse Spark, so we don't claim it is independent; the separation comes from what it is shown.

## Who it's for

The moment ProofGraph is built for: someone is about to approve, pay, or sign on a conclusion they did not check line by line.

- **Contract and policy reviewers** checking what an agreement or bylaw actually allows before acting on a summary of it.
- **Finance and audit reviewers** checking a figure in a memo against the filing it came from.
- **Anyone handed an AI summary** of a document packet and asked to sign off on it.
- **AI agents** that act on documents and need a check, with quotes, before they act.

## Try it in two minutes, no API key

The deterministic engine runs offline on recorded programs. This one checks an invoice against its rate agreement with real arithmetic. The documents are fictional; we wrote them to demonstrate the engine:

```bash
git clone https://github.com/jhanvi0905/proofgraph.git
cd proofgraph
make setup                      # needs uv and Python 3.11+: https://docs.astral.sh/uv/
uv run python -m proofgraph examples/packets/detention-overcharge.json
```

```
CONTRADICTED
COMPUTED
Detention should be $187.50, not $450.00 (4.5 h on site, 2 h free, $75/h)
```

Other runnable fixtures in [examples/packets](examples/packets), all fictional: `detention-correct.json` (SUPPORTED), `late-fee-overcharge.json` and `ship-export-this-week.json` (both CONTRADICTED).

## Run the full app with your own keys

The live review reads your documents with Muse Spark and re-checks each finding with Muse Spark Open. You need two keys.

| What | Where to get it | Environment variable |
|---|---|---|
| Meta Model API key (Muse Spark) | [dev.meta.ai](https://dev.meta.ai/docs/quickstart) | `MODEL_API_KEY` |
| Baseten key (Muse Spark Open, the blind checker) | [baseten.co](https://www.baseten.co) | `BASETEN_API_KEY` |

**1. Install.**

```bash
make setup
```

**2. Add your keys.** The code reads the process environment only; it does **not** auto-load `.env`. Copy the template, fill in the two keys, and load it into your shell:

```bash
cp .env.example .env
# edit .env: set MODEL_API_KEY and BASETEN_API_KEY
set -a; source .env; set +a
```

**3. Set a passcode.** Live checks spend your money, so the app refuses to run one until a passcode is configured. Create `.streamlit/secrets.toml` (git-ignored):

```toml
APP_PASSCODE = "pick-something"
```

**4. Start it.**

```bash
make app
```

Open the URL Streamlit prints (default http://localhost:8501), enter the passcode, paste a claim, upload one or more PDFs or images, and press **Check the claim**.

Good first inputs:

- Any contract or policy of your own: paste a sentence such as "Either party may terminate on 30 days' notice" and upload the PDF.
- The fictional demonstration pair in [examples/freight/demo-001](examples/freight/demo-001) (`invoice.pdf` and `rate_confirmation.pdf`) with the claim *"The detention charge on the invoice is correct."* The documents say 4.5 hours on site, 2 free, at $75 an hour, which is $187.50 against an invoiced $450.

<details>
<summary><b>Settings</b> (all optional; defaults in <a href=".env.example">.env.example</a>)</summary>

| Variable | Default | What it does |
|---|---|---|
| `MUSE_MODEL` | `muse-spark-1.3` | Model that splits the claim and reads the pages |
| `CHECKER_MODEL` | `meta-models/muse-spark-open-1026` | Blind second check, served by Baseten |
| `BASETEN_BASE_URL` | `https://inference.baseten.co/v1` | Baseten Chat Completions endpoint |
| `SAM_MODEL` | `sam-3.1` | Object counter used by the older Packet app check |
| `SPEND_LIMIT_USD` | `50` | Hard cap on total spend, checked before every paid call. A run stops at the cap and shows no verdict. |
| `CACHE_DIR` | `cache` | Every validated model call is cached on disk, so repeat runs cost nothing |

Optional, off by default: `PROOFGRAPH_EVIDENCE_MAP=1` shows every labelled passage for a part, grouped by relation on an inferred timeline, instead of the one deciding passage.

</details>

Run the tests: `make test` (1,000 tests, no network, no keys).

## Part statuses and the rules behind them

| Status | Meaning |
|---|---|
| **Contradicted** | A quote pinned to the PDF text says the opposite. If a pinned supporting quote exists too, the part is flagged as a source conflict. |
| **Weakened** | The quote supports it, but an exception, time limit, or condition narrows it. |
| **Supported** | A supporting quote stands and nothing above applies. |
| **Not found** | Every page was read, and a plain word sweep of the part's own terms found nothing the model skipped ([absence.py](proofgraph/review/absence.py)). |
| **Can't tell** | A page could not be read, the word sweep found an uncited mention, or the second check disagreed with all the support. |

Instructions inside documents are data. A line telling the reviewer to "approve this" is shown as a banner and not obeyed. The guardrails, such as "the proposer never checks itself", are written in [docs/08-guardrails.md](docs/08-guardrails.md) and enforced by [tests/test_boundaries.py](tests/test_boundaries.py).

<details>
<summary><b>Every Meta model in the repo, and where it runs</b></summary>

| Model | Job | On the New review page? |
|---|---|---|
| Muse Spark (`muse-spark-1.3`) | Splits the claim, reads every page per part, transcribes scans | Yes |
| Muse Spark Open (`muse-spark-open-1026`, via Baseten) | Blind wording check of each card | Yes |
| Muse Spark Open | Blind re-read of a cropped time from a photo | No: the older Packet app check only ([ground.py](proofgraph/engine/ground.py)) |
| SAM 3.1 (`sam-3.1`) | Visual evidence: counts a named object in a photo, checked against the stated count | No: built and tested, reachable only from the older Packet app check, not in the demo |

</details>

## What this is not

- Not a chatbot, and not a RAG app.
- Not legal or financial advice. It checks a claim against the documents you give it.
- Not a guarantee. A model can still pick the wrong passage; the boxes are there so a person can see that in seconds.
- Not exact on scans. Scanned pages get approximate boxes and a plain note saying so.

## Evaluation

`TODO: evaluation results`

## Built during the hackathon

All of it was built between Oct 26 and Nov 4, 2026; the first commit is a day-one scaffold. It began as a claim-level verifier, and on Oct 31 it was rebuilt around part-by-part review of uploaded packets. The deterministic engine and its tests survived and sit beside the new review layer.

| Layer | Where |
|---|---|
| Verification engine (numbers, grounding, routing, combine rules) | [proofgraph/engine](proofgraph/engine) |
| Review layer (split, read, pin, check, status, evidence map) | [proofgraph/review](proofgraph/review) |
| Model clients, cache, and spend cap | [proofgraph/clients](proofgraph/clients), [proofgraph/cache.py](proofgraph/cache.py), [proofgraph/spend.py](proofgraph/spend.py) |
| Streamlit app and the one-file HTML viewer | [app](app) |
| Prompts, as plain files | [prompts](prompts) |
| Decisions and sprint records | [docs/11-decision-log.md](docs/11-decision-log.md), [docs/council](docs/council), [docs/sprint](docs/sprint) |

The commit log is the complete record. [BUILT_DURING_HACKATHON.md](BUILT_DURING_HACKATHON.md) is a daily log that runs behind the tree.

## Licences and attribution

Code: MIT. The demonstration documents under [examples](examples) (the invoice and rate pair, and the detention, late-fee, governing-law and ship-export packets) are fictional and were written for this project. The two `numeric-*.json` packets quote SEC filing passages from FinDVer.

- ContractNLI: Koreeda and Manning, "ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts," Findings of EMNLP 2021. CC BY 4.0.
- FinDVer: Zhao et al., "FinDVer: Explainable Claim Verification over Long and Hybrid-Content Financial Documents," EMNLP 2024. MIT.
- LegalReasonBench (micro1 public sample): CC BY 4.0 per its source card.
