"""Parser for git status --porcelain=v2 --branch machine-readable output."""

from pathlib import Path
from typing import Optional

from gitpilot.core.models import (
    BranchInfo,
    FileChange,
    FileStatus,
    RepositoryState,
)

_CHAR_TO_STATUS: dict[str, FileStatus] = {
    ".": FileStatus.UNMODIFIED,
    "M": FileStatus.MODIFIED,
    "A": FileStatus.ADDED,
    "D": FileStatus.DELETED,
    "R": FileStatus.RENAMED,
    "C": FileStatus.COPIED,
    "T": FileStatus.TYPE_CHANGED,
    "?": FileStatus.UNTRACKED,
    "u": FileStatus.CONFLICT,
    "U": FileStatus.CONFLICT,
}


def unquote_git_path(path: str) -> str:
    """
    Unquote a path string if Git enclosed it in double quotes with C-style escapes.

    Git quotes paths that contain spaces, quotes, control characters, or non-ASCII bytes
    unless core.quotePath is false.
    """
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        content = path[1:-1]
        byte_list = bytearray()
        i = 0
        n = len(content)
        while i < n:
            ch = content[i]
            if ch == "\\" and i + 1 < n:
                next_ch = content[i + 1]
                if next_ch in "01234567":
                    octal_digits: list[str] = []
                    j = i + 1
                    while j < min(i + 4, n) and content[j] in "01234567":
                        octal_digits.append(content[j])
                        j += 1
                    byte_list.append(int("".join(octal_digits), 8))
                    i = j
                elif next_ch == '"':
                    byte_list.append(ord('"'))
                    i += 2
                elif next_ch == "\\":
                    byte_list.append(ord("\\"))
                    i += 2
                elif next_ch == "a":
                    byte_list.append(7)
                    i += 2
                elif next_ch == "b":
                    byte_list.append(8)
                    i += 2
                elif next_ch == "t":
                    byte_list.append(ord("\t"))
                    i += 2
                elif next_ch == "n":
                    byte_list.append(ord("\n"))
                    i += 2
                elif next_ch == "v":
                    byte_list.append(11)
                    i += 2
                elif next_ch == "f":
                    byte_list.append(12)
                    i += 2
                elif next_ch == "r":
                    byte_list.append(ord("\r"))
                    i += 2
                else:
                    byte_list.extend(ch.encode("utf-8"))
                    i += 1
            else:
                byte_list.extend(ch.encode("utf-8"))
                i += 1
        try:
            return byte_list.decode("utf-8")
        except UnicodeDecodeError:
            return byte_list.decode("utf-8", errors="replace")
    return path


def parse_porcelain_v2(output: str, root_path: Optional[Path] = None) -> RepositoryState:
    """
    Parse the stdout of `git status --porcelain=v2 --branch` into a RepositoryState object.

    Args:
        output: Raw stdout from the Git CLI command.
        root_path: Optional repository root path to attach to the state.

    Returns:
        Structured RepositoryState containing branch metadata and categorized file changes.
    """
    branch_name: Optional[str] = None
    branch_oid: Optional[str] = None
    upstream: Optional[str] = None
    ahead: int = 0
    behind: int = 0
    is_detached: bool = False
    is_initial: bool = False

    staged_files: list[FileChange] = []
    unstaged_files: list[FileChange] = []
    untracked_files: list[FileChange] = []
    conflicted_files: list[FileChange] = []

    for raw_line in output.splitlines():
        line = raw_line.rstrip("\r\n")
        if not line:
            continue

        if line.startswith("# branch."):
            header = line[9:]
            if header.startswith("oid "):
                oid_val = header[4:].strip()
                if oid_val == "(initial)":
                    is_initial = True
                    branch_oid = None
                else:
                    branch_oid = oid_val
            elif header.startswith("head "):
                head_val = header[5:].strip()
                if head_val == "(detached)":
                    is_detached = True
                    branch_name = None
                else:
                    branch_name = head_val
            elif header.startswith("upstream "):
                upstream_val = header[9:].strip()
                upstream = upstream_val if upstream_val else None
            elif header.startswith("ab "):
                ab_tokens = header[3:].split()
                for token in ab_tokens:
                    if token.startswith("+"):
                        try:
                            ahead = int(token[1:])
                        except ValueError:
                            ahead = 0
                    elif token.startswith("-"):
                        try:
                            behind = int(token[1:])
                        except ValueError:
                            behind = 0
            continue

        record_type = line[0]

        if record_type == "1":
            # Ordinary changed entries: 1 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <path>
            parts = line.split(" ", 8)
            if len(parts) < 9:
                continue

            xy = parts[1]
            x_char = xy[0] if len(xy) > 0 else "."
            y_char = xy[1] if len(xy) > 1 else "."

            staged_status = _CHAR_TO_STATUS.get(x_char, FileStatus.MODIFIED)
            unstaged_status = _CHAR_TO_STATUS.get(y_char, FileStatus.MODIFIED)
            path = unquote_git_path(parts[8])

            change = FileChange(
                path=path,
                staged_status=staged_status,
                unstaged_status=unstaged_status,
            )

            if change.is_staged:
                staged_files.append(change)
            if change.is_unstaged:
                unstaged_files.append(change)

        elif record_type == "2":
            # Renamed or copied entries: 2 <XY> <sub> <mH> <mI> <mW> <hH> <hI> <Xscore> <path><sep><origPath>
            parts = line.split(" ", 9)
            if len(parts) < 10:
                continue

            xy = parts[1]
            x_char = xy[0] if len(xy) > 0 else "R"
            y_char = xy[1] if len(xy) > 1 else "."

            staged_status = _CHAR_TO_STATUS.get(x_char, FileStatus.RENAMED)
            unstaged_status = _CHAR_TO_STATUS.get(y_char, FileStatus.UNMODIFIED)

            paths_field = parts[9]
            path_parts = paths_field.split("\t", 1)
            path = unquote_git_path(path_parts[0])
            orig_path = unquote_git_path(path_parts[1]) if len(path_parts) > 1 else None

            change = FileChange(
                path=path,
                staged_status=staged_status,
                unstaged_status=unstaged_status,
                orig_path=orig_path,
            )

            if change.is_staged:
                staged_files.append(change)
            if change.is_unstaged:
                unstaged_files.append(change)

        elif record_type == "u":
            # Unmerged / conflicted entries: u <XY> <sub> <m1> <m2> <m3> <mW> <h1> <h2> <h3> <path>
            parts = line.split(" ", 10)
            if len(parts) < 11:
                continue

            path = unquote_git_path(parts[10])
            change = FileChange(
                path=path,
                staged_status=FileStatus.CONFLICT,
                unstaged_status=FileStatus.CONFLICT,
            )
            conflicted_files.append(change)

        elif record_type == "?":
            # Untracked entries: ? <path>
            parts = line.split(" ", 1)
            if len(parts) < 2:
                continue

            path = unquote_git_path(parts[1])
            change = FileChange(
                path=path,
                staged_status=FileStatus.UNTRACKED,
                unstaged_status=FileStatus.UNTRACKED,
            )
            untracked_files.append(change)

        elif record_type == "!":
            # Ignored entries are ignored in Milestone 1
            continue

    branch_info = BranchInfo(
        name=branch_name,
        oid=branch_oid,
        upstream=upstream,
        ahead=ahead,
        behind=behind,
        is_detached=is_detached,
        is_initial=is_initial,
    )

    return RepositoryState(
        root_path=root_path,
        branch=branch_info,
        staged_files=staged_files,
        unstaged_files=unstaged_files,
        untracked_files=untracked_files,
        conflicted_files=conflicted_files,
    )

