"""GUI integration tests for the GitPilot Remotes page (M3).

These drive the real GitPilotApp against temporary local repositories and a local
bare remote, so no network access is required.
"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _git(args, cwd, check=True):
    return subprocess.run(["git"] + args, cwd=str(cwd), check=check, capture_output=True, text=True)


class TestGuiRemotesPage(unittest.TestCase):
    """Drive the real GitPilotApp Remotes page against a local bare remote."""

    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
            self.root.geometry("+3000+3000")
            self.root.update()
        except tk.TclError as exc:  # No display available (headless CI)
            self.skipTest(f"Tk unavailable: {exc}")

        self.addCleanup(self.root.destroy)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name).resolve()

        self.remote_path = self.base / "remote.git"
        subprocess.run(["git", "init", "--bare", str(self.remote_path)], check=True, capture_output=True)

        seed = self.base / "seed"
        seed.mkdir()
        subprocess.run(["git", "init", str(seed)], check=True, capture_output=True)
        self._configure(seed)
        (seed / "README.md").write_text("# Seed", encoding="utf-8")
        _git(["add", "README.md"], seed)
        _git(["commit", "-m", "Initial commit"], seed)
        _git(["remote", "add", "origin", str(self.remote_path)], seed)
        _git(["push", "-u", "origin", "HEAD"], seed)

        self.repo_path = self.base / "work"
        subprocess.run(["git", "clone", str(self.remote_path), str(self.repo_path)],
                       check=True, capture_output=True)
        self._configure(self.repo_path)

    def _configure(self, path: Path) -> None:
        _git(["config", "user.name", "Test User"], path)
        _git(["config", "user.email", "test@example.com"], path)
        _git(["config", "commit.gpgsign", "false"], path)

    def _app(self):
        from gitpilot.gui.app import GitPilotApp
        app = GitPilotApp(self.root)
        app._load_repository(self.repo_path)
        return app

    def _settle(self):
        self.root.update_idletasks()
        self.root.update()

    def _silence_dialogs(self):
        """Patch the GUI modals so tests never block on a real dialog."""
        return (
            patch("gitpilot.gui.app.messagebox.showinfo"),
            patch("gitpilot.gui.app.messagebox.showerror"),
            patch("gitpilot.gui.app.messagebox.askyesno", return_value=True),
        )

    def test_remotes_page_is_reachable(self):
        app = self._app()
        app._show_page("remotes")
        self.assertEqual(app.current_page, "remotes")
        self.assertIn("remotes", app.page_frames)

    def test_remotes_page_lists_configured_remote(self):
        app = self._app()
        app._show_page("remotes")
        app._refresh()
        self._settle()
        self.assertIn("origin", app.remotes_tree.get_children())

    def test_remotes_page_shows_upstream_and_ahead_behind(self):
        app = self._app()
        app._show_page("remotes")
        app._refresh()
        self._settle()
        # Fresh clone of a bare remote: upstream set, no divergence.
        self.assertNotEqual(app.remote_upstream_value.cget("text"), "None")
        self.assertEqual(app.remote_ahead_value.cget("text"), "0")
        self.assertEqual(app.remote_behind_value.cget("text"), "0")

    def test_fetch_through_the_gui(self):
        # Another clone pushes a commit so the fetch has something new to see.
        other = self.base / "other"
        subprocess.run(["git", "clone", str(self.remote_path), str(other)], check=True, capture_output=True)
        self._configure(other)
        (other / "new.txt").write_text("new", encoding="utf-8")
        _git(["add", "new.txt"], other)
        _git(["commit", "-m", "Remote change"], other)
        _git(["push", "origin", "HEAD"], other)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        info, error, confirm = self._silence_dialogs()
        with info, error, confirm:
            app._fetch_remote()

        self.assertEqual(app.state.branch.behind, 1)
        self.assertIn("Fetched", app.message_var.get())

    def test_push_through_the_gui(self):
        (self.repo_path / "pushed.txt").write_text("pushed", encoding="utf-8")
        _git(["add", "pushed.txt"], self.repo_path)
        _git(["commit", "-m", "GUI push"], self.repo_path)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        info, error, confirm = self._silence_dialogs()
        with info, error, confirm:
            app._push_remote()

        remote_log = _git(["log", "--all", "--pretty=%s"], self.remote_path).stdout
        self.assertIn("GUI push", remote_log)
        self.assertIn("Pushed", app.message_var.get())

    def test_pull_through_the_gui(self):
        other = self.base / "other2"
        subprocess.run(["git", "clone", str(self.remote_path), str(other)], check=True, capture_output=True)
        self._configure(other)
        (other / "pulled.txt").write_text("pulled", encoding="utf-8")
        _git(["add", "pulled.txt"], other)
        _git(["commit", "-m", "Remote pull change"], other)
        _git(["push", "origin", "HEAD"], other)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        info, error, confirm = self._silence_dialogs()
        with info, error, confirm:
            app._pull_remote()

        self.assertTrue((self.repo_path / "pulled.txt").exists())
        self.assertIn("Pulled", app.message_var.get())

    def test_pull_confirmation_can_be_declined(self):
        app = self._app()
        app._show_page("remotes")
        app._refresh()
        with patch("gitpilot.gui.app.messagebox.askyesno", return_value=False):
            with patch("gitpilot.gui.app.messagebox.showinfo") as info:
                app._pull_remote()
        # Declining must not perform the operation or claim success.
        self.assertFalse(info.called)

    def test_push_confirmation_can_be_declined(self):
        (self.repo_path / "declined.txt").write_text("x", encoding="utf-8")
        _git(["add", "declined.txt"], self.repo_path)
        _git(["commit", "-m", "Should not be pushed"], self.repo_path)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        with patch("gitpilot.gui.app.messagebox.askyesno", return_value=False):
            with patch("gitpilot.gui.app.messagebox.showinfo") as info:
                app._push_remote()

        self.assertFalse(info.called)
        remote_log = _git(["log", "--all", "--pretty=%s"], self.remote_path).stdout
        self.assertNotIn("Should not be pushed", remote_log)

    def test_error_path_on_operation_that_cannot_succeed(self):
        # Point the remote at a path that does not exist.
        _git(["remote", "set-url", "origin", str(self.base / "missing.git")], self.repo_path)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        with patch("gitpilot.gui.app.messagebox.showerror") as error:
            with patch("gitpilot.gui.app.messagebox.showinfo"):
                app._fetch_remote()

        self.assertTrue(error.called, "fetch failure did not surface an error dialog")
        self.assertEqual(app.message_label.cget("style"), "ErrorStatus.TLabel")

    def test_no_upstream_error_path_through_the_gui(self):
        _git(["checkout", "-b", "feature/no-upstream"], self.repo_path)

        app = self._app()
        app._show_page("remotes")
        app._refresh()
        with patch("gitpilot.gui.app.messagebox.showerror") as error:
            with patch("gitpilot.gui.app.messagebox.askyesno", return_value=True):
                with patch("gitpilot.gui.app.messagebox.showinfo"):
                    app._pull_remote()

        self.assertTrue(error.called)
        self.assertIn("upstream", app.message_var.get().lower())

    def test_repository_without_remotes_shows_cleanly(self):
        solo = self.base / "solo"
        solo.mkdir()
        subprocess.run(["git", "init", str(solo)], check=True, capture_output=True)
        self._configure(solo)

        from gitpilot.gui.app import GitPilotApp
        app = GitPilotApp(self.root)
        app._load_repository(solo)
        app._show_page("remotes")
        app._refresh()
        self._settle()

        self.assertEqual(app.remotes_tree.get_children(), ())
        self.assertEqual(app.remote_upstream_value.cget("text"), "None")
        self.assertIn("No remotes", app.remote_hint.cget("text"))


if __name__ == "__main__":
    unittest.main()
