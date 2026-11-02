# Evidence map UI: copy spec (tasks 2, 9, 10)

Source: "Product decisions" in `2026-11-03-evidence-map-ui.md`, D39. Strings are exact; tests compare them literally. Flag-off output stays byte-identical.

## (a) Copy table

| Element | Exact string / template |
|---|---|
| Badge, check `disagrees` (second read not settled) | `Second read of this quote alone: not settled.` |
| Badge, check `agrees` | `Second read of this quote alone: confirmed.` |
| Badge colour | One CSS class (`mark second-read`), same colour for both. No `.disagrees` or `.agrees` colour or underline. |
| Class header | `{Label} ({N}): {C} confirmed by a second read of its quote alone, {S} need other passages to settle.` e.g. `Contradicts (3): 1 confirmed by a second read of its quote alone, 2 need other passages to settle.` N = C + S for cards with a second read. |
| Class header, no card needs settling | `Contradicts (3): 3 confirmed by a second read of its quote alone.` (omit the `S` clause when S = 0; omit the `C` clause when C = 0) |
| Class header, Supports collapsed | `Supports (4)` plus a control `Show all 4`. |
| Part summary line | `{a} supports, {b} contradicts, {c} weakens, {d} irrelevant (hidden), from {x} of {y} documents; {r} document referenced, not supplied`. Worked example: `4 supports, 2 contradicts, 1 weakens, 6 irrelevant (hidden), from 2 of 3 documents; 1 document referenced, not supplied`. Zero-count classes keep their term (`0 weakens`). Omit the `; {r} ...` clause when r = 0. Use `documents` when r != 1. |
| Group summary (task 2) | Built only from counts, document names and dates. Example: `3 passages from Bylaws.pdf, Minutes.pdf, 12 Mar to 4 Apr 2024`. |
| Default open on first paint | Verdict chip and part summary: always. Contradicts: first 3 cards open. Weakens: first 2 open. Supports: collapsed. About 6 cards total. |
| Pending chip | `Pending`. Neutral colour, never red, never "supported". |
| aria-label, badge | Equals the visible badge text. |
| aria-label, class header | Equals the visible header text. |
| aria-label, "Show all N" | `Show all {N} supporting passages`. |

## (b) Banned words (case-insensitive, whole rendered HTML, aria-labels and titles)

`disagrees`, `disagree`, `failed`, `unverified`, `wrong`, `flagged`.

Pytest list: `BANNED = ["disagree", "failed", "unverified", "wrong", "flagged"]` (prefix match covers `disagrees`). The internal check value `disagrees` and CSS class names may stay in code; they must not appear in visible text, `aria-label`, `title` or class attributes. Today's `CHECK_LABEL`, `UNCONFIRMED_TEXT` ("did not confirm") and `check_reason` output must be reviewed against this list (see Q1).

## (c) Acceptance criteria (pytest assertions)

Task 2 (`_summary`)
1. Output contains no `why` or `quote` text from any card (assert no substring of those fields).
2. Output contains only digits, document names, month names and years: strip those and assert only punctuation and the fixed words (`passages`, `from`, `to`) remain.
3. A one-document, one-date group yields the singular `1 passage` form with a single date, not a range.

Task 9 (copy table)
4. Render a fixture with one `agrees` and one `disagrees` card: exactly one `Second read of this quote alone: not settled.` and one `...: confirmed.` appear.
5. Both badges carry the identical class attribute, and the CSS has no colour rule on `.disagrees` or `.agrees` badges (no red, no `text-decoration: underline`).
6. No `BANNED` term appears in any rendered string, `aria-label` or `title`, for every check value (`agrees`, `disagrees`, `unavailable`, `not_run`).
7. Class header equals the template for N = 3, C = 1, S = 2, and a card whose check is not settled still adds to N (header count equals the `data-card-id` count in the class).

Task 10 (`_part_summary`)
8. Counts equal the card counts per relation in the fixture; irrelevant is counted in the line, and zero irrelevant cards are rendered in the DOM.
9. TC17-shaped fixture (4 supports, 2 contradicts, 1 weakens, 6 irrelevant, 2 of 3 documents, 1 referenced) yields exactly the worked example string; `r = 0` drops the trailing clause.
10. Default open: Contradicts shows 3 open cards, Weakens 2, Supports 0, and every card is still reachable in at most 2 clicks.

## (d) Open questions

1. `CHECK_LABEL` has `unavailable` ("Second check unavailable") and `not_run`, plus `NOT_DOUBLE_CHECKED_TEXT` and `UNCONFIRMED_TEXT`. Do they keep their wording (none uses a banned word, but "did not confirm" is close in spirit)? And do cards with these states count toward C or S in the header? Proposal: add a third clause `{U} without a second read` so N = C + S + U and nothing is silent.
2. Banned words forbid "disagrees", but the sprint note's own Risks and task 1 text uses it internally. Confirm the ban covers user-visible output only, not code identifiers and docs.
3. The decisions say "first 3 / first 2" while task 3 says "first 2 per class". Confirm the decisions win, so the task 3 acceptance check is rewritten before the engineer starts.
