# GitHub Actions reliability: discovery experiments

This is an isolated evaluation of GitHub Actions, not a change to Proofgraph's product. All injections use made-up inputs, local files, and local transactions. No application secrets, model calls, deployments, or external services are used. The script uses Python's standard library; it adds no dependencies. The lab workflow triggers only on the `eval/actions-reliability` branch when experiment code changes. Existing product CI is unchanged.

## What we need to learn

| Order | Assumption | Impact / risk judgment | PM skill and why | Test | Decision rule |
|---|---|---|---|---|---|
| 1 | An explanation helps people correctly distinguish broken code from an execution problem. | Potentially broad impact; low confidence in user benefit. Classification mistakes can mislead users. | `prioritize-assumptions` to separate evidence from guesses; `brainstorm-experiments-existing` to compare behavior cheaply. | Frozen conservative rules on constructed logs, then a separate historical-log check, followed by a timed developer study. | Technical baseline must preserve evidence and abstain on ambiguity. Human pilot: at least 30% lower median correct-diagnosis time without lower correctness or more unsafe actions. |
| 2 | Recovery can save time without repeating a side effect. | High impact for side-effecting work; high harm if wrong. | `brainstorm-experiments-existing`: a sandbox fault injection answers the technical question cheaply. | Fail before a write, fail after a committed write, reject bad input, and exhaust retry budget. Compare naive repetition with a stable operation key and atomic transaction. | Recover all scripted recoverable cases with one effect each; stop permanent errors after one attempt; cap repeat attempts at three. A naive duplicate is an expected negative control. |
| 3 | Missing work can be distinguished from waiting or blocked work. | Impact depends on workflow criticality; low confidence in production coverage. | `metrics-dashboard`: define expected work and the measurement clock before counting misses. | Reconcile expected IDs against observations. Exercise stale data, permissions, filtered triggers, waiting, running, cancellation, and reruns; poll a real GitHub run from outside Actions. | Detect all injected misses with zero false missing alerts in the fixture set. Live valid run must be found before the agreed 180-second deadline; do not call API failure a missing run. |

These are qualitative judgments, not measured reach or satisfaction scores. Keep the ranking provisional until users describe actual incidents. All thresholds are pilot rules chosen before the run, not GitHub guarantees.

## Run the technical experiments

```sh
python3 scripts/reliability_lab.py --output /tmp/reliability-evidence
python3 scripts/reliability_lab.py --diagnose-log /path/to/downloaded-job.log
```

The script generates `results.json` and `summary.md`; the workflow uploads both as a seven-day artifact. Counts are computed from actual executed cases. The fixture labels are withheld from the explainer, but the fixture set and rules were designed together: fixture accuracy is not independent model-quality evidence. The historical log is a separate case, and it is acceptable for this baseline to say `unknown`.

The lab has one **intentionally failing** job on attempt one: `expected-transient-failure-rerun-me`. Use GitHub's rerun-failed-jobs control to retry it. The probe succeeds on later workflow attempts by design and performs no write. This validates GitHub's native rerun path, not automatic detection of an infrastructure outage. The code-error probe uses `continue-on-error`, then checks its raw outcome; the error is expected and must remain visible.

`reliability_lab.py` uses actual subprocesses and SQLite transactions for recovery tests. It simulates losing an acknowledgement after commit with a nonzero process exit. The stable-key write and completion record share one local transaction. It does not establish exactly-once behavior for deployments, payments, external APIs, concurrent callers, or unrelated databases.

The missing-work checks use constructed states and a virtual clock. The measured 30-second polling bound is therefore simulated. A live observation of one successful trigger can verify the observation path; it cannot estimate dropped-run frequency or false-alert rate in production. Trigger eligibility must include event type, filters, repository, workflow identity, and commit or unique dispatch identity. Access failures and stale snapshots are unknown states.

## Developer study: what remains to validate

Use `interview-script` for specific past behavior, followed by an observed task comparison. Do not use AI responses as substitutes for developers, and do not ask only whether they like the idea. No participants have been recruited or contacted by this experiment.

### Opening, 2 minutes

Explain that the study concerns their experience investigating failed automation, not their ability. Confirm 30 minutes. Ask permission before recording, if recording is needed. There are no right or wrong interview answers.

### Context, 4 minutes

- What do you build, and which workflows do you normally work with?
- Walk through your most recent failed run. What did you do first?
- Which tools or people helped? Can you show the sequence and timestamps?

### Past behavior, 8 minutes

- What evidence changed your mind about the cause?
- Tell me about the last time you reran a job. What happened afterward?
- Was there a repeated action or partial release? How did you discover it?
- Tell me about a run you expected but could not find. How did you check?
- How much time did the incident take? What work was delayed?
- What have you already tried to improve this? What did it cost?

Probe with “What happened next?” and “Can you show a specific example?” Listen more than you speak. Do not describe the proposed explanation feature during this part.

### Observed tasks, 12 minutes

Recruit an initial eight developers across application and platform/release roles. Build six representative incident tasks per participant from a larger reviewed pool. Independently review ground truth with two engineers; resolve disagreement before scoring. Include an ambiguous case whose correct answer is “not enough evidence.”

Each participant sees three logs-only cases and three different cases with evidence-linked explanations. Counterbalance conditions and order across participants; balance case difficulty. Do not show the same person the same incident twice. Participants who have seen the answers or built the prototype must not score those tasks. Record condition assignments before testing.

Time from opening a task to a submitted diagnosis and next action. Cap each task at two minutes; record timeouts and errors rather than excluding them. Compare participant-level median correct-diagnosis time, correctness, safe next actions, and all-task completion. Treat repeated observations from one participant as related; do not pretend they are independent users. An eight-person test is directional usability evidence, not a powered production A/B test. An apparent speed gain with more wrong answers is a failed result.

### Wrap-up, 4 minutes

- What was hardest in the tasks?
- Which information did you trust, and what evidence did you check?
- What important part of your real investigation was missing?
- Who else deals with these problems?

### Notes and task record

Participant ID / role / experience / date / recording permission:

Last real incident / current tools / steps taken / time spent / work delayed / attempted fixes / actual cost / desired outcome / unexpected finding / follow-up:

Task ID / assigned condition / order / start time / submission time / timed out / diagnosis / ground-truth category / correct / next action / safe / evidence opened / observer notes:

Do not publish identifying participant information or logs containing secrets. The current lab uses only constructed data and a minimal public-repository incident excerpt.

## Measurement and next decisions

Track technical case results separately from user outcomes. Source each number to the generated artifact, native GitHub attempt logs, external polling timestamps, or a real participant record. Unknown or unavailable values stay unknown.

- Daily during a pilot: missing work, investigation backlog, and any duplicate effects.
- Weekly: correct-diagnosis time, correctness, manual reruns, and cost per investigated incident.
- Business check: actual engineer time saved against compute, installation, and maintenance costs. There is no willingness-to-pay evidence yet.

After the technical runs, proceed to the developer study if the baseline and evidence display work. If the historical case cannot be explained, report the gap rather than editing rules and calling that same case a fresh evaluation. Do not ship automatic retries on the basis of the sandbox results.
