"""Integration and unit tests for the Repository abstraction."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.errors import (
    GitCommandError,
    NotAGitRepositoryError,
)
from gitpilot.core.git_cli import GitCommandResult
from gitpilot.core.models import FileStatus, RepositoryState
from gitpilot.core.repository import (
    Repository,
    get_repository_root,
    get_state,
    is_git_repository,
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


class TestRepositoryIntegration(unittest.TestCase):
    """Integration tests executing against real temporary Git repositories."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name).resolve()

        # Initialize real git repository
        subprocess.run(["git", "init", str(self.repo_path)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=self.repo_path, check=True, capture_output=True)

    def tearDown(self):
        _cleanup_dir(self.temp_dir)

    def test_repository_root_detected_from_root(self):
        root = get_repository_root(self.repo_path)
        self.assertEqual(root, self.repo_path)
        self.assertTrue(is_git_repository(self.repo_path))

        repo = Repository(self.repo_path)
        self.assertEqual(repo.root, self.repo_path)
        self.assertTrue(Repository.is_valid(self.repo_path))

    def test_repository_detected_from_subdirectory(self):
        sub_dir = self.repo_path / "deeply" / "nested" / "subfolder"
        sub_dir.mkdir(parents=True)

        root = get_repository_root(sub_dir)
        self.assertEqual(root, self.repo_path)
        self.assertTrue(is_git_repository(sub_dir))

        repo = Repository(sub_dir)
        self.assertEqual(repo.root, self.repo_path)

    def test_repository_detected_from_file_path(self):
        file_path = self.repo_path / "README.md"
        file_path.write_text("Hello World", encoding="utf-8")

        root = get_repository_root(file_path)
        self.assertEqual(root, self.repo_path)
        self.assertTrue(is_git_repository(file_path))

    def test_non_git_directory_rejected(self):
        non_git_temp = tempfile.TemporaryDirectory()
        try:
            non_git_path = Path(non_git_temp.name).resolve()
            self.assertFalse(is_git_repository(non_git_path))

            with self.assertRaises(NotAGitRepositoryError) as ctx:
                get_repository_root(non_git_path)
            self.assertEqual(ctx.exception.path, str(non_git_path))

            with self.assertRaises(NotAGitRepositoryError):
                Repository(non_git_path)

            with self.assertRaises(NotAGitRepositoryError):
                get_state(non_git_path)
        finally:
            _cleanup_dir(non_git_temp)

    def test_non_existent_path_handled(self):
        missing_path = self.repo_path / "does_not_exist"
        self.assertFalse(is_git_repository(missing_path))

        with self.assertRaises(FileNotFoundError):
            get_repository_root(missing_path)

        with self.assertRaises(FileNotFoundError):
            Repository(missing_path)

        with self.assertRaises(FileNotFoundError):
            get_state(missing_path)

    def test_clean_repository_state(self):
        # Create and commit an initial file
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        state = get_state(self.repo_path)

        self.assertIsInstance(state, RepositoryState)
        self.assertEqual(state.root_path, self.repo_path)
        self.assertTrue(state.is_clean)
        self.assertFalse(state.has_conflicts)
        self.assertEqual(len(state.staged_files), 0)
        self.assertEqual(len(state.unstaged_files), 0)
        self.assertEqual(len(state.untracked_files), 0)
        self.assertEqual(len(state.conflicted_files), 0)

    def test_untracked_file_state(self):
        # Commit initial file first
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Create an untracked file
        untracked = self.repo_path / "notes.txt"
        untracked.write_text("Draft notes", encoding="utf-8")

        state = get_state(self.repo_path)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.untracked_files), 1)
        self.assertEqual(state.untracked_files[0].path, "notes.txt")
        self.assertTrue(state.untracked_files[0].is_untracked)

    def test_modified_file_state(self):
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Modify file without staging
        readme.write_text("# Modified Content", encoding="utf-8")

        state = get_state(self.repo_path)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.unstaged_files), 1)
        self.assertEqual(state.unstaged_files[0].path, "README.md")
        self.assertEqual(state.unstaged_files[0].unstaged_status, FileStatus.MODIFIED)
        self.assertEqual(len(state.staged_files), 0)

    def test_staged_file_state(self):
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Modify and stage
        readme.write_text("# Staged Content", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)

        state = get_state(self.repo_path)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.staged_files), 1)
        self.assertEqual(state.staged_files[0].path, "README.md")
        self.assertEqual(state.staged_files[0].staged_status, FileStatus.MODIFIED)
        self.assertEqual(len(state.unstaged_files), 0)

    def test_branch_information_preserved(self):
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        # Create and checkout a new branch
        subprocess.run(["git", "checkout", "-b", "feature/integration-test"], cwd=self.repo_path, check=True, capture_output=True)

        state = get_state(self.repo_path)

        self.assertEqual(state.branch.name, "feature/integration-test")
        self.assertFalse(state.branch.is_detached)
        self.assertFalse(state.branch.is_initial)
        self.assertIsNotNone(state.branch.oid)

    def test_parser_integration_via_repository_class(self):
        readme = self.repo_path / "README.md"
        readme.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

        repo = Repository(self.repo_path)
        state = repo.get_state()

        self.assertIsInstance(state, RepositoryState)
        self.assertEqual(state.root_path, self.repo_path)
        self.assertEqual(repr(repo), f"Repository(root={self.repo_path})")

    def test_paths_containing_spaces(self):
        spaced_dir = tempfile.TemporaryDirectory()
        try:
            spaced_repo_path = (Path(spaced_dir.name) / "my test repository with spaces").resolve()
            spaced_repo_path.mkdir(parents=True)

            subprocess.run(["git", "init", str(spaced_repo_path)], check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=spaced_repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=spaced_repo_path, check=True, capture_output=True)
            subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=spaced_repo_path, check=True, capture_output=True)

            root = get_repository_root(spaced_repo_path)
            self.assertEqual(root, spaced_repo_path)

            doc = spaced_repo_path / "document with space.txt"
            doc.write_text("Hello", encoding="utf-8")

            state = get_state(spaced_repo_path)
            self.assertEqual(len(state.untracked_files), 1)
            self.assertEqual(state.untracked_files[0].path, "document with space.txt")
        finally:
            _cleanup_dir(spaced_dir)


class TestRepositoryErrorHandling(unittest.TestCase):
    """Unit tests with mocking to verify Git error handling paths."""

    @patch("gitpilot.core.repository.run_git")
    def test_unexpected_git_command_failure_raises_git_command_error(self, mock_run_git):
        mock_run_git.return_value = GitCommandResult(
            command=["git", "rev-parse", "--show-toplevel"],
            exit_code=1,
            stdout="",
            stderr="fatal: internal git error",
        )

        with self.assertRaises(GitCommandError) as ctx:
            get_repository_root(Path.cwd())

        self.assertEqual(ctx.exception.exit_code, 1)
        self.assertIn("internal git error", ctx.exception.stderr)


if __name__ == "__main__":
    unittest.main()

