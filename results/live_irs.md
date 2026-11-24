# Live runs: IRS annual limits, uploaded through the app

**Not a preregistration.** The expected answers were written in a claims sheet before the runs, but that sheet was not committed first. Read this as a demonstration of the product path on documents it had never seen, not as a holdout. The clean holdout on tax documents is [`family_tax.md`](family_tax.md).

## Documents (US government works, text PDFs)

| Packet | File | sha256 | States |
|---|---|---|---|
| HSA limits | [Rev. Proc. 2023-23](https://www.irs.gov/pub/irs-drop/rp-23-23.pdf) | `cdc4574b…442ded` | 2024: $4,150 self-only, $8,300 family |
| | [Rev. Proc. 2024-25](https://www.irs.gov/pub/irs-drop/rp-24-25.pdf) | `6093d2e3…dc00` | 2025: $4,300 self-only, $8,550 family |
| 401(k) limits | [Notice 2023-75](https://www.irs.gov/pub/irs-drop/n-23-75.pdf) | `dbe86eb1…93ad` | elective deferral "increased from $22,500 to $23,000" (2024) |
| | [Notice 2024-80](https://www.irs.gov/pub/irs-drop/n-24-80.pdf) | `cbf7843c…59ad` | "increased from $23,000 to $23,500" (2025) |

## Path

Upload, confirm, type the claim, find the lines, check.
- **HSA documents:** kind set to "schedule of amounts" for both. Effective dates were typed with a reason, because each prints "calendar year 2025" with no day.
- **401(k) documents:** no grouping given (one set). Both effective dates were read from the printed "Effective January 1, 202X" ([D13](../DECISIONS.md)).
- **Lines:** every line was confirmed, except where noted below.

## Results

| Claim | Expected | Result | Why |
|---|---|---|---|
| HSA self-only limit is $4,300 | right | **right** | Rev. Proc. 2024-25 controls over 2023-23: a later effective date overrides an earlier one. The first time this rule decided a claim on uploaded documents. |
| HSA self-only limit is $4,150 | wrong | **wrong** | Same rule; governing $4,300. |
| 401(k) elective deferral limit is $23,500 | right | **right** | Notice 2024-80 controls. Each "from X to Y" line came back with the right figure already pointed at, so no pick was needed. |
| 401(k) elective deferral limit is $23,000, every line confirmed | wrong | **can't be settled** (documents disagree) | For this claim the reads also pointed at the "from **$23,000**" figure inside Notice 2024-80. The newer notice then appeared to state two amounts, so the later-date rule would not pick, and the check refused. |
| Same claim, that line set aside by a person ("the old figure, superseded within this notice") | wrong | **wrong** | Notice 2024-80 controls and states $23,500. The set-aside line and its reason are shown on the result. |

## What this shows

- **The later-date rule works on uploads, with dates read from the page.** It never fired in the tax holdout.
- **"From X to Y" is the strike-and-insert trap from [`family_tax.md`](family_tax.md) in a milder form.**
  - The old figure is in the new document's own text, and a verified quote of it is still wrong as "what this document states".
  - Here the system refused rather than answer wrong, and the confirmation step let a person fix it.
  - Code does not yet recognise amending language ("from … to", "by striking … inserting"). That is the next decision.
