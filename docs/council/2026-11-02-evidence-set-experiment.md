# Experiment: evidence set per part (branch `feat/evidence-set`)

Status: pre-registered 2 Nov 2026 before code. Not merged. Built on `feat/second-check-reason` (check_answer, reason line) plus the doc-name fix. Default OFF.

Root cause (AI panel + Product, 2 Nov): `relate` can only return one passage (prompt "Pick the one passage", single-quote `Relate` schema, `_run_part` builds only `c1`). `status.py`, `conflict`, D38 and the receipt already assume several cards, so `conflict` is unreachable today. Every one of 22 parts in 16 cases has exactly one card.

Design: flag `PROOFGRAPH_EVIDENCE_SET=1` (default off). Off = today's path byte for byte, same prompt, same cache. On = `prompts/relate_set.md` (a separate prompt, so existing cache keys stay valid) returns `items`; code shapes them (drop set_aside when real items exist, dedupe, drop injection, cap 3 with at most 2 per relation, each relation present always gets a slot, worst-first before cap); each item is snapped and blind-checked alone. `status.py`, `check.py`, `models.py`, `absence.py` unchanged. No loops, no re-ask.

Viewer (only when some part has 2+ cards): cards ordered supports, weakens, contradicts; "Sources disagree" strip names both documents when `part.conflict`; "Only one passage found" on single-card parts.

Bar (no accuracy claim). Old pool TC17, TC12, TC40; unseen = the 13 cases already run.
- B1 flag off identical to `e6815ae`-behaviour (replay).
- B2 flag on: no status change on parts that still have one card; every other change listed with the causing card.
- B3 cap 3, at most 2 per relation, order holds on 100% of parts.
- B4 no duplicate or overlapping quotes; every card snaps.
- B5 every card shows its document name.
- B6 unseen: at least 8 cases and 5 parts with 2+ cards, else INCONCLUSIVE (do not adopt).
- B7 median cost per review at most 2x today (today about $0.029).
- F2 panel read: more than 1 in 6 new reds or new greens that read as padding or overreach = fail.
Decision: adopt only if B1 to B7 pass, F2 holds and the human says yes. Needs spend approval for the live run (estimate about $1 median, $2.5 worst; dev cap $10).
