"""Repository abstraction and inspection service."""

from pathlib import Path
from typing import Union
from typing import Optional, Union

from gitpilot.core.errors import (
    BranchAlreadyExistsError,
    BranchNotFoundError,
    DirtyWorkingTreeError,
    GitCommandError,
    InvalidBranchNameError,
    NotAGitRepositoryError,
)
from gitpilot.core.git_cli import run_git
from gitpilot.core.models import RepositoryState
from gitpilot.core.models import LocalBranch, RepositoryState
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


