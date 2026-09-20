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

    @patch("gitpilot.cli.Repository")
    def test_run_cli_list_branches_flag(self, mock_repo_class):
        from gitpilot.core.models import LocalBranch

        mock_repo = MagicMock()
        mock_repo.list_branches.return_value = [
            LocalBranch(name="main", is_current=True),
            LocalBranch(name="feature-x", is_current=False),
        ]
        mock_repo_class.return_value = mock_repo

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--branches"])

        self.assertEqual(exit_code, 0)
        output = stdout_capture.getvalue()
        self.assertIn("Branches:", output)
        self.assertIn("* main", output)
        self.assertIn("  feature-x", output)

    @patch("gitpilot.cli.Repository")
    def test_run_cli_create_branch_flag(self, mock_repo_class):
        from gitpilot.core.models import LocalBranch

        mock_repo = MagicMock()
        mock_repo.create_branch.return_value = LocalBranch(name="feature-new", is_current=False)
        mock_repo_class.return_value = mock_repo

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--create-branch", "feature-new"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Created branch 'feature-new'.", stdout_capture.getvalue())
        mock_repo.create_branch.assert_called_once_with("feature-new")

    @patch("gitpilot.cli.Repository")
    def test_run_cli_switch_branch_flag(self, mock_repo_class):
        from gitpilot.core.models import LocalBranch

        mock_repo = MagicMock()
        mock_repo.switch_branch.return_value = LocalBranch(name="feature-switch", is_current=True)
        mock_repo_class.return_value = mock_repo

        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--switch-branch", "feature-switch"])

        self.assertEqual(exit_code, 0)
        self.assertIn("Switched to branch 'feature-switch'.", stdout_capture.getvalue())
        mock_repo.switch_branch.assert_called_once_with("feature-switch")

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_branch_not_found(self, mock_repo_class):
        from gitpilot.core.errors import BranchNotFoundError

        mock_repo = MagicMock()
        mock_repo.switch_branch.side_effect = BranchNotFoundError("ghost-branch")
        mock_repo_class.return_value = mock_repo

        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--switch-branch", "ghost-branch"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: Branch 'ghost-branch' not found.", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_dirty_working_tree(self, mock_repo_class):
        from gitpilot.core.errors import DirtyWorkingTreeError
        mock_repo = MagicMock()
        mock_repo.switch_branch.side_effect = DirtyWorkingTreeError("local changes would be overwritten")
        mock_repo_class.return_value = mock_repo
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--switch-branch", "other"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Error: local changes would be overwritten", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_stage_flag(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.stage_files.return_value = ["a.txt", "b.txt"]
        mock_repo_class.return_value = mock_repo
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--stage", "a.txt", "b.txt"])

        self.assertEqual(exit_code, 0)
        mock_repo.stage_files.assert_called_once_with(["a.txt", "b.txt"])
        output = stdout_capture.getvalue()
        self.assertIn("Staged 2 file(s):", output)
        self.assertIn("a.txt", output)
        self.assertIn("b.txt", output)

    @patch("gitpilot.cli.Repository")
    def test_run_cli_stage_flag_with_path_containing_spaces(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.stage_files.return_value = ["my notes.txt"]
        mock_repo_class.return_value = mock_repo
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--stage", "my notes.txt"])

        self.assertEqual(exit_code, 0)
        mock_repo.stage_files.assert_called_once_with(["my notes.txt"])

    @patch("gitpilot.cli.Repository")
    def test_run_cli_unstage_flag(self, mock_repo_class):
        mock_repo = MagicMock()
        mock_repo.unstage_files.return_value = ["changed.txt"]
        mock_repo_class.return_value = mock_repo
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--unstage", "changed.txt"])

        self.assertEqual(exit_code, 0)
        mock_repo.unstage_files.assert_called_once_with(["changed.txt"])
        self.assertIn("Unstaged 1 file(s)", stdout_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_commit_flag(self, mock_repo_class):
        from gitpilot.core.models import CommitResult
        mock_repo = MagicMock()
        mock_repo.create_commit.return_value = CommitResult(
            oid="abc1234def5678", short_oid="abc1234", subject="Add feature", branch="main"
        )
        mock_repo_class.return_value = mock_repo
        stdout_capture = io.StringIO()
        with patch("sys.stdout", stdout_capture):
            exit_code = run_cli(["--commit", "Add feature"])

        self.assertEqual(exit_code, 0)
        mock_repo.create_commit.assert_called_once_with("Add feature")
        output = stdout_capture.getvalue()
        self.assertIn("Committed to main: Add feature", output)
        self.assertIn("Commit: abc1234", output)

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_invalid_commit_message(self, mock_repo_class):
        from gitpilot.core.errors import InvalidCommitMessageError
        mock_repo = MagicMock()
        mock_repo.create_commit.side_effect = InvalidCommitMessageError()
        mock_repo_class.return_value = mock_repo
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--commit", "   "])

        self.assertEqual(exit_code, 1)
        self.assertIn("A commit message is required and cannot be empty.", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_nothing_to_commit(self, mock_repo_class):
        from gitpilot.core.errors import NothingToCommitError
        mock_repo = MagicMock()
        mock_repo.create_commit.side_effect = NothingToCommitError()
        mock_repo_class.return_value = mock_repo
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--commit", "No changes"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Nothing to commit", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_stage_operation_error(self, mock_repo_class):
        from gitpilot.core.errors import StageOperationError
        mock_repo = MagicMock()
        mock_repo.stage_files.side_effect = StageOperationError(paths=["ghost.txt"])
        mock_repo_class.return_value = mock_repo
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--stage", "ghost.txt"])

        self.assertEqual(exit_code, 1)
        self.assertIn("Unable to update the staging area", stderr_capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_run_cli_handles_invalid_path(self, mock_repo_class):
        from gitpilot.core.errors import InvalidPathError
        mock_repo = MagicMock()
        mock_repo.unstage_files.side_effect = InvalidPathError()
        mock_repo_class.return_value = mock_repo
        stderr_capture = io.StringIO()
        with patch("sys.stderr", stderr_capture):
            exit_code = run_cli(["--unstage", "whatever"])

        self.assertEqual(exit_code, 1)
        self.assertIn("A non-empty file path is required.", stderr_capture.getvalue())


if __name__ == "__main__":
    unittest.main()


