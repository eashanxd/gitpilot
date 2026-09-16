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

