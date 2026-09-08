---
name: implement
description: "Implement a piece of work based on a spec or set of tickets using inline TDD and code review."
disable-model-invocation: true
---

# Implement

Execute the implementation of a feature or task defined in tickets or a specification. Implementation runs **inline in the main session** (never dispatching implementer subagents), following strict test-driven development (TDD) discipline and completing with a two-axis subagent review and external model review.

---

## 1. Setup & Context Discovery

1. **Read Domain Context**: Read `CONTEXT.md` in the project root if it exists. Adhere to established domain vocabulary in test names, variable names, and commit messages.
2. **Locate Work Items**:
   - Locate tickets under `docs/tickets/` (or from the user's argument) and the originating spec under `docs/specs/`.
   - If issue tracker configuration is missing from `docs/agents/issue-tracker.md`, prompt user to run `/setup-matt-pocock-skills`.
3. **Record Starting Fixed-Point**:
   - Save the starting commit SHA:
     ```bash
     git rev-parse HEAD
     ```
   - This baseline will be used for final code review diffing.

---

## 2. Per-Ticket Implementation Loop

Work through tickets in dependency order (blockers first). For each ticket:

### A. Read Requirements
- Read the ticket's description, acceptance criteria, and seams in `docs/tickets/`.
- Inspect existing related code using `Find`, `Grep`, and `Read`.

### B. Execute TDD Discipline
Follow the [tdd](../tdd/SKILL.md) skill process at pre-agreed seams:
1. **Red**: Write a focused, failing unit/integration test covering the requirement. Run test runner via `Bash` (e.g. `npm test`, `pytest`, `cargo test`) and confirm it fails for the expected reason.
2. **Green**: Write the minimal code necessary to make the test pass.
3. **Refactor**: Clean up duplication and code smells while keeping tests passing.
4. **Typecheck & Lint**: Run project typechecking and linting on touched files.

### C. Update Ticket Status
- Mark completed acceptance criteria as checked (`- [x]`) in the ticket file using `Edit`.

---

## 3. Full Suite Verification

Once all tickets are implemented:

1. Run the entire test suite via `Bash`.
2. Run project-wide typechecking and linting.
3. Ensure zero regressions or unhandled errors.

---

## 4. Code Review Gate

Before committing, run both internal subagent review and external model review:

### A. Internal Two-Axis Review
1. Load `skills/engineering/code-review/SKILL.md`.
2. Dispatch parallel sub-agents using the `Task` tool (Standards Review and Spec Review) against the diff from the starting commit (captured via `git diff <starting-commit>`). Single, concise task description; pass the diff path (e.g. `.scratch/review.diff`) and the spec path as inputs, not inline file contents.
3. Review aggregated findings.
4. **Fix all P0 (blocking) findings** and address important P1 findings before proceeding.

### B. External Model Review
1. Load `skills/meta/review-with-external/SKILL.md`.
2. Choose a stable `review_key` for this feature/diff (e.g. `<feature>-code`). Reuse it across fix → re-review passes.
3. Run external code review with `review_type: "code"` (primary: agy Flash 3.7 High), passing the diff, originating spec, and `review_key`.
   - Round 1 cold-starts and saves a conversation/session id; later rounds **resume** that session with a delta prompt (see `review-with-external` sticky sessions).
4. **Fix all Critical findings** identified by the external model.
5. If Critical (or Important-blocking) findings were fixed, re-invoke `review-with-external` with the **same** `review_key` until clear. Do not open a fresh disconnected external chat for each pass.

---

## 5. Commit & Report

1. Stage changes:
   ```bash
   git add -A
   ```
2. Commit with a concise message using domain terminology from `CONTEXT.md`:
   ```bash
   git commit -m "feat(<domain>): <concise summary of changes>"
   ```
3. Report completed tickets, verification status, and review summary to the user (≤15 lines).
