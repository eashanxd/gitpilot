"""Non-visual tests for the GitPilot desktop presentation helpers."""

from pathlib import Path
import sys
import unittest

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


if __name__ == "__main__":
    unittest.main()
