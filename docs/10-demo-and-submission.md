# 10 · Demo video and submission

## The 3-minute video (six scenes)
| Time | Scene | What's on screen | What you say (draft) |
|---|---|---|---|
| 0:00–0:20 | Hook | Direct Muse confidently says TRUE, with a citation | "Billing reviewers relied on document AI I built. The dangerous failures weren't missing evidence. The AI cited the right lines and still got the answer wrong." |
| 0:20–0:50 | Right lines, wrong answer | A FinDVer case in the app: click a fact to see its quote highlighted; the check fails; CONTRADICTED | "ProofGraph never lets the model decide. Every link is checked by something that didn't write it." |
| 0:50–1:20 | Muse corrects itself | A ContractNLI NDA: the blind checker rejects a clause, Muse looks again, the verdict lands labelled CHECKED | "No model marks its own homework." |
| 1:20–2:05 | Drawn on the documents | A freight bundle with the proof graph on the pages: the rate in the PDF, handwritten times re-read blind, cartons counted by SAM 3.1; then the smudged copy gives UNRESOLVED plus "what to fetch" | "Citations you can check, down to the pixel." |
| 2:05–2:40 | Scoreboard | `results/report.md`: wrongly approved, can't-tell cases caught, accuracy by label, blind check vs self-check | Read only numbers from the report. Say the D26 sentence below. Do not present 0 versus 5 as a win. |
| 2:40–3:00 | Built + next | Commit log, `BUILT_DURING_HACKATHON.md` | "Built during the hackathon: the verification engine, visual citations, the objection loop, the evaluation and the app. Next: technical specifications and policies, fully on-premises with Muse Glimmer, and using the engine as a reward to train open models." |

**Demo cases must come from real runs.** Use `scripts/pick_demo_cases.py` to list cases where A was wrong and ProofGraph was right. Don't stage model outputs. The freight bundles are labelled as our own demonstration set.

## Recording tips
- 1080p screen capture; the app zoomed to 125%; dark or light theme throughout, not mixed
- Record each scene separately; voice-over after
- Keep the cursor still between clicks; highlight the fact box before the verdict appears

## Submission checklist (by Wed Nov 4, 22:00 IST)
- [ ] Repo public, README complete, CI green, `v1.0-submission` tag
- [ ] `results/report.md` generated from committed `runs/`
- [ ] App URL works in replay mode (incognito test)
- [ ] Video ≤ 3:00, link accessible (unlisted YouTube or similar), shows only hackathon work
- [ ] Submission form: repo URL, video URL, app URL, description, track (Indie), problem statement (Build for Your World)
- [ ] Open-weight bonus: say clearly that the blind checker runs on Muse Spark Open via Baseten
- [ ] Post the demo on X and submit the post link (Most Viral prize, counted until Nov 8)
- [ ] Meta credits claimed before Nov 4, 9 PM ET

## X post (draft)
"AI can cite the right line and still be wrong. I built ProofGraph for the Meta AI hackathon: Muse Spark points to every fact on the page, a second Meta model checks it blind, SAM 3.1 counts what's in the photo, and code decides. Every verdict says how it was proven. [video] [repo]"

## Judge comparison (D26)

One recorded false claim, same evidence: Direct Muse approves it, ProofGraph does not, with one plain reason. Pick it from the five Direct Muse got wrong on the 28 Oct run. Label it as that file-order run, not a sample.

Say this once, at the scoreboard:

On the first 30 false FinDVer claims, ProofGraph approved 0 and Direct Muse approved 5. On 50 true claims, ProofGraph approved 2, rejected 25, and declined 23. Grounding is 18/24. The repair loop did not run. Criterion 1 is not claimed.

Keep off the judge screen: a comparison browser, a live Muse bake-off, a 0-versus-5 win line, 24/24 as the headline, and any claim that ProofGraph beat Direct Muse on FinDVer. The pair waits until after Friday's boxed bundle. If Sunday is full, it lives only in the video.
