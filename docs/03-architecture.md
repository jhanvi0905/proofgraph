# 03 · Architecture

## 1. What kind of system this is
**A deterministic verification workflow with one bounded agentic loop.**

- **Workflow:** the path is fixed in code. Models do work at fixed steps; code chooses every next step.
- **The one agentic part** is the objection loop (an *evaluator–optimizer* pattern). Muse proposes, the engine objects, and Muse decides how to fix its proposal. There are at most 3 rounds, and only the engine can end the loop.
- **Why:** the model must never choose whether it gets checked. Fixed routing also makes every verdict replayable and auditable.

### Who decides what
| Step | The model decides | Code decides (the next action) |
|---|---|---|
| Propose (call 1) | Which facts exist, where they are (quote, page, box), how they link | Always runs; output must match the schema, or one repair retry |
| Ground each fact | Nothing | Route by evidence type: PDF text → text in box; plain text → quote match; handwriting/scan → blind re-read; goods photo → SAM 3.1 count |
| Check each link | Nothing | Route by link type: compute/temporal → calculator; wording → blind checker; rule → logic |
| Objection (call 4) | How to fix it | Whether to send it back (only on failure reason codes) and when to stop (3 rounds) |
| Verdict | Nothing | Combine rules + weakest-link label |

```
               ┌─────────────── objection (reason codes), max 3 rounds ───────────────┐
               ▼                                                                      │
 Case ─► [Muse Spark: PROPOSE] ─► ClaimProgram ─► [ROUTER: code] ─┬─ text-in-box (code) ─────┐
          facts + links + boxes                                   ├─ quote match (code) ─────┤
                                                                  ├─ blind re-read (Spark Open)┤
                                                                  ├─ count (SAM 3.1 vs Muse) ─┤
                                                                  ├─ calculator (code) ──────┤
                                                                  ├─ wording (Spark Open) ───┤
                                                                  └─ rule logic (code) ──────┤
                                                                                             ▼
                                                              [COMBINE: code] ─► Verdict + Label + Reasons
```

## 2. Data contracts (`proofgraph/schema.py`, frozen after Day 1 hour 1)
```python
class Source(BaseModel):          # one document or one passage/clause
    id: str                       # "p107", "c6", "rate_conf", "pod"
    kind: Literal["text", "table", "pdf", "image"]
    text: str | None              # cleaned text (text/table/pdf)
    file_id: str | None           # Meta Files API id (pdf/image)
    path: str | None              # local path (pdf/image)

class Case(BaseModel):            # what every adapter produces
    id: str; dataset: Literal["findver", "contractnli", "traps", "freight"]
    mode: Literal["passage", "whole"]
    claim: str
    sources: list[Source]
    # sealed, used ONLY by scripts/report.py, never by pipeline code:
    answer: Literal["SUPPORTED", "CONTRADICTED", "UNRESOLVED"] | None = None
    gold_evidence: list[str] = []

class Fact(BaseModel):
    id: str; label: str; source_id: str
    quote: str | None             # exact text, if the source has text
    page: int | None; box: list[int] | None    # [x_min, y_min, x_max, y_max], 0–1000 grid
    points: list[list[int]] | None              # for counts
    value: float | str | None
    scale: Literal["units", "thousands", "millions", "billions", "percent"] | None
    kind: Literal["number", "date", "time", "text", "count"]
    entity: str | None = None     # conflict key; absent does not conflict
    period: str | None = None

class Link(BaseModel):
    id: str; kind: Literal["compute", "temporal", "wording", "rule"]
    inputs: list[str]             # fact ids
    statement: str                # the small claim this link asserts, in plain words
    expr: str | None              # compute/temporal only, e.g. "(f3*1000) == 183479000"
    rule_source: Literal["evidence", "assumed"] | None
    claim_span: str               # the words of the claim this link covers

class ClaimProgram(BaseModel):
    facts: list[Fact]; links: list[Link]
    required: list[str]           # link ids the conclusion needs (AND)
    unverifiable_parts: list[str]

class FactCheck(BaseModel):
    fact_id: str; status: Literal["grounded", "ungrounded", "conflict"]
    method: Literal["quote", "text_in_box", "blind_reread", "count_agreement"]
    detail: str

class LinkResult(BaseModel):
    link_id: str; status: Literal["pass", "fail", "blocked", "not_mentioned"]
    strength: Literal["COMPUTED", "CHECKED", "ASSUMED"]
    detail: str

class Verdict(BaseModel):
    case_id: str
    verdict: Literal["SUPPORTED", "CONTRADICTED", "UNRESOLVED"]
    label: Literal["COMPUTED", "CHECKED", "ASSUMED"] | None
    reasons: list[str]            # plain-language lines
    reason_codes: list[str]       # see §8
    fetch: list[str]              # "what to fetch" lines when UNRESOLVED
    rounds: int                   # objection rounds used
    fact_checks: list[FactCheck]; link_results: list[LinkResult]
    flags: list[str] = []         # operational notes only, e.g. checker=fallback
```

## 3. Pipeline (`proofgraph/pipeline.py`)
```
verify(case) -> Verdict
  program = propose(case)                         # call 1
  for round in 0..3:
      facts  = [ground(f, case) for f in program.facts]    # router by evidence type
      links  = [check(l, facts, case) for l in program.links]  # router by link type
      verdict = combine(program, facts, links, case.claim)
      if verdict has no objection-worthy reason codes or round == 3: return verdict
      program = revise(case, program, objections(verdict))  # call 4
```

## 4. Grounding rules (`engine/ground.py`)
| Evidence | Check | Grounded when |
|---|---|---|
| Text passage / clause | Quote match | Quote appears in the source after normalisation (strip `​`, collapse whitespace, normalise quotes and dashes), and the fact's value appears in the quote |
| Digital PDF | Text in box | pdfplumber words whose centres fall inside the box (2% margin) contain the value |
| Handwriting / scan / photo text | Blind re-read | Muse Spark Open, given only the crop and "Read the value in this image," returns the same value after normalisation |
| Goods in a photo | Count agreement | SAM 3.1 mask count for the noun equals Muse's pointed count |
| Any fact | Conflict | Two grounded facts whose label, entity, and period are all present and equal, and whose numeric values differ by more than 0.5%, are both marked `conflict`. A missing entity or period does not conflict. |

Parentheses mean negative: `( 2,483 )` → −2483. Handle `$`, commas, `%`, `—` (zero) and `(…)`.

## 5. Compute rules (`engine/calc.py`)
- **Safe calculator:** an `ast` whitelist (numbers, fact ids, `+ - * / ( )`, comparisons, `%` literal suffix, `abs min max round`, `hours_between`, `days_between`). Anything else → `EVAL_ERROR`. Models never write Python.
- **Rounding tolerance comes from the claim text, never from the model.** An exact literal gets ± half a unit of its last digit ("$183,479,000" → ±$500; "18.2%" → ±0.05 points). Hedge words ("about," "approximately," "nearly," "around") widen it to ±1 unit or ±2% relative, whichever is larger.
- **Scale rule:** if the evidence states the scale, use it. If not, evaluate under every plausible scale (units, thousands, millions). If the verdict is the same under all of them, it stands. If it differs, the link is `blocked` with `SCALE_AMBIGUOUS`.

## 6. Wording checks (`clients/checker.py`)
- Input: **one quote (or one clause) and one statement.** Nothing else. Not the proposer's reasoning or answer, not other clauses, not the claim's numbers where the statement can avoid them.
- Output: `entails` | `contradicts` | `not_mentioned`.
- The model is Muse Spark Open on Baseten. The fallback is a fresh Muse Spark call with the same restricted input (logged as `checker=fallback` on `Verdict.flags`, not in `reason_codes`).
- Independence comes from **what the checker sees** and from **different mechanisms** (text layer, SAM). Muse Spark Open shares lineage with Muse Spark, so we never call it an "independent witness" on weights alone.

## 7. Combine rules (`engine/combine.py`)
1. **Coverage:** extract every number from the claim. Skip integer years 1900–2100 without `$` or `%`. Each remaining number must be tested by a link or equal a grounded fact. Otherwise → `UNCOVERED_NUMBER`.
2. **Contradiction:** a required link `fail`s, its inputs are all `grounded`, and there's no conflict → **CONTRADICTED**. A required input marked `conflict` cannot be reduced to one number: **UNRESOLVED** with reason code `CONFLICT` (this does not start an objection round).
3. **Support:** all required links `pass`, coverage is complete, and `unverifiable_parts` is empty → **SUPPORTED**.
4. **For NLI-style claims (ContractNLI):** at least one grounded clause `contradicts` and none `entails` → CONTRADICTED; at least one `entails` and none `contradicts` → SUPPORTED; both → UNRESOLVED (`CLAUSE_CONFLICT`); none decides → UNRESOLVED (`NOT_MENTIONED`).
5. **Otherwise → UNRESOLVED**, with reason codes and `fetch` lines.
6. **Label:** the weakest strength among the required links that decided the verdict: ASSUMED < CHECKED < COMPUTED. A blocked link that didn't affect the verdict doesn't lower the label.
7. **Partial verdicts (freight):** one ungrounded fact blocks only the links that use it. Other grounded failures still produce CONTRADICTED. Blocked parts get their own reason and fetch line.

## 8. Reason codes
`UNGROUNDED_QUOTE` · `VALUE_NOT_IN_BOX` · `REREAD_MISMATCH` · `COUNT_MISMATCH` · `CONFLICT` · `UNIT_MISMATCH` · `SCALE_AMBIGUOUS` · `UNCOVERED_NUMBER` · `UNVERIFIABLE_PART` · `NOT_MENTIONED` · `CLAUSE_CONFLICT` · `EVAL_ERROR` · `EXTRACTION_FAILED` · `CHECKER_UNAVAILABLE`

**These codes trigger an objection round:** `UNGROUNDED_QUOTE`, `VALUE_NOT_IN_BOX`, `UNCOVERED_NUMBER`, `EVAL_ERROR`, and a wording link that returned `not_mentioned` when the proposer expected support or contradiction. **These never trigger a round** (they are facts about the evidence): `CONFLICT`, `REREAD_MISMATCH`, `COUNT_MISMATCH`, `NOT_MENTIONED` after a full search, and `SCALE_AMBIGUOUS`.

## 9. Enforced boundaries
- `proofgraph/engine/**` must not import `proofgraph.propose` or the proposer functions in `proofgraph.clients.muse`. Enforced by `tests/test_boundaries.py`, which parses imports with `ast`.
- `checker.blind_wording(quote: str, statement: str)` and `checker.blind_reread(crop: bytes)` accept nothing else, so their signatures make blindness structural.
- Only `scripts/report.py` reads `Case.answer` and `Case.gold_evidence`. A test asserts that pipeline modules never access those attributes.

## 10. Reproducibility
Every model call goes through `cache.py`, keyed by `sha256(model, endpoint, prompt, schema, inputs, sample_idx)`. Runs write `runs/<dataset>-<mode>-<system>-<date>.jsonl`. `make report` reads only `runs/`.
