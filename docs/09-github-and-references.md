# 09 · GitHub setup and references

## Repository setup (do this on Tue Oct 27, after 09:30 IST)
- **Name:** `proofgraph` · **Visibility:** public (a hackathon rule) · **Licence:** MIT
- **Description:** "Verifies AI conclusions against documents: every link checked independently, every verdict labelled by its weakest link. Built on Meta Muse Spark, SAM 3.1 and Muse Spark Open."
- **Topics:** `meta-hackathon`, `muse-spark`, `sam`, `verification`, `document-ai`, `llm-evaluation`
- **First commit:** this docs pack + scaffold (T1). Commit message: `chore: scaffold ProofGraph (hackathon day 1)`
- **Branching:** every code change is pushed on a relevant branch (`feat/`, `fix/`, `docs/`, `chore/`, `test/`, `eval/`). Do not push commits straight to `main`. Open a pull request and squash-merge.
- **Commit style:** `feat:`, `fix:`, `test:`, `docs:`, `chore:`, `eval:` (for committed run outputs)
- **Tags:** `v0.1-day1` after Checkpoint C; `v1.0-submission` on Nov 4
- **Secrets:** never in the repo. CI needs none: tests use fixtures and the cache. Deploy secrets go in Streamlit Cloud's secrets settings.

## `.gitignore` (minimum)
```
.env
data/
cache/
__pycache__/
.venv/
*.pyc
.streamlit/secrets.toml
```

## CI (`.github/workflows/ci.yml`)
- Trigger: push and pull_request to `main`
- Steps: checkout → set up uv + Python 3.11 → `uv sync` → `make test`
- No network calls in tests; the CI fails if any test tries to reach the network

## README outline
1. ProofGraph: one sentence, plus the "Latest results" table (generated)
2. The problem (from `01-product-brief.md`)
3. How it works: check every link, trust the weakest one (with a diagram)
4. How Meta's models are used: the four calls
5. Results: generated from `results/report.md`, with the pre-registered success criteria next to them
6. Scope sentence and what is not claimed
7. Run it: setup, data, test, eval, report, app (replay mode needs no key)
8. Built during the hackathon: a link to `BUILT_DURING_HACKATHON.md`
9. Licences and attribution: FinDVer (MIT), ContractNLI (CC BY 4.0), code (MIT)

## `BUILT_DURING_HACKATHON.md` format
One section per day: date, what was built (files and modules), what was measured (links to report rows), decisions made. This is what judges use to identify new work.

## References
| What | Link |
|---|---|
| Hackathon participant guide (rules, rubric, dates, resources) | https://cerebralvalley.ai/e/meta-ai-developer-hackathon/details |
| Meta Model API docs: overview | https://dev.meta.ai/docs/overview |
| Image understanding and perception grounding (point/box/count) | https://dev.meta.ai/docs/image-understanding |
| File handling (PDF text and page images) | https://dev.meta.ai/docs/file-handling |
| Meta cookbook (SAM basics, perception grounding overlay, agent loops) | https://dev.meta.ai/docs/cookbook |
| Build with Muse Spark (Meta blog) | https://dev.meta.ai/resources/blog/build-with-muse-spark |
| FinDVer repository (MIT) | https://github.com/yilunzhao/FinDVer |
| FinDVer paper | https://arxiv.org/abs/2411.05764 |
| ContractNLI dataset (CC BY 4.0) | https://stanfordnlp.github.io/contract-nli/ |
| ContractNLI paper | https://arxiv.org/abs/2110.01799 |
| Baseten (Muse Spark Open) | Quickstart linked from the hackathon guide; model `meta-models/muse-spark-open-1026` |

## Attribution text (README and app footer)
- FinDVer: Zhao et al., "FinDVer: Explainable Claim Verification over Long and Hybrid-Content Financial Documents," EMNLP 2024. MIT licence.
- ContractNLI: Koreeda and Manning, "ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts," Findings of EMNLP 2021. CC BY 4.0.
