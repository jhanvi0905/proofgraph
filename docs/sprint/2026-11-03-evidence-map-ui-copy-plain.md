# Evidence map UI: plain-word copy (supersedes the copy spec where it differs)

Test for every string: a first-time reader, such as someone at the company the case is about, understands it cold. One term, one meaning. Counts, names and dates only; no rule, no confidence, no AI text. Banned in visible text, aria-labels and titles: disagree, failed, unverified, wrong, flagged.

## (a) Answer-first sentence (above the verdict chip)

Template, one sentence per claim part, joined in part order. Strongest finding first inside a part.
`Claim part {i}: {a} passages back it up{, {c} go against it}{, {w} cast doubt}. {Detail}.`
Detail for each going-against or doubt passage: `{doc}, p{n}, {date or "no date found"}, second check {confirmed|not sure}`. If one passage only, name it. If c = 0 and w = 0, say `none go against it`. Always show backing and opposing counts together.

**TC17 (2 parts):**
> Claim part 1: 16 passages back it up and 1 casts doubt ({doc}, p{n}). Claim part 2: 12 passages back it up and 1 goes against it ({doc}, p2, no date found, second check not sure).

**TC40 (illustrative counts, short):**
> 2 passages back up this claim ({doc A}, p{n}; {doc B}, p{n}). None go against it.

Then the verdict chip (labels in b), then the legend. The sole opposing passage is never hidden or softened: "second check not sure" sits in the same sentence.

## (b) Glossary (old -> new)

| Old | New |
|---|---|
| Contradicted / Weakened / Supported | Goes against the claim / Casts doubt on the claim / Backs up the claim |
| Not found / Can't tell / Checking / Error | Nothing found about this / Not enough to decide / Still checking / Could not check |
| Contradicts / Weakens / Supports (lanes, group headers) | Goes against it / Casts doubt / Backs it up |
| Second read of this quote alone: confirmed | Second check: confirmed |
| Second read of this quote alone: not settled | Second check: not sure |
| Second check unavailable / not run | Second check: not available / Second check: not done |
| Part 2 of 3 | Claim part 2 of 3 |
| 1 document referenced, not supplied | Mentioned but not uploaded: 1 document |
| Undated | No date found |
| Group header `Contradicts (3): 1 confirmed by a second read..., 2 need other passages to settle.` | `Goes against it (3): 1 confirmed by the second check, 2 not sure.` (add `, {U} not checked` when U > 0) |
| Counts line `4 supports, 2 contradicts, 1 weakens, 6 irrelevant (hidden), from 2 of 3 documents; 1 document referenced, not supplied` | `4 back it up, 2 go against it, 1 casts doubt. 6 passages not about this part are hidden. From 2 of 3 uploaded documents. Mentioned but not uploaded: 1 document.` (zero counts kept: `0 cast doubt`) |
| Show all 4 (aria: Show all 4 supporting passages) | Show all 4 (aria: Show all 4 passages that back it up) |
| Pending | Waiting (never red, never "backs up") |

## (c) Legend, caption, aria

**Legend (one line, under the verdict):** `We split your claim into parts and checked each one against your documents. Each mark is one passage; click it to read it.`

**Stance-map caption (under the chart):** `Circle = backs it up, triangle = casts doubt, diamond = goes against it. Solid = second check confirmed, hollow = second check not sure. Dashed row = documents mentioned but not uploaded. One passage that goes against a claim is enough to count against it.`

**Mark aria-label:** `{Goes against it|Casts doubt|Backs it up}, {document}, page {n}, {date|no date found}, second check {confirmed|not sure}`
e.g. `Goes against it, Bylaws, page 2, no date found, second check not sure`.
Dashed-row mark: `Mentioned but not uploaded: {name}, cited {k} times`. Empty column label: `No date found`.

## (d) Acceptance (pytest)

1. Answer sentence contains the count of backing passages and the count of opposing passages for every part, equal to card counts per relation in the fixture.
2. TC17 fixture yields exactly the worked sentence; with c = 0 and w = 0 it contains `none go against it`.
3. A sole opposing card with check `disagrees` renders `second check not sure` inside the answer sentence.
4. Answer sentence has no model text: it matches the template after removing digits, document names and dates.
5. None of the old terms (`Second read`, `referenced, not supplied`, `Undated`, `Part 2 of`, `Contradicts (`, `weakens`) appears in visible text, aria-labels or titles; none of the banned words does either, for every check value.
6. Legend text is present exactly once and precedes the first part; the caption is present once per map.
7. Each mark's aria-label equals the template; shape matches relation and fill matches check state (confirmed filled, all other states hollow).
8. Cards with no date appear only in the `No date found` column; each referenced document gives one dashed mark.

## (e) Open questions

1. "Backs it up / goes against it" vs keeping "supports / contradicts" in lanes and chips: the plain pair is longer. Confirm plain wins, or keep the verbs and drop only the verdict chip wording.
2. Second-check states `not available` and `not done` render as hollow marks, the same as "not sure". Acceptable, or give them a third look?
3. If the claim has more than 3 parts, the answer sentence runs long. Cap at 3 parts and add `and {k} more parts below`?
