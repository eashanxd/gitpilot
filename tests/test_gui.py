"""Non-visual tests for the GitPilot desktop presentation helpers."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.models import BranchInfo, FileChange, FileStatus, RepositoryState
from gitpilot.gui.app import branch_display_name, format_change_status


class TestGuiPresentationHelpers(unittest.TestCase):
    def test_change_status_uses_model_statuses(self):
        self.assertEqual(
            format_change_status(
                FileChange(
                    path="src/main.py",
                    staged_status=FileStatus.MODIFIED,
                    unstaged_status=FileStatus.MODIFIED,
                )
            ),
            "MM",
        )
        self.assertEqual(
            format_change_status(FileChange(path="notes.txt", unstaged_status=FileStatus.UNTRACKED)),
            "??",
        )
        self.assertEqual(
            format_change_status(FileChange(path="conflict.py", staged_status=FileStatus.CONFLICT)),
            "UU",
        )

    def test_branch_display_name_handles_detached_head(self):
        state = RepositoryState(branch=BranchInfo(oid="123456789abcdef", is_detached=True))
        self.assertEqual(branch_display_name(state), "detached at 1234567")

    def test_branch_display_name_uses_branch_name(self):
        state = RepositoryState(branch=BranchInfo(name="feature/gui"))
        self.assertEqual(branch_display_name(state), "feature/gui")


class TestGuiCommitPageIntegration(unittest.TestCase):
    """Drive the real GitPilotApp against a temporary repository without a visible window."""

    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
            # The window must be mapped for Tk to allocate real widget geometry.
            # A withdrawn window reports 1x1 for every child, which would make the
            # layout assertions below meaningless. Move it off-screen instead so the
            # tests stay headless-friendly while still exercising a real layout pass.
            self.root.geometry("+3000+3000")
            self.root.update()
        except tk.TclError as exc:  # No display available (headless CI)
            self.skipTest(f"Tk unavailable: {exc}")

        self.addCleanup(self.root.destroy)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.repo_path = Path(self.temp_dir.name).resolve()
        subprocess.run(["git", "init", str(self.repo_path)], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.repo_path, check=True, capture_output=True)
        (self.repo_path / "README.md").write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_path, check=True, capture_output=True)

    def _app(self):
        from gitpilot.gui.app import GitPilotApp
        app = GitPilotApp(self.root)
        app._load_repository(self.repo_path)
        return app

    def _settle_geometry(self):
        """Force Tk to run enough layout/idle cycles for widget geometry to settle."""
        self.root.update_idletasks()
        self.root.update()
        self.root.update_idletasks()

    def _find_widgets(self, app, predicate):
        """Walk the Commit Changes page and return widgets matching predicate."""
        found = []

        def walk(widget):
            for child in widget.winfo_children():
                if predicate(child):
                    found.append(child)
                walk(child)

        walk(app.page_frames["changes"])
        return found

    def test_commit_message_entry_exists_and_is_visible(self):
        """Regression: the commit-message Entry used to be packed after an expanding

        tree, so it received no height and was never mapped (invisible).
        """
        app = self._app()
        app._show_page("changes")
        self._settle_geometry()

        entries = self._find_widgets(app, lambda w: w.winfo_class() == "TEntry")
        self.assertTrue(entries, "no Entry widget found on the Commit Changes page")
        entry = entries[0]

        # The Entry must be a packed layout slave with real geometry, not a 1x1 widget
        # that was never given room by the layout pass.
        self.assertEqual(entry.winfo_manager(), "pack", "commit-message Entry is not packed")
        self.assertGreater(entry.winfo_reqwidth(), 50, "commit-message Entry has no usable width")
        self.assertGreater(entry.winfo_reqheight(), 10, "commit-message Entry has no usable height")
        self.assertGreater(entry.winfo_width(), 50, "commit-message Entry was allocated no width")
        self.assertGreater(entry.winfo_height(), 10, "commit-message Entry was allocated no height")

        # It must be bound to the same variable _create_commit reads. cget returns a
        # Tcl variable name, so compare values rather than object identity.
        self.assertEqual(str(entry.cget("textvariable")), str(app.commit_message_var))

    def test_commit_message_field_has_a_label_and_commit_button(self):
        app = self._app()
        app._show_page("changes")
        self._settle_geometry()

        labels = self._find_widgets(
            app, lambda w: w.winfo_class() == "TLabel" and "commit message" in str(w.cget("text")).lower()
        )
        self.assertTrue(labels, "no 'Commit message:' label found")
        self.assertEqual(labels[0].winfo_manager(), "pack", "commit-message label is not packed")

        buttons = self._find_widgets(
            app, lambda w: "Create Commit" in str(w.cget("text") if "text" in w.keys() else "")
        )
        self.assertTrue(buttons, "no Create Commit button found")
        self.assertEqual(buttons[0].winfo_manager(), "pack", "Create Commit button is not packed")

    def test_commit_message_entry_has_room_and_sits_above_the_commit_button(self):
        """Regression: the tree previously starved the entry of vertical space.

        With a default-size window the entry must be allocated a real height, and it
        must be positioned above the Create Commit button (not clipped off-page).
        """
        app = self._app()
        app._show_page("changes")
        self._settle_geometry()

        entries = self._find_widgets(app, lambda w: w.winfo_class() == "TEntry")
        buttons = self._find_widgets(
            app, lambda w: "Create Commit" in str(w.cget("text") if "text" in w.keys() else "")
        )
        entry, button = entries[0], buttons[0]

        # Both widgets must be packed into the page (i.e. part of the layout), and the
        # entry must be given its natural height rather than being squeezed to nothing.
        self.assertEqual(entry.winfo_manager(), "pack")
        self.assertEqual(button.winfo_manager(), "pack")
        self.assertGreater(entry.winfo_height(), 10, "commit-message Entry was squeezed out")
        self.assertGreater(entry.winfo_reqheight(), 10)

        # The entry must sit above the Create Commit button. Compare absolute screen
        # positions, since winfo_y() is relative to each widget's immediate parent.
        self.assertLess(entry.winfo_rooty(), button.winfo_rooty(), "entry should sit above the commit button")
        # The button must still lie within the page rather than being pushed off the bottom.
        page = app.page_frames["changes"]
        self.assertLessEqual(
            button.winfo_rooty() + button.winfo_height(),
            page.winfo_rooty() + page.winfo_height(),
            "Create Commit button falls outside the visible page",
        )

    def test_typed_message_flows_into_the_commit(self):
        (self.repo_path / "typed.txt").write_text("typed", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app.commit_tree.selection_set("typed.txt")
        app._stage_selected()

        # Simulate typing into the visible Entry via its bound StringVar.
        entries = self._find_widgets(app, lambda w: w.winfo_class() == "TEntry")
        entries[0].delete(0, "end")
        entries[0].insert(0, "Message typed into the field")
        self.assertEqual(app.commit_message_var.get(), "Message typed into the field")

        with patch("gitpilot.gui.app.messagebox.showinfo"):
            app._create_commit()

        log = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(log, "Message typed into the field")

    def test_stage_then_commit_through_the_gui(self):
        (self.repo_path / "feature.txt").write_text("feature", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app._refresh()

        # The new file appears in the commit page tree and can be staged.
        self.assertIn("feature.txt", app.commit_tree.get_children())
        app.commit_tree.selection_set("feature.txt")
        app._stage_selected()
        self.assertEqual(len(app.state.staged_files), 1)

        app.commit_message_var.set("Add feature from GUI")
        # A successful commit must confirm itself with a visible dialog, matching the
        # error path. Patch the modal so the test is non-blocking and can assert on it.
        with patch("gitpilot.gui.app.messagebox.showinfo") as mock_info:
            app._create_commit()

        self.assertTrue(mock_info.called, "successful commit did not show a confirmation dialog")
        title, body = mock_info.call_args[0][0], mock_info.call_args[0][1]
        self.assertEqual(title, "Commit Created")
        self.assertIn("Add feature from GUI", body)

        self.assertEqual(app.state.staged_files, [])
        self.assertEqual(app.commit_message_var.get(), "")
        self.assertIn("Committed to", app.message_var.get())
        self.assertEqual(app.message_label.cget("style"), "SuccessStatus.TLabel")
        log = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(log, "Add feature from GUI")

    def test_unstage_through_the_gui_keeps_working_tree_change(self):
        target = self.repo_path / "README.md"
        target.write_text("# Initial\nEdited", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app.commit_tree.selection_set("README.md")
        app._stage_selected()
        self.assertEqual(len(app.state.staged_files), 1)

        app.commit_tree.selection_set("README.md")
        app._unstage_selected()

        self.assertEqual(app.state.staged_files, [])
        self.assertIn("README.md", [c.path for c in app.state.unstaged_files])
        self.assertEqual(target.read_text(encoding="utf-8"), "# Initial\nEdited")

    def test_commit_with_blank_message_shows_error_and_creates_nothing(self):
        (self.repo_path / "staged.txt").write_text("staged", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app.commit_tree.selection_set("staged.txt")
        app._stage_selected()
        before = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()

        # messagebox is presentation-only; suppress the modal dialog in tests.
        with patch("gitpilot.gui.app.messagebox.showerror"):
            with patch("gitpilot.gui.app.messagebox.showinfo"):
                with patch("gitpilot.gui.app.messagebox.showwarning"):
                    app.commit_message_var.set("   ")
                    app._create_commit()

        after = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.strip()
        self.assertEqual(before, after)
        self.assertIn("commit message is required", app.message_var.get())

    def test_commit_failure_shows_error_dialog_and_success_shows_confirm_dialog(self):
        """Regression: a commit must give visible feedback on BOTH outcomes.

        Previously the success path only updated the status bar, so a real commit
        looked like it did nothing while the failure path popped a dialog.
        """
        (self.repo_path / "staged.txt").write_text("staged", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app.commit_tree.selection_set("staged.txt")
        app._stage_selected()

        # Nothing committed yet: a blank message must raise an error dialog.
        with patch("gitpilot.gui.app.messagebox.showerror") as mock_error:
            with patch("gitpilot.gui.app.messagebox.showinfo") as mock_info:
                app.commit_message_var.set("")
                app._create_commit()
        self.assertTrue(mock_error.called, "blank message did not surface an error dialog")
        self.assertFalse(mock_info.called, "a failed commit must not report success")

        # Now a valid message must commit AND show a confirmation dialog.
        with patch("gitpilot.gui.app.messagebox.showerror") as mock_error:
            with patch("gitpilot.gui.app.messagebox.showinfo") as mock_info:
                app.commit_message_var.set("Valid message")
                app._create_commit()
        self.assertFalse(mock_error.called, "a successful commit should not report an error")
        self.assertTrue(mock_info.called, "successful commit did not show a confirmation dialog")

    def test_gui_remains_usable_after_committing(self):
        (self.repo_path / "one.txt").write_text("one", encoding="utf-8")
        app = self._app()
        app._show_page("changes")
        app.commit_tree.selection_set("one.txt")
        app._stage_selected()
        app.commit_message_var.set("First")
        with patch("gitpilot.gui.app.messagebox.showinfo"):
            app._create_commit()

        # A second round-trip must work: refresh, stage, commit again.
        (self.repo_path / "two.txt").write_text("two", encoding="utf-8")
        app._refresh()
        self.assertIn("two.txt", app.commit_tree.get_children())
        app.commit_tree.selection_set("two.txt")
        app._stage_selected()
        app.commit_message_var.set("Second")
        with patch("gitpilot.gui.app.messagebox.showinfo"):
            app._create_commit()

        subjects = subprocess.run(
            ["git", "log", "-2", "--pretty=%s"], cwd=self.repo_path, check=True, capture_output=True, text=True
        ).stdout.split()
        self.assertEqual(subjects, ["Second", "First"])

if __name__ == "__main__":
    unittest.main()
