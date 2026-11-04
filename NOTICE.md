# Notices and attribution

ProofGraph's own code is released under the MIT licence (see `LICENSE`). It builds on the following.

## Models

- **Muse Spark** (Meta Models API): reads documents, splits claims, links, compares and decides in the review.
- **Muse Spark Open** (`meta-models/muse-spark-open-1026`, served through Baseten): the blind second reader.
- **SAM 3.1** (served through Baseten): independent counts in the earlier boxed-bundle path.

## Libraries

| Library | Licence | Used for |
| --- | --- | --- |
| FastAPI | MIT | the web server |
| uvicorn | BSD-3-Clause | serving it |
| python-multipart | Apache-2.0 | file uploads |
| networkx | BSD-3-Clause | the evidence graph and its walk |
| RapidFuzz | MIT | fuzzy quote alignment and name matching |
| pdfplumber | MIT | PDF text and word boxes |
| Pillow | MIT-CMU | page images |
| pydantic | MIT | typed contracts |
| openai (SDK) | Apache-2.0 | calling the model endpoints |
| Streamlit | Apache-2.0 | the earlier front end, kept in the repository |

## Fonts

Schibsted Grotesk and Source Serif 4, loaded from Google Fonts, under the SIL Open Font License.

## Evaluation data

The suite and the clean check use documents from the sources below. Only synthetic documents are shipped in `examples/`; the recorded runs in `runs/` and `results/` quote short passages from the others.

- **ContractNLI**: Yuta Koreeda and Christopher D. Manning (2021), *ContractNLI: A Dataset for Document-level Natural Language Inference for Contracts*, Findings of EMNLP. CC BY 4.0. <https://stanfordnlp.github.io/contract-nli/>
- **LegalReasonBench** (micro1 public sample): micro1. CC BY 4.0 per its source card. <https://huggingface.co/datasets/micro1-inc/LegalReasonBench>
- **Tobacco800** (YACCLAB-packaged version): David Doermann, Tobacco 800 Dataset, v1; Lewis et al., *Building a test collection for complex document information processing*, SIGIR 2006; Grana, Bolelli, Baraldi and Vezzani, YACCLAB.
- **NIST Special Database 2** (SD02): National Institute of Standards and Technology, Structured Forms Reference Set of Binary Images. Forms are synthesized. <https://www.nist.gov/srd/nist-special-database-2>
- **Company Documents** (a Kaggle archive): the listing, publisher and licence were not verified. Passages from it appear in recorded runs only.
- The synthetic packs under `examples/` are fictional and were written for ProofGraph.
