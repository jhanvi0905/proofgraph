# Experiment: explain the second check (branch `feat/second-check-reason`)

Status: pre-registered 2 Nov 2026 before any code. Not merged. Merge only if every gate below passes AND the human says so.

## Scope (display and measurement only)
In:
- **P1.** `Card.check_answer` stores the checker's raw answer (`entails` / `contradicts` / `not_mentioned` / `None`). `check_card` still returns the same `agrees` / `disagrees` / `unavailable` / `not_run`. A fixed table `proofgraph/review/reasons.py` keyed on (relation, check_answer) gives the viewer line. No model prose reaches the UI.
- **Tabulation.** `scripts/tabulate_checks.py` reads cached checker answers only and prints relation x raw answer counts per case and pool. Output goes to `results/` through the report path only.
- **Bar runner.** A replay that runs the old code (commit `e6815ae`) and the new code on the same recorded inputs and compares.

Out (roadmap, not in this branch): P2 reorder, P3 multi-card, L1 loop, timeline feature, Muse Code gate, any edit to `prompts/*`, `status.py` logic, `engine/*`, `schema.py`, or new reason codes.

Owners: AI panel (Staff Applied AI Engineer) builds P1 plumbing. Product lead owns the reason table wording and viewer copy. Verification & Reasoning Engineer owns tabulation, replay and the bar verdict.

## Case pools
- **Old (examined):** TC17, TC12, frt-03, TC40, frt-07. These motivated the change.
- **Unseen:** every other case in `examples/suite/manifest.json` (21 cases) and the 8 own packs, with at least one cached review, using the manifest `split` field to report heldout separately. Never used to design the table.
- Cached data lives in the main checkout (`/Users/jhanviarora/proofgraph/cache`, `runs/`), read-only. No model call, no spend, no network.

## Gates (all must pass on BOTH pools)
- **G1 invariance.** Part status, `conflict`, overall status, card ids, card order, `check` badge, banners: 100% identical old vs new.
- **G2 no new calls.** Replay uses cache only. Any cache miss or transport call fails the gate.
- **G3 table.** Every (relation, check_answer) key, including `None` and an unknown string, has a line. A test fails if one is missing. No case-specific text (no TC ids, names, dates, amounts).
- **G4 wording.** Lines describe what the second check did; none says the claim or quote is true, false, wrong or correct (lint test). A `disagrees` card shows its raw-answer line. `unavailable` and `not_run` show no raw answer.
- **G5 repo health.** `make test` passes, `tests/test_boundaries.py` untouched and green.
- **G6 sample size.** The unseen pool has at least 8 cases and 12 cards that carry a check. Fewer means INCONCLUSIVE, which means do not adopt.

## "Better than now"
P1 cannot raise accuracy and must not claim to. It is better only if reviewers can tell why a check disagreed. Measures:
- **Q1.** Of all `disagrees` cards in the unseen pool, 100% show a line consistent with the raw answer (deterministic).
- **Q2.** Panel read: at least 6 `disagrees` cards from at least 3 unseen cases. At most 1 of 6 may read like a ruling on the claim.
- **Report** the unseen distribution of raw answers on `disagrees` cards (`not_mentioned` vs `entails` vs `contradicts`) with n. This is a measurement, not a pass condition, and shows whether TC17-style "needs more context" is common or rare.

## Decision rule
Adopt (propose merge to the human) only if G1 to G6 pass, Q1 is 100% and Q2 holds. Otherwise the branch stays unmerged and `main` is unchanged. A failed gate gets one fix attempt by the owner, then escalates to an Opus review. No claim of accuracy gain either way.
