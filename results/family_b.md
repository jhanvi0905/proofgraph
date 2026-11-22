# Family B transfer run: results

Run once, at commit `eeb9a2f`. The domain layer was frozen at tag `domain-freeze` (`b353e20`), and the labels and preregistration were committed at `db65334`, before the run. `git diff domain-freeze` over the 13 frozen files is empty. The run replays with no API key: `uv run pgrun familyb`.

| Packet | Label | Pipeline | Match | Gold lines cited |
|---|---|---|---|---|
| B-money-base | supported (no_conflict) | supported (no_conflict) | yes | 1/1 |
| B-jewelry-base | supported (no_conflict) | supported (no_conflict) | yes | 1/1 |
| B-firearms-base | supported (no_conflict) | supported (no_conflict) | yes | 1/1 |
| B-silverware-base | supported (no_conflict) | supported (no_conflict) | yes | 1/1 |
| B-money-endorsed | supported (no_conflict) | supported (no_conflict) | yes | 1/1 |
| B-jewelry-endorsed | supported (resolved_by_rule, endorsement_over_base → ho_00_15) | same | yes | 2/2 |
| B-firearms-endorsed | supported (resolved_by_rule, endorsement_over_base → ho_00_15) | same | yes | 2/2 |
| B-silverware-endorsed | supported (resolved_by_rule, endorsement_over_base → ho_00_15) | same | yes | 2/2 |

**8 of 8 packets match their labels.** That score overstates the evidence, and the next section says why.

## The informative sample is four packets

The four base-only packets have one instrument each, so no precedence rule can fire in them. They test that the right item is found and its amount parsed. They could still have failed, as `not_found` (nothing cited) or as a disagreement inside one block (two different items cited), but they cannot test transfer of precedence. **The informative sample is the four endorsed packets.** Three of them are packets where the endorsement replaces the item. The fourth, money, is the control: the endorsement leaves item 1 alone, and no rule may fire.

## Where precedence is what decides

The same recorded assertions, scored three ways with no new model calls (`uv run pgrun familyb --ablate`):

| Packet | Naive build: string comparison, no rules | Frozen comparator, precedence disabled | As built |
|---|---|---|---|
| B-jewelry-endorsed | documents_disagree (`$1,000` ≠ `$1000`) | unresolved (uncompared_agreement) | supported (resolved_by_rule → ho_00_15) |
| B-firearms-endorsed | documents_disagree (`$2,000` ≠ `$2000`) | unresolved (uncompared_agreement) | supported (resolved_by_rule → ho_00_15) |
| B-silverware-endorsed | documents_disagree (`$2,500` ≠ `$2500`) | unresolved (uncompared_agreement) | supported (resolved_by_rule → ho_00_15) |
| B-money-endorsed | supported | supported (no_conflict) | supported (no_conflict) |

**In three packets, string comparison fails and precedence succeeds.** Each fix does different work:
- the numeral comparator removes the disagreement that string comparison invents;
- precedence turns an agreement that cannot be certified (no basis is stated on either line) into a decision that names the governing instrument.

Without precedence, the frozen system stays `unresolved` on all three. In the control packet, all three builds agree.

## The freeze held

`git diff domain-freeze eeb9a2f` over the 13 files in `data/freeze.json` is empty, and `tests/test_freeze.py` passes at the run commit. The domain layer that produced these verdicts is byte-identical to the one frozen before any family B label was written.

## What the transfer claim covers

- **Agreement plus one rule.** Family B exercised `supported (no_conflict)` and `supported (resolved_by_rule)` via `endorsement_over_base`. It never produced `unresolved`, `not_found` or `contradicted`, and `later_effective_date` did not fire (both forms are undated).
- **The refusal path has only been exercised on family A**, as `unresolved (documents_disagree)` on the retention slot. `not_found` has never been produced on a real packet in either family, only in a unit test. `contradicted` is not built.
- No pass failed, needed a repair, or had a quote rejected.
- Every assertion cites exactly its gold line, with no extra lines.
- The attack pass correctly found nothing in all 9 of its calls with evidence lists returned empty.
- 32 model calls, 20 of them real (the rest repeated an identical prompt and replayed from the cache): 27,643 input and 1,620 output tokens on Claude Opus 5.5, about $0.14.

## Against the preregistration

1. **Transfer scores worse than family A: falsified.** I predicted at least 1 of 8 wrong; 0 were. Reported as a wrong prediction, not reinterpreted.
2. **The system decides for the first time: confirmed, 3 of 3.** `endorsement_over_base` fired in all three endorsed packets, naming `ho_00_15` as governing, and did not fire in the money packet, where the endorsement leaves the item alone.
3. **Right verdict, wrong evidence in at least one packet: falsified.** `$1000` appears in four items of the base form's block, and every pass still pointed at the right one.
4. **The arbiter is blind to the scope change: confirmed for the verdict, but the passes saw it.** The verdict line reports equal amounts and nothing more. All three HO 00 15 readings in the trace say "(also misplacing or losing)". The change is visible to a reviewer reading the evidence, not in the verdict.
5. **Recall is high by construction:** not used as a transfer measure.

## What this does and does not show

- **The decision was made over agreeing values.** In each endorsed packet both forms state the same amount ($1000 vs $1,000). Neither line states a basis, so the pair cannot be compared, and `resolved_by_rule` means the endorsement governs a pair that could not be checked against each other. It does not mean the documents stated different numbers. It is the first time a rule picked a governing instrument on real documents, but no disagreement in value was resolved.
- **The hard part was labelled by hand.** Which policy each form describes (`SPECIMEN-HO3`, a specimen policy the packets assemble, since ISO forms carry no number) and each scope (the page-2 special-limits blocks) are labels. The run tests reading, pointing at values, comparison and precedence inside those scopes, not identification.
- **The packets are easy.** One layout family, one page, and each amount on its own line. Eight packets demonstrate the pipeline end to end on documents its domain layer was not written against. They do not estimate an error rate.
- **One change landed after the labels and before the run.** The dry run (no model calls) admitted nothing, because a PDF scope block had to sit inside one extracted chunk. Admission (`retrieve.py`, not frozen) was fixed at `eeb9a2f` to match a block across chunks. No model output existed when it was made.
