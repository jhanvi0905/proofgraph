# 01 · Product brief

## The problem
AI can retrieve the right information and still reach the wrong conclusion. In enterprise work, decisions depend on evidence scattered across contracts, invoices, reports and policies. Even when AI provides citations, those citations don't prove its conclusions. A model can cite the correct table row and still get the arithmetic, the scale or the meaning wrong.

## Who it's for
People who sign off on conclusions drawn from documents, where a confident wrong answer costs more than "I can't confirm this":
- **Billing and freight reviewers** checking invoices against rate confirmations and proofs of delivery (the builder's own field)
- **Auditors and finance teams** checking figures in reports
- **Contract and compliance reviewers** checking what an agreement does and doesn't allow
- **AI agents** that act on documents and need a check before they act (stretch goal: the Muse Code gate)

## The core idea: check every link, trust the weakest one
A conclusion is a chain of small steps, and it's only as strong as its weakest link.
1. Muse Spark reads the documents and breaks the conclusion into **links**: facts (each with an exact quote, or a box on the page), calculations, clause readings and rules.
2. The verification engine checks **every** link with the strongest check that fits it, and **never with the model that proposed it**:
   - numbers and dates → executed by a safe calculator
   - printed text in a PDF → the PDF's own text inside the box
   - handwriting or scans → a blind re-read of the crop by Muse Spark Open
   - goods in a photo → an independent count by SAM 3.1
   - wording → Muse Spark Open, shown one quote and one small statement, never the proposer's answer
   - rules → explicit logic
3. Explicit rules combine the checks into a verdict and a label.

## What the user gets
- **Verdict:** SUPPORTED · CONTRADICTED · UNRESOLVED
- **Label (the weakest required link):**
  - COMPUTED: every link was a grounded fact or an executed calculation
  - CHECKED: at least one link is wording, confirmed by the blind checker
  - ASSUMED: the chain relies on a rule the documents don't state (the rule is shown)
- **Reason lines** in plain language, for example "Detention should be $165.00, not $450.00 (4.2 h on site, 2 h free, $75/h)"
- **What to fetch** when UNRESOLVED, for example "Need a clearer photo of the departure time on the POD."
- **The proof graph drawn on the documents:** every fact is a box on the actual page or photo, linked to its checks and the verdict

## What it is not
- Not a chatbot, and not a RAG app (the hackathon bans "Basic RAG Applications")
- Not an LLM grading its own answer
- Not an agent framework demo
- Not a legal or financial adviser. It verifies claims against documents; it doesn't give advice.

## What the hackathon build proves
| Evidence | Where |
|---|---|
| Checking each link independently produces fewer wrongly approved claims than Muse answering directly, with the same evidence | FinDVer (numbers), passage-given mode |
| ProofGraph finds the evidence itself | FinDVer whole-filing mode, ContractNLI, freight |
| Contract wording is verified, and "not mentioned" becomes UNRESOLVED | ContractNLI |
| Contradictions are detected instead of one side being picked | Conflict traps |
| Several documents, photos and handwriting work | Freight (designed demonstration, not a benchmark) |
| Independence matters | Parts-off test: blind checker vs the proposer checking itself |

**Not claimed:** accuracy on technical specifications or policies (roadmap), multi-document accuracy at benchmark scale, or being better than GPT-4o (the published FinDVer numbers come from a different setup).

## Sentences to reuse
- **For judges:** "ProofGraph is a deterministic verification workflow. Muse Spark finds and reads the evidence and repairs its own work when the engine objects, but routing, checking and the verdict are fixed in code, so the AI never decides whether it gets checked."
- **README scope:** "Evaluated on SEC filings (FinDVer) and contracts (ContractNLI). Demonstrated on a multi-document freight check. Every verdict states which links were computed, which were checked by an independent model, and which rest on an assumed rule."
- **Meta story:** "Citations you can check, down to the pixel."

## Hackathon context (verified 26 Oct 2026)
- **Event:** Meta Global AI Developer Hackathon (Cerebral Valley). Solo, Indie Developer track.
- **Problem statement:** *Build for Your World*. Bring Meta's models into a domain you know firsthand.
- **Build window:** Oct 27 to Nov 4. **Deadline: Nov 4, 9:00 PM ET = Thu Nov 5, 07:30 IST.**
- **Must:** use Meta models; public repo; 3-minute demo video; show only work built during the hackathon, clearly identified.
- **Rubric:** Impact 30% · Use of Meta AI tooling 25% · Demo 25% · Technical depth 20%. Stage 1 is a pass/fail check on theme fit and Meta model use.
- **Bonus to aim for:** Best Build on Meta Open Weight Models ($10K), via Muse Spark Open on Baseten. Best Agentic Use-Case ($5K) only if the Muse Code gate gets built.
- **Must-attend:** Wed Oct 28, 12 PM ET (21:30 IST), "Agents 102: Best Practices for Verifiable Agents."
