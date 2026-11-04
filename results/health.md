# Health lines (M6)

Free analysis of the recorded runs, from `scripts/health.py` (`uv run python scripts/health.py`); no model call. Runs: suite run 1 (`runs/review-on.jsonl`), suite run 2 after error analysis (`runs/review-on-2.jsonl`), clean check (`runs/clean-on.jsonl`). Gold is read by the script only. Counts are over the cards and parts the runs recorded; nothing here is a new measurement of correctness.

## 1. Quote alignment

Each statement's quote is aligned to the page text. Pinned means a card's quote was snapped to the word boxes of a text page (what the review page calls a valid quote); a transcribed scan can only be approximate.

| | Suite run 1 | Suite run 2 | Clean check |
|---|---|---|---|
| statements exact | 686/1554 (44%) | 778/1496 (52%) | 432/1192 (36%) |
| statements normalised | 835/1554 (54%) | 705/1496 (47%) | 745/1192 (62%) |
| statements fuzzy | 22/1554 (1%) | 6/1496 (0%) | 6/1192 (1%) |
| statements unmatched | 11/1554 (1%) | 7/1496 (0%) | 9/1192 (1%) |
| cards pinned | 203/222 (91%) | 147/186 (79%) | 45/47 (96%) |
| cards approximate | 19/222 (9%) | 38/186 (20%) | 2/47 (4%) |
| cards unpinned | 0/222 (0%) | 1/186 (1%) | 0/47 (0%) |

## 2. Rejected statements

Nothing is dropped silently. `unmatched` statements (above) are kept as unclear and never decide. Rejections recorded per part by the link, compare and full-read steps, and by graph construction (read from the graph cache, so only graphs found there are counted):

| | Suite run 1 | Suite run 2 | Clean check |
|---|---|---|---|
| per part: compare | 2 | 2 | 0 |
| per part: unaligned_quote | 1 | 0 | 0 |
| per part: unknown_id | 0 | 3 | 8 |
| graph build: ambiguous_override_target | 0 | 2 | 0 |
| graph build: member_not_in_quote | 202 | 165 | 366 |
| graph build: relation_not_in_quote | 17 | 29 | 12 |
| graphs found in cache | 29 | 29 | 30 |

## 3. First read against the blind second reader

Rows are the first read of a statement (the comparator's label as shown on its card: supports, or opposes = contradicts or weakens). Columns are whether the second reader, who sees the statement without the first read's label, agrees. Only statements that were second-read are counted.

**Suite run 1**

| First read | Second reader agrees | Second reader disagrees | Agreement |
|---|---|---|---|
| supports | 10 | 9 | 10/19 (53%) |
| opposes | 83 | 25 | 83/108 (77%) |
| all | 93 | 34 | 93/127 (73%) |

Not second-read on a card: 95 (not_run 95).

**Suite run 2**

| First read | Second reader agrees | Second reader disagrees | Agreement |
|---|---|---|---|
| supports | 17 | 65 | 17/82 (21%) |
| opposes | 37 | 19 | 37/56 (66%) |
| all | 54 | 84 | 54/138 (39%) |

Not second-read on a card: 48 (not_run 47, unavailable 1).

**Clean check**

| First read | Second reader agrees | Second reader disagrees | Agreement |
|---|---|---|---|
| supports | 12 | 7 | 12/19 (63%) |
| opposes | 18 | 10 | 18/28 (64%) |
| all | 30 | 17 | 30/47 (64%) |

Not second-read on a card: 0 (none).

## 4. Walk against the full read

The typed walk and an independent full read each pick the statements that bear on a part; the flag compares the relevant sets. The second table splits the parts by whether the final part status matched the gold part status (parts are matched by id; a part with no gold counterpart is left out).

| Flag | Suite run 1 | Suite run 2 | Clean check |
|---|---|---|---|
| agree | 2 | 12 | 9 |
| partial | 38 | 28 | 12 |
| disagree | 8 | 2 | 2 |
| both_empty | 0 | 6 | 7 |

Parts answered as gold, by flag:

| Flag | Suite run 1 | Suite run 2 | Clean check |
|---|---|---|---|
| agree | 0/0 | 6/9 (67%) | 4/9 (44%) |
| partial | 12/34 (35%) | 8/25 (32%) | 8/12 (67%) |
| disagree | 1/6 (17%) | 0/2 (0%) | 1/2 (50%) |
| both_empty | 0/0 | 4/4 (100%) | 6/7 (86%) |

## 5. Reachability at the hops each gold path needs

The clean check has no gold relations (its gold is a label only), so it is not shown. For every suite gold relation that supports, contradicts or weakens: the walk is run from every entity any part of the claim linked, at 1, 2 and 3 hops (3 is what ships; the walk rules, hub brake and unclear edges apply; this is the walk before ranking and truncation), and the statement is the one sharing at least half of the gold quote's words. Parts are not matched to gold parts, so a relation counts as reached when the walk for any part reaches it.

| | Suite run 2 |
|---|---|
| gold relations | 61 |
| no statement carries it | 4 |
| no linked entity | 0 |
| walk reaches at 1 hop | 48 |
| walk reaches at 2 hops | 1 |
| walk reaches at 3 hops | 0 |
| connected beyond the walk | 7 |
| not connected | 1 |
| graph not in cache | 0 |

## 6. Why the pinned share fell (91% to 79%)

Cards on pages that were pinned in run 1 and are approximate in run 2 (same case, document and page):

| | |
|---|---|
| flipped pages | 5 |
| flipped cards run 1 (pinned) | 10 |
| flipped cards run 2 (approximate) | 11 |
| cases | TC38, TC45, TC46, fin-08 |

Reading the numbers: run 1 had 203 pinned of 222 cards; run 2 has 147 of 186. Counting the flipped cards as pinned would give 157 of 186 (84%), so about 5 of the 12 points are this one effect and the rest is a change in which cards are shown (fewer cards on text pages, more on pages that were always scans). The flipped pages are the ones the text-quality check (Iteration 2 E) sends to transcription, whose boxes can only be approximate (`proofgraph/review/scan.py`). Scoring the PDF text layers locally with `proofgraph.review.text_quality`: the TC38, TC45 and TC46 agreement has 3% to 11% of tokens as `(cid:` codes on pages 1 to 5 (limit 2%), and the fin-08 earnings release and fact sheet have 6% to 9% (the 10-K/A is repaired by the tighter retry, so it stays on the text path). This is the check working as designed: the text becomes readable and the box becomes approximate.
