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
