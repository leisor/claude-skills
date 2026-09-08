---
name: review-with-external
description: "Pipe a document through an external model (grok/agy CLI) for review. Use at spec, ticket, and code review gates. Sticky sessions resume prior reviews so revision loops do not re-pay full context."
---

# External Model Review

Review a document using a stronger external model via CLI. This skill manages the tool chain, isolated unique file paths, permission flags, timeout parameters, fallback logic, and **sticky review sessions** so revision loops keep prior context.

When exploring the codebase, read `CONTEXT.md` (if it exists) and pass relevant domain context to the external reviewer.

## Inputs

The invoking skill provides:
1. **File path** to review (spec, ticket plan, or diff)
2. **Review type**: `spec`, `plan`, or `code`
3. **Spec path** (optional, for code reviews — so the reviewer can check faithfulness)
4. **Stable review key** (optional but recommended): a slug for the feature/artifact, e.g. `esp32-push-ota`. Used to find/create the sticky session file. If omitted, derive from the artifact basename (strip date prefix).

## External Model Chain

| Review type | Primary | Backup 1 | Backup 2 |
|---|---|---|---|
| `design` | `grok` (Grok 4.5 High) | `agy` (Opus 4.6) | `agy` (Flash 3.7 High) |
| `map`    | `grok` (Grok 4.5 High) | `agy` (Opus 4.6) | `agy` (Flash 3.7 High) |
| `spec`   | `grok` (Grok 4.5 High) | `agy` (Opus 4.6) | `agy` (Flash 3.7 High) |
| `plan`   | `grok` (Grok 4.5 High) | `agy` (Opus 4.6) | `agy` (Flash 3.7 High) |
| `code`   | `agy` (Flash 3.7 High) | — | — |

## Strict Execution Rules

1. **ALWAYS use UNIQUE file paths**: To prevent collisions between concurrent agents running in parallel, NEVER use static `/tmp/review-prompt.md` or `/tmp/review-output.md`. Always include a unique identifier (feature/ticket name, timestamp, or random suffix) in the filename:
   - Prompt file: `/tmp/review-<feature/task>-<unique_id>-prompt.md`
   - Output file: `/tmp/review-<feature/task>-<unique_id>-output.md`
   - Raw JSON (when using `--output-format json`): `/tmp/review-<feature/task>-<unique_id>-raw.json`
2. **ALWAYS write prompt to file**: Write the complete review prompt to your unique prompt file using the `write` tool before calling any CLI.
3. **ALWAYS capture full output to file**: Direct CLI output to your unique output file. Then read that file with `read`. Prefer JSON capture (below) so session IDs can be persisted.
4. **NEVER truncate with `tail` or `head`**: Do NOT pipe review body through `tail -n`, `head -n`, or grep filters when reading findings. Parse JSON with `jq` only to extract `.text` / `.result` / `.sessionId`.
5. **SET GENEROUS TOOL TIMEOUT (15–20 min)**: Deep reasoning models require 3–10 minutes. When invoking the `Bash` tool for `grok` or `agy` Opus, ALWAYS pass `timeout: 1200` (20 minutes).
6. **ALWAYS use permission auto-approval flags**:
   - `grok`: `--yolo`
   - `agy`: `--dangerously-skip-permissions --print-timeout 15m`
7. **STICKY SESSIONS for revision loops** (see below). Never use bare `-c` / `--continue` — it races with other agents and other reviews in the same cwd.

---

## Sticky review sessions (revision loops)

External review is often repeated: findings → edit artifact → re-review. Starting a **new** CLI chat each round wastes tokens re-reading domain context and re-arguing closed findings.

### Session state file

Persist one state file per review key:

```text
/tmp/review-session-<review_key>.json
```

Example:

```json
{
  "review_key": "esp32-push-ota",
  "review_type": "spec",
  "artifact": "docs/specs/2026-08-31-esp32-push-ota-spec.md",
  "tool": "grok",
  "model": "grok-4.5",
  "session_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "round": 2,
  "last_output": "/tmp/review-esp32-push-ota-1725028000-output.md",
  "updated_at": "2026-08-31T15:00:00Z"
}
```

- `tool` is sticky: once round 1 used `grok`, all later rounds for this key stay on `grok` (same for `agy`). Switching tools throws away memory.
- Prefer explicit `session_id` / conversation id. Do **not** use `-c` / `--continue`.

### Round 1 — cold start

1. If `/tmp/review-session-<review_key>.json` exists and has a usable `session_id` + matching `tool`, skip to **Round 2+**.
2. Otherwise write the **full** review prompt (templates below).
3. Run the primary tool (then backups on failure).
4. Capture session id and write/update the session state file.
5. Write human-readable findings to the output `.md` file.

### Round 2+ — warm continue (delta)

1. Read the session state file.
2. Build a **delta** prompt (not a full cold prompt):
   - path to current artifact (or embed a diff vs previous if cheap)
   - short changelog of what you changed to address prior findings
   - path to `last_output` (prior findings)
   - ask: re-review only remaining Critical/Important items; do not restate fixed Minors
3. Resume the **same** tool with the saved `session_id`.
4. On success: bump `round`, update `last_output` / `updated_at`.
5. On resume failure (missing session, expired, CLI error): cold-start once, but include prior findings + changelog in the new prompt so context is not totally lost, then rewrite the session file.

### When to force a cold start

Force cold start (new session, rewrite state) when:
- No session file, or `session_id` missing
- Resume fails after one retry
- Artifact was rewritten so heavily that a delta is meaningless (note this in the prompt)
- After **5** warm rounds on the same session (avoid unbounded transcript growth); then cold-start with a concise summary of open findings only

---

## Process

### 1. Resolve review key and session

Derive `review_key` from the invoking skill or artifact basename (e.g. `2026-08-31-esp32-push-ota-spec.md` → `esp32-push-ota`).

Read `/tmp/review-session-<review_key>.json` if present. Decide cold vs warm.

### 2. Prepare and write the review prompt

Read the file to review. If `CONTEXT.md` exists, incorporate relevant domain terminology and constraints.

**Cold-start prompts:**

**For design review (post-grilling session):**
```markdown
Review this engineering design — the settled decisions from a grilling session. Report findings as Critical (blocks writing a spec), Important (significant gap or assumption), or Minor (style/clarity).

Check for:
- Decisions that assume facts not yet established in the conversation
- Module or responsibility boundaries that will cause future coupling or leaky abstractions
- Missing actors or edge actors (admin paths, external systems, clock-triggered flows)
- Data model or state machine gaps
- Contradictions between decisions made at different points in the session

Design decisions summary:
<summary of grilling session decisions>
```

**For map review (post-wayfinder charting):**
```markdown
Review this Wayfinder map for a large engineering initiative. Report findings as Critical (wrong destination or fatal missing decision track), Important (significant gap in coverage), or Minor (minor framing issues).

Check for:
- A destination that is too vague to know when it has been reached
- Missing decision tracks that will block progress once the current frontier is exhausted
- Tickets that are research masquerading as implementation (or vice versa)
- Blocking relationships that are missing or incorrectly ordered
- Scope too large for one initiative map (should be split)

Wayfinder Map:
<map contents>

Initial tickets:
<ticket list>
```

**For spec review:**
```markdown
Review this software specification. Report findings as Critical (blocks implementation), Important (should fix before implementing), or Minor (style/clarity).

Check for:
- Ambiguous requirements that could be interpreted two ways
- Missing error handling or edge cases
- Contradictions between sections
- Incomplete acceptance criteria
- Scope that is too large for a single implementation cycle

Specification:
<file contents>
```

**For plan/ticket review:**
```markdown
Review this implementation plan / ticket breakdown. Report findings as Critical, Important, or Minor.

Check for:
- Missing tickets for spec requirements
- Wrong dependency order (ticket depends on work not yet done)
- Tickets that are too large (should be split)
- Horizontal slicing instead of vertical (end-to-end) slices
- Missing acceptance criteria or verification steps

Plan / Tickets:
<file contents>
```

**For code review:**
```markdown
Review this diff against the spec below. Report findings as Critical (blocks merge), Important (should fix before merging), or Minor (style/clarity).

Check for:
- Spec requirements not implemented in the diff
- Code added that the spec did not ask for (scope creep)
- Bugs, off-by-one errors, missing error handling
- Test coverage gaps for critical paths

Spec:
<spec contents>

Diff:
<diff contents>
```

**Warm-continue (delta) prompt:**
```markdown
This is a re-review of the same artifact in an ongoing review session (round N).

Prior findings are in: <last_output path>
(Do not restate Critical/Important items that were clearly fixed. Focus on regressions and remaining open issues.)

Changes since last review:
<bullet changelog of edits addressing findings>

Current artifact path: <artifact path>
Current artifact contents:
<file contents — or a unified diff against the previous version if available and smaller>

Report findings as Critical, Important, or Minor. If nothing Critical/Important remains, say so explicitly.
```

Choose a unique review ID (e.g. `feat-auth-1725028000` or `ticket-2-$(date +%s)`).
Write the prompt to `/tmp/review-<id>-prompt.md` using the `write` tool.

---

### 3. Execute the review

#### Capturing session IDs (required)

Prefer JSON output so the session can be resumed:

**Grok** — `--output-format json` includes `sessionId` and review text in `.text` (see Grok headless docs):

```bash
grok --model grok-4.5 --reasoning-effort high --yolo \
  --prompt-file /tmp/review-<id>-prompt.md \
  --output-format json \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
jq -r '.text // empty' /tmp/review-<id>-raw.json > /tmp/review-<id>-output.md
SESSION_ID=$(jq -r '.sessionId // empty' /tmp/review-<id>-raw.json)
```

**Warm Grok resume:**

```bash
grok --resume "$SESSION_ID" --yolo \
  --prompt-file /tmp/review-<id>-prompt.md \
  --output-format json \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
# extract .text and confirm .sessionId (usually same)
```

**Agy** — use `--output-format json` and parse conversation/session id from the result object (field name may be `session_id`, `conversation_id`, or nested; check the JSON). Persist whichever id `--conversation` accepts:

NOTE (retro 2026-09-03): the installed agy rejects `-p <prompt>` with the
prompt as a SPACE-separated following arg — `-p` consumes the next token as
its value. Use `--print="$(< file)"` (the `=`-attached form) and keep
`--dangerously-skip-permissions` unattached:

```bash
agy --dangerously-skip-permissions --print-timeout 15m \
  --output-format json \
  --model claude-opus-4-6-thinking \
  "--print=$(< /tmp/review-<id>-prompt.md)" \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
# Write readable markdown from the result text field into -output.md
# Persist conversation id for --conversation on later rounds
```

**Agy JSON flakiness (retro 2026-09-03, T2):** `--output-format json` has
returned `status: CANCELED` with an empty response after consuming input
tokens, and plain-text `--print` then worked on retry. If the json run comes
back CANCELED/empty, retry WITHOUT `--output-format json` (plain text) and
capture the conversation id from stderr/log if present; on failure, cold-start
next round with a delta prompt embedding prior findings.

**Warm Agy resume:**

```bash
agy --dangerously-skip-permissions --print-timeout 15m \
  --output-format json \
  --conversation "$SESSION_ID" \
  --model <same model as round 1> \
  "--print=$(< /tmp/review-<id>-prompt.md)" \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
```

If JSON session-id extraction fails for agy, still save `last_output` and on the next round cold-start with the delta prompt that embeds prior findings (better than a blank-context full review).

#### Tool chain (cold start only)

Try the primary tool first. If it fails (command not found, non-zero exit, timeout), try Backup 1, then Backup 2. Once a tool succeeds, that tool+model is sticky in the session file.

**For Spec & Plan Reviews (Primary: Grok)** — `timeout: 1200`:
```bash
grok --model grok-4.5 --reasoning-effort high --yolo \
  --prompt-file /tmp/review-<id>-prompt.md \
  --output-format json \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
```

*Backup 1 (`agy` Opus 4.6, `timeout: 1200`):*
```bash
agy --dangerously-skip-permissions --print-timeout 15m \
  --output-format json \
  --model claude-opus-4-6-thinking \
  "--print=$(< /tmp/review-<id>-prompt.md)" \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
```

*Backup 2 (`agy` Flash 3.7 High, `timeout: 900`):*
```bash
agy --dangerously-skip-permissions --print-timeout 15m \
  --output-format json \
  --model gemini-3.7-flash-high \
  "--print=$(< /tmp/review-<id>-prompt.md)" \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
```

**For Code Reviews (Primary: `agy` Flash 3.7 High)** — `timeout: 900`:
```bash
agy --dangerously-skip-permissions --print-timeout 15m \
  --output-format json \
  --model gemini-3.7-flash-high \
  "--print=$(< /tmp/review-<id>-prompt.md)" \
  > /tmp/review-<id>-raw.json 2>/tmp/review-<id>-stderr.txt
```

After a successful run, write `/tmp/review-session-<review_key>.json` with tool, model, session_id, round, artifact, last_output.

---

### 4. Read and parse findings

Read the full report from `/tmp/review-<id>-output.md`.

Extract **Critical**, **Important**, and **Minor** findings. Present them to the invoking skill and resolve Critical and Important findings before completing the gate.

When the invoking skill edits the artifact and needs another pass, call this skill again with the **same** `review_key` so the warm path runs.

---

### 5. Fallback

If all external tools fail:
- Report: "External review unavailable. Proceeding with local review only."
- Do not block the workflow. The local review (or subagent review for code) still applies.
- Leave any partial session file intact only if a prior successful round exists; otherwise delete a half-written session file so the next attempt cold-starts cleanly.

## Integration

Skills invoke this skill at their review gates:

- **grill-with-docs**: After the design tree frontier is resolved, before proceeding to /to-spec (review_type: `design`)
- **wayfinder** (Mode A): After drafting the initial map and tickets, before presenting to user (review_type: `map`)
- **to-spec**: After writing the spec, before proceeding to /to-tickets (loop: review → fix → re-review with same key)
- **to-tickets**: After writing tickets, before proceeding to /implement (same sticky loop)
- **implement**: After local code-review subagents complete, before final commit (sticky per feature/diff key)

Invoking skills MUST:
1. Pass a stable `review_key` for the feature
2. After fixing Critical/Important findings, re-invoke this skill with the **same** key instead of starting a disconnected new review
3. Stop the re-review loop when no Critical/Important findings remain (or after the warm-round cap triggers a final cold summary review)
