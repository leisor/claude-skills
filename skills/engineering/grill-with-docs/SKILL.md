---
name: grill-with-docs
description: "A relentless interview to sharpen a plan or design, which also creates docs (ADRs and CONTEXT.md glossary) as we go."
disable-model-invocation: true
---

# Grill With Docs

A relentless interview to sharpen a plan, architecture, or feature design before implementation, while actively building and maintaining project documentation (`CONTEXT.md` domain glossary and ADRs) inline as decisions are made.

This skill combines the interview methodology of [grilling](../../productivity/grilling/SKILL.md) with the active documentation habits of [domain-modeling](../domain-modeling/SKILL.md).

---

## 1. Initial Discovery

Before asking the first question:

1. **Read Domain Context**: Check for `CONTEXT.md` (or `CONTEXT-MAP.md` if multiple contexts exist) in the repository root. Load the existing domain language and boundaries.
2. **Review Existing ADRs**: Check `docs/adrs/` (or `docs/adr/`) to understand past architectural decisions and constraints.
3. **Inspect Relevant Code**: Use `Find`, `Grep`, and `Read` to understand existing code structure, interfaces, and patterns related to the topic.
4. **Identify Gaps & Inconsistencies**: Note any contradictions between what is being proposed and what the code or existing glossary states.

---

## 2. The Grilling & Documentation Loop

Structure the interview as a **design tree**: every major architectural or product choice branches into dependent sub-decisions.

Work the tree in **rounds** along the **frontier** (decisions whose prerequisites are settled):

### Rules of Engagement

- **1 Question Per Turn**: Ask exactly one focused question from the frontier at a time. Never dump multiple questions in a single message.
- **Fact-Checking First**: Look up facts yourself using `Read`, `Grep`, `Find`, or `Bash`. Never ask the user for information you can look up in the codebase.
- **Challenge Fuzzy Language**: If the user uses a term that conflicts with `CONTEXT.md` or uses overloaded words (e.g. "account", "user", "process"), challenge it immediately: *"Your glossary defines X as ..., but here you mean Y. Should we define a new term?"*
- **Concrete Edge-Case Scenarios**: Invent realistic boundary scenarios to test constraints and clarify assumptions.
- **No Code Editing (Workflow Guard Enforced)**: You are strictly exploring design. You do not have write access to codebase implementation or test files. Any call to `Edit`, `Write`, or bash redirection targeting source files is intercepted and blocked by the workflow guard hook. Never state that you are exiting plan mode or jumping to code. Only updates to `CONTEXT.md` and `docs/adrs/` are allowed.

### Question Format

Use interactive question tools when available, or output this structured format and stop:

```markdown
**Situation**: <2–4 short sentences: context, what is undecided, why it matters>
**Question**: <1 focused question>
**Options**:
- **A**: <Option title and consequence>
- **B**: <Option title and consequence>
- **C**: <Option title and consequence>
**Recommendation**: <Recommended option and why>
```

---

## 3. Inline Documentation Updates

Do not wait until the end of the interview to write documentation. Update docs as decisions crystallise:

### Updating `CONTEXT.md`
- As domain terms and entities are clarified or created, update `CONTEXT.md` immediately using `Edit` (or `Write` if creating it fresh).
- Follow the format in [CONTEXT-FORMAT.md](../domain-modeling/CONTEXT-FORMAT.md).
- Keep `CONTEXT.md` strictly as a domain glossary—free of implementation details, scratch notes, or spec snippets.

### Creating ADRs (Architecture Decision Records)
- Offer an ADR when a decision meets all three criteria:
  1. **Hard to reverse**: High cost to undo later.
  2. **Surprising without context**: Future developers would wonder why this path was chosen.
  3. **Result of a real trade-off**: Multiple viable alternatives were evaluated.
- Write ADRs to `docs/adrs/NNNN-<title>.md` (or `docs/adr/`) using `Write`.
- Follow the format in [ADR-FORMAT.md](../domain-modeling/ADR-FORMAT.md).

---

## 4. External Design Review

Once the design tree frontier is empty, before presenting to the user, consult a frontier model to challenge the design.

1. **Summarize design decisions**: Write a concise markdown summary of all decisions settled during the interview — key choices, data model, module boundaries, actors, and any open trade-offs noted.
2. **Choose a stable `review_key`**: derive from the feature name (e.g. `<feature>-design`). Reuse this key if the user revisits grilling on the same feature.
3. **Invoke `review-with-external`**: Load `skills/meta/review-with-external/SKILL.md`. Pass the decision summary, `review_type: "design"`, and the `review_key`.
4. **Address findings**:
   - For each **Critical** finding: raise it as a single targeted clarifying question following grilling rules (one question per turn, A/B/C options, stop after asking).
   - Note **Important** and **Minor** findings — surface them in the concluding summary so the user sees them before writing the spec.
5. **Re-review loop**: If Critical findings required user answers, update the design summary and re-invoke `review-with-external` with the same `review_key` (warm continue) until no Critical findings remain.

---

## 5. Concluding the Interview & Proceeding to Spec

The interview is complete when the design tree frontier is empty and the external design review is clear:

1. **Review Settled Decisions**: Briefly list the key decisions settled, glossary terms updated in `CONTEXT.md`, and any ADRs written. Include any Important/Minor findings from the external review.
2. **Proceed to Spec**: Immediately load `skills/engineering/to-spec/SKILL.md` and proceed to draft the specification.
