# 11 · Decision log

Decisions already made by the panel and the builder. **Don't reopen them** without new evidence; record any change as a new entry.

| # | Decision | Why | Rejected alternatives |
|---|---|---|---|
| D1 | **"Check every link, trust the weakest one"** replaces "code decides" | Executed checks only cover numbers and dates. Real enterprise claims are mostly wording. Trust comes from independence, grounding and published error rates, not from "it's code." | "Code decides everything" (too narrow, overclaims) |
| D2 | Three verdicts + three labels (COMPUTED, CHECKED, ASSUMED) | Reviewers need to know how strongly each verdict is proven | A single confidence score (opaque) |
| D3 | **Deterministic workflow with one evaluator–optimizer loop**; control flow in code | The model must never choose whether it gets checked; verdicts must be replayable | A free agent choosing its own tools and steps |
| D4 | **No agent framework** | Frameworks add layers, not capability; judges score impact, Meta use, depth and demo | LangChain/LangGraph orchestration |
| D5 | **Perception grounding is the Meta story** ("citations you can check, down to the pixel") | It's Muse Spark's distinctive strength and attacks the brief's exact problem | Using Muse only as a JSON extractor (basic integration) |
| D6 | SAM 3.1 counts goods in photos; it does not locate text | Muse grounds text natively; counting is SAM's unique strength and gives a truly different mechanism | SAM outlining handwriting |
| D7 | Muse Spark Open is the blind checker; independence comes from what it sees, not from its weights | It shares lineage with Muse Spark, so we don't call it an independent witness. Open weights let a company host the checker itself. | Calling it an independent witness; dropping it |
| D8 | Objection loop: at most 3 rounds, triggered only by specific reason codes | Self-correction without wandering or runaway cost | An unbounded agent loop |
| D9 | The tool-using search "investigator" is removed | Whole documents fit in Muse's 1M context; search tools add steps and failure points | The search/read tool agent |
| D10 | Voice (Muse Voice Transcribe) is cut | Saves about a day; it doesn't strengthen the core claim | A voice-evidence demo |
| D11 | **FinDVer stays**, in two modes (passage given: 250+250; whole filing: 50) | It's the only outside-graded test of numerical checks; "passage given" is a mode, not a fixed property | Dropping FinDVer for ContractNLI only |
| D12 | **ContractNLI added** as the second benchmark | Its three labels match the three verdicts; it tests wording links and evidence finding | SciFact/FEVER (not document-based contracts) |
| D13 | Conflict traps reduced to 50 conflict cases | ContractNLI's NotMentioned already covers missing evidence | Building missing-evidence traps too |
| D14 | Freight is a designed demonstration (16 bundles), never presented as a benchmark | Honest labelling; it's built by us | Presenting freight accuracy as a benchmark |
| D15 | Muse Code "verify before acting" gate is a stretch goal | It's the cleanest route to the agentic bonus, but not core | Making it core scope |
| D16 | UI: Streamlit + Graphviz + Meta's HTML overlay recipe; replay mode by default | Demo quality per hour; live mode costs money | A custom React app |
| D17 | Rejected Meta uses: Muse Image/Wonder (decoration), Glimmer (needs our own hardware; roadmap), RL post-training (roadmap) | They don't strengthen the core claim within 9 days | Using every model for coverage's sake |
| D18 | **Tech stack:** Python 3.11 + uv, `openai` SDK, pydantic v2, pdfplumber/pypdfium2/Pillow, disk cache, Streamlit + Graphviz + HTML overlay, pytest + GitHub Actions | Fastest path for one engineer; every Meta endpoint is OpenAI-compatible; free public deploy; reproducible without infrastructure (details in `06-repo-structure.md`) | FastAPI + React, LangChain, SQLite/Postgres, Docker |
| D19 | **Licence: MIT** for the code; datasets are not committed (downloaded into gitignored `data/`) and are attributed in the README | Simple, permissive, standard for hackathon and open-source repos; compatible with FinDVer (MIT) and ContractNLI (CC BY 4.0, attribution only) | Apache 2.0 (fine, but longer than needed), GPL (restrictive for anyone reusing it) |
| D20 | Operative build start is **21:30 IST, Monday 26 October 2026**, confirmed by the human. | The human confirmed the build window opened at 9:30 PM IST on 26 Oct 2026. `docs/07-build-plan.md` and `docs/08-guardrails.md` use that start. | Starting the log from a Tuesday 09:30 IST clock |
| D21 | Resequence the remaining days around a Wednesday live text slice. Files API, SAM, the `extract.md` line, demo framing, and the Muse Code gate stay on the days in `07-build-plan.md`. | Day 1 has the engine and no scored model call. Starting multimodal work or an agent loop before one verified program hides whether Muse's program checks. | Rebuilding as the workshop tool-picking agent. Pulling the Muse Code gate forward. Editing `prompts/extract.md` before the first live program. |
| D22 | The sprint manager freezes a running product by the end of Tue 3 Nov so Wed 4 is submit buffer. | A last-day build can finish with no demo. | Treating the video day as the day the app first runs. |
| D23 | The sprint manager tracks the full scheduled build. The narrow five-gate list must not drop Files API, SAM, or the prompt line. | Those are the Meta tooling story and they already have days. | A Tuesday product that is only a text verdict. |
| D24 | An UNRESOLVED fall-through keeps label null. COMPUTED, CHECKED, and ASSUMED stay on a chain that decided the verdict. | Those three labels say how a settled chain was proven. The Wednesday task sentence asked for a label on the live detention run, and the human chose null. `combine.py` stays as it is. | Forcing COMPUTED, CHECKED, or ASSUMED onto the fall-through |
