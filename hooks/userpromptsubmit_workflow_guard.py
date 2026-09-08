#!/usr/bin/env python3
"""UserPromptSubmit hook for workflow guard.

Detects workflow commands in user prompts (e.g. /grill-with-docs, /to-spec,
/to-tickets, /implement) and updates the active workflow phase.
"""

import json
import os
import sys
from pathlib import Path

# Add hooks directory to path for workflow_guard import
HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

try:
    from workflow_guard import (
        detect_phase_from_prompt,
        get_project_root,
        set_session_phase,
    )
except ImportError as e:
    # Fail open on import errors
    print(f"Warning: workflow_guard import failed: {e}", file=sys.stderr)
    sys.exit(0)


def main() -> None:
    """Read prompt submission, detect phase, and update state."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)

        data = json.loads(raw_input)
        user_prompt = data.get("user_prompt", "")
        session_id = data.get("session_id")
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")

        if not user_prompt:
            sys.exit(0)

        transition = detect_phase_from_prompt(user_prompt)
        if transition:
            new_phase, skill_name = transition
            project_root = get_project_root(cwd)
            set_session_phase(project_root, session_id, new_phase, skill_name)

            if new_phase in {"grilling", "spec", "tickets"}:
                msg = (
                    f"Workflow phase: '{new_phase}' active. Code and test modifications "
                    f"are locked until /implement."
                )
                output = {"continue": True, "systemMessage": msg}
                print(json.dumps(output))
            elif new_phase == "implement":
                msg = "Workflow phase: 'implement' active. Code and test modifications are now unlocked."
                output = {"continue": True, "systemMessage": msg}
                print(json.dumps(output))
            elif new_phase == "idle":
                msg = "Workflow guard unlocked. Normal file editing resumed."
                output = {"continue": True, "systemMessage": msg}
                print(json.dumps(output))

    except Exception as e:
        # Never crash or block user prompts on unexpected hook errors
        print(f"Workflow guard prompt hook error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
