# Decisions

Numbered and dated. The code cites them by number. A decision changes only through a later one, which says what it supersedes. The full wording, with build notes, is in git history (`c75b230` and earlier).

| # | Decision | Status |
|---|---|---|
| D1 | Every field cites its source, or is "not stated" | in force |
| D2 | A cross-document mapping is a record, on every side | in force |
| D3 | Precedence rules apply only within one policy; rule 2 uses effective dates | in force |
| D4 | Two-digit years are expanded in code | in force |
| D5 | Rule 1 never fires in family A | in force |
| D6 | An uncompared pair is recorded and counts as unresolved | comparability rule replaced by D9 |
| D7 | `unresolved` carries a reason | reason renamed by D9 |
| D8 | The domain layer is frozen and hashed | re-taken at D9 and D12; question list replaced by D11 |
| D9 | Compare the claim, refuse a missing base, quote wording | in force |
| D10 | A confirmed upload is admitted whole | in force |
| D11 | A typed claim plus a confirmed grouping replaces the question list | in force |
| D12 | Verdict inputs come from verified text in a bounded region | in force |
| D13 | Effective dates from the printed line; a person picks the figure | in force |

## D1. One atom, one span (2026-11-22)
**Decision:** every field on an atom or statement carries its source (a span id, or an offset range in the claim). A field with no source is *not stated*, never filled in.
**Why:** a field that must be filled gets invented plausibly. The Gillette claim copied USD and "each claim" from one cover note onto a document that states neither.

## D2. Mappings across documents are records, on every side (2026-11-22)
**Decision:** when a span reaches a question through anything but its own words (a position in a composite cell, a label, a normalised policy number), a `SlotMapping` records the span, target, justifying spans and method. Every side needs one.
**Why:** map one side only and two assertions land on different questions, so the conflict disappears with no record.

## D3. Rule 2 compares effective dates, within one policy (2026-11-22)
**Decision:** `later_effective_date` compares instrument effective dates, never coverage periods. Both rules fire only between instruments issued under the question's policy.
**Why:** overlapping periods have no "later". Unscoped, the Reliance binder (an excess carrier describing another insurer's policy) would override Item VII. The FD960229 cover note states the principle: a change binds only when endorsed on that policy.

## D4. Dates are expanded in code (2026-11-22)
**Decision:** two-digit years become 19xx or 20xx by a fixed rule in code, never by the model. In `6/1/96-99` the end year is expanded against the start year.

## D5. Rule 1 never fires in family A (2026-11-22)
**Decision:** recorded as expected, not fixed. The packet's only endorsements amend GS-212C, whose base wording is not in the packet, and nothing amends FD960228.

## D6. An uncompared pair counts as unresolved (2026-11-22)
**Decision:** every pair of values on a question is recorded, with `compared=false` and the reason when they cannot be compared. An uncompared pair with differing values is unresolved, never an agreement and never dropped. No equivalence (such as "each loss" = "each claim") without a cited span.
**Why:** every earlier version of the Gillette conflict was lost to a silent drop.
**Superseded in part:** D9 replaced the comparability rule; the recording rule stands.

## D7. `unresolved` carries a reason (2026-11-22)
**Decision:** `documents_disagree` became `unresolved` with a typed reason. *Supported* means nothing contradicts it and nothing comparable was left uncompared.
**Why:** a result of "supported" over a comparison that never ran reads as an agreement nobody tested.
**Amended:** D9 renamed `uncompared_agreement` to `amounts_not_comparable`.

## D8. The domain layer is frozen before family B (2026-11-22)
**Decision:** the arbiter, comparators, assertions, checker, prompts, schema, predicates and family A's labels are hashed in `data/freeze.json`; `tests/test_freeze.py` fails on any change. Parser, ingest, retrieval and CLI may change. Family B's labels go in new files, committed before the first run.
**Why:** a label sharpened after seeing output is contamination; a hash means nobody has to trust that the freeze held.
**Since:** re-hashed at D9 and D12, each by an approved decision. D11 replaced the frozen question list as the input; it remains a regression fixture.

## D9. Compare the claim, refuse a missing base, quote wording (2026-11-23, after the freeze, approved)
**Decision:**
1. A claim declares its kind (`amount` or `wording`) and, for amounts, its value as written.
2. Two amounts are comparable when currency matches (or neither states one) and basis matches (or neither states one). Otherwise the mismatch is named (`currency_not_stated`, `basis_mismatch`, …). The same rule applies between documents and between the claim and the governing value.
3. After the arbiter picks the governing value: equal is `supported`, different is `contradicted` with both shown, not comparable is `unresolved (amounts_not_comparable)`. A rule's winner is `resolved_by_rule` only when compared values differ; otherwise `no_conflict`.
4. If an asserting document amends an instrument of the question's policy that is not in the packet: `unresolved (governing_instrument_absent)`, naming both. An amended instrument outside the policy is recorded as excluded, never dropped.
5. Reasons: `unresolved` has `documents_disagree`, `amounts_not_comparable`, `governing_instrument_absent`; `not_found` has `no_addressing_span`.
6. Wording claims get no verdict: the same checks pick the controlling clause, which is quoted with its page as `quoted`, marked not checked.

**Why:** without (3) a wrong amount read as supported; without (4) a packet missing its base form was answered from what was left. Under D6's rule a claim, which states no basis, could never be compared with anything.
**Effect:** family B's recorded run is unchanged; its D9 expectations are in `data/family_b/labels_d9.json` (not preregistered). What moved is in [results/family_b.md](results/family_b.md).

## D10. A confirmed upload is admitted whole (2026-11-23, after the freeze)
**Decision:** an upload has no hand-marked scope, so once a person confirms it and its identifying line verifies, the whole document is admitted (`scope: "document"`; every hand-labelled route keeps `"citation"`). An endorsement's printed amends line ("Form HO 00 03 Only") feeds the D9 missing-document check, by string containment of another confirmed file's form number.
**Why:** otherwise only an upload's identifying line reaches the model and every upload ends not found.

## D11. A typed claim plus a confirmed grouping replaces the question list (2026-11-23)
**Decision:** a person types a claim. Code reads its kind, value, currency, basis and any policy number in it. The for and against reads run on the claim's text; a person confirms which returned lines are about the claim; the unchanged decision tree runs on the confirmed lines. The eight hand-written questions become a regression fixture.
**Why:** the fixed list mixed a guard (the model never names the question) with scaffolding (every question written in advance). The guard stays: a person confirms the grouping.
**Rules:**
- A policy number found in the claim is shown for the person to accept, never applied silently.
- Gather and decide are separate steps; the frozen files do not change.
- A basis missing from the claim may be set at confirmation, recorded as `set_at_confirmation` and shown on the result.
- Every run records `grouping_mode`, `basis_source`, `policy_source`, the lines set aside with reasons, and documents where nothing was found.
- Refusals are named: unreadable claim, more than one value, a date with no amount, no candidate line, no line confirmed.
- No auto-accept: that needs a second confirmer and its own decision.

**Check:** the five regression answers were written to `data/regression_d11.json` before any code changed; typed claims reproduce all five.

## D12. Verdict inputs come from verified text in a bounded region (2026-11-24, built)
Written after family C, where every miss came before the decision tree.
**Decision:**
1. **Value.** One amount in the verified quote: code reads it. Several: the model's pointer, only if it lies inside the quote. Otherwise `value_ambiguous` (several, no pointer) or `value_not_in_verified_span` (none).
2. **Identity.** A quote is the page plus the region the model was shown, plus a text hash; it must occur once in that region, as consecutive lines in one column. A hash mismatch is stale, never repaired.
3. **Columns** come from page coordinates (`proofgraph/geometry.py`), not the page midpoint.
4. **Wording first.** A claim's kind is decided before the amount checks.
5. **Currency and basis are data** (`data/currencies.json`, ISO 4217; `data/basis_phrases.json`, each phrase its own basis). An unknown currency token is refused by name. "$" is "dollars, country not printed": it compares with "$"; against a named currency it is not comparable until a person sets the claim's currency at confirmation.

**Check:** the D11 regression and families A and B give the same answers; family C went from 2 of 5 to 5 of 5 on two live runs ([results/family_c.md](results/family_c.md)). One fix was made after seeing family C's output, so that result is not a clean holdout.

## D13. Effective dates from the printed line; a person picks the figure (2026-11-24, built)
Decided before any tax document was opened, so the tax run stayed a holdout.
**Decision:**
1. **Effective date.** The upload proposer quotes the printed effective-date line; code parses the date from the verified quote; the person confirms, corrects or clears it. A date typed with no verified quote is a judgment and needs a reason. The form's edition date is never an effective date. With no date, rule 2 cannot fire on that document.
2. **Figure.** When a confirmed line states several amounts and has no valid pointer, the person picks one from the list code found, by position. Recorded as `set_at_confirmation` and shown on the result. Code never matches the claim's words to a figure; with no pick, `value_ambiguous` stands.

**Not decided:** a claim about an amount as of a date ("the 2024 limit"). Today code does not read the year in such a claim (README, Limitations). It needs its own decision.
