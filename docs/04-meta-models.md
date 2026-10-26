# 04 · Meta models: the four calls

Verified against Meta's docs on 26 Oct 2026 (dev.meta.ai). Anything marked **VERIFY** must be confirmed on first use.

## Models and endpoints
| Use | Model | Where | Notes |
|---|---|---|---|
| Proposer (calls 1 and 4), Contenders A/B | `muse-spark-1.3` | `https://api.meta.ai/v1`, `Authorization: Bearer $MODEL_API_KEY` | 1M-token context; structured output; reasoning effort `minimal`…`xhigh`; prompt caching; images and PDFs; perception grounding |
| Independent count | `sam-3.1` | Same base URL, `POST /v1/responses`, files via `POST /v1/files` | Text prompt plus image/video → a box and a mask for every match |
| Blind checker | `meta-models/muse-spark-open-1026` | Baseten, OpenAI-compatible (**VERIFY** base URL in Baseten's quickstart) | Use this exact model ID, not `muse-spark-open` |
| Checker fallback | `muse-spark-1.3` | Meta API, fresh call, same restricted input | Log `checker=fallback` |

- The OpenAI SDK works with `base_url="https://api.meta.ai/v1"`. Pass `api_key` explicitly; it doesn't read `MODEL_API_KEY` by itself.
- The Responses API is recommended for images and files.
- **Files and PDFs:** upload once (`client.files.create(file=..., purpose="user_data")`) and reference by `file_id`. A PDF contributes its **text for the first 100 pages** and **page images for the first 50 pages**. At most 50 images per request.
- **Pricing (published Spark rates):** $1.25 per 1M input tokens, $4.25 per 1M output tokens, about $0.15 per 1M cached input (**VERIFY** on the pricing page). A ~1280px image costs about 1,300–1,500 tokens. Use `POST /v1/responses/input_tokens` to count tokens before a big run.

## Perception grounding (the key Meta capability)
Muse Spark returns locations on a **0–1000 grid** over the image it received: (0,0) is the top left, x runs left to right, y runs top to bottom. Convert to pixels with `x*width/1000`, then clamp, because values like 1001 can occur at the edges. Ask for one output shape per request and keep the grounding instruction in the user message next to the image. Pair it with structured output.

- **Box:** `{"object_name": str, "bbox": [{"x_min","y_min","x_max","y_max"}]}`. Prefixing "You are an object grounding expert…" and "do not miss any objects" improves recall.
- **Point:** `{"object_name": str, "x": int, "y": int}`
- **Count:** point at every instance first, then count: `{"object_name": str, "points": [{x,y}…], "count": int}`

## Call 1: Propose (`propose.py`)
- **Input:** the claim; sources (text inline, or PDFs/photos by `file_id`). Never pass any field listed under the leak warnings in `05-datasets-and-eval.md`.
- **Output:** `ClaimProgram`, enforced with structured output (JSON schema from `schema.py`).
- **Settings:** `reasoning.effort="medium"` to start (tune on the dev slice only).

Draft prompt (`prompts/extract.md`):
```
You break a claim into small, checkable links. You do NOT decide whether the claim is true.

For every fact the claim depends on:
- copy the exact text from the source that contains it ("quote"), character for character
- give the source id; for PDFs and images also give the page and a box [x_min, y_min, x_max, y_max] on a 0–1000 grid
- give the value and, if stated anywhere in the evidence, its scale (thousands, millions, percent)
- for counts of physical items, point at every instance and give the count

For every step from facts to the claim, write one link:
- compute/temporal: an expression over fact ids, and put the claim's own number as a literal exactly as written (e.g. "183479000", "18%")
- wording: one plain sentence the quote should support or contradict
- rule: a rule the conclusion relies on; mark rule_source "assumed" if the documents don't state it

List "required" links. List any part of the claim you cannot map to evidence in "unverifiable_parts".
Never compute results yourself. Never invent quotes.
```

## Call 2: SAM 3.1 count (`clients/sam.py`)
- **Input:** one photo and one short noun ("carton").
- **Output:** a list of masks/boxes; the count is the length of that list. Use the official `meta-sam` parsers from Meta's SAM cookbook recipe (**VERIFY** the package name in "SAM API basics").
- **Only used for:** physical items in photos. Never used to read text.

## Call 3: Blind checks (`clients/checker.py`)
`prompts/blind_wording.md`:
```
Here is a passage and a statement. Answer with exactly one word:
entails, contradicts, or not_mentioned.
Passage: <<one quote or one clause>>
Statement: <<one plain sentence>>
```
`prompts/blind_reread.md`:
```
Read the value written in this image. Reply with only the value as written.
```
Structured output: `{"answer": "entails" | "contradicts" | "not_mentioned"}` and `{"value": str}`.

## Call 4: Objection round (`propose.py::revise`)
- **Input:** the original call-1 input, the previous `ClaimProgram`, and the engine's objections as plain lines, for example "Fact f2: quote not found in source p107." or "The claim's number 4.1B is not tested by any link."
- **Output:** a revised `ClaimProgram`. At most 3 rounds; the engine decides when to stop.

`prompts/objection.md`:
```
The verification engine rejected parts of your proposal. Fix only what is listed.
You may cite different sources, correct quotes, or add missing links.
Do not remove a link just because it failed a check.
Objections:
<<one line per objection>>
```

## Contenders (`baseline.py`)
- **A · Direct Muse:** "Read the evidence, think step by step, answer `entailed` or `refuted`, and cite your evidence." (FinDVer); `entailment | contradiction | not_mentioned` (ContractNLI).
- **B · Direct Muse that may abstain:** same as A, plus "If the evidence does not settle it, answer `cannot_tell`."
- Same model, same evidence, same reasoning effort as ProofGraph.

## Tonight's access tests (before any repo exists)
1. Muse Spark returns JSON matching a tiny schema, from India.
2. Muse Spark points to one value on a page of a real PDF (box mode). Check how tight the box is.
3. SAM 3.1 counts cartons in a phone photo (prompt "carton").
4. Note the exact model IDs and the Baseten base URL once credits arrive.

## Fallbacks
| Problem | Fallback |
|---|---|
| Meta API blocked from India | Muse Spark Open on Baseten for everything; ask in #office-hours |
| Structured output rejected | JSON mode + pydantic validation + one repair retry → `EXTRACTION_FAILED` |
| Baseten credits late | Checker fallback (fresh Muse Spark, restricted input), disclosed in the README |
| SAM miscounts on staged photos | Re-stage photos with clearly separated items; report the agreement rate honestly |
| Boxes loose | Widen the text-in-box margin to 4%; never fall back to "trust the quote" for PDFs |
