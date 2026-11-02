# Items outside the UI session (from the TC17 journey review)

Source: `product-review.md` in this folder. The UI session does not touch these files; they are for the owner and the backend/AI lane. Nothing here changes status code.

## AI / labelling
- **P17 Support precision.** Part 1 "supports" that the second read says do not mention the part. Some supports may be mislabelled. Needs a labelling-precision check on TC17 part 1.
- **P6 Part-scoped relevance.** Part 2 repeats the same ~12 supports as part 1. Relevance is not scoped to the part. Likely after 4 Nov.
- **P12 Claim splitter.** Produces fragments such as "from May 7, 2026." as a part. Needs self-contained parts. The UI will only label parts "Part N of M".
- **Weak sole contradiction.** TC17's only contradicting card is Undated and "not settled" (a bylaws sentence on effectiveness on adoption). Labelling-quality question: is it a true contradiction?

## Backend / pipeline
- **Pending state (tasks 6, 11).** New in-flight event in `run_review`; "pending" stays out of the saved review JSON. Needs the Streamlit host confirmed to re-render per event.
- **Host layout (not viewer files).** Landing title/purpose line and passcode order (P10), full file names without "0-" prefixes and a "3 files, 342 KB" line (P11), nested iframe scroll (P13) and light/dark theme match (P14) live in `app/streamlit_app.py`. Outside the UI-owned files, so they need an owner OK.

## Product decisions still open
1. Is "worst part wins" the overall rule, and may the UI state it in one sentence?
2. Where does the passcode live (last field or host-level gate)?
3. When the only contradicting card is "not settled", should the verdict stay red? (Code owns status.)
4. Is cross-part dedupe of repeated supports (P6) in scope before 4 Nov?
5. Third clause "{U} without a second read" in the class header (provisional from Wave 1).

## Added after the scan review (POD 7713)
- **No box on scans in map mode (REPRODUCED, FRT-03 pack, POD_7713_signed_scan.pdf).** Flag off: one card "Late? N", `box_status` approximate, 1 box. Flag on: two cards, both `unpinned`, 0 boxes. Cause: the transcript has 25 clean one-line entries (line 14 is "Late? N"), but in map mode `build_candidates` joins the lines into two big units of 7 and 8 lines, and `scan.locate()` only matches runs of up to `MAX_RUN = 3` lines, so it returns `unpinned`. The candidate units were identical before and after commit 4613096, so this is not that commit and not a UI regression (`proofgraph/` is unchanged by the UI work). Fix options, backend only, flag-off must stay byte-identical: (a) for scan pages in map mode make candidate units per transcript line (or 1-3 lines), more precise but more units to label (cap CAP=40); (b) raise `MAX_RUN` for map mode, cheaper but draws one big box over several lines.
- **`box_status` "located"** would raise a KeyError in the old render position map; the new ledger code handles any status.
