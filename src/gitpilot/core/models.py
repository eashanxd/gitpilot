"""Domain models for Git repository state."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class FileStatus(str, Enum):
    """Status of a file in the Git repository."""

    UNMODIFIED = "unmodified"
    MODIFIED = "modified"
    ADDED = "added"
    DELETED = "deleted"
    RENAMED = "renamed"
    COPIED = "copied"
    TYPE_CHANGED = "type_changed"
    UNTRACKED = "untracked"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class FileChange:
    """Represents a file change in the working tree or staging area."""

    path: str
    staged_status: FileStatus = FileStatus.UNMODIFIED
    unstaged_status: FileStatus = FileStatus.UNMODIFIED
    orig_path: Optional[str] = None

    @property
    def is_staged(self) -> bool:
        """True if the file has changes in the staging area (index vs HEAD)."""
        return self.staged_status not in (FileStatus.UNMODIFIED, FileStatus.UNTRACKED)

    @property
    def is_unstaged(self) -> bool:
        """True if the file has changes in the working tree (working tree vs index)."""
        return self.unstaged_status not in (FileStatus.UNMODIFIED, FileStatus.UNTRACKED)

    @property
    def is_untracked(self) -> bool:
        """True if the file is untracked."""
        return self.staged_status == FileStatus.UNTRACKED or self.unstaged_status == FileStatus.UNTRACKED

    @property
    def is_conflict(self) -> bool:
        """True if the file is in an unmerged conflict state."""
        return self.staged_status == FileStatus.CONFLICT or self.unstaged_status == FileStatus.CONFLICT


@dataclass(frozen=True)
class BranchInfo:
    """Information about the currently active branch or HEAD state."""

    name: Optional[str] = None
    oid: Optional[str] = None
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    is_detached: bool = False
    is_initial: bool = False

    @property
    def has_upstream(self) -> bool:
        """True if the branch tracks an upstream remote branch."""
        return self.upstream is not None


@dataclass
class RepositoryState:
    """Aggregated state of a Git repository."""

    root_path: Optional[Path] = None
    branch: BranchInfo = field(default_factory=BranchInfo)
    staged_files: list[FileChange] = field(default_factory=list)
    unstaged_files: list[FileChange] = field(default_factory=list)
    untracked_files: list[FileChange] = field(default_factory=list)
    conflicted_files: list[FileChange] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        """True if working tree and staging area have no modifications, untracked files, or conflicts."""
        return not (
            self.staged_files
            or self.unstaged_files
            or self.untracked_files
            or self.conflicted_files
        )

    @property
    def has_conflicts(self) -> bool:
        """True if there are any unmerged conflicts."""
        return bool(self.conflicted_files)

    @property
    def all_changes(self) -> list[FileChange]:
        """Return a deduplicated list of all file changes in this state."""
        seen: set[str] = set()
        result: list[FileChange] = []
        for change in (
            self.staged_files
            + self.unstaged_files
            + self.untracked_files
            + self.conflicted_files
        ):
            if change.path not in seen:
                seen.add(change.path)
                result.append(change)
        return result


@dataclass(frozen=True)
class LocalBranch:
    """Information about a local Git branch."""

    name: str
    is_current: bool = False
    oid: Optional[str] = None



@dataclass(frozen=True)
class CommitResult:
    """Information about a commit that was just created."""

    oid: str
    short_oid: str
    subject: str
    branch: Optional[str] = None


@dataclass(frozen=True)
class Remote:
    """A configured Git remote with its fetch and push URLs."""

    name: str
    fetch_url: Optional[str] = None
    push_url: Optional[str] = None

    @property
    def url(self) -> Optional[str]:
        """Return the fetch URL, which is the usual meaning of 'the remote URL'."""
        return self.fetch_url


@dataclass(frozen=True)
class TrackingInfo:
    """Upstream tracking relationship for the current branch."""

    branch: Optional[str] = None
    upstream: Optional[str] = None
    remote_name: Optional[str] = None
    remote_branch: Optional[str] = None
    ahead: int = 0
    behind: int = 0

    @property
    def has_upstream(self) -> bool:
        """True if an upstream tracking branch is configured."""
        return self.upstream is not None


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a fetch, pull, or push operation."""

    operation: str
    remote_name: Optional[str] = None
    branch: Optional[str] = None
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    detail: str = ""

    @property
    def is_up_to_date(self) -> bool:
        """True when the local branch is neither ahead of nor behind its upstream."""
        return self.ahead == 0 and self.behind == 0
