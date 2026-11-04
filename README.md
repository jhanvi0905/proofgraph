# ProofGraph

**Where does it say that?** ProofGraph checks a claim against every document in the packet and opens the clause that decides it, on its page.

Live: <https://proofgraph-orww.onrender.com/> (open it and choose **See the worked example**; no account, no key, no upload). Built during the Meta Global AI Developer Hackathon (Oct 27 to Nov 4, 2026).

[![ProofGraph review screen: three clauses on page 1 go against the claim, the deciding clause circled on the real page](docs/media/hero.gif)](docs/media/hero.mp4)

*The review screen on a claim about a real NDA (case TC40, from ContractNLI, CC BY 4.0, Koreeda and Manning 2021): each clause that goes against the claim is circled on its page. [Full-quality video](docs/media/hero.mp4).*

> On 30 ContractNLI pairs never used while building, ProofGraph was right on **19** against **15** for the same pipeline without the graph, and wrongly supported **1 claim in 20** against 2. At n = 30 the intervals overlap, so we say *better on unseen cases*, not *proven better*. Details and caveats are under [Results](#results).

## What it does

People trust an answer as far as they can see what it came from. Hand ProofGraph a sentence ("The recipient may share confidential information with outside consultants without written authorization") and a packet of documents. It splits the claim into parts, checks each part against every document, and answers each part with one of six words:

| Answer | Meaning |
| --- | --- |
| Supported | Statements match, nothing conflicts, no exception applies |
| Contradicted | A rule clashes with the part, including a claim that denies an exception's condition |
| Qualified | Support exists, but an exception or condition is attached |
| Not found | The documents discuss the thing but never say this, and a full read found nothing either |
| Unknown | No document mentions the thing at all |
| Documents disagree | Two documents clash and nothing decides which wins |

Each answer opens the deciding clause on its page, shows the path the reasoning took, and says which document wins and from when.

**Worked example (the one on the live app).** A synthetic packet (every name invented): a software license, a press release, an employee FAQ and a scanned Schedule 4. Claim: *"After Brightline completes its acquisition of Corvid, Corvid's license with Halvorsen will transfer automatically to Brightline without Halvorsen's consent, because the license allows assignment to Affiliates and to successors in an acquisition."*

ProofGraph splits it into three parts and answers each one. **Part 2** (automatic transfer without consent) is **Contradicted**. It reaches its clause in two hops, Change of Control then the license, page 2, where a change of control is deemed an assignment and an assignment without consent is void. Schedule 4, a scan, also goes against the claim; its box is approximate and it is labelled the model's reading. **Part 3** is **Qualified**: the license does allow assignment to an Affiliate or acquirer, an exception that may apply, so the claim is weakened, not decided. **Part 1** (the deal closing) is **Documents disagree**: the press release qualifies it, the FAQ supports it, and nothing says which wins. A notice dated 15 Jan 2026 is cited but not supplied, so nothing rests on it. Part 2 drives the whole-claim answer, Contradicted.

![Worked example: each of the three claim parts, from entity to clause to answer. Solid arrows are the deciding path, dashed arrows are other evidence](docs/img/worked-example.png)

*Interactive version: [docs/diagrams/worked-example.html](docs/diagrams/worked-example.html) (download and open).*

## Why a sceptic can believe it

Fastest to check first:

1. **The page.** The deciding clause, circled on the real page.
2. **The path.** For example Connors, CMO (interim), principal officer, Bylaws section 5.2: the reasoning a careful reviewer would write out.
3. **The override.** Which document wins, and from when.
4. **The honesty.** "Not in these documents" and "cited, not in the packet" are answers, not failures.
5. **How each link was made.** *Read from the page* (code verified the quote), *the model's reading*, or *unclear*. An unclear link never decides an answer, and an answer is only as strong as its weakest link.
6. **Two routes agree.** A typed graph walk and one full read of the packet run side by side. "Not found" needs both to come back empty.
7. **Measured, not asserted.** The wrongly-supported rate on held-out cases.

## How it works

ProofGraph is neuro-symbolic. A Meta model reads the documents and makes small, local judgments. Deterministic code builds the graph, walks it, applies precedence and dates, and decides. The graph and the decision logic are deterministic; the contents of the graph are probabilistic, and every probabilistic piece is labelled.

| # | Step | Done by | Technique |
| --- | --- | --- | --- |
| 1 | **Read** each document once into rule-shaped statements (who is bound, must / may / must-not / fact, action, value, effective date, exact quote). Exceptions become linked statements. One *gleaning* recall pass asks what was missed. | Muse Spark | Information extraction, schema-constrained JSON |
| 2 | **Align** every quote to its page: exact, then normalised, then fuzzy, else unmatched. Offsets and word boxes are kept. | Code | Deterministic string alignment |
| 3 | **Merge entities** through defined terms, party names and section numbers. A number veto stops section 3.2 merging with 3.3. Look-alike names become "unclear" links, never merges. | Code | Rule-based record linkage |
| 4 | **Link** with typed edges: mentions, same as, is a, holds office, defined by, refers to, defeats, conditions, overrides, cites. Every edge carries its tier and evidence. | Code, checked against quotes | Typed knowledge graph |
| 5 | **Link the claim**: split into parts, each attached only to entity ids and rule types that exist in the packet. | Code, then Muse Spark constrained to an enum | Entity linking, constrained decoding |
| 6 | **Retrieve two ways in parallel**: a typed path walk and one full read of the packet that cites statement ids. | Code and Muse Spark | Hybrid retrieval with a long-context read |
| 7 | **Compare, then re-read** pairs of statements (agrees, conflicts, qualifies, irrelevant, unsure). A second model re-reads deciding links (a capped number per claim) without seeing the verdict. | Muse Spark, then Muse Spark Open | Pairwise entailment (NLI) |
| 8 | **Decide** with five frozen rules. The weakest link sets the confidence label. | Code | Symbolic, defeasible deontic reasoning |

The five frozen rules: a rule cannot establish a fact about an instance; an exception defeats its rule only when it applies to this case; an extracted override wins, otherwise the later document of the same role, otherwise a declared governance order, otherwise "documents disagree"; time claims compare event dates; and the weakest link sets the label. No rule in code names a document type, a domain, a synonym or a case.

[![ProofGraph pipeline, animated: Muse Spark reads and judges, code builds the graph and decides, Muse Spark Open re-reads deciding links](docs/media/pipeline.gif)](docs/media/pipeline.webm)

*Animated: [full-quality video](docs/media/pipeline.webm), [static image](docs/img/pipeline.png). Each node links to its code in the interactive version: [docs/diagrams/pipeline.html](docs/diagrams/pipeline.html) (download and open).*

The graph is built once per packet and cached on the packet's content hash, so a second claim on the same packet answers in seconds.

**A span-grounded evidence graph, not GraphRAG.** No summaries, no embeddings, no vector store, no graph database. Each packet's graph is one JSON file. More in [docs/evidence-graph.md](docs/evidence-graph.md).

## Meta models: which, where, and for what

| Model | Runs on | Used for |
| --- | --- | --- |
| **Muse Spark** (`muse-spark-1.3`) | Meta Model API | Step 1 reading and gleaning pass; step 5 claim splitting and enum-constrained linking; step 6 full read; step 7 pairwise comparison; transcription of scanned pages with a box per line |
| **Muse Spark Open** (`meta-models/muse-spark-open-1026`) | Baseten (partner inference) | Step 7: a blind second reader of deciding links, capped per claim. It never sees the relation or the verdict. The review page reports how many were re-read and how many it confirmed. |
| **SAM 3.1** | Baseten | Counting items in photos, in the earlier engine path only. **Not used in the graph demo.** |

All graph building, alignment, merging, walking, precedence, dating and the final verdict run on our own compute (a Docker container on Render, or your machine). Every model call goes through one client with a disk cache, a spend cap, and fencing against instructions planted in documents.

![Where each Meta model runs: Muse Spark on the Meta Model API, Muse Spark Open on Baseten, everything else in our container](docs/img/where-it-runs.png)

*Interactive version, with source links per component: [docs/diagrams/where-it-runs.html](docs/diagrams/where-it-runs.html).* Muse Spark Open shares Muse Spark's lineage, so we measure its independence (the agreement table in [results/health.md](results/health.md)) rather than assume it.

*Built for Best Build on Meta Open Weight Models: the second reader is Muse Spark Open on partner-provided inference.*

## Results

All figures come from recorded runs in [`runs/`](runs/), analysed in [`results/run2-analysis.md`](results/run2-analysis.md) and [`results/run2-suite-analysis.md`](results/run2-suite-analysis.md). The table below is copied from those reports; it is not regenerated by a `make` target. Gold labels are read only by the evaluation scripts, never by product code.

**1. Held-out check: 30 ContractNLI pairs not used while building, gold is the published label.** This is the only unbiased number.

| System (n = 30) | Correct | 95% Wilson interval | Wrongly supported |
| --- | --- | --- | --- |
| No graph (flag off) | 15/30 (50%) | 33 to 67% | 2/20 (10%) |
| Per-failure code rules (run 1, ablation) | 9/30 (30%) | 17 to 48% | 0/20 |
| **ProofGraph, iteration 2 (shipped)** | **19/30 (63%)** | **45 to 78%** | **1/20 (5%)** |

- Hand-written rules per failure scored 9 of 30 on unseen cases. A small declared schema and a frozen five-rule core scored 19. Iteration 2 got 10 pairs right that run 1 got wrong, and none the other way: generic structure generalised, tuned rules did not.
- Six of the seven pairs fixed over the no-graph run were "not mentioned" cases, where plain pipelines tend to fill the gap.
- Three pairs got worse (cnli-62, 157, 289), all exceptions that agree with the claim. See Limitations.
- The one wrongly supported answer (cnli-85) read a blank-template statement as supporting "all information shall be expressly identified".

**2. Evaluation suite, 29 cases, labelled *after error analysis*** (used to find failures, so not unbiased): 14/29 correct against 9/29 without the graph. Sources: 8 LegalReasonBench cases, 8 ContractNLI, 3 Tobacco800 scanned pages, 2 Company Documents and 8 multi-document packs. See [Data and licences](#data-and-licences).

**3. The trust tier is calibrated.** Answers decided by statements read straight from the page were right in 15 of 17 suite cases and never wrongly supported a claim. Across 29 graphs and 1,496 statements, 84% were read from the page, 15% were the model's reading, and 0.5% (7) could not be aligned and were marked unclear, so they never decided anything.

**4. Honest abstention.** "Not mentioned" cases were 4 of 4 on the suite.

**5. Nothing is dropped silently.** Rejected list members (165), relations whose names were not in the quote (29) and ambiguous override targets (2) were each rejected and counted. Instructions planted in two packets were kept out of the rules.

One number to read with its cause: the share of cards pinned to a word box on a text page fell from 91% to 79% between suite runs. About 5 of those 12 points are pages that a new text-quality check correctly sent to transcription, where boxes can only be approximate; the rest is fewer cards shown on text pages. The cause is traced in [results/health.md](results/health.md), section 6.

## Recorded runs

The hosted app runs the same code. For anything you cannot rerun without a key, the evidence is in the repo:

| What | Where |
| --- | --- |
| Per-case review output of every suite run (flag off, run 1, run 2) | [`runs/review-off.jsonl`](runs/review-off.jsonl), [`runs/review-on.jsonl`](runs/review-on.jsonl), [`runs/review-on-2.jsonl`](runs/review-on-2.jsonl) |
| The 30-pair held-out check, graph on and off, and the run-1 ablation | [`runs/clean-on.jsonl`](runs/clean-on.jsonl), [`runs/clean-off.jsonl`](runs/clean-off.jsonl), [`runs/clean-on-run1.jsonl`](runs/clean-on-run1.jsonl) |
| Analysis, with the pre-registered criteria for iteration 2 | [`results/run2-analysis.md`](results/run2-analysis.md), [`results/run2-suite-analysis.md`](results/run2-suite-analysis.md), [`results/preregistration-iteration-2.md`](results/preregistration-iteration-2.md) |
| Health lines (quote alignment, rejections, first read against second reader, walk against full read) and the error split (graph missed the evidence, or reasoning misjudged it) | [`results/health.md`](results/health.md), [`results/error-split.md`](results/error-split.md) |
| A live trace of one packet | Open the live URL and choose **See the worked example** |

Some quoted passages are withheld in these files where the source licence is unverified (marked `[withheld: source licence unverified]`); verdicts, statuses and hashes are intact.

## Limitations and next steps

Each known weakness has a traced cause and a planned fix that follows the same rule: no fix may name a document type, a domain, a synonym or a case.

| Limitation | Evidence | Planned fix |
| --- | --- | --- |
| An exception that agrees with the claim is treated as a limit | Held-out 0/7 on exception cases | An applying exception that itself agrees with the claim supports it |
| Overrides across documents rarely decide | Suite 2/7 | Resolve each override to a document or provision through scoped definitions |
| Normative claims backed only by facts (the one suite case wrongly supported, TC17) | "Served from May 7" read as "authorized from May 7" | Claim typing: facts alone never support a normative claim |
| Emails, image pages and table rows not reached | 92% of gold evidence extracted, 73% reached by the walk | "About" edges from each document to its subjects |
| Small samples | n = 29 and n = 30, intervals overlap | A larger held-out slice |

Out of scope, and said so on screen: arithmetic across many figures, law outside the packet (shown as "cited, not in the packet"), and subjective claims.

## Run it

You do not need an account to look: use the [live app](https://proofgraph-orww.onrender.com/) and its worked example. To run the code yourself:

```bash
git clone https://github.com/jhanvi0905/proofgraph.git && cd proofgraph
make setup            # uv sync, Python 3.11
make test             # 1,100+ tests, all offline, no key needed
```

**Offline run, no key, no network** (the earlier deterministic engine on a recorded fixture; prints a JSON verdict):

```bash
uv run python -m proofgraph tests/fixtures/synthetic_pm_packet.json
```

**The full app, with live model calls.** This needs a Meta Model API key:

```bash
cp .env.example .env          # .env is gitignored; never commit a key
# edit .env: set MODEL_API_KEY (Meta Model API) and BASETEN_API_KEY (Muse Spark Open, the second reader)
export $(grep -v '^#' .env | xargs)
PROOFGRAPH_GRAPH=1 PROOFGRAPH_SAMPLES=examples/samples/samples.json uv run uvicorn app.server:app --port 8000
```

Open <http://localhost:8000>; the app starts, and the worked-example packet appears on the entrance screen. Running a packet makes live model calls, so it needs the keys above; the hosted app already has its result cached. `SPEND_LIMIT_USD` in `.env` caps model spend (default 50). Without `BASETEN_API_KEY` the second reader does not run, so supported answers go unchecked by it. Without `MODEL_API_KEY` the app cannot read new documents; the live URL above can.

The reproduction scripts (`scripts/eval_review.py`, `scripts/report_review.py`, `scripts/analyze_run.py`) re-run or re-analyse the evaluation, but the evaluation documents are third-party datasets that we do not redistribute. See below.

## Built during the hackathon, and what it stands on

The build window started 21:30 IST on 26 Oct 2026 (first commit 26 Oct). [`BUILT_DURING_HACKATHON.md`](BUILT_DURING_HACKATHON.md) logs the work by day, and the git history carries dated commits. The evidence graph (`proofgraph/review/graph*.py`, `precedence.py`, the review app and the evaluation scripts) was written in the window.

Not built here, used as named dependencies:

| Dependency | Licence | Used for |
| --- | --- | --- |
| networkx | BSD-3-Clause | The packet graph, typed walks and path enumeration |
| RapidFuzz | MIT | Fuzzy quote alignment and near-miss name detection |
| pdfplumber | MIT | PDF text and word boxes |
| FastAPI, uvicorn, python-multipart | MIT, BSD-3-Clause, Apache-2.0 | The server and uploads |
| pydantic, Pillow, openai SDK | MIT, MIT-CMU, Apache-2.0 | Typed contracts, page images, calling the model endpoints |
| Schibsted Grotesk, Source Serif 4 (Google Fonts) | SIL OFL | Typography |

Full list and attribution in [`NOTICE.md`](NOTICE.md). Left in the tree but **not part of the graph demo**: the SAM 3.1 counting path, the Streamlit front end (`app/streamlit_app.py`) and the freight example in `examples/freight/`.

**Ideas studied, not code copied.** graphify (trust tiers and weakest-link confidence), LangExtract (graded source grounding with offsets), Graphiti (a small declared edge schema, "unsure" allowed), LightRAG (the gleaning recall pass), Microsoft LazyGraphRAG (cheap build, model calls only where a verdict depends on them), KAG (schema-constrained extraction), the deontic-formalisation literature and LegalRuleML (rule-shaped statements), and ContractNLI (the label set). Each was adapted to the one rule here: code decides, and nothing the code cannot verify against a quote is allowed to decide. See [docs/evidence-graph.md](docs/evidence-graph.md).

## Data and licences

Code: MIT ([`LICENSE`](LICENSE)). No API key or secret is committed; `.env` is gitignored and only `.env.example` is tracked.

| Data | Licence | How it is used here |
| --- | --- | --- |
| **ContractNLI** (Koreeda and Manning, Findings of EMNLP 2021) | CC BY 4.0, attribution required, no share-alike. Documents were collected from SEC filings and search results; the dataset page does not address the rights status of the original documents, so we ship none of them. | Held-out check and suite. Published gold labels are used under the same licence. Suite documents are referenced by file name and hash, not redistributed. The hero clip shows one page of one NDA (TC40) with attribution; no other ContractNLI page is shown. |
| **LegalReasonBench** (micro1 public sample) | CC BY 4.0 per the dataset card. | Suite cases. Cite as: LegalReasonBench (micro1), <https://www.micro1.ai/benchmark/legal-reason-bench>. |
| **Tobacco800** (Doermann; YACCLAB-packaged) | **Terms not verified.** | Three suite cases, by pointer only. Quoted passages from these cases are withheld from the recorded runs. |
| **Company Documents** (Kaggle archive) | **Listing, publisher and licence not verified.** | Two suite cases, by pointer only. Quoted passages from these cases are withheld from the recorded runs. We will drop these two cases from any future published result unless the licence is confirmed. |
| NIST Special Database 2 | Forms are synthesised; terms not re-verified here. | Scanned-form tests only. |
| Packets in `examples/` | Fictional, written for ProofGraph, MIT. | The worked example and the offline run. |

Labels and transcriptions derived from a dataset's images or documents fall under that dataset's licence, so the same status applies to them.

*ProofGraph checks a claim against documents. It does not give legal advice.*
