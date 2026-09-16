"""Safe subprocess execution wrapper for the Git CLI."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
from typing import Sequence

from gitpilot.core.errors import (
    GitCommandError,
    GitNotInstalledError,
    GitTimeoutError,
)

DEFAULT_TIMEOUT_SECONDS: float = 30.0


@dataclass(frozen=True)
class GitCommandResult:
    """Structured result of a Git command execution."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str


def is_git_installed() -> bool:
    """Check if the git executable is installed and available in PATH."""
    return shutil.which("git") is not None


def verify_git_installed() -> None:
    """
    Verify that Git is installed and available in PATH.

    Raises:
        GitNotInstalledError: If the git executable cannot be found.
    """
    if not is_git_installed():
        raise GitNotInstalledError()


def run_git(
    args: Sequence[str],
    cwd: str | Path | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> GitCommandResult:
    """
    Execute a Git command safely using subprocess without shell=True.

    Args:
        args: Sequence of arguments for Git. If 'git' is not the first element,
              it is automatically prepended.
        cwd: Working directory in which to execute the Git command.
        timeout: Maximum seconds to wait before raising GitTimeoutError.
        env: Additional or overriding environment variables.
        check: If True, raises GitCommandError when the process exits non-zero.

    Returns:
        GitCommandResult containing command args, exit_code, stdout, and stderr.

    Raises:
        GitNotInstalledError: If the git executable is missing from PATH.
        GitTimeoutError: If the command execution times out.
        GitCommandError: If check=True and exit_code != 0.
    """
    if not is_git_installed():
        raise GitNotInstalledError()

    full_command = list(args)
    if not full_command or full_command[0] != "git":
        full_command = ["git"] + full_command

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    # Ensure Git never hangs waiting for interactive terminal credentials
    merged_env["GIT_TERMINAL_PROMPT"] = "0"

    working_dir = str(cwd) if cwd is not None else None

    try:
        process = subprocess.run(
            full_command,
            cwd=working_dir,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=merged_env,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise GitNotInstalledError() from exc
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError(command=full_command, timeout=timeout) from exc

    result = GitCommandResult(
        command=full_command,
        exit_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )

    if check and process.returncode != 0:
        raise GitCommandError(
            command=full_command,
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )

    return result

