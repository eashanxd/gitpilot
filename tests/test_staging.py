"""Integration and unit tests for GitPilot staging, unstaging, and commit operations."""

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
    InvalidCommitMessageError,
    InvalidPathError,
    NothingToCommitError,
    NotAGitRepositoryError,
    StageOperationError,
)
from gitpilot.core.git_cli import GitCommandResult
from gitpilot.core.models import CommitResult
from gitpilot.core.repository import (
    Repository,
    create_commit,
    get_state,
    stage_files,
    unstage_files,
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


class StagingIntegrationTestCase(unittest.TestCase):
    """Shared fixture: a real temporary Git repository with an initial commit."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = Path(self.temp_dir.name).resolve()

        subprocess.run(["git", "init", str(self.repo_path)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=self.repo_path, check=True, capture_output=True)

        # Initial commit so a baseline HEAD exists for unstage/commit tests.
        initial_file = self.repo_path / "README.md"
        initial_file.write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

    def tearDown(self):
        _cleanup_dir(self.temp_dir)


class TestStageFiles(StagingIntegrationTestCase):
    """Integration tests for stage_files."""

    def test_stage_modified_file(self):
        target = self.repo_path / "README.md"
        target.write_text("# Initial\nModified content", encoding="utf-8")

        staged = stage_files(self.repo_path, ["README.md"])

        self.assertEqual(staged, ["README.md"])
        state = get_state(self.repo_path)
        self.assertIn("README.md", [change.path for change in state.staged_files])

    def test_stage_untracked_file(self):
        new_file = self.repo_path / "notes.txt"
        new_file.write_text("hello", encoding="utf-8")

        staged = stage_files(self.repo_path, ["notes.txt"])

        self.assertEqual(staged, ["notes.txt"])
        state = get_state(self.repo_path)
        self.assertIn("notes.txt", [change.path for change in state.staged_files])
        self.assertEqual(state.untracked_files, [])

    def test_stage_multiple_files(self):
        (self.repo_path / "a.txt").write_text("a", encoding="utf-8")
        (self.repo_path / "b.txt").write_text("b", encoding="utf-8")

        staged = stage_files(self.repo_path, ["a.txt", "b.txt"])

        self.assertEqual(sorted(staged), ["a.txt", "b.txt"])
        state = get_state(self.repo_path)
        staged_paths = sorted(change.path for change in state.staged_files)
        self.assertEqual(staged_paths, ["a.txt", "b.txt"])

    def test_accepts_a_single_string_path(self):
        (self.repo_path / "single.txt").write_text("x", encoding="utf-8")

        staged = stage_files(self.repo_path, "single.txt")

        self.assertEqual(staged, ["single.txt"])

    def test_stage_path_with_spaces(self):
        spaced = self.repo_path / "my notes file.txt"
        spaced.write_text("spaced", encoding="utf-8")

        staged = stage_files(self.repo_path, ["my notes file.txt"])

        self.assertEqual(staged, ["my notes file.txt"])
        state = get_state(self.repo_path)
        self.assertIn("my notes file.txt", [change.path for change in state.staged_files])

    def test_stage_path_with_special_characters(self):
        tricky = self.repo_path / "weird'name & symbols.txt"
        tricky.write_text("tricky", encoding="utf-8")

        stage_files(self.repo_path, ["weird'name & symbols.txt"])

        state = get_state(self.repo_path)
        self.assertIn("weird'name & symbols.txt", [change.path for change in state.staged_files])

    def test_stage_accepts_pathlib_path_objects(self):
        nested_dir = self.repo_path / "nested dir"
        nested_dir.mkdir()
        (nested_dir / "file.txt").write_text("nested", encoding="utf-8")

        staged = stage_files(self.repo_path, [Path("nested dir/file.txt")])

        self.assertEqual(staged, ["nested dir/file.txt"])
        state = get_state(self.repo_path)
        self.assertIn("nested dir/file.txt", [change.path for change in state.staged_files])

    def test_stage_empty_path_list_raises_invalid_path(self):
        with self.assertRaises(InvalidPathError):
            stage_files(self.repo_path, [])

    def test_stage_blank_path_raises_invalid_path(self):
        with self.assertRaises(InvalidPathError):
            stage_files(self.repo_path, ["   "])

    def test_stage_nonexistent_file_raises_stage_operation_error(self):
        with self.assertRaises(StageOperationError) as ctx:
            stage_files(self.repo_path, ["does-not-exist.txt"])
        self.assertIn("does-not-exist.txt", str(ctx.exception))

    def test_stage_outside_repository_raises_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(NotAGitRepositoryError):
                stage_files(outside, ["anything.txt"])

    def test_stage_uses_run_git_and_never_subprocess_directly(self):
        result = GitCommandResult(command=["git", "add", "--", "f.txt"], exit_code=0, stdout="", stderr="")
        with patch("gitpilot.core.repository.run_git", return_value=result) as mock_run_git:
            with patch("gitpilot.core.git_cli.subprocess.run") as mock_subprocess:
                stage_files(self.repo_path, ["f.txt"])
                mock_subprocess.assert_not_called()

        called_args = mock_run_git.call_args[0][0]
        self.assertEqual(called_args, ["add", "--", "f.txt"])
        self.assertIn("--", called_args)


class TestRepositoryStageFiles(StagingIntegrationTestCase):
    """Tests for the Repository wrapper method for staging."""

    def test_repository_stage_files(self):
        (self.repo_path / "wrapper.txt").write_text("wrapper", encoding="utf-8")
        repo = Repository(self.repo_path)

        staged = repo.stage_files(["wrapper.txt"])

        self.assertEqual(staged, ["wrapper.txt"])
        self.assertIn("wrapper.txt", [c.path for c in repo.get_state().staged_files])


class TestUnstageFiles(StagingIntegrationTestCase):
    """Integration tests for unstage_files."""

    def test_unstage_staged_file(self):
        target = self.repo_path / "README.md"
        target.write_text("# Initial\nChanged", encoding="utf-8")
        stage_files(self.repo_path, ["README.md"])
        self.assertTrue(get_state(self.repo_path).staged_files)

        unstaged = unstage_files(self.repo_path, ["README.md"])

        self.assertEqual(unstaged, ["README.md"])
        state = get_state(self.repo_path)
        self.assertEqual(state.staged_files, [])

    def test_unstage_keeps_working_tree_modifications(self):
        target = self.repo_path / "README.md"
        target.write_text("# Initial\nStill here", encoding="utf-8")
        stage_files(self.repo_path, ["README.md"])

        unstage_files(self.repo_path, ["README.md"])

        # The edit must survive in the working tree.
        self.assertEqual(target.read_text(encoding="utf-8"), "# Initial\nStill here")
        state = get_state(self.repo_path)
        self.assertIn("README.md", [change.path for change in state.unstaged_files])

    def test_unstage_untracked_file_keeps_it_on_disk(self):
        new_file = self.repo_path / "fresh.txt"
        new_file.write_text("fresh", encoding="utf-8")
        stage_files(self.repo_path, ["fresh.txt"])

        unstage_files(self.repo_path, ["fresh.txt"])

        self.assertTrue(new_file.exists())
        self.assertIn("fresh.txt", [change.path for change in get_state(self.repo_path).untracked_files])

    def test_unstage_multiple_files(self):
        (self.repo_path / "one.txt").write_text("1", encoding="utf-8")
        (self.repo_path / "two.txt").write_text("2", encoding="utf-8")
        stage_files(self.repo_path, ["one.txt", "two.txt"])

        unstaged = unstage_files(self.repo_path, ["one.txt", "two.txt"])

        self.assertEqual(sorted(unstaged), ["one.txt", "two.txt"])
        self.assertEqual(get_state(self.repo_path).staged_files, [])

    def test_unstage_path_with_spaces(self):
        spaced = self.repo_path / "spaced file.txt"
        spaced.write_text("spaced", encoding="utf-8")
        stage_files(self.repo_path, ["spaced file.txt"])

        unstage_files(self.repo_path, ["spaced file.txt"])

        self.assertTrue(spaced.exists())
        self.assertEqual(get_state(self.repo_path).staged_files, [])

    def test_unstage_empty_path_list_raises_invalid_path(self):
        with self.assertRaises(InvalidPathError):
            unstage_files(self.repo_path, [])

    def test_unstage_outside_repository_raises_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(NotAGitRepositoryError):
                unstage_files(outside, ["anything.txt"])

    def test_unstage_uses_restore_staged_through_run_git(self):
        result = GitCommandResult(command=["git", "restore", "--staged", "--", "f.txt"], exit_code=0, stdout="", stderr="")
        with patch("gitpilot.core.repository.run_git", return_value=result) as mock_run_git:
            unstage_files(self.repo_path, ["f.txt"])

        called_args = mock_run_git.call_args[0][0]
        self.assertEqual(called_args, ["restore", "--staged", "--", "f.txt"])


class TestRepositoryUnstageFiles(StagingIntegrationTestCase):
    """Tests for the Repository wrapper method for unstaging."""

    def test_repository_unstage_files(self):
        target = self.repo_path / "README.md"
        target.write_text("# Initial\nEdit", encoding="utf-8")
        repo = Repository(self.repo_path)
        repo.stage_files(["README.md"])

        unstaged = repo.unstage_files(["README.md"])

        self.assertEqual(unstaged, ["README.md"])
        self.assertEqual(repo.get_state().staged_files, [])
        self.assertEqual(target.read_text(encoding="utf-8"), "# Initial\nEdit")


class TestCreateCommit(StagingIntegrationTestCase):
    """Integration tests for create_commit."""

    def test_successful_commit(self):
        (self.repo_path / "feature.txt").write_text("feature", encoding="utf-8")
        stage_files(self.repo_path, ["feature.txt"])

        result = create_commit(self.repo_path, "Add feature file")

        self.assertIsInstance(result, CommitResult)
        self.assertTrue(result.oid)
        self.assertEqual(len(result.short_oid), 7)
        self.assertEqual(result.subject, "Add feature file")
        self.assertIsNotNone(result.branch)

    def test_commit_clears_staging_area(self):
        (self.repo_path / "clean.txt").write_text("clean", encoding="utf-8")
        stage_files(self.repo_path, ["clean.txt"])

        create_commit(self.repo_path, "Commit staged file")

        self.assertEqual(get_state(self.repo_path).staged_files, [])

    def test_commit_records_staged_files(self):
        (self.repo_path / "recorded.txt").write_text("recorded", encoding="utf-8")
        stage_files(self.repo_path, ["recorded.txt"])

        create_commit(self.repo_path, "Record a file")

        log = subprocess.run(
            ["git", "show", "--name-only", "--pretty=format:", "HEAD"],
            cwd=self.repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("recorded.txt", log.stdout)

    def test_commit_with_multiline_message_uses_subject_line_as_summary(self):
        (self.repo_path / "multi.txt").write_text("multi", encoding="utf-8")
        stage_files(self.repo_path, ["multi.txt"])

        result = create_commit(self.repo_path, "Subject line\nBody detail.")

        self.assertEqual(result.subject, "Subject line")

    def test_empty_message_is_rejected(self):
        (self.repo_path / "x.txt").write_text("x", encoding="utf-8")
        stage_files(self.repo_path, ["x.txt"])

        with self.assertRaises(InvalidCommitMessageError):
            create_commit(self.repo_path, "")

    def test_blank_message_is_rejected(self):
        (self.repo_path / "y.txt").write_text("y", encoding="utf-8")
        stage_files(self.repo_path, ["y.txt"])

        with self.assertRaises(InvalidCommitMessageError):
            create_commit(self.repo_path, "   \n\t  ")

    def test_non_string_message_is_rejected(self):
        with self.assertRaises(InvalidCommitMessageError):
            create_commit(self.repo_path, None)  # type: ignore[arg-type]

    def test_rejected_message_does_not_create_a_commit(self):
        (self.repo_path / "z.txt").write_text("z", encoding="utf-8")
        stage_files(self.repo_path, ["z.txt"])
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()

        with self.assertRaises(InvalidCommitMessageError):
            create_commit(self.repo_path, "    ")

        after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(before, after)

    def test_nothing_to_commit_raises_nothing_to_commit_error(self):
        with self.assertRaises(NothingToCommitError):
            create_commit(self.repo_path, "No staged changes here")

    def test_nothing_to_commit_when_only_working_tree_changes_exist(self):
        (self.repo_path / "README.md").write_text("# Initial\nunstaged edit", encoding="utf-8")

        with self.assertRaises(NothingToCommitError):
            create_commit(self.repo_path, "Nothing staged")

    def test_commit_outside_repository_raises_not_a_git_repository(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(NotAGitRepositoryError):
                create_commit(outside, "message")

    def test_commit_uses_git_commit_via_run_git(self):
        from gitpilot.core import repository as repository_module
        real_run_git = repository_module.run_git
        seen_commands = []

        def fake_run_git(args, **kwargs):
            args = list(args)
            seen_commands.append(args)
            if args == ["commit", "-m", "msg"]:
                return GitCommandResult(command=["git", "commit", "-m", "msg"], exit_code=0, stdout="[main abc1234] msg\n", stderr="")
            # Delegate every other call (rev-parse, branch --show-current) to the real wrapper.
            return real_run_git(args, **kwargs)

        with patch("gitpilot.core.repository.run_git", side_effect=fake_run_git):
            create_commit(self.repo_path, "msg")

        self.assertEqual(seen_commands.count(["commit", "-m", "msg"]), 1)

    def test_unmapped_git_failure_becomes_git_command_error(self):
        failure = GitCommandResult(
            command=["git", "commit", "-m", "msg"],
            exit_code=128,
            stdout="",
            stderr="fatal: unable to write new index file",
        )
        with patch("gitpilot.core.repository.run_git", return_value=failure):
            with self.assertRaises(GitCommandError):
                create_commit(self.repo_path, "msg")


class TestRepositoryCreateCommit(StagingIntegrationTestCase):
    """Tests for the Repository wrapper method for committing."""

    def test_repository_create_commit(self):
        (self.repo_path / "wrapped.txt").write_text("wrapped", encoding="utf-8")
        repo = Repository(self.repo_path)
        repo.stage_files(["wrapped.txt"])

        result = repo.create_commit("Wrapper commit")

        self.assertEqual(result.subject, "Wrapper commit")
        self.assertEqual(repo.get_state().staged_files, [])

    def test_repository_commit_rejects_blank_message(self):
        repo = Repository(self.repo_path)
        with self.assertRaises(InvalidCommitMessageError):
            repo.create_commit("  ")


if __name__ == "__main__":
    unittest.main()
