"""Integration and unit tests for GitPilot branch operations."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.errors import (
    BranchAlreadyExistsError,
    BranchNotFoundError,
    DirtyWorkingTreeError,
    GitCommandError,
    InvalidBranchNameError,
    NotAGitRepositoryError,
)
from gitpilot.core.git_cli import GitCommandResult
from gitpilot.core.models import LocalBranch
from gitpilot.core.repository import (
    Repository,
    create_branch,
    get_current_branch,
    list_branches,
    switch_branch,
)


def _cleanup_dir(temp_dir: tempfile.TemporaryDirectory) -> None:
    """Safely remove a temporary directory on Windows handling read-only Git files."""
    try:
        temp_dir.cleanup()
    except Exception:
        def onerror(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(temp_dir.name, onerror=onerror, ignore_errors=True)


class TestBranchOperationsIntegration(unittest.TestCase):
    """Integration tests for branch operations against real temporary Git repositories."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name).resolve()

        # Initialize real git repository
        subprocess.run(["git", "init", str(self.repo_path)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=self.repo_path, check=True, capture_output=True)

        # Create an initial commit so branches can be created
        initial_file = self.repo_path / "README.md"
        initial_file.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Determine initial branch name ('main' or 'master' depending on git version)
        self.initial_branch = get_current_branch(self.repo_path)

    def tearDown(self):
        _cleanup_dir(self.temp_dir)

    def test_list_branches_in_repository(self):
        # Create additional local branches
        subprocess.run(["git", "branch", "feature-1"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "branch", "feature-2"], cwd=self.repo_path, check=True, capture_output=True)

        branches = list_branches(self.repo_path)
        branch_names = [b.name for b in branches]

        self.assertIn(self.initial_branch, branch_names)
        self.assertIn("feature-1", branch_names)
        self.assertIn("feature-2", branch_names)

        # Current branch should have is_current=True, others False
        for b in branches:
            if b.name == self.initial_branch:
                self.assertTrue(b.is_current)
            else:
                self.assertFalse(b.is_current)

    def test_correctly_identify_current_branch(self):
        current = get_current_branch(self.repo_path)
        self.assertEqual(current, self.initial_branch)

        # Switch to a new branch and check again
        subprocess.run(["git", "checkout", "-b", "dev"], cwd=self.repo_path, check=True, capture_output=True)
        self.assertEqual(get_current_branch(self.repo_path), "dev")

    def test_create_branch_and_verify_exists(self):
        created = create_branch(self.repo_path, "feature-login")

        self.assertIsInstance(created, LocalBranch)
        self.assertEqual(created.name, "feature-login")
        self.assertFalse(created.is_current)

        # Current branch must remain unchanged (create does not switch)
        self.assertEqual(get_current_branch(self.repo_path), self.initial_branch)

        # Verify new branch exists in list
        branches = list_branches(self.repo_path)
        branch_names = [b.name for b in branches]
        self.assertIn("feature-login", branch_names)

    def test_switch_to_existing_branch(self):
        create_branch(self.repo_path, "feature-search")
        self.assertEqual(get_current_branch(self.repo_path), self.initial_branch)

        switched = switch_branch(self.repo_path, "feature-search")

        self.assertIsInstance(switched, LocalBranch)
        self.assertEqual(switched.name, "feature-search")
        self.assertTrue(switched.is_current)

        # Verify current branch actually changed
        self.assertEqual(get_current_branch(self.repo_path), "feature-search")

    def test_switch_to_nonexistent_branch_raises_error(self):
        with self.assertRaises(BranchNotFoundError) as ctx:
            switch_branch(self.repo_path, "non-existent-branch")

        self.assertEqual(ctx.exception.branch_name, "non-existent-branch")
        self.assertIn("non-existent-branch", str(ctx.exception))
        # Ensure current branch remains unchanged
        self.assertEqual(get_current_branch(self.repo_path), self.initial_branch)

    def test_create_duplicate_branch_raises_error(self):
        with self.assertRaises(BranchAlreadyExistsError) as ctx:
            create_branch(self.repo_path, self.initial_branch)

        self.assertEqual(ctx.exception.branch_name, self.initial_branch)
        self.assertIn("already exists", str(ctx.exception))

    def test_create_invalid_branch_name_raises_error(self):
        # Empty string
        with self.assertRaises(InvalidBranchNameError):
            create_branch(self.repo_path, "")

        # Whitespace only
        with self.assertRaises(InvalidBranchNameError):
            create_branch(self.repo_path, "   ")

        # Name with spaces
        with self.assertRaises(InvalidBranchNameError):
            create_branch(self.repo_path, "invalid branch name with spaces")

        # Name with consecutive dots
        with self.assertRaises(InvalidBranchNameError):
            create_branch(self.repo_path, "feature..test")

    def test_branch_operations_on_non_git_repository(self):
        non_git_temp = tempfile.TemporaryDirectory()
        try:
            non_git_path = Path(non_git_temp.name).resolve()

            with self.assertRaises(NotAGitRepositoryError):
                list_branches(non_git_path)

            with self.assertRaises(NotAGitRepositoryError):
                get_current_branch(non_git_path)

            with self.assertRaises(NotAGitRepositoryError):
                create_branch(non_git_path, "dev")

            with self.assertRaises(NotAGitRepositoryError):
                switch_branch(non_git_path, "dev")
        finally:
            _cleanup_dir(non_git_temp)

    def test_branch_operations_on_nonexistent_path(self):
        missing = self.repo_path / "does_not_exist"

        with self.assertRaises(FileNotFoundError):
            list_branches(missing)

        with self.assertRaises(FileNotFoundError):
            get_current_branch(missing)

        with self.assertRaises(FileNotFoundError):
            create_branch(missing, "dev")

        with self.assertRaises(FileNotFoundError):
            switch_branch(missing, "dev")

    def test_local_modifications_not_discarded_when_switching_conflicts(self):
        # Setup conflicting branch
        subprocess.run(["git", "branch", "feature-conflict"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "switch", "feature-conflict"], cwd=self.repo_path, check=True, capture_output=True)

        target_file = self.repo_path / "README.md"
        target_file.write_text("# Feature content", encoding="utf-8")
        subprocess.run(["git", "commit", "-am", "Feature commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Switch back to initial branch
        subprocess.run(["git", "switch", self.initial_branch], cwd=self.repo_path, check=True, capture_output=True)

        # Make local uncommitted changes to README.md
        uncommitted_content = "# Uncommitted Work in Progress"
        target_file.write_text(uncommitted_content, encoding="utf-8")

        # Attempt to switch to feature-conflict - Git must refuse because local changes would be overwritten
        with self.assertRaises(DirtyWorkingTreeError) as ctx:
            switch_branch(self.repo_path, "feature-conflict")

        self.assertIn("local uncommitted changes would be overwritten", str(ctx.exception))

        # Crucial verification: user's uncommitted work is NOT lost or overwritten
        self.assertEqual(target_file.read_text(encoding="utf-8"), uncommitted_content)

        # Current branch remains unchanged
        self.assertEqual(get_current_branch(self.repo_path), self.initial_branch)

    def test_repository_class_branch_methods(self):
        repo = Repository(self.repo_path)

        # Current branch
        self.assertEqual(repo.get_current_branch(), self.initial_branch)

        # Create branch
        created = repo.create_branch("feature-class-test")
        self.assertEqual(created.name, "feature-class-test")
        self.assertFalse(created.is_current)

        # List branches
        branch_names = [b.name for b in repo.list_branches()]
        self.assertIn("feature-class-test", branch_names)

        # Switch branch
        switched = repo.switch_branch("feature-class-test")
        self.assertEqual(switched.name, "feature-class-test")
        self.assertTrue(switched.is_current)
        self.assertEqual(repo.get_current_branch(), "feature-class-test")


class TestBranchErrorHandling(unittest.TestCase):
    """Unit tests with mocking to verify Git error propagation."""

    @patch("gitpilot.core.repository.run_git")
    def test_git_command_failure_propagated(self, mock_run_git):
        mock_run_git.return_value = GitCommandResult(
            command=["git", "branch", "dev"],
            exit_code=128,
            stdout="",
            stderr="fatal: unexpected error occurred in repository",
        )

        with self.assertRaises(GitCommandError) as ctx:
            create_branch(Path.cwd(), "dev")

        self.assertEqual(ctx.exception.exit_code, 128)
        self.assertIn("unexpected error occurred", ctx.exception.stderr)


if __name__ == "__main__":
    unittest.main()

