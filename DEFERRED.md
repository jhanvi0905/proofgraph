# Deferred

Items found and deliberately left. Each has the reason it waits. Line numbers refer to `data/raw/gillette_10k405_1996.txt`.

## Found in the packet

- **London's primary limit: $20M or two $10M layers.** Item VII (Endorsement 13) lists London twice: `Primary … 757/FD960228 … $10M` (line 1325) and `1st Excess … 757/FD960229 … $10M` (line 1326). The ACE binder's program table gives `London $20M Primary ($0/$0/$1M)` (line 1389). The Reliance binder gives `Primary Carrier: Lloyd's London` / `Limits of Liability: $20,000,000` (lines 1741–1742). This is a second conflict, on limits rather than retention: two documents treat London as one $20M primary, and the schedule splits it. *Deferred:* the retention verdict does not need it, and chasing it costs the family B run. It also weakens the route `reliance_primary_carrier_to_fd960228` (see that record).
- **A fourth asserter on the retention slot.** The same ACE line (1389) states the primary retention as `($0/$0/$1M)`. It agrees with Item VII and the cover note, so the verdict does not change. It is still an unrecorded asserter on the headline slot. *Deferred:* recording it needs a route like Item VII's (position 3 of a composite cell, plus `London` → FD960228). Add it when the slot is next touched. **It does double duty:** the same line is ACE's program table, so it is also a third statement on the London limits split above. Note that it sides with Reliance's $20M against Item VII's two $10M layers, so it adds to the conflict rather than settling it. Un-defer both together.

- **Retrieval misses Item VII's rows for other layers.** In `data/retrieval_eval.json`, `chubb_do_limit` and `erma_limit` miss `coda_end13`. Item VII's whole schedule is a single span (one table), and its policy numbers drift from the binders': `81385411B` vs `81385411`, `752034765-96` vs `752-034765-96`. *Deferred:* found while measuring another change, so fixing it now would be fitting to the eval. Candidate fixes are splitting table rows into spans, or normalising identifiers. Either must be judged on queries written before the fix.

- **A fifth asserter, found by the support pass.** The FD960229 cover note (the first excess layer) restates the primary's terms: `POLICY NO: FD960228 … RETENTION: USD NIL/USD NIL/USD 1,000,000`. It agrees with $1M, and unlike Item VII it states USD. It is not in `data/mappings.json`. *Deferred:* it becomes an assertion when pass evidence is turned into assertions (next step). Recording it by hand now would be labelling what the pass already found.

- **The passes cannot cross-reference identification.** Each pass reads passages one at a time. Once the claim names FD960228, the model accepts only passages that name that policy themselves. Reliance's block ("Primary Carrier: Lloyd's London", $500,000) never does, so attack missed it in 2 of 3 runs, and support dropped the cover note's I.B line in the latest one. The link from Reliance to FD960228 runs through Item VII's row, the same step the hand route `reliance_primary_carrier_to_fd960228` records as judgment. *Deferred:* the fix is a design question (give the passes the identification routes, or a step that resolves which policy a passage is about), not a prompt edit. Re-running the prompt until attack finds Reliance would be tuning to the answer.

## Done before the family B run

- ~~Assertions reject PDF citations.~~ Citations now carry a typed locator: `raw_offsets` for text sources, `page_quote` (a single-line quote that must occur exactly once on the page, as found by the PDF parser) for PDFs. Both are verified by `checker.verify_citation`. No citation is checked against this project's own text rebuild.
- ~~The atomize prompt's worked example is FD960228.~~ Model-facing examples are now an invoice (`INV-2291.freight.unit_price`). `tests/test_no_family_literals.py` checks code and model-facing data for either family's literals. It sees literals, not shape.

## Code

- **`parse_amount` and `numeral` duplicate the number rules.** `parse_amount` still needs decimals and the stated currency. *Deferred:* they agree today; fold `parse_amount` onto `numeral` before a second number format arrives.
- **Atomize sources claim fields (D1 on the claim side).** The test claim still carries USD and "each claim" copied from the cover note. *Deferred:* atomize reads no document, and the verdict path does not use it yet.
- **Rule 1 has no test showing it can flip a verdict.** `endorsement_over_base` never fires in family A (D5). *Deferred to family B,* where a mutation inserts a superseding endorsement. Until then rule 1 is untested decoration, and the README says so.
