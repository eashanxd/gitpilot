"""Repository abstraction and inspection service."""

from pathlib import Path
from typing import Union

from gitpilot.core.errors import (
    GitCommandError,
    NotAGitRepositoryError,
)
from gitpilot.core.git_cli import run_git
from gitpilot.core.models import RepositoryState
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

    @classmethod
    def is_valid(cls, path: PathLike) -> bool:
        """Check whether the supplied path is inside a Git repository."""
        return is_git_repository(path)

    def __repr__(self) -> str:
        return f"Repository(root={self.root})"

