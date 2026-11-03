---
version: 1
slug: "app-web-index-html"
primary_target: "app/web/index.html"
related_targets: ["app/viewer/graph_view.py","app/viewer/graph_view.css"]
---

# Surface brief: ProofGraph web app (entrance, live reading, review, shared review, how we measure it)

Scope: whole web app, one world. Modes: entrance Persuade; live reading and review Operate; how we measure it Read. Audience: hackathon judges first; Maya-type reviewers second. Real packets never appear; synthetic packets only, labelled synthetic. Pricing and video out.

## Direction contract

THESIS: A claim is checked the way an auditor ties out a workpaper: every part gets a pencilled tickmark that means one defined thing, backed by a legend and a reference to the page it ties to. Refuses the legal-AI default (chat box, citation chips, a confidence score) and the discarded green ledger.

OWN-WORLD: Cool white workpaper sheet with pale cyan column rules; blue-black ink; stamp cobalt as the one saturated field and the primary action; audit-pen red for exceptions, audit-pen green for tied-out. Tickmarks are hand-drawn SVG pencil strokes (tick, circle, caret, bracket, question), each with a legend entry. Workpaper reference codes (A-1, B-3) tag every section and cell. Prepared-by and reviewed-by sign-off boxes carry the receipt and the second-reader line. Evidence cells are columnar analysis cells. Schibsted Grotesk for what ProofGraph says; Source Serif 4 only for what documents say; tabular figures, no monospace.

STORY: A sentence arrives that must be trusted. The visitor watches the packet get read and every part tied out, sees which documents agree, which clause breaks the claim and which document wins, then opens a tick to its page. They believe it because every mark has a legend entry and gaps are written down as open items, not hidden.

FIRST VIEWPORT: Stamp-cobalt field. Left: "Where does it say that?" at display scale, one support sentence, the claim field and one button, "Check claim". Right: a white workpaper sheet, pinned slightly off square, showing a synthetic claim with red and green tickmarks, a reference code, a legend strip and a sign-off box. No real packet. Primary action sits under the field, left, above the fold.

FORM: Audit working papers with tick-and-tie marks, position 1 of 7 (Impeccable's pick, chosen over the assigned candidate 4), seed:832f28b065b800d9.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance.

## Open decisions
- Synthetic example packet: who authors it, and it needs a cached run so the demo costs nothing.
- "How we measure it" ships with "Runs pending" until a results report exists.
- Backend: the documents-disagree answer does not exist yet.
