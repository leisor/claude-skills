---
name: retro
description: "Conduct a retrospective on a coding session."
disable-model-invocation: true
---

The user has asked for a **retrospective**. You are suggesting improvements to the coding agent's **environment** to improve future runs.

## Steps

1. Call the Skill tool with `writing-for-agents` for the writing style guide.

2. Use the **current in-context conversation** as the session to review. Do not search for log files.

3. Look for candidates for improvement in these categories.

   - **Navigation**: how easy was it for the agent to find the right files? Are there hidden dependencies between files? Would a **navigation pointer** make it easier? _Use when_ the session took a long time to find a piece of information.
   - **Automated checks**: are there automated checks that could catch errors the agent made? Linting, typing, tests, filesystem linters? _Use when_ the agent made a mistake that could have been caught by an automated check.
   - **Coding standards**: should the standards reviewer or repo rules be given a new rule to enforce? Should an existing rule be removed or clarified? _Use when_ the reviewer failed to catch a mistake, or when a pattern keeps recurring across sessions.
   - **CLAUDE.md / global scope**: are there steering instructions that should be turned into coding standards or automated checks instead of staying in CLAUDE.md? _Use when_ the system prompt or CLAUDE.md is growing large or contains rules that could be enforced mechanically.
   - **Tool economy**: did the agent make expensive tool calls that could be streamlined?

4. Write findings to `docs/retros/YYYY-MM-DD-<slug>.md` (create `docs/retros/` if `docs/` exists). If no `docs/` directory exists, write to `retro-<slug>.md` in the project root. Report the path after writing.

5. **Ship the cheap mechanical remedies now, before the retro is done.** A finding that says "add a pin test" is finished only when the test exists and passes; a "add a pointer" finding finishes when the pointer is written. Write the file, land the small fixes with it (repo retros may carry their guard updates — see the repo's CLAUDE.md / AGENTS.md main-edit exceptions), and say in the retro what shipped. Leave only design-judgment items as recommendations, and name them as such.
