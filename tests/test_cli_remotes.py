"""CLI tests for GitPilot remote operations (M3)."""

import io
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.cli import format_remotes, run_cli
from gitpilot.core.errors import (
    NoRemoteError,
    NoUpstreamError,
    PullConflictError,
    PushRejectedError,
    RemoteNotFoundError,
    RemoteOperationError,
)
from gitpilot.core.models import Remote, SyncResult, TrackingInfo


class TestFormatRemotes(unittest.TestCase):
    """Tests for the remote formatting helper."""

    def _repo(self, remotes, tracking):
        repo = MagicMock()
        repo.list_remotes.return_value = remotes
        repo.get_tracking_info.return_value = tracking
        return repo

    def test_no_remotes_is_reported(self):
        repo = self._repo([], TrackingInfo(branch="main"))
        output = format_remotes(repo)
        self.assertIn("Remotes:", output)
        self.assertIn("(none configured)", output)
        self.assertIn("Upstream: none", output)

    def test_single_remote_with_urls(self):
        repo = self._repo(
            [Remote(name="origin", fetch_url="/tmp/remote.git", push_url="/tmp/remote.git")],
            TrackingInfo(branch="main", upstream="origin/main", remote_name="origin", ahead=2, behind=1),
        )
        output = format_remotes(repo)
        self.assertIn("  origin", output)
        self.assertIn("fetch: /tmp/remote.git", output)
        self.assertIn("Upstream: origin/main", output)
        self.assertIn("Ahead: 2", output)
        self.assertIn("Behind: 1", output)

    def test_non_origin_remote_name(self):
        repo = self._repo(
            [Remote(name="upstream", fetch_url="git://example/repo.git")],
            TrackingInfo(branch="main"),
        )
        output = format_remotes(repo)
        self.assertIn("upstream", output)
        self.assertNotIn("origin", output)

    def test_distinct_push_url_is_shown(self):
        repo = self._repo(
            [Remote(name="origin", fetch_url="fetch-url", push_url="push-url")],
            TrackingInfo(branch="main"),
        )
        output = format_remotes(repo)
        self.assertIn("push:  push-url", output)


class TestRunCliRemotes(unittest.TestCase):
    """Tests for the --remotes CLI flag."""

    @patch("gitpilot.cli.Repository")
    def test_remotes_flag_success(self, mock_repo_class):
        repo = MagicMock()
        repo.list_remotes.return_value = [Remote(name="origin", fetch_url="/tmp/r.git")]
        repo.get_tracking_info.return_value = TrackingInfo(
            branch="main", upstream="origin/main", remote_name="origin", ahead=1, behind=0
        )
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stdout", capture):
            code = run_cli(["--remotes"])

        self.assertEqual(code, 0)
        output = capture.getvalue()
        self.assertIn("Remotes:", output)
        self.assertIn("origin", output)
        self.assertIn("Ahead: 1", output)

    @patch("gitpilot.cli.Repository")
    def test_remotes_flag_with_no_remotes(self, mock_repo_class):
        repo = MagicMock()
        repo.list_remotes.return_value = []
        repo.get_tracking_info.return_value = TrackingInfo(branch="main")
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stdout", capture):
            code = run_cli(["--remotes"])

        self.assertEqual(code, 0)
        self.assertIn("(none configured)", capture.getvalue())


class TestRunCliFetchPullPush(unittest.TestCase):
    """Tests for the --fetch, --pull, and --push CLI flags."""

    @patch("gitpilot.cli.Repository")
    def test_fetch_flag_success(self, mock_repo_class):
        repo = MagicMock()
        repo.fetch.return_value = SyncResult(
            operation="fetch", remote_name="origin", upstream="origin/main", ahead=0, behind=2
        )
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stdout", capture):
            code = run_cli(["--fetch"])

        self.assertEqual(code, 0)
        repo.fetch.assert_called_once_with(None)
        output = capture.getvalue()
        self.assertIn("Fetched from 'origin'.", output)
        self.assertIn("Behind: 2", output)

    @patch("gitpilot.cli.Repository")
    def test_fetch_flag_with_explicit_remote(self, mock_repo_class):
        repo = MagicMock()
        repo.fetch.return_value = SyncResult(operation="fetch", remote_name="upstream")
        mock_repo_class.return_value = repo

        with patch("sys.stdout", io.StringIO()):
            code = run_cli(["--fetch", "upstream"])

        self.assertEqual(code, 0)
        repo.fetch.assert_called_once_with("upstream")

    @patch("gitpilot.cli.Repository")
    def test_push_flag_success(self, mock_repo_class):
        repo = MagicMock()
        repo.push.return_value = SyncResult(
            operation="push", remote_name="origin", upstream="origin/main", ahead=0, behind=0
        )
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stdout", capture):
            code = run_cli(["--push"])

        self.assertEqual(code, 0)
        repo.push.assert_called_once_with(None, set_upstream=False)
        output = capture.getvalue()
        self.assertIn("Pushed to 'origin'.", output)
        self.assertIn("Status: up to date", output)

    @patch("gitpilot.cli.Repository")
    def test_push_flag_with_set_upstream(self, mock_repo_class):
        repo = MagicMock()
        repo.push.return_value = SyncResult(operation="push", remote_name="origin", upstream="origin/feature")
        mock_repo_class.return_value = repo

        with patch("sys.stdout", io.StringIO()):
            code = run_cli(["--push", "--set-upstream"])

        self.assertEqual(code, 0)
        repo.push.assert_called_once_with(None, set_upstream=True)

    @patch("gitpilot.cli.Repository")
    def test_pull_flag_success(self, mock_repo_class):
        repo = MagicMock()
        repo.pull.return_value = SyncResult(
            operation="pull", remote_name="origin", upstream="origin/main", ahead=0, behind=0
        )
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stdout", capture):
            code = run_cli(["--pull"])

        self.assertEqual(code, 0)
        repo.pull.assert_called_once_with(None)
        self.assertIn("Pulled from 'origin'.", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_fetch_no_remote_error(self, mock_repo_class):
        repo = MagicMock()
        repo.fetch.side_effect = NoRemoteError()
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--fetch"])

        self.assertEqual(code, 1)
        self.assertIn("no configured remotes", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_push_no_upstream_error(self, mock_repo_class):
        repo = MagicMock()
        repo.push.side_effect = NoUpstreamError(branch="feature/x")
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--push"])

        self.assertEqual(code, 1)
        self.assertIn("no upstream tracking branch", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_pull_conflict_error(self, mock_repo_class):
        repo = MagicMock()
        repo.pull.side_effect = PullConflictError()
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--pull"])

        self.assertEqual(code, 1)
        self.assertIn("Pull could not complete cleanly", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_push_rejected_error(self, mock_repo_class):
        repo = MagicMock()
        repo.push.side_effect = PushRejectedError()
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--push"])

        self.assertEqual(code, 1)
        self.assertIn("Push was rejected", capture.getvalue())
        self.assertIn("will not force-push", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_remote_not_found_error(self, mock_repo_class):
        repo = MagicMock()
        repo.fetch.side_effect = RemoteNotFoundError("ghost")
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--fetch", "ghost"])

        self.assertEqual(code, 1)
        self.assertIn("Remote 'ghost' is not configured", capture.getvalue())

    @patch("gitpilot.cli.Repository")
    def test_remote_operation_error(self, mock_repo_class):
        repo = MagicMock()
        repo.fetch.side_effect = RemoteOperationError("fetch from 'origin'")
        mock_repo_class.return_value = repo

        capture = io.StringIO()
        with patch("sys.stderr", capture):
            code = run_cli(["--fetch"])

        self.assertEqual(code, 1)
        self.assertIn("Error:", capture.getvalue())


if __name__ == "__main__":
    unittest.main()
