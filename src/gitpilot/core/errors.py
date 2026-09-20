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



class InvalidPathError(GitPilotError):
    """Raised when a file path supplied for a staging operation is empty or unusable."""

    def __init__(self, message: str = "A non-empty file path is required."):
        super().__init__(message)


class StageOperationError(GitPilotError):
    """Raised when staging or unstaging files fails for a reason other than an invalid path."""

    def __init__(
        self,
        paths: Sequence[str],
        message: str = "Unable to update the staging area for the requested files.",
        detail: str | None = None,
    ):
        self.paths = list(paths)
        self.detail = detail
        if detail:
            message = f"{message} {detail}"
        super().__init__(message)


class InvalidCommitMessageError(GitPilotError):
    """Raised when a commit message is empty, blank, or otherwise rejected before Git runs."""

    def __init__(self, message: str = "A commit message is required and cannot be empty."):
        super().__init__(message)


class NothingToCommitError(GitPilotError):
    """Raised when a commit is requested but there are no staged changes to record."""

    def __init__(self, message: str = "Nothing to commit: the staging area is empty."):
        super().__init__(message)


class NoRemoteError(GitPilotError):
    """Raised when a remote operation is requested but the repository has no configured remotes."""

    def __init__(self, message: str = "This repository has no configured remotes."):
        super().__init__(message)


class RemoteNotFoundError(GitPilotError):
    """Raised when a named remote does not exist in the repository."""

    def __init__(self, remote_name: str, message: str | None = None):
        self.remote_name = remote_name
        if message is None:
            message = f"Remote '{remote_name}' is not configured in this repository."
        super().__init__(message)


class NoUpstreamError(GitPilotError):
    """Raised when an operation needs an upstream tracking branch but none is configured."""

    def __init__(self, branch: str | None = None, message: str | None = None):
        self.branch = branch
        if message is None:
            if branch:
                message = (
                    f"Branch '{branch}' has no upstream tracking branch. "
                    "Push it with an explicit remote and --set-upstream first."
                )
            else:
                message = "The current branch has no upstream tracking branch."
        super().__init__(message)


class RemoteOperationError(GitPilotError):
    """Raised when a fetch, pull, or push fails for a non-specific reason."""

    def __init__(self, operation: str, message: str | None = None, detail: str | None = None):
        self.operation = operation
        self.detail = detail
        if message is None:
            message = f"Git could not complete the {operation} operation."
        if detail:
            message = message + "\n" + detail
        super().__init__(message)


class PushRejectedError(GitPilotError):
    """Raised when a push is rejected, typically because the remote has newer commits."""

    def __init__(
        self,
        message: str = (
            "Push was rejected because the remote branch contains commits you do not have "
            "locally. Fetch and integrate those commits first; GitPilot will not force-push."
        ),
        detail: str | None = None,
    ):
        self.detail = detail
        if detail:
            message = message + "\n" + detail
        super().__init__(message)


class PullConflictError(GitPilotError):
    """Raised when a pull cannot complete cleanly."""

    def __init__(
        self,
        message: str = (
            "Pull could not complete cleanly and your local changes were not discarded. "
            "Commit or stash your work, resolve any conflict, then try again."
        ),
        detail: str | None = None,
    ):
        self.detail = detail
        if detail:
            message = message + "\n" + detail
        super().__init__(message)
