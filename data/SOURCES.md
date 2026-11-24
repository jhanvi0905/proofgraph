# Sources

Raw files live in `data/raw/` (gitignored). Every fact below was read from the file, not from a listing.

## Family A (dev): Gillette D&O, 1996

(Planned as 12 packets when this file was written; one labelled claim, the FD960228 retention, was built, plus 6 retrieval queries in `retrieval_eval.json`.)

- File: SEC EDGAR accession 0000950135-97-001269 (Gillette 10-K405, FY1996), `gillette_10k405_1996.txt`, 726,516 bytes.
- Use `<DOCUMENT>` with `<TYPE>EX-10.(E)` / `<SEQUENCE>4`. It runs 993 lines and has 18 `<PAGE>` markers. Everything else in the file is out of scope.
- Age: these are 1996 instruments. They are real, but they are not current market practice.

### Instruments (9)

| # | Instrument | Policy no. | Key terms |
|---|---|---|---|
| 1 | CODA Endorsement No. 12 (effective 6/1/96) | GS-212C | Extends the policy period to 6/1/99. "All other terms of this POLICY remain unchanged." |
| 2 | CODA Endorsement No. 13 (effective 6/1/96) | GS-212C | Item VII (schedule of underlying D&O) is "deleted in its entirety and replaced". Five layers: London 10, London 10, Chubb 20, CNA 20, ERMA 10, for $70M total. Primary retention NIL/NIL/1,000,000. |
| 3 | ACE binder, June 4, 1996 (one instrument, two policy numbers) | GS-8099D / GS-8100D | $10M xs $90M follow-form CODA D&O, and $10M xs $70M follow-form London Corp Re. Its PROGRAM table lists London $20M primary (0/0/1M), Chubb 20xs20, CNA 20xs40, ERMA 10xs60, CODA 20 xs/d.i.c. 70, ACE. |
| 4 | London cover note | FD960228 | Primary. Retention Nil / Nil / USD 1,000,000. |
| 5 | London cover note | FD960229 | 1st excess. "NO AMENDMENTS TO THE PRIMARY POLICY SHALL BE BINDING UPON UNDERWRITERS ... UNLESS ... ENDORSED HEREON" (self-stated precedence rule). |
| 6 | Reliance revised binder, dated 12/16/96 | NDA 0134456-96 | $10M excess of $70M of underlying. Period 12/31/96 to 6/1/99, so the layer was added mid-term. It states the underlying primary retention as $0/$0/**$500,000**. Conditional on receipt, review and acceptance. |
| 7 | CNA / Continental binder | 132034203 | $20M xs $40M, 6/1/96 to 6/1/99. Conditional. |
| 8 | Chubb binder | 81385411 | $20M xs $20M, 6/1/96 to 6/1/99. Follows underlying terms. |
| 9 | Chubb binder, **Excess Fiduciary Liability** (not D&O) | 81344529 | $5M, form 14-02-182, term 7/1/96 to 7/1/99. The "DEDUCTIBLE AMOUNT" field holds "$20,000,000 Annual Aggregate - Aetna" and then "$100,000 Deductible". The basis of the $20M figure is ambiguous. It does not appear in Item VII. |
| (10) | ERMA binder | 752-034765-96 | $10M inclusive of defense. Conditional. Effective date June 1, 1996. |

Count note: confirm whether ERMA is the 9th or 10th instrument when ingest splits the exhibit.

### Checked disagreements

- **Retention conflict (real):** Item VII and FD960228 give the corporate-reimbursement retention as $1,000,000. The Reliance binder gives $500,000 for the same primary. Two documents say one figure and one document says another.
- **CODA "missing" from Item VII is not a conflict.** CODA (Corporate Officers and Directors Assurance Ltd.) issues GS-212C, so Endorsement 13 is CODA's own schedule of the insurance *underlying* it. That schedule ends at $70M, which is exactly where CODA attaches (20 xs 70). Label packets on this point `supported`, not `documents_disagree`.
- **Three instruments attach at $70M:** CODA 20 xs 70 (D&O / DIC), ACE GS-8100D 10 xs 70 (follow-form London Corp Re), and Reliance 10 xs 70 (from 12/31/96). The question is which tower and which coverage part each belongs to.
- **Policy-number drift:** Chubb is 81385411 in the binder and 81385411B in Item VII. CNA is 132034203 in the binder and DOX132034203 in Item VII.
- **Layer period ≠ policy period:** Reliance starts 12/31/96, and the Chubb fiduciary binder runs 7/1/96 to 7/1/99.
- **Parser traps:** "US$10,000,0O0" (letter O), "GILETTE" vs "GILLETTE", SGML `<TABLE>/<S>/<C>` tags, and "xs/d.i.c.".

### Refusal ground truth

GS-212C's base wording (insuring clauses, exclusions, definitions) is **not** among these instruments. Any coverage question ("does the policy cover X") has the correct answer `not_found`, and the reason is that the governing wording is absent. This is real absence, not synthetic.

The refusal label is mechanical. A packet gets `not_found` with reason `governing_instrument_absent` only when the packet's manifest has no instrument of the type the atom requires (here: base policy wording for GS-212C). Those six refusal packets therefore label themselves from the manifest. They need no human label.

## Family B (holdout, 8 packets): ISO HO 00 03 04 91

- File: `ho_00_03_04_91.pdf` (user-downloaded in a browser as `2a.-HO-00-03-04-91-Homeowners-3-Special-Form.pdf`; scripted fetch of the Nevada DOI copy is WAF-blocked). 105,884 bytes, PDF 1.6, 18 pages, letter size, Acrobat PDFWriter 3.02 from Word.
- sha256 `7624ad2e85eb3d838478242159d1e871620acd8bef263d5cf89ee3eb7aac8648`. Gillette: `66bb7e76bba9ff46a0797e61bf7210b4349b52e55ba81c47f62e56ccaddf1db4`.
- Footer on every page: "HO 00 03 04 91 Copyright, Insurance Services Office, Inc., 1990 Page n of 18". Because the form is ISO copyrighted, the PDF is kept out of git. Only extracted spans and the hash are committed.
- Text is selectable on all 18 pages (1,085–4,191 chars per page).
- **Layout trap (verified):** the body is two columns. pdfplumber's default `extract_text` interleaves the columns line by line, so its output is unusable. A naive crop at x = 306 truncates full-width headings ("HOMEOW", "AGREE", "DEFINI"); 2–6 characters per page straddle the gutter. Ingest must detect full-width lines first, then split the columns, and take offsets from the parser's character positions.
- Structure: Agreement, Definitions (numbered and quoted, e.g. `"Bodily injury" means`), Section I (Property Coverages, Perils Insured Against, Exclusions, Conditions), Section II (Liability Coverages, Exclusions, Additional Coverages, Conditions), Sections I and II Conditions.
- Precedence rules stated in the instrument itself: I.7 Other Insurance; Sections I & II conditions 1 Policy Period, 3 Liberalization Clause, 4 Waiver or Change of Policy Provisions.
- No endorsements and no Declarations page are included. Limits live on the Declarations, so a limit-amount question is a real `governing_instrument_absent` case here too. Endorsement-precedence packets for B must come from scripted mutations (insert a superseding endorsement).

## Family B endorsement: ISO HO 00 15 04 91

- File: `ho_00_15_04_91.pdf`, from independentagent.com (URL pinned in `data/instruments.json`). 16,670 bytes, PDF 1.2, 2 pages, selectable text, the same two-column layout as HO 00 03. sha256 `35b0fea3608165104b34a43cd01af5051993264ed538066f5258282747b4ca4a`. Read in full before any label was written.
- Header: "HOMEOWNERS / HO 00 15 04 91 / THIS ENDORSEMENT CHANGES THE POLICY. PLEASE READ IT CAREFULLY. / SPECIAL PERSONAL PROPERTY COVERAGE / Form HO 00 03 Only".
- Page 1: the Perils Insured Against under Coverages A, B and C are deleted and replaced (open perils, with listed exclusions).
- Page 2: "The Special Limits of Liability items 5., 6., and 7., are deleted and replaced by the following": $1,000 for loss by theft, misplacing or losing of jewelry…; $2,000 … of firearms; $2,500 … of silverware…. **The amounts equal HO 00 03's ($1000, $2000, $2500), but the scope widens from "theft" to "theft, misplacing or losing".** The arbiter compares amounts only, so it cannot see that change.
- Both forms are the 04 91 edition, and neither carries a policy number or an effective date. The family B packets assemble a specimen policy, `SPECIMEN-HO3`.
