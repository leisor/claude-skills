#!/usr/bin/env python3
"""PreToolUse hook for workflow guard.

Intercepts Edit, Write, MultiEdit, and file-modifying Bash commands.
Blocks code or test modifications while in grilling, spec, or tickets phases.
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
        GUARDED_PHASES,
        format_block_message,
        get_project_root,
        get_session_phase,
        is_bash_command_allowed,
        is_path_allowed,
    )
except ImportError as e:
    # Fail open on import errors so user is not locked out
    print(f"Warning: workflow_guard import failed: {e}", file=sys.stderr)
    sys.exit(0)


def block_operation(phase: str, target: str, reason: str) -> None:
    """Output denial payload and terminate with exit code 2."""
    message = format_block_message(phase, target, reason)

    # Output JSON error structure for Claude Code
    block_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny"
        },
        "systemMessage": message
    }
    print(json.dumps(block_payload), file=sys.stderr)
    sys.exit(2)


def main() -> None:
    """Evaluate tool invocation against workflow guard policy."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)

        data = json.loads(raw_input)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        session_id = data.get("session_id")
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")

        project_root = get_project_root(cwd)
        phase = get_session_phase(project_root, session_id)

        if phase not in GUARDED_PHASES:
            sys.exit(0)

        # File modification tools
        if tool_name in {"Edit", "Write", "MultiEdit"}:
            file_path = tool_input.get("file_path", "")
            if not file_path:
                sys.exit(0)

            allowed, reason = is_path_allowed(file_path, phase, project_root)
            if not allowed:
                block_operation(phase, file_path, reason)

        # Bash tool file modifications
        elif tool_name == "Bash":
            command = tool_input.get("command", "")
            if not command:
                sys.exit(0)

            allowed, reason = is_bash_command_allowed(command, phase)
            if not allowed:
                block_operation(phase, f"Bash command: {command}", reason)

        sys.exit(0)

    except json.JSONDecodeError:
        # Non-JSON or broken stdin - allow operation
        sys.exit(0)
    except Exception as e:
        # On internal error, log warning and fail open
        print(f"Workflow guard PreToolUse error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
