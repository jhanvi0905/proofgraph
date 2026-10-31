# ProofGraph: final prioritisation, roadmap, sprint plan and restructure

Panel: Product & Hackathon Strategy Lead (PM), Principal Engineer & Technical Lead (PE), Staff Applied AI Engineer (AI), Senior Software Engineer (SWE), Verification & Reasoning Engineer (VR), plus the human builder (HB). Written Sat 31 Oct 2026, afternoon IST. Read-only pass, $0 spent.

Skills applied: pm-execution:prioritization-frameworks (weighted rubric plus ICE-style confidence and effort, MoSCoW), pm-execution:sprint-plan (capacity, critical path, Sprint 1), pm-execution:pre-mortem (tigers, paper tigers, elephants). Engineering system-design and testing-strategy were applied as methods from memory, not loaded.

Inputs read: product-2.md, data-research.md, engineering-research.md, packs-freight-aipm.md, packs-finance-legal.md, all 28 `pack.json` summaries plus frt-07 and fin-08 in detail, docs/02, 03, 04, 06, 08, 10, 11, the two council memos, docs/sprint/2026-10-31-final.md, the code in proofgraph/, app/, prompts/, tests/, and the diffstats and descriptions of open PRs 27, 28, 29 and 30.

Facts found beyond the brief:
- D18 already names pdfplumber, pypdfium2 and Pillow; `pyproject.toml` lacks pdfplumber.
- PR 29 (boxed bundle) is also open: Pillow, crop plus blind re-read, SAM count in `engine/ground.py`, 302 tests passing.
- Gold keys differ by family: freight and AI PM use `gold.part_status` with free-form values; finance and legal use `gold.part_verdicts`. My quick parse found 36 of 71 parts without a usable status. A normaliser is required.
- Gold has six relations (supports 69, contradicts 79, weakens 38, conditions 25, irrelevant 25, not_enough 8; 244 total).
- docs/06 requires approval for new paths (Decision 4).

---

## 1. Conflict resolution

| # | Tension | Ruling | Reason | Changes the plan? |
|---|---|---|---|---|
| C1 | Freight as primary domain (product-2) versus 30% confidence in line-level scan boxes, thin public freight data, and only a placeholder photo | Freight stays the lead story and lead packet (frt-07). The hero visual is a box on a text-layer PDF, which is exact. Handwriting and SAM are not the hero. Finance and legal packets prove generality. | Theme fit is a Stage 1 gate and the builder's world is freight. frt-07 is three text-layer PDFs, so its boxes do not depend on the weak part of the stack. | Yes. Product-2's storyboard (handwritten "2 short", SAM count of 22) is replaced. |
| C2 | Highlighted document first (human, three panes) versus the older council's evidence tree first | Human decision wins. The tree council ruling is superseded. A shallow tree navigator is Could, only for 3+ parts or 4+ documents. | The human decided after that council. The tree serves the old per-link engine; the new product is per-part relations. | Yes. "Evidence tree" and "computed value in tree" tasks are dropped; the computed value moves onto the evidence card. |
| C3 | Retrieval-free whole-packet reading versus the "basic RAG" ban | No retriever, no embeddings, no top-k. Muse Spark reads every page of the packet, per claim part. A stdlib lexical sweep runs only after the model, as an audit for the absence receipt. | Whole-packet reading is the opposite of basic RAG. Output is typed relations including contradiction and absence, pinned by code, checked blind. Rule B8 forbids an index, not a post-hoc keyword audit. | No (confirms), but rule B8 wording should be clarified (Decision 9). |
| C4 | Evidence hunter agent (engineering 4.3) versus D9, rule B7, and true-claim false-red risk | Hunter is Won't before freeze. The agentic element is the existing D8 objection loop, narrowed: when a card's quote cannot be pinned, or the absence sweep finds an uncited hit, code sends one targeted re-ask (max 2 rounds) with the page text. Could, after Must items. | D9 removed a search agent; reviving it needs the human. The old run rejected 25 of 50 true claims; a hunter looking for problems will raise false reds on frt-03, fin-07 and leg-02. The D8 loop is approved and gives a defensible agentic story. | Yes. Hunter (4 h) is cut; objection re-ask (3 h) is Could. |
| C5 | pdfplumber dependency | Add `pdfplumber` (MIT, brings pdfminer.six and pypdfium2). | D18 already lists it. `pdf.py` reads only the Courier PDFs it writes itself, so no uploaded pack can be read without it. | Yes. It is ticket S1-03 and Decision 1. |
| C6 | Streamlit shell plus HTML component versus a separate frontend (Next.js F4/F5 on the old board) | Streamlit shell plus one self-contained HTML/JS viewer (`st.components.v1.html`, no npm, no CDN). Next.js, FastAPI and Vercel are cut. | Reuses upload, passcode, spend guard and deploy; hover and keys work inside one iframe; the same HTML is the cached fallback. B9 needs an explicit clarification (Decision 8). | Yes. F4, F5, E5 on the old board are cut. |
| C7 | Verdict engine (per-link pass/fail/blocked, SUPPORTED/CONTRADICTED/UNRESOLVED) versus per-part typed relations | New layer `proofgraph/review/` with its own models. `schema.py` stays frozen and the engine stays as is. The engine is reused as a deterministic check for numeric and date cards (calculator, tolerance, scale). Part status is derived by a code rule from accepted cards. | Rebuilding the engine to emit relations would break 270 tests and the boundary guarantees. A bridge keeps both green. | Yes. Section 7 gives the bridge. |
| C8 | Direct Muse comparison framing (D26, PR 28) | Merge PR 28. Run Direct Muse at claim level on the 16 held-out packs, report both systems side by side with n and intervals. Never claim an accuracy win. In the video show at most one labelled case where the direct answer misses a weakener, and say n. | D26 and the honesty rule. On 16 packs no difference will be significant anyway. | Partly. The 30-claim FinDVer scoreboard (V4) is replaced by the pack table. |
| C9 | docs/02 "never cut: both benchmarks against Direct Muse, conflict traps, proof graph, objection loop" and D27 to D29 FinDVer gate versus the new product | Recommend amending docs/02: cut the full FinDVer and ContractNLI runs and conflict traps before freeze; the 28 packs become the evaluation; external slices only after freeze if time and budget remain. | The human asked to keep prior decisions aside. Running FinDVer (~$48) measures the old engine, not the product judges will see. | Yes. Decision 10. |
| C10 | "Demo must run on files uploaded on screen" versus product-2's one-click precomputed examples (job story 1) | The video and the live demo use uploads. The app offers "Download sample packets" (a zip of the three demo packs) so judges can upload them. A precomputed result is shown only as the fallback, with a "replayed from cache, recorded <time>" badge. | Human requirement. D25 also says the app runs a live check and does not play a saved verdict. | Yes. Job story 1 is rewritten. |
| C11 | Scan support "later" (engineering 4.2) versus live uploads that include scans (engineering 9) | Minimal scan path is Must: Muse Spark transcription lines with boxes, fuzzy match, box status `approximate`; blind re-read upgrade to `located` is Should. | 72 of 244 gold relations sit on image-only pages; a demo upload of a scan must not fail. | Yes. |
| C12 | Typed weakener badges (product Must) versus unknown type accuracy (engineering 40% confidence) | Ship typed badges if dev type accuracy given a correct weakens is at least 0.60; otherwise show "Weakens" plus the cue words in bold. | Product-2's own threshold rule, lowered to the engineering realistic range. | Conditional, decided Mon 12:00. |
| C13 | Six gold relations versus three card relations plus statuses | `conditions` displays as Weakens with type condition; `irrelevant` is a greyed "Set aside" lane (Should); `not_enough` feeds the part status Not found or Can't tell. | Keeps the UI simple and still scores every gold label. | Yes. Scorer mapping in section 6. |
| C14 | SAM 3.1 as a hero (product-2) versus one optional placeholder photo (frt-04) | SAM is Could. It enters the demo only if probe P4 passes on the builder's own pallet photos. | Honest Meta breadth beats a staged miscount. | Yes. |
| C15 | Old 31 Oct board (`ship-export-this-week` lead, FinDVer scoreboard, bundle) | Superseded once approved; its done items stay. | One board. | Yes. |
| C16 | Model boxes on digital PDFs versus snapping | Never draw a model box on a text-layer page. | Exact and free. | Confirms. |
| C17 | Checker vocabulary (entails, contradicts, not_mentioned) versus weakens cards | Signature unchanged (A3). Code adjudicates: supports agrees on `entails`, contradicts on `contradicts`, weakens is consistent on anything but `entails`. | No rule change needed. | No. |

Findings that change the plan: C1, C2, C4 to C11, C13 to C15. The most important single change is C7: the product becomes a new review layer over the old engine, not a rewrite of it.

---

## 2. Prioritised backlog

### Method
Weighted rubric tied to the judging lines. Each item gets 0 to 3 on Impact (I, weight 30), Meta tooling (M, 25), Demo (D, 25), Technical depth (T, 20). Value = (30I + 25M + 25D + 20T) / 3, so the maximum is 100. Confidence (C) is 0.3 to 1.0 and stands for technical risk. Score = Value × C / Hours. Must items that unblock everything (ingest, contract) are Must regardless of score. Hours are builder-attention hours for review and integration with an AI agent doing the typing; agent wall time is roughly double.

### Gate: probes before big commitments (Sat evening, total under $1)

| Probe | What | Spend | Decision rule |
|---|---|---|---|
| P1 | Muse Spark box versus gold box on 1 text-layer page (fin-07 p1) and 3 scan pages (frt-03 POD, fin-02 scan p1, leg-01 p2), about 20 quoted lines. Send exactly the PNG we display. | ~$0.10 | Grid padding: if text-layer comparison shows a constant offset, fix the mapping before anything else. Scans: centre-in-box at least 70% → scan cards can reach `located`, frt-03 stays a demo pack. 40 to 70% → scan boxes ship as `approximate` (dotted), frt-03 stays but the video does not zoom on the scan box. Under 40% → scan cards show page plus quote with no box, frt-03 is replaced by fin-07 as the true-claim demo. |
| P2 | Muse Spark Open on Baseten with one image crop (frt-03 handwritten time) | ~$0.02 | Works → blind re-read of scan crops runs on Spark Open (open-weight bonus story). Fails or rejects images → re-read uses a fresh Muse Spark restricted call flagged `checker=fallback`; Spark Open stays the text blind checker only. |
| P3 | Whole-packet relation pass, per part, on frt-07 and fin-08 with a draft `relate.md`. Record tokens, wall time, and whether the "No TONU shall be paid if" clause and the 10-K/A restated figure come back as contradicts. | ~$0.40 | Per-part wall time at most 40 s and cost at most $0.15 per claim → live demo on screen. 40 to 90 s → live with per-part streaming, video cut at the wait. Over 90 s → reasoning effort lowered to `low`, re-probe; if still over, the video uses a replayed run with a badge. If neither deciding clause is found after one prompt revision by Sun 14:00, switch the lead packet to fin-08 or leg-06 (domain trigger, Decision 11). |
| P4 | SAM 3.1 and Muse counts on 3 photos of pallets or cartons taken by the human | ~$0.10 | SAM exact on at least 2 of 3 and at least as good as Muse → SAM count card (E15) moves to Should and frt-04 can use a real photo. Otherwise SAM is cut from the demo and named honestly in the README as tested and dropped. If no photos by Sun 18:00, P4 is skipped and SAM is cut. |

### Backlog table

| ID | Item | I | M | D | T | Value | C | Hrs | Score | MoSCoW | Owner |
|---|---|---|---|---|---|---|---|---|---|---|---|
| G0 | Merge PR 30, 28, 27, 29 to main, green | 1 | 1 | 0 | 2 | 32 | 1.0 | 0.5 | 64 | Must | HB, PE |
| G1 | Probes P1 to P3 | 2 | 3 | 2 | 2 | 78 | 0.9 | 2.5 | 28 | Must | AI |
| G2 | Probe P4 (needs photos) | 0 | 3 | 2 | 1 | 49 | 0.6 | 1 | 29 | Could | AI, HB |
| E1 | Ingest: pdfplumber, page classify, PNG render, words on the 0 to 1000 grid | 3 | 1 | 3 | 2 | 78 | 0.9 | 3 | 23 | Must | SWE |
| E2 | Review JSON contract and models | 2 | 0 | 2 | 2 | 50 | 1.0 | 1.5 | 33 | Must | PE |
| E3 | Quote snapping, exact then difflib, one rectangle per line | 3 | 1 | 3 | 3 | 85 | 0.9 | 3 | 26 | Must | VR |
| E4 | Per-part typed relation pass (Muse Spark, whole packet, datamarked docs) | 3 | 3 | 3 | 3 | 100 | 0.7 | 4 | 18 | Must | AI |
| E5 | Span-anchored claim split | 2 | 2 | 3 | 2 | 75 | 0.85 | 2 | 32 | Must | AI |
| E6 | Part status and overall status rule (code) | 2 | 0 | 2 | 2 | 50 | 1.0 | 1 | 50 | Must | VR |
| E7 | Scan path: Muse transcription lines plus boxes, fuzzy match, `approximate` | 2 | 3 | 2 | 2 | 75 | 0.6 | 3 | 15 | Must | AI |
| E8 | Blind check per card (Spark Open, quote plus part) and adjudication | 2 | 3 | 1 | 3 | 72 | 0.8 | 2 | 29 | Must | VR |
| E9 | Calculator bridge for numeric and date cards (reuse calc.py with PR 30) | 2 | 0 | 2 | 3 | 57 | 0.8 | 2 | 23 | Must | VR |
| E10 | Absence receipt (lexical sweep, pages read, unread pages) | 3 | 0 | 2 | 3 | 67 | 0.8 | 2.5 | 21 | Must | VR |
| E11 | Injection banner: datamark docs, flag instruction-like text as a card | 2 | 0 | 2 | 2 | 50 | 0.9 | 1 | 45 | Should | AI |
| E12 | Per-part parallel calls, streaming chips | 1 | 0 | 3 | 1 | 42 | 0.8 | 2 | 17 | Should | SWE |
| E13 | Blind re-read of scan crops (`located` upgrade) | 1 | 3 | 1 | 2 | 57 | 0.6 | 1.5 | 23 | Should | AI |
| E14 | Supersession: doc dates and "amends" field, "controls" marker | 2 | 0 | 2 | 3 | 57 | 0.6 | 2 | 17 | Should | VR |
| E15 | SAM count card on a photo | 0 | 3 | 2 | 1 | 49 | 0.5 | 2.5 | 10 | Could (Should if P4 passes) | AI |
| E16 | Objection re-ask for unpinned quotes and uncited sweep hits (D8, max 2 rounds) | 1 | 2 | 1 | 3 | 55 | 0.6 | 3 | 11 | Could | AI |
| E17 | Evidence hunter with tools | 1 | 2 | 1 | 3 | 55 | 0.4 | 4 | 6 | Won't | |
| E18 | Files API upload of originals for layout pages | 0 | 2 | 0 | 1 | 23 | 0.8 | 1 | 18 | Should | AI |
| F1 | Viewer S1: static three panes from JSON, one box | 3 | 1 | 3 | 1 | 72 | 0.9 | 4 | 16 | Must | SWE |
| F2 | Viewer S2: linked highlight both ways, keyboard | 2 | 0 | 3 | 1 | 52 | 0.85 | 2.5 | 18 | Must | SWE |
| F3 | Viewer S3: states (checking, unreadable, not found, can't tell, error, cap, checker unavailable) | 3 | 0 | 2 | 1 | 53 | 0.9 | 2 | 24 | Must | SWE |
| F4 | Upload screen: per-file ingest status, thumbnails, limits | 2 | 0 | 2 | 1 | 43 | 0.9 | 1.5 | 26 | Must | SWE |
| F5 | Viewer S4: relation filters, accept and reject, set-aside lane | 2 | 0 | 2 | 0 | 37 | 0.9 | 2 | 17 | Should | SWE |
| F6 | Static HTML export and cached-run replay with badge | 2 | 0 | 2 | 1 | 43 | 0.9 | 1 | 39 | Must | SWE |
| F7 | Deploy on Streamlit Community Cloud, private, secrets, passcode | 2 | 0 | 3 | 0 | 45 | 0.8 | 1 | 36 | Must | SWE, HB |
| F8 | Tree navigator | 0 | 0 | 1 | 0 | 8 | 0.9 | 1.5 | 5 | Could | |
| F9 | Printable export view | 1 | 0 | 1 | 0 | 18 | 0.9 | 1.5 | 11 | Could | |
| F10 | Direct Muse panel beside the review | 1 | 1 | 1 | 1 | 33 | 0.8 | 1 | 26 | Could | SWE |
| F11 | Retire old replay screen and its tests | 0 | 0 | 0 | 1 | 7 | 0.9 | 1.5 | 4 | Could (after freeze is fine) | SWE |
| V1 | Pack loader, gold normaliser (quote_pdf, part status map, per-line boxes), leak test | 2 | 0 | 0 | 3 | 40 | 0.9 | 2 | 18 | Must | VR |
| V2 | Scorer: relations, part status, box metrics, Wilson intervals | 2 | 0 | 1 | 3 | 48 | 0.9 | 2.5 | 17 | Must | VR |
| V3 | Dev runs and prompt iteration (2 to 3 rounds) | 3 | 2 | 1 | 3 | 85 | 0.8 | 3 | 23 | Must | AI |
| V4 | Held-out run once, `results/report.md` | 3 | 1 | 1 | 3 | 77 | 0.9 | 1 | 69 | Must | AI, VR |
| V5 | Direct Muse on held-out packs, claim level | 1 | 1 | 1 | 2 | 38 | 0.9 | 0.5 | 68 | Should | AI |
| V6 | Human review of demo-pack gold and spot check of held-out gold | 2 | 0 | 1 | 2 | 40 | 1.0 | 2 | 20 | Must | HB |
| V7 | FinDVer mixed slice, ContractNLI slice | 1 | 0 | 0 | 2 | 23 | 0.6 | 3 | 5 | Won't before freeze | |
| V8 | Kaggle scan sets download | 0 | 0 | 0 | 1 | 7 | 0.5 | 1 | 3 | Won't | |
| S1 | README rewrite with honest scope and generated numbers | 3 | 2 | 1 | 1 | 65 | 1.0 | 2 | 33 | Must | PM |
| S2 | BUILT_DURING_HACKATHON entries | 1 | 0 | 0 | 0 | 10 | 1.0 | 0.5 | 20 | Must | PM |
| S3 | Video script, record, edit | 3 | 3 | 3 | 1 | 92 | 0.8 | 5 | 15 | Must | HB, PM |
| S4 | Repo public, tag, submission form, X post | 2 | 0 | 2 | 0 | 37 | 1.0 | 1 | 37 | Must | HB |
| S5 | Q&A sheet | 1 | 1 | 1 | 1 | 33 | 1.0 | 0.5 | 66 | Should | PM |
| S6 | docs/02, 03, 06, 08, 11 amendments after the human's decisions | 1 | 0 | 0 | 1 | 17 | 1.0 | 1 | 17 | Must | PM, PE |

### Cut line for the Mon 2 Nov freeze

Above the line (committed, about 52 builder hours of item time, of which roughly half is agent typing the human reviews): G0, G1, E1 to E10, F1 to F4, F6, F7, V1 to V4, V6, S1, S2, S6. Should items in this order if time remains Monday: E11, V5, E13, F5, E12, E14, E18. Below the line: E15 (unless P4 passes), E16, F8 to F11, V7, V8, E17. Video (S3) and submission (S4) are after freeze and are not features.

Kill rule: any Should item still unfinished Mon 2 Nov 20:00 IST is reverted from its branch, not merged half done.

---

## 3. Roadmap

### Now / next / later

| Horizon | Outcome | What ships |
|---|---|---|
| Now (to Wed 4 Nov) | A judge uploads a packet and a claim and, within about a minute, sees each claim part's status and the clauses that contradict or weaken it, boxed on the page, with a blind second check and an honest measured table | Section 2 above the cut line, three demo packs, README, video |
| Next (1 to 3 months) | Claims and audit staff use it weekly on real packets | Tree navigator, export, objection re-ask, supersession precedence, SAM counts, external slices (ContractNLI, FinDVer mixed) |
| Later | Checks become a record and a reward | Self-hosted open-weight mode, audit trail across shipments, evidence hunter once false-red rate on true claims is measured |

### Capacity
One builder, about 29 focused hours before freeze (Sat 5, Sun 12, Mon 12), 15% held back for merges and surprises, so 25 planned hours. Up to three agent sessions run in parallel on disjoint files: Lane A engine (`proofgraph/review/`, `prompts/`), Lane B viewer (`app/viewer/`, `app/streamlit_app.py`), Lane C eval (`scripts/`, `tests/fixtures/packs/`). The builder's hours go to reviewing diffs, running the app, and merging.

### Day by day

**Sat 31 Oct, 15:00 to 23:00 IST (5 builder hours). Goal: unblock and measure.**

| Task | Owner | Depends on | Parallel lane | Hrs |
|---|---|---|---|---|
| Answer Decisions 1 to 6 | HB | none | | 0.5 |
| G0 merge PRs 30, 28, 27, 29 | HB, PE | Decision 5 | | 0.5 |
| G1 probes P1 to P3 (scripts in scratchpad, results to `docs/council/2026-10-31-probes.md`) | AI | G0, keys | A | 1 |
| S1-03 ingest with pdfplumber | SWE | Decision 1 | A | 1.5 |
| S1-04 review contract and fixture JSON | PE | none | C | 0.5 |
| S1-05 viewer S1 on the fixture | SWE | S1-04 | B | 1 |
| Kaggle: not needed (Decision 7) | HB | | | 0 |

Exit (yes/no): main is green with PRs 28 to 30 merged; the probe memo states P1 to P3 numbers and the rulings they trigger; the viewer shows the fixture JSON with one box in three panes locally.

**Sun 1 Nov, 08:00 to 22:00 IST (12 builder hours). Goal: walking skeleton by 12:00, then the full Must engine on dev packs.**

| Task | Owner | Depends on | Lane | Hrs |
|---|---|---|---|---|
| S1-06 snapping, S1-07 relation call, S1-08 skeleton wiring | VR, AI, SWE | S1-03 to S1-05 | A, B | 3 |
| Walking skeleton checkpoint, 12:00 | HB | above | | 0.5 |
| S1-09 pack loader and gold normaliser | VR | none | C | 1 |
| S1-10 claim split, S1-11 status rule | AI, VR | S1-07 | A | 1.5 |
| S1-12 scorer v0 | VR | S1-09 | C | 1.5 |
| S1-13 scan path | AI | S1-03, P1 result | A | 1.5 |
| S1-14 viewer S2 linking and keyboard | SWE | S1-05 | B | 1 |
| S1-15 per-part parallel and chips | SWE | S1-10 | B | 0.5 |
| S1-16 blind card check, S1-17 calculator bridge | VR | S1-07 | A | 1 |
| Human: review gold of the three demo packs (V6 part 1), photograph pallets if SAM is wanted | HB | none | | 1 (inside the 12) |
| Probe P4 if photos exist | AI | photos | A | 0.5 |

Exit: uploading frt-07's three PDFs and its claim on the local app produces three part chips, a red P2 card boxed on "No TONU shall be paid if", and the box lands on that line; the scorer prints a dev table for at least 8 of the 12 dev packs.

**Mon 2 Nov, 08:00 to 23:00 IST (12 builder hours). Goal: every Must done, deployed, frozen.**

| Task | Owner | Depends on | Lane | Hrs |
|---|---|---|---|---|
| E10 absence receipt | VR | S1-10 | A | 1.5 |
| F3 states, F4 upload status, F6 export and replay badge | SWE | S1-14 | B | 3 |
| V3 dev runs, 2 to 3 prompt rounds; decide typed badges (C12) at 12:00 | AI | S1-12 | C | 2 |
| F7 deploy private on Streamlit Cloud, secrets, passcode, spend cap $15 | SWE, HB | F3 | B | 1 |
| Should items in order E11, V5, E13, F5, E12, E14 | all | Musts | A, B | 3 |
| S6 doc amendments, S2 BUILT log | PM | decisions | C | 1 |
| Freeze: tag `v0.9-freeze`, prompts versioned | HB | all | | 0.5 |

Exit: the deployed private URL runs frt-07 live from uploads; `pytest -q` green on main; all Must tickets merged; prompt versions recorded.

**Tue 3 Nov (8 hours, no features). Goal: numbers and video.**
- V4 held-out run once, `results/report.md` generated (AI, VR, 1 h). Exit: the report file exists and came from `runs/`.
- V6 part 2, human spot check of 5 held-out packs' gold before the run (HB, 1 h, must happen before V4).
- S1 README (PM, 2 h), S5 Q&A (PM, 0.5 h).
- S3 record video: script (PM), screen capture and voice (HB), 4 h. Exit: a 3:00 or shorter cut uploaded unlisted.

**Wed 4 Nov (buffer). Goal: submitted by 22:00 IST.**
- Fix only bugs found in the video take. HB makes repo public after a secrets scan, switches the app to public with passcode kept for live calls, tags `v1.0-submission`, fills the form, posts on X, claims credits before 9 PM ET (07:30 IST Thu, so do it Wed). Exit: submission confirmation received.

Human-only tasks across the week: answer decisions (Sat), merge PRs (daily), review demo-pack gold (Sun), photograph pallets (Sun, optional), spot-check held-out gold (Tue before the run), record voice and screen (Tue), make repo public, submit, X post (Wed). Kaggle sign-in: not required (Decision 7).

---

## 4. Sprint 1 (Sat evening to Sun night)

Sprint goal: an uploaded packet and a pasted claim produce per-part statuses and boxed evidence cards in three panes, measured on the dev packs.

Capacity: 17 builder hours, 3 agent lanes. Committed S1-01 to S1-15 (about 31 ticket hours, about 15 builder review hours). Stretch S1-16 to S1-18.

| # | Title | User value | Acceptance criteria | Files likely touched | Tests (red, then green) | Est | Risk |
|---|---|---|---|---|---|---|---|
| S1-01 | Merge PRs 30, 28, 27, 29 | Correct percent tolerance and a Direct Muse baseline on main | `git switch main && uv run pytest -q` passes; four PRs closed as merged | none (merge) | existing suite | 0.5 | Low. Merge order 30, 27, 28, 29; rebase 29 if `uv.lock` conflicts |
| S1-02 | Probes P1 to P3 | Decides scan box display, checker path, live versus replay | Memo with numbers and the triggered rulings; total ledger under $1 | scratch scripts only; `docs/council/2026-10-31-probes.md` | none (probe) | 2 | Medium. API keys and Baseten image input |
| S1-03 | Real PDF ingest | Any text-layer or scan PDF, PNG or JPG can be read and displayed | `ingest(paths)` returns pages with kind `text_layer`, `image_only` or `image`, a PNG per page (144 dpi, long side up to 1600 px, rotation and EXIF applied), and words with 0 to 1000 boxes; `(cid:` garbage over 10% marks image_only; locked or corrupt file returns a per-file error, never raises | `pyproject.toml`, `uv.lock`, `proofgraph/review/ingest.py`, `tests/test_ingest.py` | Red: frt-07 RateCon page 1 has words and each gold quote's first word box lies inside the gold bbox; frt-03 POD scan is image_only; a truncated PDF gives a file error; a JPG with EXIF rotation renders upright | 3 | Medium. Rotation and CropBox edge cases |
| S1-04 | Review JSON contract | One shape for backend, viewer, export, cache, scorer | Pydantic models for Review, Part, Card, Box, Doc, Page, Receipt (section 5); `model_json_schema()` committed as fixture; a hand-written frt-07 review JSON validates | `proofgraph/review/models.py`, `tests/fixtures/review_frt07.json`, `tests/test_review_models.py` | Red: invalid status rejected; box outside 0 to 1000 rejected; card without quote rejected | 1.5 | Low |
| S1-05 | Viewer S1 | Judges see claim parts, cards and the page with a box | `app/viewer/viewer.html` renders the fixture: left parts with chips, centre cards grouped Contradicts, Weakens, Supports, right page PNG with percentage-positioned box; clicking a card shows its page and box | `app/viewer/viewer.html`, `app/viewer/render.py`, `tests/test_viewer_render.py` | Red: `render(review)` returns HTML containing one element per card with `data-card-id` and a box div with `left:` equal to x_min/10 percent; no external URL in the HTML | 4 | Medium. Iframe height and image embedding size (base64 PNG; cap 1600 px) |
| S1-06 | Quote snapping | Boxes are exact on text-layer pages | `snap(quote, page_words)` returns line rectangles via normalised token match, then difflib window at 0.9; table quotes match with pipes removed; status `pinned` or `unpinned` | `proofgraph/review/snap.py`, `tests/test_snap.py` | Red: on all text-layer gold relations of the 12 dev packs, at least 95% snap with union IoU at least 0.7 (fixture subset committed: frt-07, fin-08 PDFs are synthetic, so they can be test fixtures); the fin-02 par value row is a documented known miss | 3 | Medium. Multi-column order, hyphenation |
| S1-07 | Relation call for one part | The core Muse Spark read of the whole packet | `relate(part, pages)` sends datamarked page-tagged text, asks for `{relation, weakener_type, quote, doc, page, why}`, structured output through `MuseClient.structured` and the cache; leak test proves `pack.json` text never enters the request | `prompts/relate.md`, `proofgraph/review/relate.py`, `tests/test_relate.py` | Red with a fake transport: request body contains every page tag, contains no gold note sentinel, response with an unknown relation is repaired once then fails as `EXTRACTION_FAILED` | 2 | Medium. Prompt quality, settled by S1-18 |
| S1-08 | Walking skeleton | Upload one PDF, paste a claim, see three panes with one real box | Streamlit route: upload, ingest, whole claim as one part, relate, snap, render viewer; passcode and spend cap enforced as today | `app/streamlit_app.py` (new entry function), `proofgraph/review/run.py`, `tests/test_review_run.py` | Red: offline run of frt-07 with a recorded relate reply produces a review JSON with at least one pinned contradicts card on RateCon p1 | 2 | Medium. Streamlit rerun behaviour |
| S1-09 | Pack loader and gold normaliser | Scoring is possible and gold stays sealed | `load_pack(dir)` returns uploads and claim only; `load_gold(dir)` (used only by scripts) returns normalised gold: relation, part status mapped to supported, weakened, contradicted, not_found, cannot_tell; `quote_pdf` with pipes removed; boxes split per line where a quote wraps | `proofgraph/review/packs.py`, `scripts/eval_packs.py` (stub), `tests/test_packs_gold.py` | Red: all 28 packs load; every part has a normalised status; a boundary test asserts `proofgraph/review/run.py` never imports `load_gold` | 2 | Medium. 36 parts lack a status key; derive from relations by the guideline rule, flag for human review |
| S1-10 | Claim split | Left pane shows the parts | `split(claim)` returns parts with exact character spans; code checks substrings and that every number in the claim is covered; one repair; cached by claim hash | `prompts/split.md`, `proofgraph/review/split.py`, `tests/test_split.py` | Red with fake transport: a part whose span is not a substring is rejected; an uncovered "$250" triggers repair | 2 | Low |
| S1-11 | Status rule | Chips and banner are deterministic | Part status from accepted cards: any pinned or located contradicts → Contradicted; else any weakens → Weakened; else any supports → Supported; else Not found if receipt complete, Can't tell otherwise; overall is the worst part by the product-2 order | `proofgraph/review/status.py`, `tests/test_status.py` | Red: table-driven cases including an unpinned contradicts card that must not turn a part red | 1 | Low |
| S1-12 | Scorer v0 | Honest numbers from day one | Reads `runs/packs-*.jsonl` and gold; prints relation P and R by relation (card matches gold when same part, same mapped relation, same page, and word overlap at least 0.5), part status accuracy, box Hit@0.5 and centre-in-box by file kind, pin rate, Wilson 95% intervals | `scripts/report_packs.py`, `tests/test_report_packs.py` | Red: synthetic run equal to gold scores 1.0; a run with a shifted box fails Hit@0.5 | 2.5 | Low |
| S1-13 | Scan path | Scans and photos get evidence too | Image pages go to Muse Spark transcription (`prompts/transcribe.md`) returning lines with boxes; quotes fuzzy-match lines at 0.85; card box status `approximate`; transcribed text feeds the relation call | `proofgraph/review/scan.py`, `prompts/transcribe.md`, `tests/test_scan.py` | Red with a recorded transcription of frt-03 POD: the "09:18" quote maps to a box whose centre lies in the gold box | 3 | High. Depends on P1 |
| S1-14 | Viewer S2 | Fast, linked review | Hover or focus a card flashes its box and its part; click a box focuses its card; J and K next and previous card; [ and ] next contradicts; Enter scrolls page to box; visible focus rings; reduced motion respected | `app/viewer/viewer.html`, `tests/test_viewer_render.py` | Red: rendered HTML has a keydown handler and `aria-live`; a JS smoke test in the browser pane is manual (documented) | 2.5 | Low |
| S1-15 | Per-part parallel and chips | Screen is alive within seconds | Parts appear grey "Checking" after the split; each part's call runs in a thread pool; native Streamlit chips update per part; the viewer swaps in when all parts finish | `app/streamlit_app.py`, `proofgraph/review/run.py` | Red: `run_review` yields events in completion order with a fake slow transport | 2 | Medium. Worker threads must not call Streamlit |
| S1-16 | Blind card check | Every card is checked by a model that did not write it | For each card call `blind_wording(quote, part_text)`; adjudication per C17; card gets `check: agrees, disagrees, unavailable`; disagreement shows on the card, never hides it | `proofgraph/review/check.py`, `tests/test_review_check.py` | Red: checker transport receives only the two strings; checker error yields `unavailable` and no status change | 2 | Low |
| S1-17 | Calculator bridge | Numbers on cards are computed, not asserted | For cards where the part has a number and the quote has a number, build a one-link `ClaimProgram` and run `check_compute`; show "Computed X; the claim says Y" on the card and mark `computed: true` | `proofgraph/review/numeric.py`, `tests/test_review_numeric.py` | Red: fin-08 restated $52.1m versus claimed $58.4m fails; 38.33 versus 38.39 percent (PR 30 case) fails; an exact match passes | 2 | Medium. Choosing operands needs the model to name them; fall back to no computation |
| S1-18 | Dev run 1 | First real numbers and a prompt fix | Run the 12 dev packs live, cost printed before the run and under $5; scorer table committed under `runs/` as dev; one prompt revision logged with version | `runs/packs-dev-*.jsonl`, `prompts/relate.md` | none beyond scorer | 2 | Medium. Spend and latency |

---

## 5. Frontend plan

**Architecture decision.** Streamlit is the shell for passcode, claim box, uploader, progress and deploy. The review itself is one self-contained file, `app/viewer/viewer.html`, with inline CSS and vanilla JS, filled by `render.py` with the review JSON and base64 page PNGs, and mounted with `st.components.v1.html(height=900, scrolling=False)`. Reasons: no npm or build step, works on Streamlit Community Cloud, hover and keyboard linking work because all three panes share one iframe, one coordinate system for PDFs, scans and photos (percentages of the displayed image), and the same file saved to disk is the offline cached demo. pdf.js, react-pdf-highlighter, streamlit-pdf-viewer and Next.js are rejected (effort, no cross-pane hover, or a second deploy).

**Components.** TopBar (claim, AI-drafted tag, banner naming the driving part, counts, filters, Export). PartList, left 22% (status chip, counts, text; tree toggle Could). CardList, centre 33% (groups Contradicts, Weakens, Supports, Set aside; card = relation stripe and word, weakener badge, quote with cue words bold, part, doc and page, why, computed line, check badge, box status, Accept and Reject). AbsenceRow (pages read, terms, unread pages). PageView, right 45% (image, numbered boxes, doc tabs, thumbnails). Banners (injection, unreadable, cap, checker unavailable, replayed).

**State model (JS, single object).** `{review, filters:{relations:Set, part:null|id, doc:null|id}, focus:{cardId, partId}, page:{docId, page}, decisions:{cardId: "accepted"|"rejected"}}`. Every change goes through one `setState(patch)` that re-renders only affected regions. Decisions are kept in `localStorage` keyed by review hash (wrapped in try/catch) and included in export; they do not change the backend status (overrides are displayed with a pen icon).

**Data contract (backend to viewer, also the cache and run record).**
```json
{
  "version": "review-1",
  "review_id": "sha256 of claim + file hashes + prompt versions",
  "claim": {"text": "...", "origin": "pasted"},
  "status": "contradicted",
  "driver_part": "P2",
  "run": {"mode": "live|replayed", "recorded_at": "2026-11-01T11:02:00+05:30",
          "models": {"proposer": "muse-spark-1.3", "checker": "meta-models/muse-spark-open-1026"},
          "cost_usd": 0.12, "flags": ["checker=fallback"]},
  "docs": [{"id": "d1", "name": "RateCon_Load_88412.pdf", "pages": [
            {"n": 1, "kind": "text_layer|image_only|image", "png": "pages/d1-1.png",
             "w": 1224, "h": 1584, "readable": true, "note": null}]}],
  "parts": [{"id": "P2", "text": "Tallgrass is owed a TONU fee", "span": [0, 31],
             "status": "contradicted|weakened|supported|not_found|cannot_tell|checking|error",
             "reason": null, "card_ids": ["c3", "c4"],
             "receipt": {"pages_read": 3, "unread": [], "terms": ["TONU", "cancel"], "uncited_hits": []}}],
  "cards": [{"id": "c3", "part": "P2", "relation": "contradicts|weakens|supports|set_aside",
             "weakener_type": "exception|condition|qualifier|scope|time|magnitude|definition|weak_source|null",
             "quote": "No TONU shall be paid if ...", "cue_words": ["No", "if", "before"],
             "doc": "d1", "page": 1,
             "boxes": [[112, 398, 848, 415], [112, 415, 600, 433]],
             "box_status": "pinned|located|approximate|unpinned",
             "why": "Cancelled 16:20 the day before, which is before 18:00.",
             "computed": {"ok": false, "text": "Computed $150.00; the claim says $250."},
             "check": "agrees|disagrees|unavailable|not_run",
             "controls": true, "superseded_by": null}],
  "banners": [{"kind": "injection|unreadable|cap|checker_unavailable", "text": "...", "card": "c9"}]
}
```
Boxes are always 0 to 1000 over the displayed PNG. One rectangle per line. The viewer never needs the source of a box beyond `box_status`.

**Slices.**
| Slice | Content | Hours | Done when |
|---|---|---|---|
| S1 | Static three panes from fixture JSON, click card shows page and box | 4 | frt-07 fixture renders correctly at 1280 and 1440 px |
| S2 | Linked highlight both ways, keyboard map, numbered boxes, focus rings, ARIA live | 2.5 | All keys work in the browser pane on the deployed app |
| S3 | States: checking shimmer, unreadable, not found with receipt, can't tell with reason, error with retry, cap, checker unavailable, injection banner, replay badge | 2 | Each state has a fixture and a render test |
| S4 | Filters, accept and reject, set-aside lane, export as static HTML | 2 | Export opens offline in a browser and shows the same boxes |

**Linked highlighting and keys.** Cards and boxes share `data-card-id`. Card hover or focus lights its boxes for 600 ms (outline only under reduced motion), switches page, scrolls the box into view and lights the part. Box click focuses its card. Keys: J/K, [ and ], Enter, A/R, 1 to 9 (part), F (filter), ? (sheet); ignored inside inputs.

**Error and streaming states.** Streamlit, outside the iframe, shows the step list and native per-part chips as parts finish; the viewer mounts once at the end to avoid flicker. A failed part says "We could not check this part. Retry." and never becomes Supported. The cap stops the run and marks results incomplete.

**Deployment for judges.** Streamlit Community Cloud from the private repo, made public at submit. Secrets hold both keys and a passcode. `SPEND_LIMIT_USD` about 15 in the app. Upload cap 25 MB per file, 60 pages per packet for the demo. A "Download sample packets" link serves a zip of the three demo packs from `examples/demo-packs/`.

**Cached demo fallback.** Every review is cached by `review_id`. Re-uploading the same files and claim replays instantly with the badge "Replayed from cache, recorded <time>, model <id>". The three demo reviews are also saved as static HTML in `examples/demo-packs/<id>/review.html`, which opens with no network. If the API is down on the day, the video uses a replayed run with the badge visible.

**Design tokens.**
| Token | Value |
|---|---|
| `--contradicts` | #D55E00, solid border, ✕ |
| `--weakens` | #E69F00, dashed border, ! |
| `--supports` | #0072B2, thin solid, ✓ |
| `--notfound` | #7A7A7A, hatched, ? |
| `--canttell` | grey outline, dotted, ~ |
| `--bg` | #FAF9F6 off-white; card #FFFFFF; text #1F2328 |
| Fonts | system UI for chrome; Georgia or a serif stack for quotes; ui-monospace for numbers |
| Box styles | pinned solid 2 px, located dashed 2 px, approximate dotted 2 px, all 15% fill of the relation colour |
| Spacing | 4 px base; card padding 12 px; pane gutters 16 px |
No percentages of confidence, no sparkles, verbatim marker on every quote.

---

## 6. Evaluation and data plan

**Split (fixed now, before any run).**
- Dev, 12 packs (tune here, demo packs live here): frt-01, frt-03, frt-05, frt-07, aipm-02, aipm-05, fin-02, fin-04, fin-05, fin-08, leg-03, leg-06. 29 parts, 106 relations (81 on text-layer pages, 25 on images).
- Held-out, 16 packs (run once): frt-02, frt-04, frt-06, frt-08, aipm-01, aipm-03, aipm-04, aipm-06, fin-01, fin-03, fin-06, fin-07, leg-01, leg-02, leg-04, leg-05. 42 parts, 138 relations (91 text-layer, 47 image). Gold overall: contradicted 7, partly supported 6, supported 2, cannot tell 1.
- Why: every domain on both sides; two true claims held out to measure false reds; demo packs in dev so demo polish cannot inflate reported numbers.

**Three demo packs.** frt-07 (lead: freight, three text-layer PDFs, exception clause plus timestamp, injection surfaced), fin-08 (generality: restatement supersedes the release, weak-source fact sheet), frt-03 (true claim, handwritten scan, no cry wolf). If P1 fails, fin-07 replaces frt-03. Alternate lead if P3 fails: leg-06. frt-07 and fin-08 are fully synthetic, so they can be committed to the public repo. fin-01 to fin-03 carry FinDVer excerpts with licence marked UNVERIFIED; FinDVer is MIT, so they are likely fine, but keep them out of the repo until checked.

**Gold fixes (S1-09, plus human review).**
1. Add `quote_pdf` per relation: the quote with markdown pipes removed and whitespace collapsed (fixes 22 of the 23 pipe quotes). Mark fin-02's "Common stock ($ 0.001 par value…" row as `known_mismatch` and exclude it from snap scoring, counted and reported.
2. Per-line boxes: for text-layer pages regenerate gold boxes from pdfplumber words of `quote_pdf` (one per line), keep the authored union box as `bbox_union`. For scans keep the union box plus `quad`; score scans with union IoU and centre-in-box only.
3. Part status: map to five values. supported; weakened (supported_with_qualifier, supported_with_scope_caveat, supported_headline_weakened, supported_weakly, conditional); contradicted; not_found (not_enough with an absence note); cannot_tell (conditional_not_met_in_packet, judgment cases). Parts with no status get one derived by the guideline rule and are flagged `derived` for the human to confirm.
4. Relation map for scoring: contradicts → contradicts; weakens and conditions → weakens; supports → supports (with weak_source kept as a badge); irrelevant → must not appear as a contradicts or supports card (distractor false positive); not_enough → part-level only.
5. Human checks: all relations of the three demo packs (about 25), plus 5 random held-out packs, before the held-out run. Record in `docs/council/gold-review.md`.

**Metrics and pass thresholds.**
| Metric | Definition | Target to say it in the video |
|---|---|---|
| Contradicts precision and recall | Card matches gold on part, mapped relation, page, word overlap at least 0.5 | Precision at least 0.75 |
| Weakens recall | Same match | Reported, no target |
| Weakener type accuracy | Among matched weakens | At least 0.60 to keep typed badges |
| Part status accuracy | Five-way | Reported |
| True-claim false red | Parts gold supported that we mark contradicted | At most 1 of the supported parts in held-out |
| Distractor false positive | Gold irrelevant spans shown as supports or contradicts | Reported |
| Text-layer box pass | Union IoU at least 0.7 and word F1 at least 0.95 | At least 95% of pinned cards, else it is a bug |
| Scan box pass | Union IoU at least 0.5, or centre-in-box with word recall at least 0.8 | Report rate with n; no claim below 70% |
| Pin rate by status | pinned, located, approximate, unpinned | Always shown beside box accuracy |
| Cost and time per claim | Ledger and wall time | Reported |
Every rate carries n and a Wilson 95% interval. At n of about 40 contradicts relations, 0.75 has an interval of roughly 0.60 to 0.86; say that.

**Not tuning on held-out.** Held-out ids are a frozen list in `scripts/eval_packs.py`; the held-out run refuses unless prompt hashes match tag `v0.9-freeze`, and a rerun needs a logged `--rerun-reason`. Only the scorer reads gold.

**Wording.** "Measured on 16 held-out packets we built and labelled ourselves during the hackathon (synthetic documents, three with real SEC excerpts). Labels are ours, not independent. Numbers come from `results/report.md`." Direct Muse row: "Same model asked directly for a claim-level verdict." Never "beats", "catches all", or a number not in the report.

**External slices** only Wed morning if $10 and 3 hours remain: a stratified FinDVer mixed testmini slice and a 30-pair ContractNLI slice, reported by name as externally labelled.

**May claim.** The product reads every page, splits the claim, pins quotes exactly on text-layer PDFs, checks each card blind with Muse Spark Open, computes numbers in code, names unread pages, and these are the measured rates on our own held-out set. **May not claim.** Better accuracy than Direct Muse, generalisation to real freight paperwork, legal or financial advice, independence of the second model on weights alone, any FinDVer result from the old engine as a product result, or that scan boxes are exact.

---

## 7. Restructure and reuse plan

### Target pipeline
```
uploads + claim
  → ingest (pdfplumber: page kind, PNG, words on grid)               review/ingest.py
  → scan transcription for image pages (Muse Spark, lines + boxes)    review/scan.py
  → claim split (Muse Spark, span-anchored, code-validated)           review/split.py
  → per-part typed relation pass, parallel (Muse Spark, whole packet) review/relate.py
  → grounding and snapping (text layer exact; scans fuzzy)            review/snap.py
  → blind second check per card (Muse Spark Open, quote + part)      review/check.py → clients/checker.py
  → deterministic numbers and dates (engine/calc.py via a 1-link program) review/numeric.py
  → absence receipt (lexical sweep, pages read)                       review/absence.py
  → optional: crop re-read (located), SAM count, objection re-ask     review/scan.py, clients/sam.py
  → status rule (code)                                                review/status.py
  → review JSON (cache key = review_id)                               review/models.py, review/run.py
  → viewer                                                            app/viewer/
```

### Module map

| Current | Verdict | Reason and use |
|---|---|---|
| `proofgraph/schema.py` | KEEP frozen | Engine and FinDVer path still use it. New models live in `review/models.py`, so rule A6 holds |
| `engine/numbers.py`, `engine/calc.py` (PR 30) | KEEP | Split coverage, absence terms; numeric bridge runs `check_compute` with claim-text tolerance |
| `engine/route.py`, `combine.py`, `ground.py` (PR 29) | KEEP, indirect | `run_program` on a one-link program gives a COMPUTED pass or fail for a card, never the product verdict |
| `proofgraph/engine/graph.py` | RETIRE from UI | DOT graph is out of the product; code stays because `ClaimRun.graph` and tests use it |
| `proofgraph/engine/spans.py` | KEEP (legacy) | Offline span proposer for old tests; not in the new path |
| `proofgraph/pdf.py` | REPLACE internals, keep API | Reimplement `read_page_words` and `map_text_span` on pdfplumber so PR 29's text-in-box and `test_text_span.py` keep working; Courier parser deleted once tests pass on pdfplumber |
| `proofgraph/propose.py`, `prompts/extract.md` | KEEP (legacy) | The old claim program path and its tests; not called by the review path |
| `proofgraph/pipeline.py` | KEEP (legacy) | `run_claim` stays for CLI and old packets; new orchestration is `review/run.py` |
| `proofgraph/clients/muse.py` | KEEP | `structured`, files, retries, spend guard, cache are reused by every new call |
| `proofgraph/clients/checker.py` | KEEP | `blind_wording` for card checks, `blind_reread` for scan crops; signatures unchanged |
| `proofgraph/clients/sam.py` | KEEP, Could | Used only if P4 passes |
| `proofgraph/cache.py`, `spend.py`, `config.py` | KEEP | Unchanged; the review JSON is cached alongside model calls |
| `proofgraph/adapters/base.py` | ADAPT | Add pack gold keys (`gold`, `note`, `gold_rationale`, `expected_user_value`) to the leak list |
| `proofgraph/adapters/findver.py` | KEEP, dormant | Only for the optional external slice |
| `proofgraph/direct.py` (PR 28) | ADAPT | Add a packet mode: claim plus page-tagged text → supported, contradicted, cannot_tell with reason; used by V5 |
| `proofgraph/__main__.py` | ADAPT | Add `review --claim … --files …` writing review JSON |
| `app/streamlit_app.py` | ADAPT, then RETIRE parts | Keep passcode, spend refusal, stage messages, uploader. Add the review entry. Retire the replay screen (`_review_groups`, `render_marked_pdf`, `courier_pdf`, `_show_upload`) in a late, separate PR |
| `examples/packets/`, `examples/claim-packets/` | KEEP as legacy fixtures | Old tests read them |
| New `examples/demo-packs/` | ADD | frt-07, fin-08, frt-03 uploads and claims, no gold in the folder (gold in `tests/fixtures/packs/` read only by scripts) |

**Tests.** All 270 current tests (302 after PR 29) remain valid because no legacy module changes behaviour. Watch points: `test_text_span.py` and `test_bundle.py` after the pdf.py reimplementation (word box values may differ slightly from Courier AFM; adjust only tolerances, never assertions about grounded versus ungrounded); `test_app.py` and `test_claim_journey.py` until the retire PR, which deletes them together with the code they test. `test_boundaries.py` gains two assertions: `proofgraph/review/**` does not import `review.packs.load_gold`, and `review/check.py` passes only two strings to the checker.

New tests: `test_ingest.py`, `test_review_models.py`, `test_snap.py`, `test_relate.py`, `test_split.py`, `test_status.py`, `test_scan.py`, `test_review_check.py`, `test_review_numeric.py`, `test_absence.py`, `test_review_run.py`, `test_viewer_render.py`, `test_packs_gold.py`, `test_report_packs.py`. Fixtures: the synthetic PDFs of frt-07 and fin-08, a recorded relate reply and transcription per pack used in tests.

### Bridging the old design and the new product
- Per-link verdict versus per-part relations: the part status comes from cards by the rule in S1-11. The old engine contributes only the `computed` line on numeric cards. A failed COMPUTED check turns a supports card into contradicts only if the operands were pinned; otherwise it is shown as "could not compute".
- Labels COMPUTED, CHECKED, ASSUMED: shown as small card evidence tags (computed in code, checked blind, model only), not as a claim-level label.
- UNRESOLVED: maps to part status Can't tell or Not found depending on the absence receipt.
- Reason codes: keep internal for logs; the viewer shows plain sentences.

### Branch and PR sequence (each small, from `origin/main`, CI green before the next)
1. `fix/percent-tolerance` (PR 30), `docs/drop-pick-demo-cases` (PR 27), `feat/direct-muse-baseline` (PR 28), `feat/boxed-bundle` (PR 29): merge as they are.
2. `docs/review-architecture`: docs/02, 03 (new section "Review layer"), 06, 08, 11 amendments after decisions.
3. `feat/pdf-ingest`: pdfplumber, `review/ingest.py`, pdf.py reimplementation.
4. `feat/review-contract`: `review/models.py`, fixture, `review/status.py`.
5. `feat/viewer-s1`: viewer and render (can run in parallel with 3 and 4, disjoint files).
6. `feat/review-snap` then `feat/review-relate` then `feat/review-skeleton` (walking skeleton wired into the app).
7. `eval/pack-gold` (loader, normaliser, scorer) in parallel with 6.
8. `feat/review-split`, `feat/review-scan`, `feat/review-check`, `feat/review-numeric`, `feat/review-absence`.
9. `feat/viewer-s2-s3`, `feat/viewer-export`.
10. `eval/dev-runs` (runs and prompt versions), later `eval/heldout-report`.
11. After freeze or last: `chore/retire-replay-screen`.
Commit types per AGENTS.md, imperative subjects, body says why, no co-author lines (user memory).

### Guardrails and scope to amend (all listed as decisions in section 9)
docs/02 never-cut list and tiers (Decision 10); docs/02 out-of-scope front end and rule B9 (Decision 8); rule A5 vocabulary (Decision 13); rule B8 lexical sweep (Decision 9); rules C12 and C13 extended to pack gold, read only by `scripts/eval_packs.py` and `scripts/report_packs.py`; rule C14 dev split (Decision 14); docs/06 paths (Decision 4); D14 and D26 to D29 superseded by the section 6 wording; D25 labelled replay (Decision 17).

---

## 8. Demo and submission plan

**Demo packets.** frt-07 (lead), fin-08 (generality), frt-03 or fin-07 (true claim). All uploaded on screen.

**Storyboard (3:00).**
| Time | Screen | Voice-over | Rubric |
|---|---|---|---|
| 0:00 to 0:15 | Builder title card, a pile of rate confirmations and emails | "I worked in freight. AI now drafts the claims. Someone still signs them." | Impact, theme |
| 0:15 to 0:35 | Paste the frt-07 claim (tagged AI-drafted), drag three PDFs; thumbnails and "3 pages, text layer" appear; three parts turn grey | "Here is a claim and the three files behind it, uploaded now." | Demo |
| 0:35 to 1:10 | P1 blue, P2 and P3 red. Click P2's card: the rate confirmation jumps to "No TONU shall be paid if … before 18:00", boxed. Linked card shows the email time 16:20. Computed line on P3: "$150.00 flat; the claim says $250." | "The fee only applies after 18:00 the day before. The shipper cancelled at 16:20. And the agreed fee is $150, not $250." | Impact, depth |
| 1:10 to 1:25 | Injection banner on the dispute letter, boxed | "One file tells the AI to mark this supported. ProofGraph shows the instruction and ignores it." | Depth |
| 1:25 to 1:45 | Hover a card: "Second check agrees", model name Muse Spark Open | "Every card is re-read blind by Meta's open-weight Muse Spark Open, which sees only the quote and the part." | Meta, open-weight bonus |
| 1:45 to 2:10 | fin-08 upload: "Net income $58.4m" red against the 10-K/A restatement; the fact sheet card tagged weak source | "Same engine on a company filing: a later restatement controls." | Impact breadth |
| 2:10 to 2:30 | frt-03: handwritten POD time boxed (dashed, approximate), claim green | "And when the claim is true, it says so. Scans get a dashed box, because we only call a box exact when the PDF text proves it." | Meta (vision), honesty |
| 2:30 to 2:50 | `results/report.md` table, held-out n, intervals, one miss named | "Measured on 16 packets we held out and labelled ourselves. Here is what it still misses." | Depth, honesty |
| 2:50 to 3:00 | Repo, "Built 26 Oct to 4 Nov", models list | "Built this week on Muse Spark and Muse Spark Open." | |

**Meta tooling story.** Muse Spark: splits the claim, transcribes scans with line boxes on its 0 to 1000 grid, reads the whole packet per part and returns typed relations with quotes. Muse Spark Open on Baseten: blind check of every card and blind re-read of scan crops (if P2 passes). SAM 3.1: only if P4 passes, counts pallets in the photo with masks. Files API: originals uploaded for layout-heavy pages (Should).

**"Basic RAG" answer.** "There is no retriever, no index and no chat. The model reads every page for each part of the claim and must return a relation type, including contradiction and absence. Code pins every quote to the page, computes the numbers, and a second Meta model re-checks each card without seeing the first one's reasoning. If nothing is found, it tells you which pages it read."

**X post (draft).** "AI drafts claims. People sign them. I built ProofGraph for the Meta AI hackathon: upload the paperwork, paste the claim, and see the exact clause that contradicts it, boxed on the page. Muse Spark reads every page, Muse Spark Open checks each finding blind, code does the maths. [video] [repo]"

**README structure.** Purpose; GIF; Try it (URL, passcode, sample zip); How it works (who decides what); Meta models; Results (generated block, section 6 wording); Limits; Run locally; Data and licences; Built during the hackathon; what changed from the original plan.

**BUILT_DURING_HACKATHON entries.** Sat 31: pivot to the three-pane review, 28 packs, probe results, PRs 27 to 30. Sun 1: ingest, snapping, relation pass, skeleton time. Mon 2: blind check, absence receipt, viewer, deploy, freeze tag. Tue 3: held-out run, report, video. Cuts with reasons: hunter, tree, FinDVer and ContractNLI runs, traps, Next.js, SAM if cut, Kaggle.

**Video production.** PM writes the script Mon night; HB records Tue (1080p, 125% zoom, light theme, scene by scene, voice after), edits to 3:00, uploads unlisted; PM checks every number against `results/report.md`.

**Q&A prep.** Packets real? Synthetic documents in real formats plus three real SEC excerpts, labelled by us. Accuracy? Read the held-out table, name the weakest relation, give n. Better than Muse directly? "Both are side by side; on 16 packets we cannot claim a difference; we add location, blind check and computed numbers." Wrong answers? Every card shows quote, page and check; unpinned findings are not evidence. Scan boxes? Dashed means approximate; solid means the PDF text proves it. Agentic? Fixed workflow, parallel per-part readers, code-bounded re-ask. Prior work? Commit history and the BUILT log from 26 Oct 21:30 IST.

---

## 9. Risks and decisions

### Pre-mortem: the demo failed. Why?

| # | Tiger | Likelihood | Impact | Mitigation | Kill criterion |
|---|---|---|---|---|---|
| 1 | Relation pass misses the deciding clause (weakeners share few words with the claim) | Medium | High | Per-part calls, cue-word list and 2 to 3 examples per type in `relate.md`, absence sweep surfaces uncited hits | If dev contradicts recall is under 0.5 after two prompt rounds (Mon 12:00), show weakens as "Possible issue" and lead with frt-07 only |
| 2 | Walking skeleton slips past Sun 12:00 | Medium | High | Lanes on disjoint files; skeleton uses one part and text-layer only | If no end-to-end box by Sun 16:00, cut scan path to page-plus-quote and cut E14, E12 |
| 3 | Scan boxes land on the wrong line | High | Medium | Dashed and dotted styles; text-layer hero | P1 under 40%: no boxes on scans |
| 4 | Live latency over 90 s in the app | Medium | Medium | Parallel parts, reasoning effort low, cache, streaming chips | Over 90 s on Mon: video uses replay badge |
| 5 | False reds on true claims | Medium | High | Blind check disagreement shown; status ignores unpinned cards; held-out measures it | Any true demo claim turns red on Mon dev run: swap to fin-07 and investigate |
| 6 | pdfplumber reimplementation breaks PR 29 tests | Low | Medium | Keep the API, adjust tolerances only | If not green in 1 h, keep the Courier reader beside pdfplumber and switch only the review path |
| 7 | Gold labels contain errors that look like system misses | Medium | Medium | Human review of demo and 5 held-out packs; `derived` flags | Any gold relation the human disputes is fixed before the held-out run, never after |
| 8 | Spend runs away in judge sessions | Low | High | Existing total cap, passcode, cache | Cap hit: app shows partial results; no raise without the human |
| 9 | Streamlit Cloud deploy fails with pdfplumber or memory limits | Low | High | Deploy Mon morning, not night; page cap 60 | If not live by Mon 16:00, deploy on Hugging Face Spaces (Streamlit SDK) |
| 10 | Scope creep from Should items into Monday night | High | Medium | Kill rule at 20:00 | Revert, do not merge half-done work |

Paper tigers: the RAG perception (answered by design); freight looking niche (finance packet on screen). Elephants: the packs were written and labelled by AI agents, so the eval is a construction test, not field evidence, and the README must say so; the old engine's FinDVer work mostly leaves the video; the product is built in about 30 hours, so polish is limited.

### Decisions for the human (recommended answer first)

1. Add `pdfplumber` (MIT; brings pdfminer.six, pypdfium2). Yes; D18 already names it.
2. Probe spend P1 to P4, up to $1. Yes.
3. Dev runs (12 packs, up to 3 rounds), held-out run once (16 packs), Direct Muse on held-out: about $15 at $0.15 to $0.40 per claim; approve up to $25, each run under the $50 cap. Yes.
4. New paths: `proofgraph/review/`, `app/viewer/`, `prompts/split.md`, `relate.md`, `transcribe.md`, `scripts/eval_packs.py`, `scripts/report_packs.py`, `examples/demo-packs/`, `tests/fixtures/packs/`. Yes.
5. Merge PRs 30, 27, 28, 29 in that order. Yes.
6. Supersede the evidence-tree ruling and the 31 Oct board. Yes; tree stays Could.
7. Kaggle sign-in and downloads. No before freeze; scan realism only, no labels.
8. Amend B9 and docs/02 for one vanilla HTML/JS viewer; cut Next.js, FastAPI, Vercel. Yes.
9. Amend B8 to allow the post-hoc lexical sweep. Yes.
10. Amend docs/02 never-cut list and D27 to D29: drop full FinDVer, ContractNLI and traps before freeze; packs are the evaluation; small external slices Wed only if $10 and time remain. Yes.
11. Domain switch: lead stays frt-07 unless P3 plus one prompt revision misses its deciding clause by Sun 14:00, then fin-08 or leg-06. Yes.
12. Evidence hunter. No (D9, B7 stand); D8-style re-ask is Could.
13. New vocabulary under A5 (card relations, nine weakener types, part and box statuses), recorded in docs/03. Yes.
14. Freeze the section 6 split now. Yes.
15. Gold fixes, plus your review of demo-pack gold Sunday (1 h) and 5 held-out packs Tuesday (1 h). Yes.
16. Pallet photos for P4. Only if you have 30 minutes Sunday; else SAM is cut and named.
17. Labelled cached replay as fallback (amends D25). Yes.
18. Commit only synthetic demo packs to the public repo; FinDVer-excerpt packs wait for a licence check. Yes.
19. Direct Muse: side-by-side table, no win claim, at most one labelled video example. Yes.
20. App cap $15, passcode kept after going public. Yes.

Unsure items and the cheap way to find out: Muse box padding (P1, 10 minutes); Spark Open image input (P2, one call); real latency (P3); whether pdfplumber word boxes match the pack authors' `pdftotext -bbox` boxes closely enough for the 0.7 IoU threshold (run S1-06's test on frt-07 and fin-08 first, about 15 minutes); whether Streamlit Cloud handles base64 page images for a 20-page packet inside the component size limit (render fin-01's 8 pages locally and measure the HTML size; keep under about 8 MB by capping PNG width at 1200 px if needed).
