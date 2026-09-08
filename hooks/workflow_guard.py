#!/usr/bin/env python3
"""Workflow guard core module for enforcing Matt Pocock engineering stages.

Prevents agents from eagerly editing code or tests during grilling, spec,
and ticket breakdown phases. Unlocks edits during the implement phase.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

GUARDED_PHASES = {"grilling", "spec", "tickets"}
ALL_PHASES = {"idle", "grilling", "spec", "tickets", "implement"}

CODE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".go", ".rs", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".java", ".kt", ".scala", ".rb", ".php", ".swift", ".cs",
    ".sh", ".bash", ".zsh", ".sql", ".html", ".css", ".scss"
}

CODE_DIRS = {
    "src", "app", "lib", "pkg", "packages", "tests", "test",
    "spec", "__tests__", "scripts", "bin"
}

ALLOWED_DOC_PREFIXES = (
    "docs/",
    ".claude/",
    ".agents/",
)

ALLOWED_DOC_FILENAMES = {
    "context.md",
    "context-map.md",
    "claude.md",
    "agents.md",
    "readme.md",
    "changelog.md",
}


def get_project_root(cwd: Optional[str] = None) -> Path:
    """Find the root directory of the current project or git worktree."""
    start_path = Path(cwd).resolve() if cwd else Path.cwd().resolve()
    current = start_path

    # Check for git root or .claude directory
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() or (parent / ".claude").exists():
            return parent

    # Fallback to CLAUDE_PROJECT_DIR if present
    env_project = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_project:
        p = Path(env_project).resolve()
        if p.exists():
            return p

    return start_path


def get_state_file_path(project_root: Path) -> Path:
    """Return the path to the workflow state file."""
    claude_dir = project_root / ".claude"
    try:
        claude_dir.mkdir(parents=True, exist_ok=True)
        return claude_dir / "workflow-state.json"
    except (OSError, PermissionError):
        # Fallback to user tmp directory if project directory is read-only
        tmp_dir = Path("/tmp") / f"claude-workflow-{os.getuid()}"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        safe_name = str(project_root).replace("/", "_").strip("_")
        return tmp_dir / f"{safe_name}.json"


def load_state(project_root: Path) -> Dict[str, Any]:
    """Load workflow state from file."""
    state_file = get_state_file_path(project_root)
    if not state_file.exists():
        return {"current_phase": "idle", "sessions": {}}

    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                return {"current_phase": "idle", "sessions": {}}
            data.setdefault("current_phase", "idle")
            data.setdefault("sessions", {})
            return data
    except (json.JSONDecodeError, OSError):
        return {"current_phase": "idle", "sessions": {}}


def save_state(project_root: Path, state: Dict[str, Any]) -> None:
    """Save workflow state atomically."""
    state_file = get_state_file_path(project_root)
    temp_file = state_file.with_name(f"{state_file.name}.tmp.{os.getpid()}")
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
        temp_file.replace(state_file)
    except OSError:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def get_session_phase(project_root: Path, session_id: Optional[str] = None) -> str:
    """Get the active workflow phase for the given session or project."""
    state = load_state(project_root)
    if session_id and session_id in state.get("sessions", {}):
        return state["sessions"][session_id].get("phase", "idle")
    return state.get("current_phase", "idle")


def set_session_phase(
    project_root: Path,
    session_id: Optional[str],
    phase: str,
    skill: Optional[str] = None
) -> None:
    """Set the workflow phase for a session and update project current phase."""
    if phase not in ALL_PHASES:
        raise ValueError(f"Invalid phase '{phase}'. Must be one of: {sorted(ALL_PHASES)}")

    state = load_state(project_root)
    now_iso = datetime.now(timezone.utc).isoformat()

    state["current_phase"] = phase
    state["updated_at"] = now_iso

    if session_id:
        sessions = state.setdefault("sessions", {})
        sessions[session_id] = {
            "phase": phase,
            "skill": skill or phase,
            "updated_at": now_iso
        }

    save_state(project_root, state)


def is_path_allowed(
    file_path: str,
    phase: str,
    project_root: Path
) -> Tuple[bool, str]:
    """Check whether a file write or edit is allowed in the current phase."""
    if phase not in GUARDED_PHASES:
        return True, f"Phase '{phase}' does not restrict file modifications."

    raw_path = Path(file_path)

    # If path is absolute, try resolving relative to project root
    if raw_path.is_absolute():
        try:
            rel_path = raw_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            # File is outside project root
            # Allow temporary files outside project (e.g. in /tmp)
            resolved_str = str(raw_path.resolve())
            if resolved_str.startswith("/tmp") or resolved_str.startswith("/var/tmp"):
                return True, "Temporary files outside project are allowed."
            return False, f"Modifications outside project root are blocked during '{phase}'."
    else:
        rel_path = raw_path

    rel_posix = rel_path.as_posix()
    if rel_posix.startswith("./"):
        rel_posix = rel_posix[2:]
    rel_lower = rel_posix.lower()
    file_name_lower = rel_path.name.lower()
    ext_lower = rel_path.suffix.lower()

    # Always allowed during grilling and spec:
    # 1. Root documentation files: CONTEXT.md, README.md, etc.
    if file_name_lower in ALLOWED_DOC_FILENAMES:
        return True, "Core documentation file is allowed."

    # 2. Files under allowed directories: docs/**, .claude/**, .agents/**
    if any(rel_lower.startswith(prefix) for prefix in ALLOWED_DOC_PREFIXES):
        return True, "Documentation and configuration directory is allowed."

    # 3. Any local markdown file unless explicitly located in code directory
    parts = [p.lower() for p in rel_path.parts[:-1]]
    is_in_code_dir = any(part in CODE_DIRS for part in parts)

    if ext_lower == ".md" and not is_in_code_dir:
        return True, "Documentation markdown file outside code directories is allowed."

    # Block code files or files inside code directories
    if is_in_code_dir:
        return (
            False,
            f"Directory '{rel_posix}' is inside codebase or test folders (blocked in '{phase}')."
        )

    if ext_lower in CODE_EXTENSIONS:
        return (
            False,
            f"File extension '{ext_lower}' indicates source code or executable (blocked in '{phase}')."
        )

    if file_name_lower in {"package.json", "cargo.toml", "pyproject.toml", "makefile", "dockerfile"}:
        return (
            False,
            f"Build or dependency manifest '{rel_posix}' is blocked in '{phase}'."
        )

    # By default, block unclassified files in guarded phase
    return (
        False,
        f"File '{rel_posix}' is not recognised as documentation or configuration in '{phase}'."
    )


def is_bash_command_allowed(
    command: str,
    phase: str
) -> Tuple[bool, str]:
    """Check if a bash command attempts to write to source or test files during guarded phase."""
    if phase not in GUARDED_PHASES:
        return True, f"Phase '{phase}' does not restrict bash commands."

    cmd_clean = command.strip()

    # Look for redirection operators targeting code directories or extensions
    redirect_pattern = r"(?:>|>>|tee\s+(?:-[a-zA-Z]+\s+)*)\s*['\"]?(?:(\.?\/?(?:src|app|lib|pkg|tests|test|spec)\/[^\s'\"]+)|([^\s'\"]+\.(?:py|ts|tsx|js|jsx|go|rs|c|cpp|java|rb|sh)))"
    match = re.search(redirect_pattern, cmd_clean, re.IGNORECASE)
    if match:
        target = match.group(1) or match.group(2)
        return (
            False,
            f"Bash command redirects output into source or test file '{target}' during '{phase}'."
        )

    # Look for in-place modifications (sed -i, perl -i)
    inplace_pattern = r"\b(?:sed|perl)\s+-[a-zA-Z]*i[a-zA-Z]*\s+.*?(?:src\/|tests\/|\.(?:py|ts|tsx|js|jsx|go|rs))"
    if re.search(inplace_pattern, cmd_clean, re.IGNORECASE):
        return (
            False,
            f"In-place file modification command detected during '{phase}'."
        )

    return True, "Command is read-only or does not modify guarded code files."


def detect_phase_from_prompt(user_prompt: str) -> Optional[Tuple[str, str]]:
    """Detect if the user prompt triggers a workflow phase transition.

    Returns (phase, skill_name) or None if no transition.
    """
    text = user_prompt.strip()

    # Grilling triggers
    if re.search(r"(?:^|\s)/(?:grill-with-docs|grill-me|grilling)\b|^\s*(?:grill-with-docs|grill-me|grilling)\b", text, re.IGNORECASE):
        return "grilling", "grill-with-docs"

    # Spec triggers
    if re.search(r"(?:^|\s)/(?:to-spec)\b|^\s*(?:to-spec)\b", text, re.IGNORECASE):
        return "spec", "to-spec"

    # Ticket breakdown triggers
    if re.search(r"(?:^|\s)/(?:to-tickets)\b|^\s*(?:to-tickets)\b", text, re.IGNORECASE):
        return "tickets", "to-tickets"

    # Implementation triggers
    if re.search(r"(?:^|\s)/(?:implement)\b|^\s*(?:implement)\b", text, re.IGNORECASE):
        return "implement", "implement"

    # Manual unlock triggers
    if re.search(r"(?:^|\s)/(?:unlock-workflow|cancel-grill|workflow-unlock|workflow-reset)\b", text, re.IGNORECASE):
        return "idle", "manual-unlock"

    return None


def format_block_message(
    phase: str,
    target: str,
    reason: str
) -> str:
    """Format a clear, actionable blocking message for Claude."""
    return f"""🛑 WORKFLOW GUARD BLOCKED OPERATION

Active Workflow Phase: '{phase}'
Target: {target}
Reason: {reason}

You are in the design, architecture, or planning stage. Modifying application
source code or test files is strictly forbidden until the /implement phase.

Allowed modifications during '{phase}':
  • CONTEXT.md (domain language and boundaries)
  • docs/adrs/ (Architecture Decision Records)
  • docs/specs/ (Feature specifications)
  • docs/tickets/ (Implementation tickets)
  • .claude/ (local configurations)

Next Steps:
1. If in 'grilling':
   - Continue asking one focused question per turn from the decision tree frontier.
   - Inline document settled choices in CONTEXT.md and docs/adrs/.
   - Run external design review with /review-with-external.
   - When the interview is complete, proceed to /to-spec.
2. If in 'spec':
   - Write the feature specification in docs/specs/ and proceed to /to-tickets.
3. If in 'tickets':
   - Create tickets in docs/tickets/ and proceed to /implement.
4. If implementation is ready, invoke /implement to unlock code and test files.

To manually unlock anytime, run: workflow-gate unlock
"""
