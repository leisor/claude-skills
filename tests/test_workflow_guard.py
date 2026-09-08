#!/usr/bin/env python3
"""Comprehensive unit tests for the workflow guard system."""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Add hooks directory to path
REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "hooks"
import sys
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from workflow_guard import (
    detect_phase_from_prompt,
    get_session_phase,
    is_bash_command_allowed,
    is_path_allowed,
    load_state,
    save_state,
    set_session_phase,
)


class TestWorkflowGuard(unittest.TestCase):
    """Test suite for workflow guard validation and phase handling."""

    def setUp(self):
        """Create a temporary project directory for testing."""
        self.temp_dir = tempfile.mkdtemp(prefix="workflow_guard_test_")
        self.project_root = Path(self.temp_dir)
        (self.project_root / ".git").mkdir()
        (self.project_root / "src").mkdir()
        (self.project_root / "tests").mkdir()
        (self.project_root / "docs" / "adrs").mkdir(parents=True)

    def tearDown(self):
        """Clean up temporary test directory."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_phase_from_prompt(self):
        """Test slash command and prompt pattern detection."""
        self.assertEqual(
            detect_phase_from_prompt("/grill-with-docs"),
            ("grilling", "grill-with-docs")
        )
        self.assertEqual(
            detect_phase_from_prompt("/grill-me please"),
            ("grilling", "grill-with-docs")
        )
        self.assertEqual(
            detect_phase_from_prompt("Let us do /grilling now"),
            ("grilling", "grill-with-docs")
        )
        self.assertEqual(
            detect_phase_from_prompt("/to-spec"),
            ("spec", "to-spec")
        )
        self.assertEqual(
            detect_phase_from_prompt("/to-tickets"),
            ("tickets", "to-tickets")
        )
        self.assertEqual(
            detect_phase_from_prompt("/implement"),
            ("implement", "implement")
        )
        self.assertEqual(
            detect_phase_from_prompt("/unlock-workflow"),
            ("idle", "manual-unlock")
        )
        # Non-matching prompts
        self.assertIsNone(detect_phase_from_prompt("What is the to-spec syntax?"))
        self.assertIsNone(detect_phase_from_prompt("a+b"))
        self.assertIsNone(detect_phase_from_prompt("print both odds"))

    def test_state_management_and_isolation(self):
        """Test state persistence and session isolation."""
        # Initial phase should be idle
        self.assertEqual(get_session_phase(self.project_root, "session-1"), "idle")

        # Set session-1 to grilling
        set_session_phase(self.project_root, "session-1", "grilling", "grill-with-docs")
        self.assertEqual(get_session_phase(self.project_root, "session-1"), "grilling")

        # Session-2 should remain idle
        self.assertEqual(get_session_phase(self.project_root, "session-2"), "grilling")
        # Explicitly set session-2 to implement
        set_session_phase(self.project_root, "session-2", "implement", "implement")
        self.assertEqual(get_session_phase(self.project_root, "session-2"), "implement")
        self.assertEqual(get_session_phase(self.project_root, "session-1"), "grilling")

    def test_path_allowed_in_grilling(self):
        """Test allowed and forbidden file paths during grilling."""
        phase = "grilling"

        # Allowed documentation files
        allowed_paths = [
            "CONTEXT.md",
            "CONTEXT-MAP.md",
            "docs/adrs/0001-initial.md",
            "docs/specs/feature-a.md",
            "docs/tickets/001-task.md",
            ".claude/settings.json",
            ".claude/workflow-state.json",
            "README.md",
            "/tmp/scratch.py",
        ]
        for path in allowed_paths:
            allowed, reason = is_path_allowed(path, phase, self.project_root)
            self.assertTrue(allowed, f"Expected '{path}' to be allowed: {reason}")

        # Blocked implementation and test files
        blocked_paths = [
            "src/signals/vedonlyoja.py",
            "tests/test_vedonlyoja.py",
            "src/index.ts",
            "app/main.py",
            "lib/engine.rs",
            "package.json",
            "Cargo.toml",
            "pyproject.toml",
            "src/utils.js",
        ]
        for path in blocked_paths:
            allowed, reason = is_path_allowed(path, phase, self.project_root)
            self.assertFalse(allowed, f"Expected '{path}' to be blocked in {phase}: {reason}")

    def test_path_allowed_in_implement(self):
        """Test that all files are unlocked during implement phase."""
        phase = "implement"

        paths = [
            "src/signals/vedonlyoja.py",
            "tests/test_vedonlyoja.py",
            "package.json",
            "CONTEXT.md",
        ]
        for path in paths:
            allowed, reason = is_path_allowed(path, phase, self.project_root)
            self.assertTrue(allowed, f"Expected '{path}' to be allowed in {phase}: {reason}")

    def test_bash_commands_in_grilling(self):
        """Test bash command inspection during grilling phase."""
        phase = "grilling"

        # Safe read-only or inspection commands
        safe_commands = [
            "git status",
            "git diff",
            "git rev-parse HEAD",
            "pytest tests/test_foo.py",
            "cat src/signals/vedonlyoja.py",
            "find src/ -name '*.py'",
            "grep -rn 'current_odds' src/",
            "ls -la docs/",
            "echo 'hello world'",
        ]
        for cmd in safe_commands:
            allowed, reason = is_bash_command_allowed(cmd, phase)
            self.assertTrue(allowed, f"Expected safe command '{cmd}' to be allowed: {reason}")

        # Dangerous write commands targeting source or tests
        dangerous_commands = [
            "cat << 'EOF' > src/signals/vedonlyoja.py",
            "echo 'x = 1' > src/foo.py",
            "echo 'x = 1' >> tests/test_foo.py",
            "tee src/app.ts < input.txt",
            "sed -i 's/old/new/g' src/signals/vedonlyoja.py",
        ]
        for cmd in dangerous_commands:
            allowed, reason = is_bash_command_allowed(cmd, phase)
            self.assertFalse(allowed, f"Expected write command '{cmd}' to be blocked in {phase}: {reason}")

    def test_end_to_end_hook_scripts(self):
        """Test the actual hook script entry points via subprocess."""
        import json
        import subprocess

        hooks_dir = REPO_ROOT / "hooks"
        prompt_hook = hooks_dir / "userpromptsubmit_workflow_guard.py"
        pretool_hook = hooks_dir / "pretooluse_workflow_guard.py"
        session_hook = hooks_dir / "sessionstart_workflow_guard.py"

        session_id = "test-session-e2e"
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.project_root)}

        # 1. User submits /grill-with-docs
        p1 = subprocess.run(
            [sys.executable, str(prompt_hook)],
            input=json.dumps({
                "user_prompt": "/grill-with-docs",
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p1.returncode, 0)
        out1 = json.loads(p1.stdout)
        self.assertIn("Workflow phase: 'grilling' active", out1.get("systemMessage", ""))

        # 2. Agent tries to edit src/foo.py -> BLOCKED (exit 2)
        p2 = subprocess.run(
            [sys.executable, str(pretool_hook)],
            input=json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/foo.py"},
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p2.returncode, 2)
        self.assertIn("WORKFLOW GUARD BLOCKED", p2.stderr)

        # 3. Agent edits CONTEXT.md -> ALLOWED (exit 0)
        p3 = subprocess.run(
            [sys.executable, str(pretool_hook)],
            input=json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "CONTEXT.md"},
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p3.returncode, 0)

        # 4. User moves to /to-spec
        p4 = subprocess.run(
            [sys.executable, str(prompt_hook)],
            input=json.dumps({
                "user_prompt": "/to-spec",
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p4.returncode, 0)

        # 5. Agent writes docs/specs/new.md -> ALLOWED (exit 0)
        p5 = subprocess.run(
            [sys.executable, str(pretool_hook)],
            input=json.dumps({
                "tool_name": "Write",
                "tool_input": {"file_path": "docs/specs/new.md"},
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p5.returncode, 0)

        # 6. User moves to /implement
        p6 = subprocess.run(
            [sys.executable, str(prompt_hook)],
            input=json.dumps({
                "user_prompt": "/implement",
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p6.returncode, 0)

        # 7. Agent edits src/foo.py -> ALLOWED in implement (exit 0)
        p7 = subprocess.run(
            [sys.executable, str(pretool_hook)],
            input=json.dumps({
                "tool_name": "Edit",
                "tool_input": {"file_path": "src/foo.py"},
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p7.returncode, 0)

        # 8. Session startup resets to idle
        p8 = subprocess.run(
            [sys.executable, str(session_hook)],
            input=json.dumps({
                "source": "startup",
                "session_id": session_id,
                "cwd": str(self.project_root),
            }),
            text=True,
            capture_output=True,
            env=env,
        )
        self.assertEqual(p8.returncode, 0)
        self.assertEqual(get_session_phase(self.project_root, session_id), "idle")


if __name__ == "__main__":
    unittest.main()
