# Family C: a packet the system was never built on

Preregistered in `data/family_c/preregistration.json` (commit `9a2a336`) before any run. One document: Chubb's Blink personal cyber sample policy (forms PF-53914 / PF-53915, 07/20), uploaded through the product path, confirmed by a person, five claims typed, every candidate line confirmed (nothing set aside).

## Results

| Claim | Expected | Run 1 (parser as frozen) | Run 2 (watermark glyphs dropped) | Why |
|---|---|---|---|---|
| C1 cyber bullying wages $5,000 | supported | no lines | **supported**, page 8 | Run 1: a watermark letter ("e") sat inside the sentence, so no faithful quote could verify |
| C2 same, $10,000 | contradicted | no lines | no lines | the right line was found, but the model gave no value pointer and the assertion step discards it |
| C3 identity fraud fees $5,000 | supported | **supported**, page 9 | no lines | run 2's quote spanned two lines of a 2-up page; the checker reads that as crossing columns |
| C4 wages only for the first 60 days (wording) | quoted | refused | not re-run | atomize framed it as a `states` statement with no amount and rejected it |
| C5 cyber extortion limit $25,000 (placeholder) | no answer | no lines | no lines | correct: nothing was compared against `$[XXX.XX]` |

**Preregistered answers matched: 2 of 5 on the final run (C1, C5).** C3 passed once and failed once: one live run per claim is not enough evidence on a new document set.

Predictions: P1 held (the proposer quoted `PF-53914 (07/20)` from page 1, though it proposed no policy number); P2 held (watermark and 2-up pages both broke claims); P3 held (C5 never compared against the placeholder); P4 did not (C1 returned one line, not three).

## What this shows

The decision tree held: it never answered wrong, and C5 refused to compare against a placeholder. The losses are all before it, in places shaped by the first two packets:

1. **Watermarks** (fixed here, parser only): glyphs over three times the page's typical text size are dropped. ISO and Gillette runs are unchanged (all tests replay).
2. **Two columns per page** is assumed by the parser and by the checker's "same column" test (page midpoint). A 2-up page has four.
3. **Each quoted line must occur once on its page.** Policies repeat parallel wording across coverages; a quote that is unique as a block can still fail line by line.
4. **The value must come from the model's pointer.** When the model quotes the right line but omits the pointer, code does not read the amount from the verified quote itself.
5. **Wording claims pass through the amount-shaped atom check**, so a wording claim about a duration is refused.
6. Untested but predicted: only US dollars are read as a currency; the basis lexicon has six phrases.

Items 2 to 5 sit in frozen files (`checker.py`, `assertions.py`, `atomize.py`) and need a decision before they change.
