# 10 · Demo video and submission

## 31 Oct plan (accepted 31 Oct, D34 and D37; replaces the six scenes, the X post and the judge comparison below)

Positioning: "Paste the conclusion an AI or a colleague wrote, upload the documents behind it, and ProofGraph shows, part by part, the exact sentences that support it and the ones that contradict or weaken it, boxed on the original page."

Demo cases, uploaded on screen: LegalReasonBench Test Case 17 (lead), ContractNLI Test Case 40 (Bosch NDA), frt-07 (freight). Backups: Test Case 18; Test Case 25 as a 10-second scan beat only if probe P1 passes and the Tobacco800 terms allow public display, otherwise frt-03.

| Time | Screen | Voice-over (draft) |
|---|---|---|
| 0:00–0:12 | A memo saying "no compliance gap exists" | "AI and colleagues write confident conclusions. Someone still has to sign them." |
| 0:12–0:30 | Upload three IHP PDFs, paste the TC17 claim; parts appear | "A governance claim and the three documents behind it, uploaded now." |
| 0:30–1:05 | Part 2 red: bylaws 5.2 boxed; amber card for the May 13 adoption; blue card for the memo, tagged weak source | "The memo says valid from May 7. The bylaws say no appointment is effective until the board approves. The board approved on May 13. Both sides are shown." |
| 1:05–1:20 | "Second check agrees", Muse Spark Open | "Every card is re-read blind by Meta's open-weight Muse Spark Open, which sees only the quote and the part." |
| 1:20–1:50 | Bosch NDA (ContractNLI citation on screen), consultant clause boxed | "A real public contract. Consultants only with written authorisation, boxed on page one." |
| 1:50–2:20 | frt-07: exception and 16:20 boxed, injection banner | "I worked in freight. The fee is owed only after 18:00 the day before. The shipper cancelled at 16:20. One file tells the AI to approve; ProofGraph shows it and ignores it." |
| 2:20–2:30 | Optional scan beat, dashed box | "Scans get a dashed box. Solid means the PDF text proves the location." |
| 2:30–2:50 | `results/report.md` | Read only numbers from the report, with n and source groups. Name one miss. |
| 2:50–3:00 | Repo, dates, models | "Built this week on Muse Spark and Muse Spark Open." |

Say: the held-out wording in `05-datasets-and-eval.md` (31 Oct section). Do not say: more accurate than Direct Muse or any baseline, legal advice, catches every contradiction, exact boxes on scans, a template was signed, Company Documents are freight data, LegalReasonBench files are real case files. SAM 3.1 is not in the video; the README says it was built and tested and is not on the product path.

X post (draft): "AI drafts conclusions. People sign them. For the Meta AI hackathon I built ProofGraph: upload the documents, paste the claim, and see the exact sentence that supports, contradicts or weakens each part, boxed on the page. Muse Spark reads every page, Muse Spark Open checks each finding blind. [video] [repo]"

The six-scene plan, X post and judge comparison below are kept as history (D30).

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

The submission video is an animation the human makes from one of those runs (decision D25). The scene list above is the content. The Streamlit app the judges open runs the check again. It does not play a stored verdict.

## Recording tips
- 1080p screen capture; the app zoomed to 125%; dark or light theme throughout, not mixed
- Record each scene separately; voice-over after
- Keep the cursor still between clicks; highlight the fact box before the verdict appears

## Submission checklist (by Wed Nov 4, 22:00 IST)
- [ ] Repo public, README complete, CI green, `v1.0-submission` tag
- [ ] `results/report.md` generated from committed `runs/`
- [ ] Judge URL runs a live check under the spend cap. The URL is not posted as an open endpoint
- [ ] Animation ≤ 3:00, link accessible (unlisted YouTube or similar), made from a real run, shows only hackathon work
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
