# Pre-registration: unseen run of the evidence map (PROOFGRAPH_EVIDENCE_MAP=1)

Frozen 2 Nov 2026 before the run. Code: branch `feat/evidence-map` @4613096. No prompt, threshold or code edit after the first run; a failed bar means the flag stays off and unmerged.

## Sample
The 9 unseen suite cases whose Evidence Packet is entirely PDF: Test Case 1, 2, 5, 6, 7 (Company archive), 13, 15 (Braddock record), 39, 42 (ContractNLI). Honest label: these were used for the earlier quote-bounds and evidence-set arms (statuses seen), but never to design or tune the evidence map, so they are unseen for this design, not fresh. TC17 and TC40 are reported separately as the design cases. A stricter run later needs human-written sealed claims over documents never used. Answer keys, the Why column and gold labels are not used; nothing is scored against gold.

## Arms
Flag-off single-card path (today) versus map mode, same claims and files, same cache dir. Hard spend stop: ledger at start + $0.60. No re-runs.

## Bar (mechanical, no accuracy claim, per source group with n)
- M1 flag-off replay identical to the old code (already passing in CI).
- M2 every shown card: quote is an exact substring of its page text, no duplicate within a part, document name present, a dated item's date appears in its stated source span.
- M3 coverage: for every case with 2 or more documents, report whether passages from 2 or more documents are shown; list each exception with the reason (no candidate, labelled irrelevant).
- M4 status stability against the flag-off arm: every status change is listed with the card that caused it; an Opus panel read judges each new red or amber; fail if more than 1 in 6 read as overreach or padding.
- M5 label inflation: the share of examined passages labelled relevant per part; fail if the median exceeds 60%; report the median and the maximum.
- M6 no errors and no hangs: every review completes in under 90 seconds with no error banner.
- M7 cost and speed: median cost per review at most $0.08 and median wall time at most 40 seconds.
- M8 'Referenced, not supplied' nodes are listed for a hand check (reported, not a pass condition).
Decision: adoptable as an optional flag only if M1 to M6 pass and the human says yes. Otherwise it stays off and unmerged. The recorded demo path stays single-card.

## Result (run once, 2 Nov 2026, 9 cases, no re-runs, spend $0.20 of the $0.60 stop)
- M1 pass (flag-off replay 0 differences). M2 pass: 26 cards, all pinned, 0 duplicates, all with a document name (date source spans not individually verified; see caveat). M5 pass: relevant share median 23%, max 50%. M6 pass: 0 errors, slowest 20.5 s. M7 pass: median $0.024 and 18.1 s per review (ledger deltas; some calls were cache hits from earlier arms).
- M3 (reported): of 7 cases with 2 or more documents, 3 showed passages from 2 or more documents (TC1, TC7, TC13); TC2, TC6 and TC15 showed one document, TC5 showed none (0 of 5 examined relevant).
- M4: one status change against the flag-off arm: TC39 cannot_tell to weakened, from three weakens cards (an exclusion for public information, an expiry after three years, a legally-compelled-disclosure carve-out). Read by the builder, not by the pre-registered Opus panel: relevant qualifiers, not padding. No new reds.
- Caveats: dates from the 'first page' tier can be an unrelated date (TC39 shows 2002-08-02 on a 2018 file); the sample was seen in earlier experiments; no accuracy claim.
Decision: M1 to M6 pass, so adoptable as an optional flag if the human says yes; the recorded demo path stays single-card.
