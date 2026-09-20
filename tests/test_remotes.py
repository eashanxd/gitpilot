"""Integration tests for GitPilot remote operations (M3).

All remote tests use local bare repositories created in temporary directories, so
the suite never touches the network, external services, or credentials.
"""

import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.errors import (
    NoRemoteError,
    NoUpstreamError,
    NotAGitRepositoryError,
    PullConflictError,
    PushRejectedError,
    RemoteNotFoundError,
    RemoteOperationError,
)
from gitpilot.core.models import Remote, SyncResult, TrackingInfo
from gitpilot.core.repository import (
    Repository,
    fetch_remote,
    get_remote_names,
    get_tracking_info,
    has_remotes,
    list_remotes,
    pull_remote,
    push_remote,
    resolve_remote_name,
)


def _cleanup_dir(temp_dir: tempfile.TemporaryDirectory) -> None:
    """Remove a temporary directory, handling read-only Git files on Windows."""
    try:
        temp_dir.cleanup()
    except Exception:
        def onerror(func, path, exc_info):
            os.chmod(path, stat.S_IWRITE)
            func(path)
        shutil.rmtree(temp_dir.name, onerror=onerror, ignore_errors=True)


def _git(args, cwd, check=True):
    """Run a real git command in a test repository."""
    return subprocess.run(["git"] + args, cwd=str(cwd), check=check, capture_output=True, text=True)


def _configure_repo(path: Path) -> None:
    _git(["config", "user.name", "Test User"], path)
    _git(["config", "user.email", "test@example.com"], path)
    _git(["config", "commit.gpgsign", "false"], path)


def _commit_file(repo: Path, name: str, content: str, message: str) -> str:
    """Write a file, stage and commit it, returning the new HEAD oid."""
    (repo / name).write_text(content, encoding="utf-8")
    _git(["add", name], repo)
    _git(["commit", "-m", message], repo)
    return _git(["rev-parse", "HEAD"], repo).stdout.strip()


class RemoteTestCase(unittest.TestCase):
    """Base fixture: a local bare 'remote' plus a clone that tracks it."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.addCleanup(lambda: _cleanup_dir(self.temp_dir))

        # Bare repository acting as the remote.
        self.remote_path = self.root / "remote.git"
        subprocess.run(
            ["git", "init", "--bare", str(self.remote_path)], check=True, capture_output=True
        )

        # Seed it with one commit so clones have a branch to track.
        seed = self.root / "seed"
        seed.mkdir()
        subprocess.run(["git", "init", str(seed)], check=True, capture_output=True)
        _configure_repo(seed)
        _commit_file(seed, "README.md", "# Seed", "Initial commit")
        _git(["remote", "add", "origin", str(self.remote_path)], seed)
        _git(["push", "-u", "origin", "HEAD"], seed)

        # The repository under test, cloned from the bare remote.
        self.repo_path = self.root / "work"
        subprocess.run(
            ["git", "clone", str(self.remote_path), str(self.repo_path)],
            check=True, capture_output=True,
        )
        _configure_repo(self.repo_path)

    def _second_clone(self, name: str = "other") -> Path:
        """Create a second clone of the same remote, to simulate another developer."""
        other = self.root / name
        subprocess.run(
            ["git", "clone", str(self.remote_path), str(other)],
            check=True, capture_output=True,
        )
        _configure_repo(other)
        return other


class TestRemoteDetection(RemoteTestCase):
    """Tests for remote inspection."""

    def test_list_remotes_returns_configured_remote(self):
        remotes = list_remotes(self.repo_path)
        self.assertEqual(len(remotes), 1)
        self.assertEqual(remotes[0].name, "origin")
        self.assertTrue(remotes[0].fetch_url)
        self.assertIsInstance(remotes[0], Remote)

    def test_remote_url_is_a_local_path_not_the_network(self):
        remote = list_remotes(self.repo_path)[0]
        self.assertEqual(Path(remote.fetch_url).resolve(), self.remote_path.resolve())

    def test_get_remote_names(self):
        self.assertEqual(get_remote_names(self.repo_path), ["origin"])

    def test_has_remotes_true_when_configured(self):
        self.assertTrue(has_remotes(self.repo_path))

    def test_repository_with_no_remotes(self):
        bare_no_remote = self.root / "lonely"
        bare_no_remote.mkdir()
        subprocess.run(["git", "init", str(bare_no_remote)], check=True, capture_output=True)
        _configure_repo(bare_no_remote)

        self.assertEqual(list_remotes(bare_no_remote), [])
        self.assertEqual(get_remote_names(bare_no_remote), [])
        self.assertFalse(has_remotes(bare_no_remote))

    def test_multiple_remotes_are_all_listed(self):
        _git(["remote", "add", "backup", str(self.remote_path)], self.repo_path)
        names = sorted(get_remote_names(self.repo_path))
        self.assertEqual(names, ["backup", "origin"])

    def test_non_origin_remote_name_is_supported(self):
        _git(["remote", "rename", "origin", "upstream"], self.repo_path)
        self.assertEqual(get_remote_names(self.repo_path), ["upstream"])
        self.assertEqual(list_remotes(self.repo_path)[0].name, "upstream")

    def test_list_remotes_outside_repository_raises(self):
        with tempfile.TemporaryDirectory() as outside:
            with self.assertRaises(NotAGitRepositoryError):
                list_remotes(outside)

    def test_repository_wrapper_exposes_remote_helpers(self):
        repo = Repository(self.repo_path)
        self.assertTrue(repo.has_remotes())
        self.assertEqual(repo.get_remote_names(), ["origin"])
        self.assertEqual(len(repo.list_remotes()), 1)


class TestResolveRemoteName(RemoteTestCase):
    """Tests for remote name resolution."""

    def test_single_remote_is_resolved_implicitly(self):
        self.assertEqual(resolve_remote_name(self.repo_path), "origin")

    def test_explicit_remote_is_accepted(self):
        self.assertEqual(resolve_remote_name(self.repo_path, "origin"), "origin")

    def test_blank_remote_name_falls_back_to_implicit(self):
        self.assertEqual(resolve_remote_name(self.repo_path, "   "), "origin")

    def test_unknown_remote_raises(self):
        with self.assertRaises(RemoteNotFoundError) as ctx:
            resolve_remote_name(self.repo_path, "ghost")
        self.assertEqual(ctx.exception.remote_name, "ghost")

    def test_no_remotes_raises_no_remote_error(self):
        bare = self.root / "empty"
        bare.mkdir()
        subprocess.run(["git", "init", str(bare)], check=True, capture_output=True)
        with self.assertRaises(NoRemoteError):
            resolve_remote_name(bare)

    def test_multiple_remotes_require_explicit_choice(self):
        _git(["remote", "add", "backup", str(self.remote_path)], self.repo_path)
        with self.assertRaises(RemoteNotFoundError):
            resolve_remote_name(self.repo_path)
        # An explicit choice still works.
        self.assertEqual(resolve_remote_name(self.repo_path, "backup"), "backup")


class TestTrackingInfo(RemoteTestCase):
    """Tests for ahead/behind tracking information."""

    def test_tracking_info_has_upstream_and_no_divergence(self):
        info = get_tracking_info(self.repo_path)
        self.assertIsInstance(info, TrackingInfo)
        self.assertTrue(info.has_upstream)
        self.assertTrue(info.upstream.endswith("master") or info.upstream.endswith("main"))
        self.assertEqual(info.remote_name, "origin")
        self.assertEqual(info.ahead, 0)
        self.assertEqual(info.behind, 0)

    def test_ahead_count_after_local_commit(self):
        _commit_file(self.repo_path, "local.txt", "local", "Local work")

        info = get_tracking_info(self.repo_path)
        self.assertEqual(info.ahead, 1)
        self.assertEqual(info.behind, 0)
        self.assertFalse(info.ahead == 0 and info.behind == 0)

    def test_behind_count_after_remote_commit(self):
        other = self._second_clone()
        _commit_file(other, "remote.txt", "remote", "Remote work")
        _git(["push", "origin", "HEAD"], other)

        fetch_remote(self.repo_path)
        info = get_tracking_info(self.repo_path)
        self.assertEqual(info.behind, 1)
        self.assertEqual(info.ahead, 0)

    def test_ahead_and_behind_both_reported(self):
        other = self._second_clone()
        _commit_file(other, "remote.txt", "remote", "Remote work")
        _git(["push", "origin", "HEAD"], other)
        _commit_file(self.repo_path, "local.txt", "local", "Local work")

        fetch_remote(self.repo_path)
        info = get_tracking_info(self.repo_path)
        self.assertEqual(info.ahead, 1)
        self.assertEqual(info.behind, 1)

    def test_no_upstream_reports_cleanly(self):
        # A new local branch has no upstream tracking branch.
        _git(["checkout", "-b", "feature/untracked"], self.repo_path)
        info = get_tracking_info(self.repo_path)
        self.assertFalse(info.has_upstream)
        self.assertIsNone(info.upstream)
        self.assertEqual(info.ahead, 0)
        self.assertEqual(info.behind, 0)

    def test_repository_without_remote_reports_no_upstream(self):
        bare = self.root / "solo"
        bare.mkdir()
        subprocess.run(["git", "init", str(bare)], check=True, capture_output=True)
        _configure_repo(bare)
        _commit_file(bare, "a.txt", "a", "Initial")

        info = get_tracking_info(bare)
        self.assertFalse(info.has_upstream)


class TestFetch(RemoteTestCase):
    """Tests for fetching."""

    def test_fetch_succeeds_and_returns_sync_result(self):
        result = fetch_remote(self.repo_path)
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.operation, "fetch")
        self.assertEqual(result.remote_name, "origin")
        self.assertTrue(result.is_up_to_date)

    def test_fetch_does_not_modify_working_tree(self):
        other = self._second_clone()
        _commit_file(other, "new.txt", "content", "Remote change")
        _git(["push", "origin", "HEAD"], other)

        before = (self.repo_path / "new.txt").exists()
        fetch_remote(self.repo_path)

        # Fetch updates remote-tracking refs only; the working tree is untouched.
        self.assertFalse(before)
        self.assertFalse((self.repo_path / "new.txt").exists())
        self.assertEqual(get_tracking_info(self.repo_path).behind, 1)

    def test_fetch_with_explicit_remote(self):
        result = fetch_remote(self.repo_path, "origin")
        self.assertEqual(result.remote_name, "origin")

    def test_fetch_unknown_remote_raises(self):
        with self.assertRaises(RemoteNotFoundError):
            fetch_remote(self.repo_path, "nope")

    def test_fetch_unreachable_remote_raises_remote_operation_error(self):
        _git(["remote", "set-url", "origin", str(self.root / "missing.git")], self.repo_path)
        with self.assertRaises(RemoteOperationError):
            fetch_remote(self.repo_path)

    def test_fetch_with_no_remotes_raises_no_remote_error(self):
        bare = self.root / "norems"
        bare.mkdir()
        subprocess.run(["git", "init", str(bare)], check=True, capture_output=True)
        with self.assertRaises(NoRemoteError):
            fetch_remote(bare)


class TestPull(RemoteTestCase):
    """Tests for pulling."""

    def test_successful_pull_from_local_bare_remote(self):
        other = self._second_clone()
        _commit_file(other, "shared.txt", "shared", "Shared change")
        _git(["push", "origin", "HEAD"], other)

        result = pull_remote(self.repo_path)

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.operation, "pull")
        self.assertTrue((self.repo_path / "shared.txt").exists())
        self.assertTrue(result.is_up_to_date)

    def test_pull_with_no_upstream_raises(self):
        _git(["checkout", "-b", "feature/no-upstream"], self.repo_path)
        with self.assertRaises(NoUpstreamError) as ctx:
            pull_remote(self.repo_path)
        self.assertEqual(ctx.exception.branch, "feature/no-upstream")

    def test_pull_with_no_upstream_does_not_create_upstream(self):
        _git(["checkout", "-b", "feature/keep-clean"], self.repo_path)
        with self.assertRaises(NoUpstreamError):
            pull_remote(self.repo_path)

        # GitPilot must not invent an upstream configuration.
        info = get_tracking_info(self.repo_path)
        self.assertFalse(info.has_upstream)

    def test_pull_diverged_history_raises_without_discarding_work(self):
        other = self._second_clone()
        _commit_file(other, "remote.txt", "remote", "Remote change")
        _git(["push", "origin", "HEAD"], other)

        # Local commit diverges from the remote.
        _commit_file(self.repo_path, "local.txt", "local", "Local change")

        with self.assertRaises((PullConflictError, RemoteOperationError)):
            pull_remote(self.repo_path)

        # Local work must still be present and committed.
        self.assertTrue((self.repo_path / "local.txt").exists())
        subjects = _git(["log", "--pretty=%s"], self.repo_path).stdout
        self.assertIn("Local change", subjects)

    def test_pull_would_overwrite_local_changes_raises(self):
        other = self._second_clone()
        _commit_file(other, "README.md", "changed remotely", "Remote README change")
        _git(["push", "origin", "HEAD"], other)

        # Uncommitted local edit to the same file.
        (self.repo_path / "README.md").write_text("uncommitted local edit", encoding="utf-8")

        with self.assertRaises((PullConflictError, RemoteOperationError)):
            pull_remote(self.repo_path)

        # The uncommitted edit must survive.
        self.assertEqual(
            (self.repo_path / "README.md").read_text(encoding="utf-8"),
            "uncommitted local edit",
        )

    def test_pull_uses_ff_only_and_never_resets(self):
        """The pull command must be fast-forward-only (no merge, no reset)."""
        captured = []

        from gitpilot.core import repository as repository_module
        real_run_git = repository_module.run_git

        def spy(args, **kwargs):
            captured.append(list(args))
            return real_run_git(args, **kwargs)

        other = self._second_clone()
        _commit_file(other, "ff.txt", "ff", "Fast forward me")
        _git(["push", "origin", "HEAD"], other)

        repository_module.run_git = spy
        try:
            pull_remote(self.repo_path)
        finally:
            repository_module.run_git = real_run_git

        pull_commands = [c for c in captured if c and c[0] == "pull"]
        self.assertEqual(len(pull_commands), 1)
        self.assertIn("--ff-only", pull_commands[0])
        for command in captured:
            self.assertNotIn("--force", command)
            self.assertNotIn("--hard", command)


class TestPush(RemoteTestCase):
    """Tests for pushing."""

    def test_successful_push_to_local_bare_remote(self):
        _commit_file(self.repo_path, "pushed.txt", "pushed", "Work to push")

        result = push_remote(self.repo_path)

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.operation, "push")
        self.assertEqual(result.remote_name, "origin")
        # The remote now has the commit.
        remote_subjects = _git(["log", "--pretty=%s", "HEAD"], self.remote_path).stdout
        self.assertIn("Work to push", remote_subjects)

    def test_push_then_tracking_is_up_to_date(self):
        _commit_file(self.repo_path, "sync.txt", "sync", "Sync me")
        result = push_remote(self.repo_path)
        self.assertTrue(result.is_up_to_date)
        self.assertEqual(get_tracking_info(self.repo_path).ahead, 0)

    def test_push_with_no_upstream_raises(self):
        _git(["checkout", "-b", "feature/unpushed"], self.repo_path)
        with self.assertRaises(NoUpstreamError):
            push_remote(self.repo_path)

    def test_push_with_no_upstream_does_not_invent_configuration(self):
        _git(["checkout", "-b", "feature/clean"], self.repo_path)
        with self.assertRaises(NoUpstreamError):
            push_remote(self.repo_path)
        self.assertFalse(get_tracking_info(self.repo_path).has_upstream)

    def test_push_set_upstream_is_explicit_and_works(self):
        _git(["checkout", "-b", "feature/explicit"], self.repo_path)
        _commit_file(self.repo_path, "feature.txt", "feature", "Feature work")

        result = push_remote(self.repo_path, set_upstream=True)

        self.assertEqual(result.operation, "push")
        info = get_tracking_info(self.repo_path)
        self.assertTrue(info.has_upstream)
        self.assertEqual(info.remote_name, "origin")

    def test_rejected_push_with_divergent_history(self):
        other = self._second_clone()
        _commit_file(other, "remote.txt", "remote", "Remote work")
        _git(["push", "origin", "HEAD"], other)

        # Local commit diverges without fetching first.
        _commit_file(self.repo_path, "local.txt", "local", "Local work")

        with self.assertRaises(PushRejectedError):
            push_remote(self.repo_path)

        # The remote must NOT have been overwritten. Check the bare remote directly so
        # the assertion does not depend on the default branch being named master/main.
        remote_log = _git(["log", "--all", "--pretty=%s"], self.remote_path)
        self.assertIn("Remote work", remote_log.stdout)
        self.assertNotIn("Local work", remote_log.stdout)

    def test_push_rejection_does_not_destroy_remote_commit(self):
        other = self._second_clone()
        _commit_file(other, "important.txt", "important", "Important remote commit")
        _git(["push", "origin", "HEAD"], other)

        _commit_file(self.repo_path, "local.txt", "local", "Local work")
        with self.assertRaises(PushRejectedError):
            push_remote(self.repo_path)

        # The other developer's commit must still exist on the remote.
        heads = _git(["log", "--all", "--pretty=%s"], self.remote_path).stdout
        self.assertIn("Important remote commit", heads)

    def test_push_unknown_remote_raises(self):
        with self.assertRaises(RemoteNotFoundError):
            push_remote(self.repo_path, "ghost")

    def test_push_never_uses_force_flags(self):
        captured = []

        from gitpilot.core import repository as repository_module
        real_run_git = repository_module.run_git

        def spy(args, **kwargs):
            captured.append(list(args))
            return real_run_git(args, **kwargs)

        _commit_file(self.repo_path, "noforce.txt", "noforce", "No force")

        repository_module.run_git = spy
        try:
            push_remote(self.repo_path)
        finally:
            repository_module.run_git = real_run_git

        push_commands = [c for c in captured if c and c[0] == "push"]
        self.assertTrue(push_commands)
        for command in push_commands:
            for flag in ("--force", "-f", "--force-with-lease", "--delete"):
                self.assertNotIn(flag, command)

    def test_push_uses_explicit_remote_name(self):
        captured = []

        from gitpilot.core import repository as repository_module
        real_run_git = repository_module.run_git

        def spy(args, **kwargs):
            captured.append(list(args))
            return real_run_git(args, **kwargs)

        _commit_file(self.repo_path, "named.txt", "named", "Named remote")

        repository_module.run_git = spy
        try:
            push_remote(self.repo_path, "origin")
        finally:
            repository_module.run_git = real_run_git

        push_commands = [c for c in captured if c and c[0] == "push"]
        self.assertEqual(push_commands[0], ["push", "origin"])


class TestRepositoryRemoteWrapper(RemoteTestCase):
    """Tests for the Repository wrapper over remote operations."""

    def test_wrapper_fetch_pull_push_round_trip(self):
        repo = Repository(self.repo_path)

        # Push a local commit out through the wrapper.
        _commit_file(self.repo_path, "round.txt", "round", "Round trip")
        pushed = repo.push()
        self.assertEqual(pushed.operation, "push")

        # A second clone makes a change, and the wrapper pulls it.
        other = self._second_clone()
        _commit_file(other, "fromother.txt", "from other", "Other side change")
        _git(["push", "origin", "HEAD"], other)

        fetched = repo.fetch()
        self.assertIsNotNone(fetched.upstream)
        pulled = repo.pull()
        self.assertTrue((self.repo_path / "fromother.txt").exists())
        self.assertEqual(pulled.operation, "pull")

    def test_wrapper_tracking_info(self):
        repo = Repository(self.repo_path)
        info = repo.get_tracking_info()
        self.assertTrue(info.has_upstream)


class TestGitExecutionStaysCentralized(RemoteTestCase):
    """Guard: remote operations must route through run_git, not raw subprocess."""

    def test_repository_module_has_no_direct_subprocess_calls(self):
        source = Path("src/gitpilot/core/repository.py").read_text(encoding="utf-8")
        self.assertNotIn("subprocess.", source)

    def test_gui_does_not_execute_git(self):
        gui_source = Path("src/gitpilot/gui/app.py").read_text(encoding="utf-8")
        for forbidden in ("subprocess", "run_git", "Popen"):
            self.assertNotIn(forbidden, gui_source)

    def test_no_destructive_flags_in_remote_operations(self):
        source = Path("src/gitpilot/core/repository.py").read_text(encoding="utf-8")
        # Look for real command flags rather than substrings of prose.
        for forbidden in ('"--force"', '"--hard"', '"--force-with-lease"', '"--prune"', "'--force'"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
