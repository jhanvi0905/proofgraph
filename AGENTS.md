# Agent Instructions

## Feature Work

When you are the main/orchestrator agent and the user asks to create a new feature or modify an existing feature, load and follow feature-implementation-workflow skill before making code changes.

That skill is the authoritative workflow for feature research, planning, user approval, implementation, and verification.

## General Rules

### Think Before Coding

- State assumptions, uncertainty, and meaningful tradeoffs explicitly.
- If a request has multiple reasonable interpretations, present them or ask before choosing.
- Push back when a simpler approach would satisfy the goal.
- Stop when confused. Name what is unclear and ask for clarification.

### Keep Changes Simple And Surgical

- Use the minimum code that solves the approved goal.
- Touch only files needed for the request.
- Match the existing style and project patterns.
- Do not add speculative features, abstractions, configurability, or unrelated cleanup.
- Preserve user changes. Do not revert work you did not make.
- Remove only unused code created by your own change.

### Git

- Push every code change on a relevant branch named for the work (`feat/…`, `fix/…`, `docs/…`, `chore/…`, `test/…`, `eval/…`).
- Do not push commits straight to `main`. Open a pull request to land the branch.
- Commit with `feat:`, `fix:`, `test:`, `docs:`, `chore:`, or `eval:`, an imperative subject, and a body that says why.

### Verify And Report

- Define success criteria for non-trivial work.
- Run focused checks that match the risk and scope.
- If verification fails, debug the implementation before weakening checks.
- Final responses should summarize what changed, how it was verified, and any unresolved issues.

### Look things up only when the task needs them
| Task | Read |
|---|---|
| Engine, routing, verdict rules | `docs/03-architecture.md` |
| Any Meta model call or prompt | `docs/04-meta-models.md` |
| Adapters, datasets, metrics | `docs/05-datasets-and-eval.md` |
| Where a file goes | `docs/06-repo-structure.md` |
| What to build today | `docs/12-sprint-manager.md` (daily board), `docs/07-build-plan.md` (calendar) |
| Is this in scope? | `docs/02-scope.md`, `docs/11-decision-log.md` |

Ask before changing a rule above, adding a dependency, or spending more than $10 in a run. If something isn't covered, write it in `QUESTIONS.md` and move to the next task.