# 06 · Repository structure

Repo name: **`proofgraph`** · public · MIT. Create files only where this tree says. If something new seems needed, ask first.

```
proofgraph/
├── AGENTS.md · CLAUDE.md · README.md · BUILT_DURING_HACKATHON.md · LICENSE
├── pyproject.toml · .env.example · .gitignore · Makefile
├── .github/workflows/ci.yml          pytest on push; no API keys; uses fixtures and cache only
├── docs/                             these build docs (01–11)
├── prompts/                          extract.md · objection.md · blind_wording.md · blind_reread.md · baseline_a.md · baseline_b.md
├── proofgraph/
│   ├── __init__.py
│   ├── __main__.py                   CLI: verify --case ID | --claim TEXT --files ...
│   ├── schema.py                     FROZEN contracts (03-architecture §2)
│   ├── config.py                     env vars, model ids, flags (mode, ablations)
│   ├── cache.py                      disk cache for every model call
│   ├── pipeline.py                   verify(case) -> Verdict (03-architecture §3)
│   ├── propose.py                    call 1 (propose) + call 4 (revise with objections)
│   ├── baseline.py                   contenders A and B
│   ├── pdf.py                        pdfplumber words + positions, page images, crops
│   ├── clients/
│   │   ├── muse.py                   Meta Model API: responses, files, structured output, retries
│   │   ├── sam.py                    SAM 3.1 count
│   │   └── checker.py                blind_wording(quote, statement), blind_reread(crop)
│   ├── engine/                       NO imports from propose.py or the proposer in clients/muse.py
│   │   ├── numbers.py                parse numbers, negatives in brackets, scales, normalise text
│   │   ├── ground.py                 quote match, text-in-box, re-read agreement, count agreement, conflicts
│   │   ├── calc.py                   safe calculator, tolerance from claim text, scale rule
│   │   ├── route.py                  dispatch facts and links to the right check
│   │   ├── combine.py                coverage, verdict rules, label, reasons, fetch lines
│   │   └── graph.py                  build proof graph, DOT export, overlay data
│   └── adapters/
│       ├── base.py                   Case model re-export, Adapter protocol, leak-field stripping
│       ├── findver.py · contractnli.py · traps.py · freight.py
├── app/streamlit_app.py              case browser, graph on documents, objection timeline, replay mode
├── scripts/
│   ├── download_data.sh              FinDVer clone; check ContractNLI is present
│   ├── run_eval.py                   --dataset --mode --n --systems --seed → runs/*.jsonl
│   ├── build_traps.py · make_freight_pdfs.py · pick_demo_cases.py
│   └── report.py                     runs/ → results/report.md (the ONLY source of numbers)
├── tests/
│   ├── test_numbers.py · test_calc.py · test_ground.py · test_route.py · test_combine.py
│   ├── test_adapters.py              includes leak-field tests
│   ├── test_boundaries.py            engine never imports the proposer; pipeline never reads Case.answer
│   └── fixtures/                     small hand-written programs + cached model replies
├── examples/freight/bundle_01 … bundle_16/
├── data/        (gitignored)  FinDVer/, contract-nli/
├── cache/       (gitignored)
├── runs/        committed final runs (jsonl)
└── results/     report.md (generated)
```

## Key interfaces
```python
# adapters
class Adapter(Protocol):
    def cases(self, split: str, mode: str, n: int | None, seed: int = 7) -> Iterator[Case]: ...

# pipeline
def verify(case: Case, *, ablate: set[str] = frozenset(), max_rounds: int = 3) -> Verdict: ...

# engine
def ground(fact: Fact, case: Case) -> FactCheck: ...
def check(link: Link, facts: dict[str, FactCheck], program: ClaimProgram, case: Case) -> LinkResult: ...
def combine(program: ClaimProgram, facts, links, claim: str) -> Verdict: ...

# clients
def propose(case: Case) -> ClaimProgram: ...
def revise(case: Case, program: ClaimProgram, objections: list[str]) -> ClaimProgram: ...
def blind_wording(quote: str, statement: str) -> Literal["entails","contradicts","not_mentioned"]: ...
def blind_reread(crop_png: bytes) -> str: ...
def sam_count(image_path: str, noun: str) -> int: ...
```

## Tech stack and why (panel decision D18)
| Choice | Why | Rejected |
|---|---|---|
| **Python 3.11 + uv** | Your strongest language; uv gives a lockfile and a one-command setup | Node/TypeScript (weaker data and PDF libraries for this job) |
| **`openai` SDK** | The Meta Model API and Baseten are both OpenAI-compatible, so one client covers Muse Spark, SAM 3.1 calls and Muse Spark Open | Hand-written HTTP calls everywhere; LangChain wrappers |
| **pydantic v2** | One set of models gives validation and the JSON schema for Muse's structured output | Plain dicts (silent shape errors) |
| **pdfplumber + pypdfium2 + Pillow** | Word positions for the text-in-box check, page images for crops and overlays | OCR engines (Muse and the PDF text layer already cover it) |
| **Disk cache (JSON files)** | Reproducible runs, free replays, no infrastructure | SQLite/Postgres (not needed) |
| **Streamlit + `st.graphviz_chart` + HTML box overlay** | One day of UI work, free deploy on Streamlit Community Cloud from a public repo, Meta's overlay recipe fits directly | FastAPI + React (too slow to build), Gradio (less layout control) |
| **pytest + GitHub Actions** | Engine tests run without network or keys; CI proves the repo works | No CI |
| **reportlab** | Generates the fictional freight PDFs from a template | Hand-made PDFs |
| **Not used** | LangChain, LangGraph, vector databases, Docker, any front-end framework (see `08-guardrails.md`) | |

## Allowed dependencies (ask before adding anything else)
`openai`, `pydantic>=2`, `pdfplumber`, `pypdfium2` (page images), `pillow`, `httpx`, `python-dotenv`, `streamlit`, `pytest`, `reportlab` (freight PDFs only), plus Meta's `meta-sam` parser package if the SAM cookbook requires it.

## Environment (`.env.example`)
```
MODEL_API_KEY=            # Meta Model API
MUSE_MODEL=muse-spark-1.3
SAM_MODEL=sam-3.1
BASETEN_API_KEY=
BASETEN_BASE_URL=https://inference.baseten.co/v1
CHECKER_MODEL=meta-models/muse-spark-open-1026
CHECKER_FALLBACK=muse     # use fresh Muse Spark if Baseten is unavailable
CACHE_DIR=cache
SPEND_LIMIT_USD=10        # per run; run_eval aborts above this estimate
```

## Makefile targets
`setup` · `data` · `test` · `eval` · `report` · `app` · `traps` · `freight-pdfs`

## Tests that must exist before Tier 1
- calculator whitelist rejects `__import__`, attribute access and lambdas
- `( 2,483 )` → −2483; `$183,479` → 183479; `12.5%` → 0.125
- the tolerance rule for exact and hedged literals
- the scale rule: verdict stable under all scales → stands; otherwise `SCALE_AMBIGUOUS`
- each verdict rule with hand-written programs (SUPPORTED, CONTRADICTED, each UNRESOLVED reason)
- the leak fields never appear in any `Case` or in any request payload (by inspecting cached requests)
- boundaries (`test_boundaries.py`)
