"""Repository abstraction and inspection service."""

from pathlib import Path
from typing import Iterator, Optional, Sequence, Union
from gitpilot.core.errors import (
    BranchAlreadyExistsError,
    BranchNotFoundError,
    DirtyWorkingTreeError,
    GitCommandError,
    InvalidBranchNameError,
    InvalidCommitMessageError,
    InvalidPathError,
    NotAGitRepositoryError,
    NothingToCommitError,
    StageOperationError,
)
from gitpilot.core.git_cli import run_git
from gitpilot.core.models import CommitResult, LocalBranch, RepositoryState
from gitpilot.core.parser import parse_porcelain_v2

PathLike = Union[str, Path]


def get_repository_root(path: PathLike) -> Path:
    """
    Find and return the root directory of the Git repository containing the path.

    Args:
        path: Path to a repository root, subdirectory, or file.

    Returns:
        Absolute, resolved Path to the repository root.

    Raises:
        FileNotFoundError: If the provided path does not exist on disk.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If the git executable is not available.
        GitCommandError: If the underlying git rev-parse command fails unexpectedly.
    """
    target = Path(path).resolve()
    if not target.exists():
        raise FileNotFoundError(f"Path does not exist: {target}")

    search_dir = target if target.is_dir() else target.parent

    result = run_git(["rev-parse", "--show-toplevel"], cwd=search_dir, check=False)

    if result.exit_code != 0:
        err_lower = result.stderr.lower()
        if "not a git repository" in err_lower:
            raise NotAGitRepositoryError(path=str(target))
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    toplevel = result.stdout.strip()
    return Path(toplevel).resolve()


def is_git_repository(path: PathLike) -> bool:
    """
    Check if the specified path is inside a Git repository.

    Args:
        path: Filesystem path to inspect.

    Returns:
        True if the path exists and is within a Git repository; False otherwise.
    """
    try:
        get_repository_root(path)
        return True
    except (NotAGitRepositoryError, FileNotFoundError):
        return False


def get_state(path: PathLike) -> RepositoryState:
    """
    Retrieve the current RepositoryState for the repository containing the path.

    Args:
        path: Path to the repository or any subdirectory within it.

    Returns:
        RepositoryState containing branch metadata and categorized file changes.

    Raises:
        FileNotFoundError: If the path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitCommandError: If the status command fails.
        GitNotInstalledError: If Git is not installed.
    """
    root = get_repository_root(path)
    result = run_git(["status", "--porcelain=v2", "--branch"], cwd=root)
    return parse_porcelain_v2(result.stdout, root_path=root)


def list_branches(path: PathLike) -> list[LocalBranch]:
    """
    List all local branches in the repository.

    Args:
        path: Path to the repository or any subdirectory.

    Returns:
        List of LocalBranch objects sorted as returned by Git.

    Raises:
        FileNotFoundError: If the path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        GitCommandError: If the git branch command fails.
    """
    root = get_repository_root(path)
    result = run_git(
        ["branch", "--list", "--format=%(refname:short)|%(HEAD)|%(objectname)"],
        cwd=root,
    )
    branches: list[LocalBranch] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        b_name = parts[0].strip()
        is_current = len(parts) > 1 and parts[1].strip() == "*"
        oid = parts[2].strip() if len(parts) > 2 and parts[2].strip() else None
        branches.append(LocalBranch(name=b_name, is_current=is_current, oid=oid))
    return branches


def get_current_branch(path: PathLike) -> Optional[str]:
    """
    Get the name of the currently active branch.

    Args:
        path: Path to the repository or any subdirectory.

    Returns:
        The current branch name, or None if HEAD is detached.

    Raises:
        FileNotFoundError: If the path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        GitCommandError: If the git command fails.
    """
    root = get_repository_root(path)
    result = run_git(["branch", "--show-current"], cwd=root)
    name = result.stdout.strip()
    return name if name else None


def create_branch(path: PathLike, name: str) -> LocalBranch:
    """
    Create a new local branch pointing at HEAD without switching to it.

    Args:
        path: Path to the repository or any subdirectory.
        name: Name for the new branch.

    Returns:
        LocalBranch representing the created branch.

    Raises:
        InvalidBranchNameError: If name is empty, whitespace, or rejected by Git ref rules.
        BranchAlreadyExistsError: If a branch with this name already exists.
        FileNotFoundError: If the path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        GitCommandError: If the branch creation fails.
    """
    if not name or not name.strip():
        raise InvalidBranchNameError(name)

    clean_name = name.strip()
    root = get_repository_root(path)

    result = run_git(["branch", clean_name], cwd=root, check=False)
    if result.exit_code != 0:
        err_lower = result.stderr.lower()
        if "already exists" in err_lower:
            raise BranchAlreadyExistsError(branch_name=clean_name)
        if "not a valid branch name" in err_lower or "not a valid ref name" in err_lower:
            raise InvalidBranchNameError(branch_name=clean_name)
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    return LocalBranch(name=clean_name, is_current=False)


def switch_branch(path: PathLike, name: str) -> LocalBranch:
    """
    Switch to an existing local branch without discarding or forcing changes.

    Args:
        path: Path to the repository or any subdirectory.
        name: Name of the existing branch to switch to.

    Returns:
        LocalBranch representing the newly checked-out branch.

    Raises:
        InvalidBranchNameError: If name is empty or invalid.
        BranchNotFoundError: If the specified branch does not exist.
        DirtyWorkingTreeError: If switching is refused because local changes would conflict.
        FileNotFoundError: If the path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        GitCommandError: If switching fails or verification fails.
    """
    if not name or not name.strip():
        raise InvalidBranchNameError(name)

    clean_name = name.strip()
    root = get_repository_root(path)

    result = run_git(["switch", clean_name], cwd=root, check=False)
    if result.exit_code != 0:
        err_lower = result.stderr.lower()
        if (
            "would be overwritten by" in err_lower
            or "commit your changes or stash them" in err_lower
        ):
            raise DirtyWorkingTreeError(
                message=f"Cannot switch to branch '{clean_name}': local uncommitted changes would be overwritten.",
                detail=result.stderr.strip(),
            )
        if (
            "invalid reference" in err_lower
            or "did not match any file" in err_lower
            or "not found" in err_lower
        ):
            raise BranchNotFoundError(branch_name=clean_name)
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    # Verification: Confirm the active branch has changed to clean_name
    current = get_current_branch(root)
    if current != clean_name:
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=f"Verification failed: expected current branch to be '{clean_name}', but found '{current}'.",
        )

    return LocalBranch(name=clean_name, is_current=True)


class Repository:
    """High-level domain abstraction for interacting with a local Git repository."""

    def __init__(self, path: PathLike):
        """
        Initialize a Repository instance by discovering the repository root.

        Args:
            path: Path to the repository root or any subdirectory within it.

        Raises:
            FileNotFoundError: If the path does not exist.
            NotAGitRepositoryError: If the path is not within a Git repository.
        """
        self.root: Path = get_repository_root(path)

    def get_state(self) -> RepositoryState:
        """
        Retrieve the current repository state.

        Returns:
            RepositoryState describing branch and file changes.
        """
        return get_state(self.root)

    def list_branches(self) -> list[LocalBranch]:
        """
        List all local branches in this repository.

        Returns:
            List of LocalBranch objects.
        """
        return list_branches(self.root)

    def get_current_branch(self) -> Optional[str]:
        """
        Get the name of the currently active branch.

        Returns:
            Current branch name, or None if detached.
        """
        return get_current_branch(self.root)

    def create_branch(self, name: str) -> LocalBranch:
        """
        Create a new local branch without switching to it.

        Args:
            name: Name for the new branch.

        Returns:
            LocalBranch representing the created branch.
        """
        return create_branch(self.root, name)

    def switch_branch(self, name: str) -> LocalBranch:
        """
        Switch to an existing local branch.

        Args:
            name: Name of the existing branch to switch to.

        Returns:
            LocalBranch representing the checked-out branch.
        """
        return switch_branch(self.root, name)

    @classmethod
    def is_valid(cls, path: PathLike) -> bool:
        """Check whether the supplied path is inside a Git repository."""
        return is_git_repository(path)

    def __repr__(self) -> str:
        return f"Repository(root={self.root})"

    def stage_files(
        self,
        files: Union[str, Path, Sequence[Union[str, Path]]],
    ) -> list[str]:
        """
        Stage the specified files into the index.

        Args:
            files: A single path or a sequence of paths to stage.

        Returns:
            The list of repository-relative paths that were staged.
        """
        return stage_files(self.root, files)

    def unstage_files(
        self,
        files: Union[str, Path, Sequence[Union[str, Path]]],
    ) -> list[str]:
        """
        Remove the specified files from the staging area, keeping working-tree changes.

        Args:
            files: A single path or a sequence of paths to unstage.

        Returns:
            The list of repository-relative paths that were unstaged.
        """
        return unstage_files(self.root, files)

    def create_commit(self, message: str) -> CommitResult:
        """
        Create a commit from the current staging area.

        Args:
            message: The commit message. Must not be empty or whitespace-only.

        Returns:
            CommitResult describing the created commit.
        """
        return create_commit(self.root, message)




def _normalize_paths(paths: Union[str, Path, Sequence[Union[str, Path]]]) -> list[str]:
    """
    Normalize a path argument into a non-empty list of repository-relative path strings.

    A single string/Path is treated as one path. Sequence items that are Path objects
    are converted with as_posix() so separators stay stable across platforms.

    Raises:
        InvalidPathError: If the resulting list is empty or contains only blank entries.
    """
    if isinstance(paths, (str, Path)):
        candidates: Sequence[Union[str, Path]] = [paths]
    else:
        candidates = list(paths)

    normalized: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, Path):
            text = candidate.as_posix()
        else:
            text = str(candidate)
        text = text.strip()
        if text:
            normalized.append(text)

    if not normalized:
        raise InvalidPathError("At least one non-empty file path is required.")
    return normalized


def _split_git_single_quoted(message: str) -> list[str]:
    """
    Extract single-quoted fragments from a Git status/error message.

    Git names paths inside single quotes in messages such as
    "pathspec 'foo bar.txt' did not match any file(s)". Returning the inner
    fragments lets callers compare them against the requested paths.
    """
    fragments: list[str] = []
    current: list[str] = []
    inside = False
    escaped = False
    for ch in message:
        if inside:
            if escaped:
                current.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                fragments.append("".join(current))
                current = []
                inside = False
            else:
                current.append(ch)
        elif ch == "'":
            inside = True
            current = []
    return fragments


def _stage_error(result, targets: list[str], action: str) -> StageOperationError:
    """Translate a failed stage/unstage command result into a domain error."""
    stderr = result.stderr.strip()
    reported = _split_git_single_quoted(stderr)
    detail = stderr or result.stdout.strip() or f"git exited with code {result.exit_code}"

    if reported:
        missing = [target for target in targets if target in reported]
        if missing:
            return StageOperationError(
                paths=targets,
                message=f"Git could not {action} these paths because they do not exist or are not tracked:",
                detail=", ".join(missing) + f" ({detail})",
            )

    return StageOperationError(paths=targets, message=f"Unable to {action} the requested files.", detail=detail)


def stage_files(
    path: PathLike,
    files: Union[str, Path, Sequence[Union[str, Path]]],
) -> list[str]:
    """
    Stage the specified files into the Git index.

    Args:
        path: Path to the repository or any subdirectory.
        files: A single path or a sequence of paths to stage.

    Returns:
        The list of repository-relative paths that were staged.

    Raises:
        InvalidPathError: If no usable path was supplied.
        FileNotFoundError: If the repository path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        StageOperationError: If Git rejects one or more of the supplied paths.
        GitCommandError: If the git command fails unexpectedly.
    """
    targets = _normalize_paths(files)
    root = get_repository_root(path)

    # '--' separates the revision from paths, so filenames that resemble branch or
    # option names (e.g. '-f') cannot be misinterpreted by Git.
    result = run_git(["add", "--"] + targets, cwd=root, check=False)
    if result.exit_code != 0:
        raise _stage_error(result, targets, "stage")

    return targets


def unstage_files(
    path: PathLike,
    files: Union[str, Path, Sequence[Union[str, Path]]],
) -> list[str]:
    """
    Remove the specified files from the staging area without touching the working tree.

    Uses `git restore --staged`, which resets only the index entry to HEAD and leaves
    the user's working-tree modifications intact. Falls back to `git reset --` on older
    Git versions where `restore` is unavailable.

    Args:
        path: Path to the repository or any subdirectory.
        files: A single path or a sequence of paths to unstage.

    Returns:
        The list of repository-relative paths that were unstaged.

    Raises:
        InvalidPathError: If no usable path was supplied.
        FileNotFoundError: If the repository path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        StageOperationError: If Git rejects one or more of the supplied paths.
        GitCommandError: If the git command fails unexpectedly.
    """
    targets = _normalize_paths(files)
    root = get_repository_root(path)

    result = run_git(["restore", "--staged", "--"] + targets, cwd=root, check=False)
    if result.exit_code != 0:
        err_lower = result.stderr.lower()
        restore_unavailable = "unknown option" in err_lower or "not a git command" in err_lower
        if restore_unavailable:
            # `git restore` requires Git >= 2.23; fall back for older installations.
            result = run_git(["reset", "--"] + targets, cwd=root, check=False)
            if result.exit_code != 0:
                raise _stage_error(result, targets, "unstage")
        else:
            raise _stage_error(result, targets, "unstage")

    return targets


def _message_subject(message: str) -> str:
    """Return the first non-empty line of a commit message as its subject."""
    for line in message.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _build_commit_result(root: Path, message: str) -> CommitResult:
    """Extract commit metadata from `git commit` output and the resulting repository state."""
    # The subject comes from the message GitPilot supplied rather than from the
    # git commit stdout summary line, because Git collapses a multi-line message
    # onto one line ('[main abc1234] subject body'), which would misreport it.
    oid = ""
    rev = run_git(["rev-parse", "HEAD"], cwd=root, check=False)
    if rev.exit_code == 0:
        oid = rev.stdout.strip()

    short_oid = oid[:7] if oid else ""
    short = run_git(["rev-parse", "--short", "HEAD"], cwd=root, check=False)
    if short.exit_code == 0 and short.stdout.strip():
        short_oid = short.stdout.strip()

    return CommitResult(
        oid=oid,
        short_oid=short_oid,
        subject=_message_subject(message),
        branch=get_current_branch(root),
    )


def create_commit(path: PathLike, message: str) -> CommitResult:
    """
    Create a commit from the current staging area.

    Args:
        path: Path to the repository or any subdirectory.
        message: The commit message. Must contain non-whitespace content.

    Returns:
        CommitResult describing the created commit.

    Raises:
        InvalidCommitMessageError: If the message is empty, non-string, or only whitespace.
        FileNotFoundError: If the repository path does not exist.
        NotAGitRepositoryError: If the path is not inside a Git repository.
        GitNotInstalledError: If Git is not installed.
        NothingToCommitError: If there are no staged changes to commit.
        GitCommandError: If the commit fails for any other reason (e.g. missing identity).
    """
    if not isinstance(message, str) or not message.strip():
        raise InvalidCommitMessageError()

    root = get_repository_root(path)

    result = run_git(["commit", "-m", message], cwd=root, check=False)
    if result.exit_code != 0:
        # Git reports "nothing to commit" on stdout, while genuine failures (bad
        # identity, index lock, hooks) surface on stderr. Inspect both streams so
        # the empty-staging case maps to the specific domain error.
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if (
            "nothing to commit" in combined
            or "no changes added to commit" in combined
            or "nothing added to commit" in combined
        ):
            raise NothingToCommitError()
        raise GitCommandError(
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    return _build_commit_result(root, message)
