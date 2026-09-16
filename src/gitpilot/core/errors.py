"""Domain-specific exceptions for GitPilot."""

from typing import Sequence


class GitPilotError(Exception):
    """Base exception for all GitPilot domain errors."""
    pass


class GitNotInstalledError(GitPilotError):
    """Raised when the git executable cannot be found on the system PATH."""

    def __init__(self, message: str = "Git executable not found in PATH. Please install Git and try again."):
        super().__init__(message)


class GitCommandError(GitPilotError):
    """Raised when a Git command returns a non-zero exit code."""

    def __init__(
        self,
        command: Sequence[str],
        exit_code: int,
        stdout: str,
        stderr: str,
        message: str | None = None,
    ):
        self.command = list(command)
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr

        if message is None:
            cmd_str = " ".join(self.command)
            err_detail = stderr.strip() or stdout.strip() or f"Exit code {exit_code}"
            message = f"Command '{cmd_str}' failed with exit code {exit_code}: {err_detail}"

        super().__init__(message)


class GitTimeoutError(GitPilotError):
    """Raised when a Git command execution exceeds the timeout limit."""

    def __init__(self, command: Sequence[str], timeout: float):
        self.command = list(command)
        self.timeout = timeout
        cmd_str = " ".join(self.command)
        super().__init__(f"Command '{cmd_str}' timed out after {timeout} seconds.")


class NotAGitRepositoryError(GitPilotError):
    """Raised when an operation targets a directory that is not inside a Git repository."""

    def __init__(self, path: str, message: str | None = None):
        self.path = path
        if message is None:
            message = f"Path '{path}' is not inside a Git repository."
        super().__init__(message)


class BranchNotFoundError(GitPilotError):
    """Raised when a specified branch does not exist."""

    def __init__(self, branch_name: str, message: str | None = None):
        self.branch_name = branch_name
        if message is None:
            message = f"Branch '{branch_name}' not found."
        super().__init__(message)


class BranchAlreadyExistsError(GitPilotError):
    """Raised when attempting to create a branch that already exists."""

    def __init__(self, branch_name: str, message: str | None = None):
        self.branch_name = branch_name
        if message is None:
            message = f"A branch named '{branch_name}' already exists."
        super().__init__(message)


class InvalidBranchNameError(GitPilotError):
    """Raised when a branch name is invalid according to Git ref rules."""

    def __init__(self, branch_name: str, message: str | None = None):
        self.branch_name = branch_name
        if message is None:
            message = f"'{branch_name}' is not a valid branch name."
        super().__init__(message)


class DirtyWorkingTreeError(GitPilotError):
    """Raised when a branch switch fails because local uncommitted changes would conflict."""

    def __init__(
        self,
        message: str = "Cannot switch branches: local uncommitted changes would be overwritten.",
        detail: str | None = None,
    ):
        self.detail = detail
        if detail:
            message = f"{message}\n{detail}"
        super().__init__(message)

