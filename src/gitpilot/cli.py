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
    InvalidCommitMessageError,
    InvalidPathError,
    NoRemoteError,
    NoUpstreamError,
    NotAGitRepositoryError,
    NothingToCommitError,
    PullConflictError,
    PushRejectedError,
    RemoteNotFoundError,
    RemoteOperationError,
    StageOperationError,
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


def _print_sync_result(result) -> None:
    """Print a compact ahead/behind summary for a fetch, pull, or push result."""
    if result is None:
        return
    if not result.upstream:
        print("Upstream: none (no upstream tracking branch configured)")
        return
    print(f"Upstream: {result.upstream}")
    print(f"Ahead: {result.ahead}")
    print(f"Behind: {result.behind}")
    if result.is_up_to_date:
        print("Status: up to date")


def format_remotes(repo) -> str:
    """Format repository remotes and upstream tracking into readable CLI output."""
    lines: list[str] = []
    remotes = repo.list_remotes()

    lines.append("Remotes:")
    if not remotes:
        lines.append("  (none configured)")
    else:
        for remote in remotes:
            lines.append(f"  {remote.name}")
            if remote.fetch_url:
                lines.append(f"    fetch: {remote.fetch_url}")
            if remote.push_url and remote.push_url != remote.fetch_url:
                lines.append(f"    push:  {remote.push_url}")

    tracking = repo.get_tracking_info()
    lines.append("")
    lines.append("Tracking:")
    lines.append(f"  Branch: {tracking.branch or '(detached)'}")
    if tracking.upstream:
        lines.append(f"  Upstream: {tracking.upstream}")
        lines.append(f"  Ahead: {tracking.ahead}")
        lines.append(f"  Behind: {tracking.behind}")
    else:
        lines.append("  Upstream: none")

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
    parser.add_argument(
        "--stage",
        nargs="+",
        metavar="PATH",
        help="Stage one or more files into the index",
    )
    parser.add_argument(
        "--unstage",
        nargs="+",
        metavar="PATH",
        help="Remove one or more files from the staging area, keeping working-tree changes",
    )
    parser.add_argument(
        "--commit",
        metavar="MESSAGE",
        help="Create a commit from the currently staged changes",
    )
    parser.add_argument(
        "--remotes",
        action="store_true",
        help="List configured remotes and upstream tracking information",
    )
    parser.add_argument(
        "--fetch",
        nargs="?",
        const="",
        metavar="REMOTE",
        help="Fetch from a remote without modifying the working tree",
    )
    parser.add_argument(
        "--pull",
        nargs="?",
        const="",
        metavar="REMOTE",
        help="Fast-forward the current branch from its upstream",
    )
    parser.add_argument(
        "--push",
        nargs="?",
        const="",
        metavar="REMOTE",
        help="Push the current branch to a remote (never forces)",
    )
    parser.add_argument(
        "--set-upstream",
        action="store_true",
        help="With --push, record the upstream for the current branch",
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
        if args.stage:
            staged = repo.stage_files(args.stage)
            print(f"Staged {len(staged)} file(s):")
            for path in staged:
                print(f"  {path}")
            return 0
        if args.unstage:
            unstaged = repo.unstage_files(args.unstage)
            print(f"Unstaged {len(unstaged)} file(s) (working-tree changes were kept):")
            for path in unstaged:
                print(f"  {path}")
            return 0
        if args.commit is not None:
            commit = repo.create_commit(args.commit)
            location = commit.branch or commit.short_oid
            print(f"Committed to {location}: {commit.subject}")
            print(f"Commit: {commit.short_oid}")
            return 0
        if args.remotes:
            print(format_remotes(repo))
            return 0
        if args.fetch is not None:
            result = repo.fetch(args.fetch or None)
            print(f"Fetched from '{result.remote_name}'.")
            _print_sync_result(result)
            return 0
        if args.pull is not None:
            result = repo.pull(args.pull or None)
            print(f"Pulled from '{result.remote_name}'.")
            _print_sync_result(result)
            return 0
        if args.push is not None:
            result = repo.push(args.push or None, set_upstream=args.set_upstream)
            print(f"Pushed to '{result.remote_name}'.")
            _print_sync_result(result)
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
    except InvalidPathError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except StageOperationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except InvalidCommitMessageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NothingToCommitError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NoRemoteError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RemoteNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except NoUpstreamError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except PushRejectedError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except PullConflictError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except RemoteOperationError as exc:
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
