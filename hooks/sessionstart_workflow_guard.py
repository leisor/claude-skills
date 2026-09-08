#!/usr/bin/env python3
"""SessionStart hook for workflow guard.

Initializes new sessions in 'idle' phase so fresh conversations are not
unintentionally locked into previous workflow phases.
"""

import json
import os
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

try:
    from workflow_guard import get_project_root, set_session_phase
except ImportError as e:
    print(f"Warning: workflow_guard import failed: {e}", file=sys.stderr)
    sys.exit(0)


def main() -> None:
    """Initialize session state on startup."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            sys.exit(0)

        data = json.loads(raw_input)
        session_id = data.get("session_id")
        source = data.get("source", "startup")
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")

        # On startup (new conversation), start in idle
        if source == "startup" and session_id:
            project_root = get_project_root(cwd)
            set_session_phase(project_root, session_id, "idle", skill="init")

    except Exception as e:
        print(f"Workflow guard SessionStart error: {e}", file=sys.stderr)
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
