"""Unit tests for the porcelain-v2 status parser and domain models."""

from pathlib import Path
import sys
import unittest

# Ensure src is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gitpilot.core.models import (
    BranchInfo,
    FileChange,
    FileStatus,
    RepositoryState,
)
from gitpilot.core.parser import parse_porcelain_v2, unquote_git_path


class TestPorcelainV2Parser(unittest.TestCase):
    """Test suite for parsing git status --porcelain=v2 --branch output."""

    def test_clean_repository(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "# branch.upstream origin/main\n"
            "# branch.ab +0 -0\n"
        )
        state = parse_porcelain_v2(output)

        self.assertTrue(state.is_clean)
        self.assertFalse(state.has_conflicts)
        self.assertEqual(state.branch.name, "main")
        self.assertEqual(state.branch.oid, "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")
        self.assertEqual(state.branch.upstream, "origin/main")
        self.assertEqual(state.branch.ahead, 0)
        self.assertEqual(state.branch.behind, 0)
        self.assertFalse(state.branch.is_detached)
        self.assertFalse(state.branch.is_initial)
        self.assertEqual(len(state.staged_files), 0)
        self.assertEqual(len(state.unstaged_files), 0)
        self.assertEqual(len(state.untracked_files), 0)
        self.assertEqual(len(state.conflicted_files), 0)

    def test_modified_unstaged_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 .M N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 src/app.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.staged_files), 0)
        self.assertEqual(len(state.unstaged_files), 1)

        change = state.unstaged_files[0]
        self.assertEqual(change.path, "src/app.py")
        self.assertEqual(change.staged_status, FileStatus.UNMODIFIED)
        self.assertEqual(change.unstaged_status, FileStatus.MODIFIED)
        self.assertFalse(change.is_staged)
        self.assertTrue(change.is_unstaged)
        self.assertFalse(change.is_untracked)

    def test_modified_staged_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 M. N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 src/app.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.staged_files), 1)
        self.assertEqual(len(state.unstaged_files), 0)

        change = state.staged_files[0]
        self.assertEqual(change.path, "src/app.py")
        self.assertEqual(change.staged_status, FileStatus.MODIFIED)
        self.assertEqual(change.unstaged_status, FileStatus.UNMODIFIED)
        self.assertTrue(change.is_staged)
        self.assertFalse(change.is_unstaged)

    def test_file_modified_both_staged_and_unstaged(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 MM N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 src/app.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.staged_files), 1)
        self.assertEqual(len(state.unstaged_files), 1)

        staged = state.staged_files[0]
        self.assertEqual(staged.path, "src/app.py")
        self.assertEqual(staged.staged_status, FileStatus.MODIFIED)
        self.assertEqual(staged.unstaged_status, FileStatus.MODIFIED)
        self.assertTrue(staged.is_staged)
        self.assertTrue(staged.is_unstaged)

        # all_changes deduplicates
        self.assertEqual(len(state.all_changes), 1)

    def test_untracked_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "? notes.txt\n"
        )
        state = parse_porcelain_v2(output)

        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.untracked_files), 1)
        change = state.untracked_files[0]
        self.assertEqual(change.path, "notes.txt")
        self.assertEqual(change.staged_status, FileStatus.UNTRACKED)
        self.assertEqual(change.unstaged_status, FileStatus.UNTRACKED)
        self.assertTrue(change.is_untracked)

    def test_deleted_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 D. N... 100644 000000 000000 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 0000000000000000000000000000000000000000 staged_deleted.txt\n"
            "1 .D N... 100644 100644 000000 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 unstaged_deleted.txt\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(len(state.staged_files), 1)
        self.assertEqual(state.staged_files[0].path, "staged_deleted.txt")
        self.assertEqual(state.staged_files[0].staged_status, FileStatus.DELETED)

        self.assertEqual(len(state.unstaged_files), 1)
        self.assertEqual(state.unstaged_files[0].path, "unstaged_deleted.txt")
        self.assertEqual(state.unstaged_files[0].unstaged_status, FileStatus.DELETED)

    def test_renamed_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "2 R. N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 R100 new_file.py\told_file.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(len(state.staged_files), 1)
        change = state.staged_files[0]
        self.assertEqual(change.path, "new_file.py")
        self.assertEqual(change.orig_path, "old_file.py")
        self.assertEqual(change.staged_status, FileStatus.RENAMED)
        self.assertEqual(change.unstaged_status, FileStatus.UNMODIFIED)
        self.assertTrue(change.is_staged)

    def test_added_file(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 A. N... 000000 100644 100644 0000000000000000000000000000000000000000 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 new_added.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(len(state.staged_files), 1)
        change = state.staged_files[0]
        self.assertEqual(change.path, "new_added.py")
        self.assertEqual(change.staged_status, FileStatus.ADDED)
        self.assertEqual(change.unstaged_status, FileStatus.UNMODIFIED)
        self.assertTrue(change.is_staged)

    def test_conflict_unmerged_state(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "u UU N... 100644 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 conflict.py\n"
        )
        state = parse_porcelain_v2(output)

        self.assertTrue(state.has_conflicts)
        self.assertFalse(state.is_clean)
        self.assertEqual(len(state.conflicted_files), 1)
        change = state.conflicted_files[0]
        self.assertEqual(change.path, "conflict.py")
        self.assertEqual(change.staged_status, FileStatus.CONFLICT)
        self.assertEqual(change.unstaged_status, FileStatus.CONFLICT)
        self.assertTrue(change.is_conflict)

    def test_branch_name(self):
        output = (
            "# branch.oid 1122334455667788990011223344556677889900\n"
            "# branch.head feature/authentication\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(state.branch.name, "feature/authentication")
        self.assertFalse(state.branch.is_detached)
        self.assertFalse(state.branch.is_initial)

    def test_upstream_branch(self):
        output = (
            "# branch.oid 1122334455667788990011223344556677889900\n"
            "# branch.head feature/authentication\n"
            "# branch.upstream origin/feature/authentication\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(state.branch.upstream, "origin/feature/authentication")
        self.assertTrue(state.branch.has_upstream)

    def test_ahead_behind_counts(self):
        output = (
            "# branch.oid 1122334455667788990011223344556677889900\n"
            "# branch.head main\n"
            "# branch.upstream origin/main\n"
            "# branch.ab +3 -5\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(state.branch.ahead, 3)
        self.assertEqual(state.branch.behind, 5)

    def test_detached_head(self):
        output = (
            "# branch.oid 9f8e7d6c5b4a3928170192837465abcde1234567\n"
            "# branch.head (detached)\n"
        )
        state = parse_porcelain_v2(output)

        self.assertTrue(state.branch.is_detached)
        self.assertIsNone(state.branch.name)
        self.assertEqual(state.branch.oid, "9f8e7d6c5b4a3928170192837465abcde1234567")

    def test_unborn_initial_branch(self):
        output = (
            "# branch.oid (initial)\n"
            "# branch.head main\n"
        )
        state = parse_porcelain_v2(output)

        self.assertTrue(state.branch.is_initial)
        self.assertFalse(state.branch.is_detached)
        self.assertEqual(state.branch.name, "main")
        self.assertIsNone(state.branch.oid)

    def test_paths_containing_spaces(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            "1 .M N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 my documents/annual report 2026.docx\n"
            "? draft notes for team meeting.txt\n"
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(len(state.unstaged_files), 1)
        self.assertEqual(state.unstaged_files[0].path, "my documents/annual report 2026.docx")

        self.assertEqual(len(state.untracked_files), 1)
        self.assertEqual(state.untracked_files[0].path, "draft notes for team meeting.txt")

    def test_quoted_and_special_paths(self):
        output = (
            "# branch.oid a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n"
            "# branch.head main\n"
            '1 .M N... 100644 100644 100644 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 e69de29bb2d1d6434b8b29ae775ad8c2e48c5391 "path/with \\"quote\\".txt"\n'
            '? "data/caf\\303\\251.csv"\n'
            '? "folder\\\\backslash.txt"\n'
        )
        state = parse_porcelain_v2(output)

        self.assertEqual(state.unstaged_files[0].path, 'path/with "quote".txt')
        self.assertEqual(state.untracked_files[0].path, "data/café.csv")
        self.assertEqual(state.untracked_files[1].path, "folder\\backslash.txt")

    def test_empty_output(self):
        state = parse_porcelain_v2("")
        self.assertTrue(state.is_clean)
        self.assertIsNone(state.branch.name)

    def test_root_path_attached(self):
        test_root = Path("/repos/my_project")
        state = parse_porcelain_v2("# branch.head main\n", root_path=test_root)
        self.assertEqual(state.root_path, test_root)

    def test_unquote_git_path_helper(self):
        self.assertEqual(unquote_git_path("normal.txt"), "normal.txt")
        self.assertEqual(unquote_git_path('"quoted.txt"'), "quoted.txt")
        self.assertEqual(unquote_git_path('"tab\\tfile.txt"'), "tab\tfile.txt")
        self.assertEqual(unquote_git_path('"newline\\nfile.txt"'), "newline\nfile.txt")
        self.assertEqual(unquote_git_path('"escaped\\\\slash.txt"'), "escaped\\slash.txt")


if __name__ == "__main__":
    unittest.main()

