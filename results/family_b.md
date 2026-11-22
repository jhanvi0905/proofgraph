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

**8 of 8 packets match their labels** (n = 8).
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
