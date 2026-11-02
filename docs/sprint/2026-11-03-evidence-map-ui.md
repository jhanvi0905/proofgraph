# Evidence map UI: strip, groups, progressive cards (frontend tasks)

## Handoff for the UI session (read this first)

**Branch.** Start from `feat/evidence-map` (it holds the whole stack: reason line, document names, candidate generator, evidence map, date fix, this note). Make your own branch: `git switch -c feat/evidence-map-ui feat/evidence-map`. Open PRs against `feat/evidence-map`, **not `main`**. Nothing here is merged to `main`; the recorded demo path stays the single-card path.

**Read first.** This file; `docs/council/2026-11-02-evidence-map-unseen-prereg.md` (what was tested and what was not); D39 in `docs/11-decision-log.md`; the 'Evidence map' paragraph in `docs/03-architecture.md`.

**Flag and the hard rule.** Everything is behind `PROOFGRAPH_EVIDENCE_MAP=1`, off by default. With the flag off the output must stay byte-identical: keep `tests/fixtures/review_tc40_render_golden.html` and `viewer_single_card_golden.html` passing and `scripts/replay_compare.py` at 0 differences.

**What you own / do not touch.** Own: `app/viewer/render.py` (`_map`, `_part`, `_card`, `EVIDENCE_CSS`), `app/viewer/viewer.html` (JS), viewer tests. Data already on each part: `Part.evidence_map` (ordered `MapItem`s: card or referenced) and `Part.map_counts` (examined, relevant, suggested, shown). Do not edit `status.py`, `check.py`, `label.py`, `candidates.py`, `timeline.py` or prompts; the status is computed by code and a UI must never change it.

**Run it.** Tests: `uv run pytest -q` (move `.streamlit/secrets.toml` aside while running; one test expects no passcode) and `uv run python scripts/replay_compare.py`. App: `PROOFGRAPH_EVIDENCE_MAP=1 CACHE_DIR=/Users/jhanviarora/proofgraph/cache SPEND_LIMIT_USD=<current ledger + a small cap> uv run streamlit run app/streamlit_app.py --server.port 8502`, keys from `/Users/jhanviarora/proofgraph/.env` (never print them), your own gitignored `.streamlit/secrets.toml` with `APP_PASSCODE`. Spend ledger was about $2.71; a live TC17 review costs about $0.04 and TC40 about $0.03; repeats hit the cache. Test inputs: the PDFs in `~/Downloads/Dataset/Test Cases/Test Case 17/Evidence Packet` and `Test Case 40` (PDF files only; never open `Solutions/` or `_Evaluation/`). Build UI fixtures from the hand-built ones in `tests/test_evidence_map.py` first so most work costs $0.

**Order.** Tasks 1, 2, 9, 10, 3, 4, 5, 7 first (pure display, no backend change). Tasks 6 and 11 (cards appearing as they arrive, 'Pending' chip) need a new pipeline event in `run_review`; do them last and keep the 'pending' value out of the saved review JSON.

**Known facts to design around.** A live review takes about 20 s; a document with no explicit header date is Undated (the earlier 'first page' date guess was removed on purpose); the same unsupplied letter can be cited several times (one marker per distinct reference); about half of the cards show 'not settled' from the second check, which is why the product copy below replaces the old wording. Open questions are at the end of this file.

## Goal

Replace the one long ordered list per part (19 and 12 cards on TC17, 13 of 19 carrying "Second check disagrees") with a compact view that reads without scrolling: a timeline strip per part, one collapsible group per relation with a code-built summary, the first two cards open, near-duplicates merged, unconfirmed cards folded away, and one marker per distinct unsupplied reference. Flag stays `PROOFGRAPH_EVIDENCE_MAP` (off by default); flag-off output stays byte-identical. Plain HTML/CSS/JS inside `render.py` and `viewer.html`, no dependency, no model text in any summary.

## Frontend tasks

| # | Task | Size | Owner role | Acceptance check | Order | 
|---|------|------|-----------|------------------|-------|
| 1 | `_map_items(part, cards)`: pure function that dedupes referenced items by normalised `ref_text` (one marker, "cited in N places"), merges near-duplicate cards (same doc and page, or adjacent pages with same relation and date) into one primary plus `also:` list, and splits out cards with `check == "disagrees"` | M | Frontend engineer | Unit test on a TC17-shaped fixture: 4 repeated references become 1; merged cards keep every `data-card-id` reachable; flag off changes nothing | 1 |
| 2 | `_summary(group)`: code-built one-line text per relation (count, distinct documents, date span) from card fields only | S | Frontend engineer | Test: string contains only numbers, document names and dates; no `why` or `quote` text | 2 |
| 3 | Rewrite `_map` to emit per-relation `<details>` groups: first 2 cards open, rest in a nested `<details>` "show N more", disagreeing cards in a collapsed "Not confirmed by the second check" inside the class; reuse `_card` and `check_reason` unchanged | M | Frontend engineer | TC17 p1: at most 2 cards per class visible on load; a card is reachable in at most 2 clicks; counts in summaries equal cards in the group | 3 |
| 4 | `_strip(part, items)`: inline SVG or flex strip, points grouped by day, colour by relation plus a distinct shape per relation (not colour alone), an Undated lane, one dashed marker per distinct reference; each point carries `data-card-id` | M | Frontend engineer | Three relations distinguishable in greyscale; undated lane present only when needed; day with several points shows a count | 4 |
| 5 | Viewer JS `reveal(card)`: on strip-point click, open ancestor `<details>`, then reuse `show`, `focus` and `scrollIntoView`; keyboard `j/k` skips collapsed cards or opens them | S | Frontend engineer | Click a point inside a collapsed group: group opens, card scrolls to centre, box highlights; `j/k` still works | 5 |
| 6 | Part shells and incremental render: render parts with a "Checking" chip first, re-render on each event; card `check` badge shows "checking…" and fills in | M | Frontend engineer | Shell visible before any part finishes; no layout jump when badges fill in; a finished page equals the old final render | 6, after backend event ticket |
| 7 | CSS in `EVIDENCE_CSS`: strip, group header, summary line, "show N more"; delete the `.map` list, `.map-rel`, `.map-date`, `.map-undated` rules and the `seen_dated` "Undated" separator logic | S | Frontend engineer | Dark mode and 375 px width render without horizontal scroll | 4 |
| 8 | Check against the live TC17 run in map mode, not the 2.4 MB review file: compare screens before and after | S | QA | Scroll length per part cut by at least half; every card still linked to its box | last |

## Risks

- Merging near-duplicates must never hide a contradicting card: merge only inside one relation, and keep every merged card's id clickable.
- A card whose second check disagreed is folded away: the group summary must still count it ("3 not confirmed"), so a contradiction is never silent.
- Task 6 needs a live host that re-renders per event. A static saved page cannot stream, so replay mode renders final state only.
- `CheckName` has no "pending" value. Add it only to the in-flight view, never to the saved `review-1` JSON.
- Dates are inferred: the strip must keep the "inferred from the text" caveat visible.
- Flag-off byte-identity is easy to break while editing `render()`; keep a golden test.

## Product decisions (from the journey map; these override the defaults above where they differ)

- **Default open on first paint, about 6 cards total:** the verdict chip and the part summary line always; Contradicts open with its first 3 cards; Weakens open with its first 2; Supports collapsed to its counts line with "Show all N". Task 3 uses these numbers, not "first 2 per class".
- **Second-check wording (replaces "Second check disagrees/agrees" everywhere):** badge "Second read of this quote alone: not settled." / "Second read of this quote alone: confirmed."; class header "Contradicts (3): 1 confirmed by a second read of its quote alone, 2 need other passages to settle." The words "disagrees", "failed", "unverified", "wrong" and "flagged" never appear. The badge uses one neutral colour for both states; only the verdict chip is coloured. It is never shown as a confidence score. (Today's `mark.disagrees` is red and underlined: change in task 7.)
- **Text outside the cards:** a code-built counts-and-sources line per class and per part, for example "4 supports, 2 contradicts, 1 weakens, 6 irrelevant (hidden), from 2 of 3 documents; 1 document referenced, not supplied". No AI-written summary this sprint.
- **Wait state:** a stage strip ("Reading documents, labelling passages, second checks (7 of 19)"), the chip reads "Pending" until every check finishes, never red or "supported" while pending; copy "Results fill in as checks finish. Nothing is final until every check is done."
- **Cut for 4 Nov:** AI summary, per-card re-explanation, timeline polish, filters. Keep: collapse, counts line, badge copy, pending state, referenced nodes.
- **TC17 fallback note** if the recall fix does not pass its check: "Bylaws were uploaded; no passage from them was labelled relevant."

## Added frontend tasks

| # | Task | Size | Acceptance check | Order |
|---|------|------|------------------|-------|
| 9 | Second-check copy table in one place (reuse `check_reason`/`CHECK_LABEL`), neutral badge class | S | Test: no banned word in any rendered string or aria-label; both badges share one colour class | 2 |
| 10 | Part summary line `_part_summary(part, cards)` from counts, documents and the referenced list | S | Counts equal card counts; irrelevant counted, not rendered | 2 |
| 11 | Pending chip and stage strip | M | While checks are pending the chip reads "Pending"; after completion red needs a pinned contradicting quote | 6 |

## Open questions for the owner
- Whether "pending" may exist in the in-flight view only (recommended) and never in the saved review JSON.
- Near-duplicate merge rule: merge only inside one relation (recommended), keep every merged card's id clickable.
- Task 6 needs a live host that re-renders per event: confirm the Streamlit host before starting it.
