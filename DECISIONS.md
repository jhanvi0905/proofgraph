# Decisions

Each one is numbered, dated, and has a reason. The code cites them by number. A decision changes only by a new entry that supersedes it.

## D1. One atom, one span (2026-11-22)

Every data field on an atom or statement carries its source: a value plus a span id (or a claim-text offset range for claim atoms). A field with no source is explicitly *not stated*. It is never filled in.
**Why:** a field that must be filled and can't be sourced gets invented, and it gets invented plausibly. The retention claim showed this. USD and "each claim" in the claim text were copied from the FD960228 cover note, so Item VII looked as if it supported fields it never states.
**Consequence:** currency and basis may be absent. Two quantities whose currency is not stated are not comparable until a shown mapping supplies one.

## D2. Mappings across documents are records, on every side (2026-11-22)

When a span reaches a slot through anything other than its own words, a `SlotMapping` records the span, the target slot, the spans that justify it, and the method (position in a composite cell, a label, normalising a policy number). Every asserter of a slot needs a mapping, not only one side.
**Why:** Item VII reaches `FD960228.corp_reimbursement.retention` through position 3 of `NIL/NIL/1,000,000`, and through `757/FD960228` → `FD960228`. Reliance reaches the same slot through the label "Corporate Reimbursement". Map one side only and the two assertions land on different slots, so the conflict drops for a reason nobody wrote down.

## D3. Rule 2 compares instrument effective dates, scoped to the slot's policy (2026-11-22)

`later_effective_date` compares `Instrument.effective_date`. It fires only between instruments issued under the policy that the slot's first segment names. `endorsement_over_base` has the same scope. Coverage periods (`6/1/96-99`) are evidence on the atom (`period`, used by `effective_during`) and never reach the arbiter.
**Why:** overlapping intervals have no "later", and there is no precedence order for them that we could defend. Unscoped, rule 2 would let Reliance (effective 12/31/96) override Item VII (effective 6/1/96), but Reliance is an excess carrier describing another insurer's primary, not amending it.
**Source in the packet:** the FD960229 cover note states the scope principle itself: "NO AMENDMENTS TO THE PRIMARY POLICY SHALL BE BINDING UPON UNDERWRITERS UNDER THIS INSURANCE UNLESS SPECIFICALLY AGREED BY UNDERWRITERS AND ENDORSED HEREON" (`london_fd960229`, span `1db0f48fa77d4d72`, page 8, offsets 14324–14511). A change binds a policy only when it is endorsed on that policy. Limit of this citation: the clause is FD960229 protecting itself from changes to the primary. It supports the principle; it does not by itself prove that a binder on another layer cannot amend FD960228.
**Consequence for the retention slot:** Item VII belongs to GS-212C and Reliance to NDA 0134456-96. Neither is issued under FD960228, so neither rule fires. If the values conflict, the result is `unresolved_conflict` and so `documents_disagree`: the arbiter refuses to pick a winner without a rule.

## D4. Dates are expanded in code (2026-11-22)

Two-digit years become 19xx or 20xx by a fixed rule in code, never by the model. In an interval like `6/1/96-99`, the end year is expanded against the start year (`99` → 1999), never parsed as a date of its own.

## D5. Rule 1 never fires in Family A (2026-11-22, closes O2)

The packet's only endorsements are Nos. 12 and 13, both to GS-212C (`data/instruments.json`). The FD960228 cover note is the document that places that policy, not an amendment to it. Nothing in the packet amends FD960228, so `endorsement_over_base` has nothing to fire on for its slots. Within GS-212C, Endorsement 13 replaces Item VII, but the base GS-212C wording is not in the packet. So there is no base span for rule 1 to override either.
**Consequence:** in Family A, precedence questions end in `later_effective_date` (if two instruments issued under one policy conflict) or in `unresolved_conflict`. The README says so next to the four verdicts.

## D6. An uncompared pair is recorded and counts as unresolved (2026-11-22, closes O1)

The FD960228 cover note says USD 1,000,000 *each claim*. Reliance says $500,000 Corporate Reimbursement *each loss*. Item VII states no basis. Numbers compares only on equal currency and basis, so the comparator returns `mismatch` with its reason. It is never treated as an agreement and never dropped.
The arbiter records every pair of asserters on a slot: `compared=false` plus the reason (`basis_mismatch: each_claim vs each_loss`, `currency_not_stated`). An uncompared pair on a slot with differing raw values is `unresolved_conflict`, so the verdict is `documents_disagree`, not `supported`. The eval counts these pairs separately as unresolved.
**Why:** a mismatch nobody wrote down is a drop, and every earlier version of this conflict was lost to a silent drop. No lexicon entry makes "each loss" equal "each claim" unless a cited span supports it.

## D7. `documents_disagree` becomes `unresolved`, with a reason (2026-11-22)

Still four verdicts: supported, contradicted, unresolved, not found. `unresolved` carries a typed reason:
- `documents_disagree`: the numerals differ and no rule picks one;
- `uncompared_agreement`: the numerals agree, but currency or basis blocked the comparison, so the agreement was never tested.

**Supported** means nothing contradicts the answer, and nothing that could have been compared was left uncompared. One assertion with no pairs is supported, the ordinary case. A pair with no numeral (NIL) could never be compared, so it does not block supported.
**Why:** the counterfactual without Reliance returned `supported` on two assertions whose comparison was blocked by Item VII's unstated currency. A reader would draw an agreement the arbiter never tested. Nothing disagrees there, so it needs its own name, not `documents_disagree`.

## D8. The domain layer is frozen before family B (2026-11-22)

The claim "no code change for family B" is no longer true: the column gutter was fixed on the ISO form. The narrower claim, which can be tested, has two layers:
- **May change:** parser, ingest, retrieval, fetch, the CLI, the trace writer, `data/instruments.json`. Column gutters and line breaks have nothing to do with insurance meaning.
- **Frozen, byte-identical from the freeze commit to the family B verdict commit:** the arbiter, comparators (`numbers.py`), assertions, claims and slot resolution, the checker, the passes and atomize prompts, the schema, `predicates.json`, and family A's slots, claims, citations and document mappings. Their sha256 values are in `data/freeze.json`, and `tests/test_freeze.py` fails if any file differs.

Family B's claims, slot keys, document mappings and expected verdicts go in new files under `data/family_b/`, never appended to a frozen file. They are written with the system not running, and committed with the preregistration before the first family B run, so the labels provably predate the output.
**Why:** a label written, run, seen wrong and quietly sharpened is the other way contamination gets in. A hash check means nobody has to trust that the freeze held.

## D9. The claim's value is compared, a missing base document is refused, wording is quoted (2026-11-23, post-freeze)

**Post-freeze.** This changes the domain layer frozen at D8. The user approved the extension: record it here, make the changes, take new hashes (`data/freeze.json`). Family B's recorded run (`eeb9a2f`) stays as run; [results/family_b.md](results/family_b.md) gains a dated section saying what moves under D9, and its recorded tables are not edited. `data/family_b/labels.json` is unchanged and is still scored; D9's expectations are in a new file, `data/family_b/labels_d9.json`, written by the person who built the rules, so they are not preregistered.

What changed, each approved as worded:
1. **A claim declares its kind and value.** `Claim.kind` is `amount` or `wording`; an amount claim declares `value`, the amount as the author wrote it (`"USD 1,000,000"`). Neither is inferred at run time; an unreadable declared value fails at load.
2. **Comparability (supersedes D6's rule, keeps its record).** Two amounts are comparable when the currencies match, or neither states one, **and** both state the same basis, or neither states one: the question already fixes the quantity. One side stating a currency or basis and the other not, two different currencies, or two different bases is a named mismatch saying which side lacked what (`currency_not_stated`, `basis_not_stated`, `currency_mismatch`, `basis_mismatch`). The same rule applies to two asserters (`numbers.compare`) and to the claim against the governing value (`numbers.compare_claim`). D6 still holds: every pair is recorded, an uncompared pair counts as unresolved, and no lexicon makes two bases equal.
3. **The claim against the governing value.** After the arbiter picks the governing assertion (by a precedence rule, or the sole asserter, or the agreeing asserters), it compares that value with the claim's: equal is `supported`, different is `contradicted` with both amounts shown, not comparable is `unresolved (amounts_not_comparable)` naming the mismatch between claim and governing value.
   **Bug fixed:** a rule's winner is `resolved_by_rule` only when some pair was compared and its numerals differ. Equal pairs are no dispute: the rule still names the governing document, with reason `no_conflict`. A rule ordering pairs that could not be compared is also `no_conflict` under this wording; the pairs stay recorded with their mismatch.
4. **Missing-document check.** A document mapping may carry `amends`: the instrument the document amends as printed, its catalogue id if any, the policy it belongs to, and a citation to the printed words, verified by `checker.verify_citation` before any model call (a broken one stops the run), with a route strength. Before the precedence rules: if a document asserting on the question amends an instrument of the question's policy set and that instrument is not in the packet, the verdict is `unresolved (governing_instrument_absent)`, naming both. The policy set is the slot registry entry's optional `policies`, defaulting to the key's first segment. An amended instrument outside the policy set is skipped **and recorded** as excluded with the reason; it is never dropped. Routes added: HO 00 15 page 1, "Form HO 00 03 Only" (judgment: the form is named in its words, its tie to SPECIMEN-HO3 is the packet author's); CODA Endorsement 13, "ATTACHED TO AND FORMING PART OF POLICY NO.   GS-212C" (read).
5. **Reasons, each named.** `unresolved` has three: `documents_disagree` (no rule picks), `amounts_not_comparable`, `governing_instrument_absent`; `not_found` has `no_addressing_span`. Two moves, both recorded: `uncompared_agreement` is renamed `amounts_not_comparable`, because the same refusal now also covers the claim against the governing value, and one name for one refusal is clearer than two; `governing_instrument_absent` moves from `not_found` to `unresolved`, because the packet does address the question, and what is missing is the instrument the asserting document amends. `SlotVerdict.unresolved_detail` names the mismatch or both documents. `governing_reason` (no_conflict or resolved_by_rule) says how the governing value was chosen whatever the verdict, so a `contradicted` verdict names its rule too.
6. **Wording claims.** `kind = "wording"` gets no amount verdict. `arbitrate_wording` runs the same missing-document check and precedence rules over documents and returns the governing clause verbatim with document and page, marked not checked. The verdict is `quoted`, a fifth value that is explicitly not an answer, chosen over a separate flag so no reader can take a wording run for `supported`. Attack-pass clauses are surfaced as `clashes`, each a judgment route with its quote, never a code verdict.

**Why:** without (3) `contradicted` could never be produced and a wrong amount read as supported; without (4) a packet missing its base form was answered from what was left (README limitations, D5). The comparability change is what (3) needs: a claim states no basis, and under D6's rule no claim could ever have been compared with anything.

**Every verdict that moved** (before: as recorded; after: `pgrun familyb`, `pgrun verdict`, `pgrun derive`, replayed with no key):
- Family A, `pgrun verdict` and `pgrun derive`: unchanged, `unresolved (documents_disagree)`. New in the record: Endorsement 13 is excluded from the missing-document check (it amends GS-212C, outside FD960228). No value governs, so the claim is not compared.
- B-jewelry-endorsed, B-firearms-endorsed, B-silverware-endorsed: `supported (resolved_by_rule, endorsement_over_base → ho_00_15)` → `supported (no_conflict, endorsement_over_base → ho_00_15)`. The pairs ($1000 vs $1,000, etc.) are now compared and equal, so the rule named the governing form over agreeing values. Each claim equals the governing value.
- The five other family B packets: unchanged, `supported (no_conflict)`, now with the claim compared and equal.
- `--ablate`, comparator with rules disabled, the three endorsed packets: `unresolved (uncompared_agreement)` → `supported (no_conflict)`. Under D9 precedence is no longer what makes these three supported.
- Counterfactual tests: Reliance moved into scope (`later_effective_date` fires) went from `supported (resolved_by_rule)` to `unresolved (amounts_not_comparable)` against the author's claim, which states no basis while Reliance states "each loss"; a claim of "$500,000 each loss" is `supported (no_conflict)`. The cover note alone went from `supported` to `unresolved (amounts_not_comparable)` for the same reason ("each Claim" vs no basis).
- New packets (`data/family_b/labels_d9.json`): B-jewelry-wrong-endorsed ($1,500) `contradicted`, governing ho_00_15; B-jewelry-endorsement-alone `unresolved (governing_instrument_absent)`; B-jewelry-wording-endorsed `quoted`, HO 00 15 item 5 governing, HO 00 03 item 5 shown as a judgment clash.
