# 08 · Guardrails: how not to go off the grid

Every rule here exists because breaking it would either break the core claim or get the project disqualified. If a task seems to require breaking one, **stop and ask the human.**

## A. Architecture
1. **Control flow is code.** Never let a model choose which check runs, whether a check runs, or the verdict. Models fill content at fixed steps only.
2. **The proposer never checks itself.** `engine/` must not import `propose.py` or the proposer functions in `clients/muse.py`. Don't weaken `test_boundaries.py`.
3. **Blind checkers stay blind.** `blind_wording(quote, statement)` and `blind_reread(crop)` take nothing else. Don't add a "context" parameter.
4. **Tolerance and scale come from rules in `calc.py`, never from a model.**
5. **No new link kinds, verdicts, labels or reason codes** without updating `03-architecture.md` and getting the human's approval.
6. **`schema.py` is frozen** after Day 1 hour 1.

## B. What not to build
7. No agent frameworks (LangChain, LangGraph, CrewAI, AutoGen, Semantic Kernel, DSPy pipelines), no multi-agent orchestration, and no tool-using search agent.
8. No vector database, embeddings or retrieval index. Whole documents fit in Muse's context.
9. No custom front end (React, Next.js, Vue). Use Streamlit + Graphviz + the HTML box overlay.
10. No auth, accounts, database server, Docker or Kubernetes.
11. No Muse Image or Muse Wonder, and no voice. They are decoration or cut (`11-decision-log.md`).

## C. Data integrity
12. **Leak fields never reach a model or the engine:** FinDVer `explanation`, `explaination`, `python_calculation`, `execution_result`, `knowledge`, `entailment_label`; ContractNLI `annotation_sets`; freight `key.json`. Adapters strip them, and tests check cached request payloads.
13. **Only `scripts/report.py` reads `Case.answer` and `Case.gold_evidence`.**
14. **Tune prompts only on dev slices** (FinDVer: first 50 numeric of `test.json`; ContractNLI: 30 dev pairs). Run each scored split once per prompt version and log the version.
15. **Never hand-edit `runs/` or `results/`.** Never write a result number in the README, app, slides or video unless it comes from `results/report.md`.
16. Don't use Hugging Face mirrors of ContractNLI for scored runs. Use the official files.

## D. Models and money
17. Every model call goes through `cache.py`. No uncached calls in loops. `bypass_cache` is for a named experiment, not the default.
18. `run_eval.py` estimates cost first (using `POST /v1/responses/input_tokens` on a sample) and aborts above `SPEND_LIMIT_USD` unless the human raises it.
19. Use the exact model IDs in `.env`. Every model in the product must be a Meta model. Meta proposes. Baseten runs the blind checker only (`meta-models/muse-spark-open-1026`). Modal and Fireworks stay unused.
20. Retries: at most 4 with exponential backoff on 429/5xx; one repair retry on invalid JSON; then fail honestly (`EXTRACTION_FAILED`). Do not start that repair in the same step as the first paid call.

Minimum budget, 28 Oct 2026. Meta $150 is for proposes. Baseten $100 is for checks, Chat Completions at `https://inference.baseten.co/v1`, model `meta-models/muse-spark-open-1026` only. The next spends are one Meta detention propose, then one Baseten checker call on one quote and one statement. One call each, then stop. Ten dev-slice proposes wait until both of those calls settle. Keys stay in an untracked `.env` and are never printed.

## E. Hackathon rules
21. **Operative build start is Mon Oct 26, 21:30 IST** (decision D20). Log each day in `BUILT_DURING_HACKATHON.md`.
22. **The repo is public.** No keys, no `.env`, no `data/`, no `cache/` committed. Check `git diff --cached` for secrets before every commit.
23. Use only data we have rights to: FinDVer (MIT), ContractNLI (CC BY 4.0, cite it), and our own freight documents with fictional names. No real company logos or real people's names in freight documents.
24. The video and README show **only work built during the hackathon** and say so explicitly.

## F. Code quality
25. Small modules; pure functions in `engine/`; type hints everywhere; pydantic for every boundary.
26. Engine code is written tests first. `make test` passes before every commit, and CI must stay green.
27. Tests never touch the network. Use fixtures and the cache.
28. No silent fallbacks. Every fallback is logged in the `Verdict` (for example `checker=fallback`) and counted in the report.

## G. When unsure
Write the question in `QUESTIONS.md` with the options you see and your recommendation. Then stop work on that item and continue with the next unblocked task in `07-build-plan.md`.
