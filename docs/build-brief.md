<!-- Task progress (tick as each lands): [x] A1 [x] A2 [x] N1 [x] N3 -->

# ProofGraph: Final Build Brief

Nov 3, 2026 · @Jhanvi

A memo says one thing; the contracts and bylaws behind it say another. ProofGraph catches that in under a minute and opens the exact clause that decides it, on its page. Value leads every conversation with judges; the method only answers "why should I trust it?" Hard deadline: Thu 5 Nov 2026, 07:30 IST (9:00 PM ET, 4 Nov).

## How it works

Paste a claim and drop in its documents. ProofGraph reads the packet once into a graph of who must, may or must not do what, with every statement pinned to its page. It then checks each part of the claim by walking from the things the claim names to the rules that govern them.

1. **Read.** Each document is read once, before any claim arrives. Every rule is written down with who it binds, whether it is a must, a may or a must-not, what it covers, its date, and its exact quote. Exceptions ("unless...", "provided that...") become their own linked statements.
2. **Connect.** Statements about the same thing join one node, through definitions, party names and section numbers. A person links to her office, an office to its class, and an amendment to the section it changes. Look-alike names never merge.
3. **Ask.** The claim splits into parts, and each part attaches to things that really exist in the graph.
4. **Walk and read.** The graph walks typed paths from those things to the rules that govern them. At the same time, one full read of the packet looks for anything the walk might miss.
5. **Decide.** The model judges two statements at a time. Code decides the answer from the structure, which document takes precedence, and the dates. Every answer shows its proof path, how each link was made, and what kind of reasoning it needed.

### Two real cases

**TC17: two documents, a rule on a class.** Claim: "Connors was continuously authorized to act as Interim CMO from May 7, 2026."

- The resolution says the CEO appointed her on May 7 and the Board ratified it on May 13, "effective as of May 7".
- The bylaws never mention Connors. They do say a Chief Medical Officer is a principal officer (§5.1), that no principal-officer appointment is effective until the Board approves it (§5.2), and that ratification is effective on adoption (§5.9).
- The path runs Connors → CMO (interim) → principal officer → §5.2, then to the resolution's own record of adoption on May 13. Bylaws take precedence over a resolution, so authority runs from May 13, not May 7.
- The CEO's May 7 letter is cited but not in the packet, and the answer says so.

**TC40: one document, a rule with an exception.** Claim: "The Bosch NDA allows the recipient to share confidential information with outside consultants without written authorization."

- §2 forbids disclosure to consultants unless the Disclosing Party authorizes it in writing.
- The claim denies exactly that condition, so the claim is contradicted.
- §5.4 (information "independently developed by... a consultant") and §14 (the parties as "independent contractors") share the claim's words but not its meaning, so they are set aside.

### What the graph holds

| Piece | What it is |
| --- | --- |
| Entity | A person, organisation, office, section, concept or dated event |
| Rule statement | Who it binds, must / may / must-not / is, the action, the value and whether it is stated or left blank, its date, its exact quote |
| Exception | A separate statement linked to the rule it carves out |
| Document | Its role (contract, amendment, bylaws, resolution, memo) and date |
| Claim part | One checkable piece of the claim, attached to its entities |

| Link | Meaning | Made by |
| --- | --- | --- |
| mentions | A statement is about this entity | Code |
| same as | Two names are one thing (a definition, the parties clause, a section number) | Code |
| is a / holds office | Connors holds the CMO office; the CMO is a principal officer | The model lists them, code checks each one against the quote |
| defined by / refers to section | A term's definition; a clause pointing at another section | Code |
| excepts / conditions / carves out | An exception or condition on a rule | The model extracts it, code links it |
| supersedes / precedence | An amendment replaces a section; one document outranks another | Code finds candidates and ranks documents; the model labels the effect |
| cites | A document refers to one that is not in the packet | Code |

### The six answers

| Answer | When |
| --- | --- |
| Supported | Statements match the part, nothing conflicts, no exception applies; more documents agreeing makes it stronger |
| Contradicted | A rule or statement clashes with the part, including a claim that denies an exception's condition |
| Qualified | Support exists, but an exception or condition is attached |
| Not found | The documents discuss the thing but never say this, and the full read found nothing either |
| Unknown | No document mentions the thing at all |
| Documents disagree | Two documents clash and nothing decides which one wins |

### Why people can trust it

- **Every statement opens on its page**, with a tier: read from the page, the model's reading, or unclear. An unclear link never decides an answer, and each answer is only as strong as its weakest link.
- **Two independent routes** to the evidence (the walk and the full read) must agree on what matters. When they don't, the screen says so.
- **Nothing is dropped silently.** Every rejected statement is counted, and "not found" needs both routes to come up empty.
- **The model judges only small, local things**, two statements at a time, which a person can check at a glance. Code does all the combining.
- **Reliability is measured on gold cases**, broken down by tier, not asserted.

## The flow at a glance

&#91;embedded content: ProofGraph flow: built once per packet, run for every claim\]

Only the filled boxes call a Meta model. The walk, the merges, the links and the decision are code, so every step can be replayed and checked.

## Scenarios we cover

A claim is classified by the shape of the proof path that decided it, read off by code. That one tag is shown on screen and used to break down the results. Thirteen scenarios are covered; three are out of scope and say so.

| # | Scenario | Example | Mechanism | Covered |
| --- | --- | --- | --- | --- |
| S1 | Direct statement | Bosch §18: Michigan law governs | One-hop path | Yes |
| S2 | Rule with exception or condition | TC40: consultants need written authorization (§2) | Exception as its own statement; a claim that denies the condition is a conflict | Yes |
| S3 | Hinges on a definition | Bosch §16: "Affiliate" means 51% control | defined-by link | Yes |
| S4 | Rule on a class, claim names an instance | TC17: Connors → CMO → principal officer → §5.2 | is-a and holds-office; a third hop allowed only along class links | Yes |
| S5 | Override or precedence across documents | TC17: §5.9 against the resolution; amendments in memo packs | supersedes plus a role-rank table and dates | Yes |
| S6 | Timing and sequence | TC17 "continuously from May 7"; TC18 "before she began" | effective\_from dates compared by code; "continuously" judged by the model | Mostly |
| S7 | Not mentioned | The governing-law-not-mentioned pack | Walk and full read both empty | Yes |
| S8 | Blank template value | Bosch's empty Period of Confidentiality | value status: blank | Yes |
| S9 | Multi-part claim | Shares with consultants and keeps copies | split.py; the worst part decides | Yes |
| S10 | Evidence cited but not supplied | TC17's CEO letter of May 7 | cites link via referenced\_documents() | Yes |
| S11 | Word-overlap distractor | Bosch §5.4, §14 | Different subject and concept; comparator says irrelevant | Yes |
| S12 | Instruction planted in a page | frt-07, fin-08 | Data marking plus an injection field in extraction | Yes |
| S13 | Scanned page | Tobacco800 cases | Transcription with line boxes; approximate tier | Yes |
| U1 | Arithmetic across many figures | Summing invoice lines; FinDVer | engine/calc.py path, not the graph | Out of scope for the demo |
| U2 | Depends on law outside the packet | 18 U.S.C. §1833(b) in Bosch §5.6 | Shown as a cites link to a law not supplied | Shown, not decided |
| U3 | Subjective claim | "Reasonable care is strong protection" | Ends as cannot tell | Honest, not solved |

## Build tasks by specialist

Thirty-two tasks, grouped by the specialist whose screening shaped them. Each one is pinned by graphify to its file, line and the existing tests that must stay green. Everything sits behind `PROOFGRAPH_GRAPH=1`, and every model call goes through `MuseClient`, which keeps the cache, spend cap and injection fencing. `test_boundaries.py` covers `split`, `check_cards`, `blind_wording` and `run_review`, and must stay green untouched.

### NLP engineer: text into rules and judgments

| # | Change | Where (graphify) | Tech | In → out | Done when | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| N1 | Rule-shaped extraction | new `review/graph_extract.py`, `prompts/assert.md`; calls `clients/muse.py::structured` L303; scans via `scan.py::transcribe` L49 | Muse Spark, JSON schema; one call per document, split by section above 15 pages | text with page tags → header (role, date, parties, defined terms with quotes, vocabulary) plus rules (bearer, deontic type, action, value and its status, all-of / any-of members, exceptions as linked statements, effective\_from, concepts, page, quote, injection quote) | valid JSON after at most one repair; pronouns resolved against defined terms, kept and tagged INFERRED | new `test_graph_extract.py` |
| N2 | Recall pass | same file | Muse Spark | document plus extracted ids → missed obligations, exceptions, definitions | runs once per document | new |
| N3 | Graded quote alignment | `graph_extract.py::align`, reusing `engine/numbers.py::normalise_text` L45, `snap.py::snap` L53, `scan.py::locate` L65 | normalise, exact match, then rapidfuzz `partial_ratio_alignment` | quote → exact / normalised / fuzzy / unmatched, offsets, boxes | unmatched never decides; rejections counted per document | `test_numbers`, `test_snap`, `test_scan`, `test_candidates` unchanged |
| N4 | Comparator | new `review/compare.py` (pattern of `label.py::label_candidates` L49), `prompts/neighbourhood.md` | Muse Spark, low effort | part plus top paths → agrees / conflicts / qualifies / irrelevant; amendment effect replaces / adds / deletes / restates; "unsure" allowed | a claim that denies an exception's condition is labelled conflicts; unknown ids dropped | new `test_compare.py`; `test_label` unchanged |
| N5 | Second-read input | `check.py::check_cards` L72 → `checker.py::blind_wording` L421 | Muse Spark Open | deciding statement with its exception, plus the part → entails / contradicts / not mentioned | the checker still never sees the relation or the verdict | `test_review_check`, `test_boundaries` |

### IR engineer: finding the evidence that matters

| # | Change | Where (graphify) | Tech | In → out | Done when | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| I1 | Claim linking and expansion | new `graph.py::link_parts`; `split.py::split` L44 unchanged | exact match, then Muse Spark with an enum of entity ids and rule types from the packet vocabulary | part → entity ids and rule types | no id or term outside the packet | `test_split` unchanged |
| I2 | Typed path walk | `graph.py::paths` | networkx `all_simple_paths` (cutoff 3) on a typed subgraph view; third hop only along is-a, defined-by or holds-office; hub brake (an entity in over 25% of statements is ranked, not walked through) | entity ids → candidate paths | same order every run | new `test_paths.py` |
| I3 | Path ranking | `graph.py::rank_paths`, new `review/bm25.py` | weakest hop × 0.7 per hop; BM25 in plain Python to break ties | paths → top 5 to 8, at most 30 statements, strongest last | deterministic | new |
| I4 | Full read in parallel | new `review/full_read.py` | Muse Spark over the whole packet (about 25k tokens), citing statement ids | part plus packet → cited ids | agreement flag set; "not found" only when the walk and the read are both empty | new |
| I5 | Keep lexical candidates for flag-off only | `evidence_map.py::build_map` L35, `candidates.py::build_candidates` L211 | none | none | flag-off output byte-identical | `test_candidates`, `test_evidence_map` unchanged |

### ML engineer: entities and measurement

| # | Change | Where (graphify) | Tech | In → out | Done when | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | Build entities | new `review/graph.py::build_entities` | Python | subjects plus header → entities typed person, organisation, office, section, concept or event | every statement points at one entity | new `test_graph.py` |
| M2 | Merge entities | `graph.py::merge` | rules plus networkx `connected_components`; number veto adapted from graphify's `dedup._numeric_tokens_differ` (attributed); rapidfuzz Jaro-Winkler band for near misses | entities → same-as links with rule and quotes; near misses → unclear links | defined terms scoped to their document, linked across only on "as defined in"; no fuzzy merges | new, including §3.2 ≠ §3.3 |
| M3 | Results table and gate | `scripts/report_review.py::main` L322, `wilson` L53 | existing scorer | runs, flag off and on → correct, wrongly supported, gold evidence quoted, valid quotes, fixed and broken case ids, rows per tier | gate decided: ship only if wrongly supported does not rise | `test_report_review` |
| M4 | Error split | same | none | each wrong case → graph miss or reasoning error | every wrong case labelled | new |
| M5 | Three ablations | switches in `graph.py` | none | typed walk against one hop; precedence off; hub brake off → paired fixed / broken counts | case ids listed | new |
| M6 | Health lines | counters from N3, I4, N5 | none | alignment rates, rejections, a 2×2 agreement table for Muse Spark against Muse Spark Open, walk-against-read agreement, reachability at the hop count each gold path needs | printed in the report | new |

### AI engineer: the graph system, decisions and wiring

| # | Change | Where (graphify) | Tech | In → out | Done when | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Setup | `pyproject.toml`, `docs/11-decision-log.md` (D40 FastAPI, D41 networkx and rapidfuzz), `AGENTS.md` (query the code graph before changing a shared model) | `uv add fastapi uvicorn python-multipart networkx rapidfuzz`; `graphify hook install` | none | `uv lock` passes; the code graph rebuilds on commit | none |
| A2 | Endpoint check | `clients/muse.py::structured` L303 | Muse Spark 1.3 | one test call → JSON | 200 and valid JSON | none |
| A3 | Typed links with evidence lists | `graph.py::edges`; `timeline.py::referenced_documents` L102 | networkx `MultiDiGraph`; regex for section references | statements → mentions, defined by, refers to section, is a (members checked against the quote), holds office (interim as a qualifier), excepts / conditions / carves out, cites | every link carries a tier and an evidence list (document, page, box, offsets, alignment) | `test_timeline` unchanged |
| A4 | Supersedes, precedence, dates | `graph.py::amendments`, `precedence`, `resolve_dates` | regex candidates, then section resolution, with the effect from N4; role-rank table; effective\_from anchors ("upon adoption" resolves to the adoption date) | amendment and document nodes → supersedes and precedence links, resolved dates | no override guessed when the role or date is missing | new |
| A5 | Decide | `graph.py::graph_status`, beside `status.py::part_status` L17 and `overall_status` L63 | rules | labels, tiers, precedence, dates and path → status, weakest tier, scenario tag, reason, agreement flag | outcomes map onto today's part statuses | `test_status` unchanged |
| A6 | Store and cache | `graph.py::save` / `load`; `cache.py::cache_key` L36 | networkx `node_link_data` JSON keyed on the packet's content hash; comparator cache keyed on the statement pair; shrink guard | graph → cached file | a rebuild never serves a smaller graph than the last good one | `test_muse` |
| A7 | Wire behind the flag | `run.py::run_review` L88 (build after `_collect` L251), `_run_part` L160, `_assemble` L291; optional `models.py::Review` L173 field using the serializer pattern of `Receipt._omit_unused_evidence` L93; flag helper beside `evidence.py::evidence_map_on` L23 | `PROOFGRAPH_GRAPH=1` | none | golden page byte-identical with the flag off | `test_review_run`, `test_review_models`, `test_viewer_render`, `test_evidence_map_run`, `test_report_review`, `test_boundaries` |
| A8 | Progress events and budgets | `run.py` | events DocRead, PageRead, EntityFound, GraphReady, PartLinked, PathFound, PartDone, AllDone; second reads capped per claim; a part that times out resolves to unclear | graph build and claim run → events | the frontend can show every state | `test_review_run` |
| A9 | Attribution and record | `BUILT_DURING_HACKATHON.md`, `README.md`, a NOTICE line | none | none | libraries named; graphify-derived logic attributed | none |

### Frontend: one server, one page

| # | Change | Where (graphify) | Tech | In → out | Done when | Tests |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Passcode helper | move `streamlit_app.py::passcode_ok` L269 into `app/auth.py` | `hmac.compare_digest`, env `APP_PASSCODE` | passcode → ok or refusal | the old app imports it from there | `test_claim_journey` |
| F2 | Server | new `app/server.py`, replacing `streamlit_app.py::review_events` L2042 | FastAPI: `GET /`; `POST /api/review` (multipart: claim, files, passcode) as a `text/event-stream`; `POST /api/review/{id}/ask` reuses the cached graph; `GET /api/review/{id}` | A8 events → named server-sent events | the stream ends with a review id | new `test_server.py`; `test_app` kept for the old app |
| F3 | Start and live page | new `app/web/index.html`, `app.js`, `app.css` | vanilla JS, `fetch` with a streamed body, `aria-live="polite"` | form → live list of what is read and found | each event updates one line | none |
| F4 | Review page | `render.py::render` L853, `_ledger_body` L822 | HTML, CSS, inline SVG | Review plus graph → underlined claim, proof-path breadcrumb, evidence grid, tier legend, agreement note, "cited, not supplied", red-pencil circle, override arrow, Ask another claim, Download review | golden page unchanged with the flag off | `test_viewer_render`, `test_evidence_map`, `test_evidence_lines` |
| F5 | Design tokens | `app/viewer/viewer.html` styles | Source Serif 4, Atkinson Hyperlegible, 6 colour tokens | none | contrast meets WCAG AA | none |
| F6 | Deploy | new `Dockerfile` (python:3.11-slim, `uv sync`, `uvicorn app.server:app`) | a host with a public URL | env secrets → live URL | one cached and one live packet run on the public URL | smoke test |
| F7 | Judge entrance | `README.md` | none | none | the README points at the new URL; Streamlit stays in the repo | none |

### Gate, freeze and cut lines

- **Gate:** M3 runs before the freeze. If wrongly supported rose, ship with the flag off and show the graph on the demo packets only.
- **Freeze, then the video and submission,** well before the hard deadline of Thu 5 Nov, 07:30 IST.
- **If behind, cut in this order:** N2; I3's decay (keep the plain weakest hop); M5 down to one ablation; F4's grid (keep the breadcrumb and cards); the scan path in the demo.
- **Never cut:** N1, N3, I4, the M3 gate, F6.

## Measurement

One table goes to judges. Its story: wrongly supported answers fall, and the read-from-page tier is almost never wrong. Gate: ship the graph only if wrongly supported does not rise against the flag-off run.

| System (n = 29) | Correct | Wrongly supported | Gold evidence quoted | Valid quotes | Against flag off: fixed / broken |
| --- | --- | --- | --- | --- | --- |
| Flag off | k/29 \[Wilson\] | k/n \[Wilson\] | % | % | — |
| ProofGraph | k/29 \[Wilson\] | k/n \[Wilson\] | % | % | +x / −y, with case ids |
| …read from page | k/n | k/n | % | % |  |
| …unclear, sent to review | k/n | — | — | — |  |

Beside it, in the report:

- **Results by scenario**, with raw counts per case, not percentages.
- **Error split:** each wrong case is either a graph miss or a reasoning error.
- **Three ablations** as paired fixed / broken counts with case ids: the typed walk against one hop, precedence off, and the hub brake off.
- **Health lines:** quote alignment rates, rejected statements, the 2×2 agreement table for Muse Spark against Muse Spark Open, walk-against-read agreement, and reachability at the hop count each gold path needs.

**Cut, and why.** At n = 29 these would be noise:

- Cohen's kappa: too wide an interval, and it misleads on skewed labels.
- Per-label comparator accuracy: each label has only a handful of cases.
- Conformal prediction: the calibration set is too small.
- Reachability at three hops as a headline.

A difference of 1 to 3 cases is noise. It takes about 6 discordant cases, all in one direction, to mean anything.

## Positioning

ProofGraph is claim verification across a multi-document packet, led by contracts, governance documents and memos, and measured on ContractNLI and LegalReasonBench cases. Freight leaves the story and stays only as one pack in the evaluation suite.

|  | Now |
| --- | --- |
| Who it is for | Anyone who must check a claim against the documents behind it: contracts and legal-ops analysts, compliance reviewers, people checking a memo or summary |
| What people see first | The caught mistake: a claim that looked right, and the clause that breaks it, on its page |
| Lead proof | ContractNLI and LegalReasonBench cases, then your contract-plus-memo packets |
| Name of the method, when asked | A span-grounded evidence graph for claim verification. Not GraphRAG: no summaries, no embeddings |
| Why believe it | Every statement opens on its page, every link says how it was made, two routes must agree, and accuracy is measured on gold cases |

### The statements

- **One line:** ProofGraph checks a claim against every document in the packet and shows what each one says, pinned to the page.
- **For a reviewer:** see which clause holds, which one breaks the claim, and which document overrides another, before you sign off.
- **First run:** paste the claim, drop in the documents, and open any statement to see it on its page.

### Meta models, exactly as used

| Model | Job | Where |
| --- | --- | --- |
| Muse Spark (`muse-spark-1.3`) | Reads each document into rules, runs the recall pass, splits and links the claim, does the full read, compares pairs, transcribes scans with a box per line | N1, N2, N4, I1, I4; `scan.py` |
| Muse Spark Open (`meta-models/muse-spark-open-1026`, on Baseten) | Independent second reader of every deciding link (N5) | C5 |
| SAM 3.1 | Counts items in photos, in the engine path only | not in the graph demo |

No model is added to fit the rubric. Muse Spark Open on partner-provided inference qualifies the project for Best Build on Meta Open Weight Models; say so in the submission.

### Stop saying

- Freight-first examples.
- "AI checks AI" as the trust claim.
- Any score or percentage that was not measured.
- "GraphRAG".

## Interface and demo

The screen reads as a reviewer's marked-up working paper, not a dashboard. The proof path is the explanation.

### Stack

| Layer | Choice |
| --- | --- |
| Server | FastAPI + uvicorn (`app/server.py`) |
| Live updates | Server-sent events, one per state change |
| Page | One HTML file, vanilla JS and CSS, no build step |
| Review view | `render.py`, extended |
| Deploy | Dockerfile to a host with a public URL |
| Secrets | `APP_PASSCODE` and API keys as env vars; the spend cap is unchanged |

### What the reader sees at each step

| Event | On screen | Example copy |
| --- | --- | --- |
| Files accepted | Each document with its page count | 2 documents, 5 pages |
| DocRead | Role and date beside each document | Bylaws, as amended through March 12, 2025 |
| PageRead | A quiet list ticks off | Reading the bylaws, page 2 of 3 |
| EntityFound | Things found and how many documents name them | Chief Medical Officer, in 2 documents |
| GraphReady | One receipt line | Read 5 pages: 38 rules about 14 things |
| PartLinked | The claim at the top, each part underlined and marked as checking | Checking 1 part |
| PathFound | The breadcrumb draws | Connors → CMO → principal officer → §5.2 |
| PartDone | Its underline takes its colour and a tick | Contradicted |
| AllDone | The answer, the evidence grid and the page | Authorized from May 13, not May 7 |
| Disagreement | A note when the walk and the full read cite different evidence | The full read also cites §5.7; open it |
| Spend limit, timeout, failure | One plain line saying what stopped and what is missing | Stopped at the spend limit; nothing after page 2 was read |
| Unreadable page | A note on that document | Page 3 has no text layer and was not read |

Progress is announced to screen readers through a polite live region.

### The review screen

```
+----------------------------------------------------------------+
| Connors was continuously authorized to act as Interim CMO      |
| from May 7, 2026.                                              |
| ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ |
| Authorized from May 13, not May 7.                             |
| Connors -> CMO (interim) -> principal officer -> Bylaws 5.2    |
+-----------------------------------------+----------------------+
| What the documents say                  |                      |
|                Resolution   Bylaws      |  page image, white,  |
| authorized     ratified     5.2 needs   |  box drawn, circled  |
| from May 7     May 13,      Board       |                      |
|                "as of       approval;   |                      |
|                May 7"       5.9 on      |                      |
|                             adoption    |                      |
| CEO letter of May 7: cited, not in the packet                  |
+-----------------------------------------+----------------------+
| tick = read from the page   ~ = model's reading   ? = unclear   |
| Ask another claim about this packet [                       ]   |
+----------------------------------------------------------------+
```

- **The grid:** rows are the claim's parts and columns are the documents, so no taxonomy is needed. Each cell is a verbatim quote, and clicking it moves the page pane to its box.
- **Marks:** a conflict is circled, an exception is underlined, an override is an arrow.
- **No network view:** a force-directed graph reads as a hairball and hides the one thing a reviewer needs.

### Visual direction

| Token | Value | Use |
| --- | --- | --- |
| Ledger paper | #EDF1EA | Page background |
| Graphite | #262B2A | Text |
| Ledger rule | #B9C8B5 | Dividers |
| Red pencil | #B42318 | Contradicted; conflict circles |
| Blue pencil | #1D4F91 | Supported; ticks |
| Ochre | #9A6A00 | Qualified; exceptions |

- **Type carries meaning.** Source Serif 4 only for what the documents say; Atkinson Hyperlegible for everything ProofGraph says.
- **One bold element.** The red-pencil circle draws itself once when a contradiction is revealed; reduced motion turns it off.
- **Statuses, not scores.** Buttons say what happens: Check claim, Ask another claim, Download review.

### The three-minute demo

1. **0:00** One question on screen: was Connors authorized as Interim CMO from May 7?
2. **0:10** Drop in the resolution and the bylaws. Pages tick off, and the Chief Medical Officer lights up in both documents.
3. **0:30** The answer: authorized from May 13, not May 7. The path draws from Connors to §5.2, and a date strip shows the six-day gap in red.
4. **0:55** Click any cell: the real page opens at the exact box. Point at the tick legend.
5. **1:15** The recorded Direct Muse answer on the same packet, beside ProofGraph's path. Use the same packet, never a handicapped one.
6. **1:35** TC40, the Bosch NDA: consultants need written authorization. §2 is circled; §5.4 and §14 are set aside.
7. **2:00** A memo pack: an amendment overrides a clause. Ask a second claim; it answers in seconds because the packet was read once.
8. **2:30** The results table: wrongly supported, flag off against on, and the read-from-page tier.
9. **2:50** Why trust it, in one line: two routes agree, every link says how it was made, and Muse Spark Open is the independent second reader.

## Rules and approvals

The plan fits the Meta participant guide, as long as everything not built here is named and Meta's models keep doing all the language understanding.

| Rule | How we meet it | Action |
| --- | --- | --- |
| Use Meta's models | Muse Spark reads, links and compares; Muse Spark Open is the second reader | None |
| Public repository | networkx (BSD-3), rapidfuzz (MIT) and FastAPI are installed dependencies, not vendored code | Keep the repo public |
| Only code you have rights to | Any logic adapted from graphify (Apache-2.0 / MIT) keeps its licence notice; the other projects are borrowed as ideas only | Attribution comment plus a NOTICE line |
| Demo shows only what you built | The graph rules, rule-shaped extraction, typed walk, precedence logic and UI are yours; libraries are named; graphify stays out of the video | Update `BUILT_DURING_HACKATHON.md` (it is behind the code) and the README |
| New work only | The graph module is written in the build window | Date the commits |
| No basic RAG | No embeddings, no vector store, positioned as span-grounded claim verification | None |
| Open-weight bonus | Muse Spark Open via Baseten (`meta-models/muse-spark-open-1026`) | Say it in the submission |
| AGENTS.md: ask before adding a dependency | fastapi, uvicorn, python-multipart, networkx, rapidfuzz | Your yes, then D40 and D41 |
| Claim API credits | Meta and Baseten credits | Claim by Wed 4 Nov, 9:00 PM ET |

## Sources

Opened by the four specialists during research. A "ContraVis" paper cited by an earlier consult could not be found and is not relied on.

- [graphify](https://github.com/Graphify-Labs/graphify)
- [LangExtract](https://github.com/google/langextract)
- [Graphiti](https://github.com/getzep/graphiti)
- [Zep temporal knowledge graph paper](https://arxiv.org/html/2501.13956v1)
- [LazyGraphRAG](https://www.microsoft.com/en-us/research/blog/lazygraphrag-setting-a-new-standard-for-quality-and-cost/)
- [RAG vs GraphRAG, systematic evaluation](https://arxiv.org/html/2502.11371v3)
- [HippoRAG 2](https://arxiv.org/html/2502.14802)
- [LightRAG](https://arxiv.org/abs/2410.05779)
- [KAG](https://github.com/OpenSPG/KAG)
- [Formalising legal text into deontic logic](https://arxiv.org/html/2506.08899v3)
- [ContractNLI](https://stanfordnlp.github.io/contract-nli/)
- [Splink, Fellegi-Sunter model](https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html)
- [Neo4j: GraphRAG for commercial contracts](https://neo4j.com/blog/developer/agentic-graphrag-for-commercial-contracts/)
