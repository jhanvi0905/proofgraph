# Preregistration: family B transfer run

Written before any family B run, and committed in the same commit as `data/family_b/labels.json`. The domain layer is frozen at tag `domain-freeze` (commit `b353e20`, [DECISIONS.md](DECISIONS.md) D8), and `tests/test_freeze.py` checks it by hash. Only orchestration may still change: running the frozen passes once per source file, since a family B packet combines two PDFs.

## What runs

Eight packets on a specimen homeowners policy assembled from ISO HO 00 03 04 91 and HO 00 15 04 91. There are four Coverage C special limits (money, jewelry theft, firearms theft, silverware theft), each tested twice:
- once on the base form alone;
- once with the endorsement.

The endorsement replaces items 5–7 and leaves item 1 (money) alone. Each packet runs once: claim file → atomize → admit → retrieve → support and attack → assertions → arbiter.

## Predictions

1. **Transfer scores worse than family A.** On family A, the pipeline's verdict matched the hand labels on the one slot tested (1 of 1). On family B, I expect **at least 1 of the 8 packets** to get a verdict, reason, rule or governing instrument different from its label.
2. **The system decides, for the first time.** In at least one of the three endorsed packets (jewelry, firearms, silverware), `endorsement_over_base` fires and the verdict is `supported (resolved_by_rule)` with governing instrument `ho_00_15`. Before this run, no packet has produced a rule firing on real documents; only counterfactual tests have.
3. **Right verdict, wrong evidence, in at least one packet.** `$1000` appears in four items of HO 00 03's block (securities, watercraft, trailers, jewelry). A pass can point at the wrong item and still produce the right verdict, because the amounts are equal. I will report, per packet, whether the cited line is the gold line, separately from whether the verdict matches.
4. **A known blind spot, stated in advance.** HO 00 15 keeps the amounts but widens the scope from "theft" to "theft, misplacing or losing". The arbiter compares amounts only, so it cannot see that change. A correct verdict on the endorsed packets does not mean the system understood what the endorsement changed.
5. **Recall is not a transfer measure here.** Admission scopes are one block per document, so retrieval sees few passages and recall@10 will be high by construction. It will be reported, but it is not evidence of transfer.

## What will be reported, whichever way it lands

For each packet:
- the verdict, reason, rule and governing instrument, against its label;
- whether each gold line was cited;
- pass failures, repairs and rejects;
- tokens.

Plus the totals, the counts for predictions 1–3, and the commit that produced them. Nothing in `data/family_b/` changes after this commit. If a label turns out to be wrong, that goes in the report as a wrong label. It does not get edited.
