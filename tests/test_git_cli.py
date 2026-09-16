"""Unit tests for the Git CLI wrapper and domain errors."""

import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is in python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.errors import (
    GitCommandError,
    GitNotInstalledError,
    GitPilotError,
    GitTimeoutError,
)
from gitpilot.core.git_cli import (
    GitCommandResult,
    is_git_installed,
    run_git,
    verify_git_installed,
)


class TestGitAvailability(unittest.TestCase):
    """Tests for Git installation detection."""

    @patch("gitpilot.core.git_cli.shutil.which", return_value="C:\\Program Files\\Git\\cmd\\git.exe")
    def test_git_is_available(self, mock_which):
        self.assertTrue(is_git_installed())
        mock_which.assert_called_once_with("git")

    @patch("gitpilot.core.git_cli.shutil.which", return_value=None)
    def test_git_is_not_available(self, mock_which):
        self.assertFalse(is_git_installed())
        mock_which.assert_called_once_with("git")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    def test_verify_git_installed_success(self, mock_is_installed):
        # Should complete without raising any exception
        verify_git_installed()
        mock_is_installed.assert_called_once()

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=False)
    def test_verify_git_installed_failure(self, mock_is_installed):
        with self.assertRaises(GitNotInstalledError):
            verify_git_installed()

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=False)
    def test_run_git_raises_when_git_not_installed(self, mock_is_installed):
        with self.assertRaises(GitNotInstalledError):
            run_git(["status"])


class TestRunGitExecution(unittest.TestCase):
    """Tests for run_git subprocess execution."""

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_successful_git_command(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout="On branch main\nnothing to commit",
            stderr="",
        )

        result = run_git(["status"])

        self.assertIsInstance(result, GitCommandResult)
        self.assertEqual(result.command, ["git", "status"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "On branch main\nnothing to commit")
        self.assertEqual(result.stderr, "")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_failed_git_command_raises_git_command_error(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "checkout", "non-existent"],
            returncode=1,
            stdout="",
            stderr="error: pathspec 'non-existent' did not match any file(s) known to git",
        )

        with self.assertRaises(GitCommandError) as context:
            run_git(["checkout", "non-existent"])

        exc = context.exception
        self.assertEqual(exc.command, ["git", "checkout", "non-existent"])
        self.assertEqual(exc.exit_code, 1)
        self.assertEqual(exc.stdout, "")
        self.assertIn("error: pathspec 'non-existent'", exc.stderr)
        self.assertIn("failed with exit code 1", str(exc))

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_failed_git_command_with_check_false(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=128,
            stdout="",
            stderr="fatal: not a git repository",
        )

        result = run_git(["status"], check=False)

        self.assertEqual(result.exit_code, 128)
        self.assertEqual(result.stderr, "fatal: not a git repository")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_timeout_behavior(self, mock_run, mock_installed):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["git", "fetch"], timeout=5.0)

        with self.assertRaises(GitTimeoutError) as context:
            run_git(["fetch"], timeout=5.0)

        exc = context.exception
        self.assertEqual(exc.command, ["git", "fetch"])
        self.assertEqual(exc.timeout, 5.0)
        self.assertIn("timed out after 5.0 seconds", str(exc))

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_correct_arguments_passed_to_subprocess(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status", "--porcelain=v2"],
            returncode=0,
            stdout="",
            stderr="",
        )

        test_dir = Path("C:/test_repo")
        run_git(["status", "--porcelain=v2"], cwd=test_dir, timeout=15.0)

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0], ["git", "status", "--porcelain=v2"])
        self.assertEqual(kwargs["cwd"], str(test_dir))
        self.assertEqual(kwargs["timeout"], 15.0)
        self.assertEqual(kwargs["shell"], False)
        self.assertEqual(kwargs["capture_output"], True)
        self.assertEqual(kwargs["text"], True)
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_git_prefix_not_duplicated_if_already_present(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "version"],
            returncode=0,
            stdout="",
            stderr="",
        )

        run_git(["git", "version"])

        args, _ = mock_run.call_args
        self.assertEqual(args[0], ["git", "version"])

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_git_terminal_prompt_zero_is_applied(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout="",
            stderr="",
        )

        run_git(["status"])

        _, kwargs = mock_run.call_args
        env = kwargs["env"]
        self.assertIn("GIT_TERMINAL_PROMPT", env)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run")
    def test_custom_env_preserves_git_terminal_prompt(self, mock_run, mock_installed):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["git", "status"],
            returncode=0,
            stdout="",
            stderr="",
        )

        run_git(["status"], env={"CUSTOM_VAR": "value"})

        _, kwargs = mock_run.call_args
        env = kwargs["env"]
        self.assertEqual(env["CUSTOM_VAR"], "value")
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")

    @patch("gitpilot.core.git_cli.is_git_installed", return_value=True)
    @patch("gitpilot.core.git_cli.subprocess.run", side_effect=FileNotFoundError())
    def test_file_not_found_raises_git_not_installed(self, mock_run, mock_installed):
        with self.assertRaises(GitNotInstalledError):
            run_git(["status"])


class TestRealGitCLIIntegration(unittest.TestCase):
    """Smoke test with the real system Git if installed."""

    def test_real_git_version(self):
        if not is_git_installed():
            self.skipTest("Git not installed on system")

        result = run_git(["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout.startswith("git version"))


if __name__ == "__main__":
    unittest.main()

