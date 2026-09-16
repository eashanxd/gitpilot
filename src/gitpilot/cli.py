"""Command Line Interface for GitPilot."""

import argparse
from pathlib import Path
import sys
from typing import Optional, Sequence

from gitpilot.core.errors import (
    BranchAlreadyExistsError,
    BranchNotFoundError,
    DirtyWorkingTreeError,
    GitCommandError,
    GitNotInstalledError,
    GitTimeoutError,
    InvalidBranchNameError,
    NotAGitRepositoryError,
)
from gitpilot.core.models import FileChange, FileStatus, RepositoryState
from gitpilot.core.repository import Repository

_STATUS_LETTER_MAP: dict[FileStatus, str] = {
    FileStatus.MODIFIED: "M",
    FileStatus.ADDED: "A",
    FileStatus.DELETED: "D",
    FileStatus.RENAMED: "R",
    FileStatus.COPIED: "C",
    FileStatus.TYPE_CHANGED: "T",
    FileStatus.UNTRACKED: "?",
    FileStatus.CONFLICT: "U",
}


def _get_status_letter(status: FileStatus) -> str:
    """Return single-letter status indicator."""
    return _STATUS_LETTER_MAP.get(status, " ")


def format_status(state: RepositoryState) -> str:
    """
    Format a RepositoryState into a clean, human-readable terminal output.

    Args:
        state: The repository state model to format.

    Returns:
        Formatted string suitable for printing to stdout.
    """
    lines: list[str] = [
        "GitPilot",
        "--------",
        "",
        f"Repository: {state.root_path or 'Unknown'}",
    ]

    # Branch information
    branch = state.branch
    if branch.is_detached:
        oid_short = f" at {branch.oid[:7]}" if branch.oid else ""
        lines.append(f"Branch: (detached{oid_short})")
    elif branch.is_initial:
        name = branch.name or "main"
        lines.append(f"Branch: {name} (initial commit)")
    else:
        lines.append(f"Branch: {branch.name or 'unknown'}")

    if branch.has_upstream:
        lines.append(f"Upstream: {branch.upstream}")
        lines.append(f"Ahead: {branch.ahead}")
        lines.append(f"Behind: {branch.behind}")
    else:
        lines.append("Upstream: none")

    lines.append("")

    # Changes summary
    lines.append("Changes:")
    if state.is_clean:
        lines.append("Working tree is clean (nothing to commit).")
        return "\n".join(lines)

    lines.append(f"Staged: {len(state.staged_files)}")
    lines.append(f"Unstaged: {len(state.unstaged_files)}")
    lines.append(f"Untracked: {len(state.untracked_files)}")
    lines.append(f"Conflicts: {len(state.conflicted_files)}")

    # File listing
    lines.append("")
    lines.append("Files:")

    if state.conflicted_files:
        for f in state.conflicted_files:
            lines.append(f"U  {f.path} (conflict)")

    if state.staged_files:
        for f in state.staged_files:
            letter = _get_status_letter(f.staged_status)
            if f.orig_path:
                lines.append(f"{letter}  {f.path} (staged, renamed from {f.orig_path})")
            else:
                lines.append(f"{letter}  {f.path} (staged)")

    if state.unstaged_files:
        for f in state.unstaged_files:
            letter = _get_status_letter(f.unstaged_status)
            lines.append(f"{letter}  {f.path}")

    if state.untracked_files:
        for f in state.untracked_files:
            lines.append(f"?  {f.path}")

    return "\n".join(lines)


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    """
    Execute the GitPilot CLI application.

    Args:
        argv: Optional command line arguments. If None, sys.argv[1:] is used.

    Returns:
        Process exit code (0 for success, non-zero for handled error).
    """
    parser = argparse.ArgumentParser(
        prog="gitpilot",
        description="GitPilot - Goal-oriented Git workflow assistant",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to the Git repository or subdirectory (defaults to current directory)",
    )
    parser.add_argument(
        "--branches",
        action="store_true",
        help="List all local branches in the repository",
    )
    parser.add_argument(
        "--create-branch",
        metavar="NAME",
        help="Create a new local branch without switching to it",
    )
    parser.add_argument(
        "--switch-branch",
        metavar="NAME",
        help="Switch to an existing local branch",
    )

    args = parser.parse_args(argv)
    target_path = Path(args.path)

    try:
        repo = Repository(target_path)

        if args.branches:
            branches = repo.list_branches()
            print("Branches:")
            for b in branches:
                prefix = "* " if b.is_current else "  "
                print(f"{prefix}{b.name}")
            return 0

        if args.create_branch:
            created = repo.create_branch(args.create_branch)
            print(f"Created branch '{created.name}'.")
            return 0

        if args.switch_branch:
            switched = repo.switch_branch(args.switch_branch)
            print(f"Switched to branch '{switched.name}'.")
            return 0

        state = repo.get_state()
        output = format_status(state)
        print(output)
        return 0
    except FileNotFoundError:
        print(f"Error: Path does not exist: {target_path}", file=sys.stderr)
        return 1
    except NotAGitRepositoryError as exc:
        print(f"Error: '{exc.path}' is not inside a Git repository.", file=sys.stderr)
        return 1
    except GitNotInstalledError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except GitTimeoutError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except BranchNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except BranchAlreadyExistsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except InvalidBranchNameError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except DirtyWorkingTreeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except GitCommandError as exc:
        err_msg = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        print(f"Error: Git command failed ({' '.join(exc.command)}): {err_msg}", file=sys.stderr)
        return 1


def main() -> None:
    """CLI entry point function."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
