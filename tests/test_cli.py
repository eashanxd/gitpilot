"""Unit and integration tests for the GitPilot CLI and status formatter."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.cli import format_status, run_cli
from gitpilot.core.errors import (
    GitCommandError,
    GitNotInstalledError,
    GitTimeoutError,
    NotAGitRepositoryError,
)
from gitpilot.core.models import (
    BranchInfo,
    FileChange,
    FileStatus,
    RepositoryState,
)


class TestStatusFormatter(unittest.TestCase):
    """Test suite for format_status."""

    def test_format_clean_repository(self):
        state = RepositoryState(
            root_path=Path("C:/test_repo"),
            branch=BranchInfo(
                name="main",
                oid="1234567890abcdef",
                upstream="origin/main",
                ahead=0,
                behind=0,
            ),
            staged_files=[],
            unstaged_files=[],
            untracked_files=[],
            conflicted_files=[],
        )

        output = format_status(state)

        self.assertIn("GitPilot", output)
        self.assertIn("Repository: C:\\test_repo" if sys.platform == "win32" else "Repository: C:/test_repo", output)
        self.assertIn("Branch: main", output)
        self.assertIn("Upstream: origin/main", output)
        self.assertIn("Ahead: 0", output)
        self.assertIn("Behind: 0", output)
        self.assertIn("Working tree is clean (nothing to commit).", output)
        self.assertNotIn("Files:", output)

    def test_format_no_upstream(self):
        state = RepositoryState(
            root_path=Path("/repo"),
            branch=BranchInfo(name="feature/login"),
        )
        output = format_status(state)
        self.assertIn("Branch: feature/login", output)
        self.assertIn("Upstream: none", output)
        self.assertNotIn("Ahead:", output)

    def test_format_detached_head(self):
        state = RepositoryState(
            root_path=Path("/repo"),
            branch=BranchInfo(
                oid="a1b2c3d4e5f6",
                is_detached=True,
            ),
        )
        output = format_status(state)
        self.assertIn("Branch: (detached at a1b2c3d)", output)
        self.assertIn("Upstream: none", output)

    def test_format_initial_unborn_commit(self):
        state = RepositoryState(
            root_path=Path("/repo"),
            branch=BranchInfo(
                name="main",
                is_initial=True,
            ),
        )
        output = format_status(state)
        self.assertIn("Branch: main (initial commit)", output)

    def test_format_repository_with_all_change_types(self):
        state = RepositoryState(
            root_path=Path("/repo"),
            branch=BranchInfo(name="main"),
            staged_files=[
                FileChange(path="src/new.py", staged_status=FileStatus.ADDED),
                FileChange(
                    path="src/renamed.py",
                    orig_path="src/old.py",
                    staged_status=FileStatus.RENAMED,
                ),
            ],
            unstaged_files=[
                FileChange(path="src/modified.py", unstaged_status=FileStatus.MODIFIED),
                FileChange(path="src/deleted.py", unstaged_status=FileStatus.DELETED),
            ],
            untracked_files=[
                FileChange(path="notes.txt", staged_status=FileStatus.UNTRACKED, unstaged_status=FileStatus.UNTRACKED),
            ],
            conflicted_files=[
                FileChange(path="src/conflict.py", staged_status=FileStatus.CONFLICT, unstaged_status=FileStatus.CONFLICT),
            ],
        )

        output = format_status(state)

        self.assertIn("Staged: 2", output)
        self.assertIn("Unstaged: 2", output)
        self.assertIn("Untracked: 1", output)
        self.assertIn("Conflicts: 1", output)

        self.assertIn("Files:", output)
        self.assertIn("U  src/conflict.py (conflict)", output)
        self.assertIn("A  src/new.py (staged)", output)
        self.assertIn("R  src/renamed.py (staged, renamed from src/old.py)", output)
        self.assertIn("M  src/modified.py", output)
        self.assertIn("D  src/deleted.py", output)
        self.assertIn("?  notes.txt", output)


class TestRunCLI(unittest.TestCase):
    """Test suite for run_cli execution and argument handling."""

    @patch("gitpilot.cli.Repository")
    def test_run_cli_defaults_to_current_directory(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.get_state.return_value = RepositoryState(
            root_path=Path.cwd(),
            branch=BranchInfo(name="main"),
        )
        mock_repo_class.return_value = mock_repo

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli([])

        self.assertEqual(exit_code, 0)
        mock_repo_class.assert_called_once_with(Path("."))
        self.assertIn("GitPilot", stdout_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_with_explicit_path(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.get_state.return_value = RepositoryState(
            root_path=Path("/custom/repo"),
            branch=BranchInfo(name="develop"),
        )
        mock_repo_class.return_value = mock_repo

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["/custom/repo"])

        self.assertEqual(exit_code, 0)
        mock_repo_class.assert_called_once_with(Path("/custom/repo"))
        self.assertIn("Branch: develop", stdout_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_file_not_found(self, mock_repo_class):
        mock_repo_class.side_effect = FileNotFoundError("Path does not exist")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["non_existent_folder"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Path does not exist", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_not_a_git_repository(self, mock_repo_class):
        mock_repo_class.side_effect = NotAGitRepositoryError("/not/a/repo")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["/not/a/repo"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: '/not/a/repo' is not inside a Git repository.", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_git_not_installed(self, mock_repo_class):
        mock_repo_class.side_effect = GitNotInstalledError("Git not in PATH")

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli([])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Git not in PATH", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_git_timeout(self, mock_repo_class):
        mock_repo_class.side_effect = GitTimeoutError(command=["git", "status"], timeout=30.0)

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli([])

        self.assertEqual(exit_code, 1)
        self.assertIn("timed out after 30.0 seconds", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_git_command_error(self, mock_repo_class):
        mock_repo_class.side_effect = GitCommandError(
            command=["git", "status"],
            exit_code=128,
            stdout="",
            stderr="fatal: corrupt repository",
        )

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli([])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Git command failed (git status): fatal: corrupt repository", stderr_capture.getvalue())


if __name__ == "__main__":
    unittest.main()

