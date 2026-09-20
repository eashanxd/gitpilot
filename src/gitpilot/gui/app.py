"""Tkinter desktop presentation for GitPilot."""

from __future__ import annotations

import logging
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gitpilot.core.errors import GitPilotError
from gitpilot.core.models import FileChange, FileStatus, RepositoryState, SyncResult
from gitpilot.core.repository import Repository

LOGGER = logging.getLogger(__name__)

_STATUS_LETTERS: dict[FileStatus, str] = {
    FileStatus.MODIFIED: "M",
    FileStatus.ADDED: "A",
    FileStatus.DELETED: "D",
    FileStatus.RENAMED: "R",
    FileStatus.COPIED: "C",
    FileStatus.TYPE_CHANGED: "T",
    FileStatus.UNTRACKED: "?",
    FileStatus.CONFLICT: "U",
}


def _status_letter(status: FileStatus) -> str:
    return _STATUS_LETTERS.get(status, " ")


def format_change_status(change: FileChange) -> str:
    """Return a compact two-column status code for a file change."""
    if change.is_conflict:
        return "UU"
    if change.is_untracked:
        return "??"
    return f"{_status_letter(change.staged_status)}{_status_letter(change.unstaged_status)}"


def branch_display_name(state: RepositoryState) -> str:
    """Return a user-facing label for the current HEAD state."""
    if state.branch.is_detached:
        oid = state.branch.oid[:7] if state.branch.oid else "unknown"
        return f"detached at {oid}"
    return state.branch.name or "unknown"


class GitPilotApp:
    """Desktop application that presents the core Repository abstraction."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.repository: Repository | None = None
        self.state: RepositoryState | None = None
        self.page_frames: dict[str, ttk.Frame] = {}
        self.navigation_buttons: dict[str, ttk.Button] = {}
        self.current_page = "overview"

        self.root.title("GitPilot")
        self.root.geometry("1050x680")
        self.root.minsize(800, 520)
        self._build_style()
        self._build_layout()
        self._show_page("overview")

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.colors = {
            "background": "#0F1115",
            "sidebar": "#151922",
            "panel": "#1B202B",
            "border": "#2A3040",
            "text": "#F1F5F9",
            "secondary": "#AAB4C3",
            "muted": "#8793A5",
            "accent": "#6EA8FE",
            "accent_dark": "#2D5E9E",
            "hover": "#242B38",
            "input": "#181D27",
            "success": "#5CCB8A",
            "warning": "#E8B86D",
            "error": "#F07070",
        }
        self.root.configure(background=self.colors["background"])
        style.configure(".", background=self.colors["background"], foreground=self.colors["text"], font=("Segoe UI", 10))
        style.configure("TFrame", background=self.colors["background"])
        style.configure("TLabel", background=self.colors["background"], foreground=self.colors["text"])
        style.configure("HeaderTitle.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Segoe UI", 21, "bold"))
        style.configure("HeaderPath.TLabel", background=self.colors["panel"], foreground=self.colors["muted"])
        style.configure("Title.TLabel", font=("Segoe UI", 21, "bold"), foreground=self.colors["text"])
        style.configure("PageTitle.TLabel", font=("Segoe UI", 18, "bold"), foreground=self.colors["text"])
        style.configure("Muted.TLabel", foreground=self.colors["muted"])
        style.configure("MetricValue.TLabel", font=("Segoe UI", 18, "bold"), foreground=self.colors["text"])
        style.configure("MetricLabel.TLabel", foreground=self.colors["secondary"])
        style.configure("DetailValue.TLabel", font=("Segoe UI", 11, "bold"), foreground=self.colors["text"])
        style.configure("Section.TLabel", font=("Segoe UI", 12, "bold"), foreground=self.colors["text"])
        style.configure("Panel.TFrame", background=self.colors["panel"])
        style.configure("StatusClean.TLabel", background=self.colors["panel"], foreground=self.colors["success"], font=("Segoe UI", 11, "bold"))
        style.configure("StatusDirty.TLabel", background=self.colors["panel"], foreground=self.colors["warning"], font=("Segoe UI", 11, "bold"))
        style.configure("Header.TFrame", background=self.colors["panel"])
        style.configure("Sidebar.TFrame", background=self.colors["sidebar"])
        style.configure("Sidebar.TLabel", background=self.colors["sidebar"], foreground=self.colors["secondary"])
        style.configure("Sidebar.TButton", background=self.colors["sidebar"], foreground=self.colors["secondary"], anchor="w", padding=(14, 10), borderwidth=0)
        style.map("Sidebar.TButton", background=[("active", self.colors["hover"]), ("pressed", self.colors["hover"])], foreground=[("active", self.colors["text"])])
        style.configure("SidebarActive.TButton", background=self.colors["accent_dark"], foreground=self.colors["text"], anchor="w", padding=(14, 10), borderwidth=0)
        style.map("SidebarActive.TButton", background=[("active", self.colors["accent_dark"]), ("pressed", self.colors["accent_dark"])], foreground=[("active", self.colors["text"])])
        style.configure("TButton", background=self.colors["panel"], foreground=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=(13, 7), font=("Segoe UI", 10, "bold"))
        style.map("TButton", background=[("disabled", self.colors["input"]), ("pressed", self.colors["accent_dark"]), ("active", self.colors["hover"])], foreground=[("disabled", self.colors["muted"])])
        style.configure("TEntry", fieldbackground=self.colors["input"], foreground=self.colors["text"], insertcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["accent"], darkcolor=self.colors["border"], padding=(9, 7))
        style.configure("Treeview", background=self.colors["input"], fieldbackground=self.colors["input"], foreground=self.colors["text"], bordercolor=self.colors["border"], rowheight=29)
        style.map("Treeview", background=[("selected", self.colors["accent_dark"])], foreground=[("selected", self.colors["text"])])
        style.configure("Treeview.Heading", background=self.colors["panel"], foreground=self.colors["secondary"], bordercolor=self.colors["border"], padding=(8, 7), font=("Segoe UI", 10, "bold"))
        style.map("Treeview.Heading", background=[("active", self.colors["hover"])])
        style.configure("Status.TLabel", background=self.colors["panel"], foreground=self.colors["secondary"])
        style.configure("SuccessStatus.TLabel", background="#173326", foreground=self.colors["success"])
        style.configure("ErrorStatus.TLabel", background="#3A2025", foreground=self.colors["error"])
        style.configure("WarningStatus.TLabel", background="#3A3020", foreground=self.colors["warning"])

    def _build_layout(self) -> None:
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(22, 16, 22, 12))
        header.pack(fill="x")
        ttk.Label(header, text="GitPilot", style="HeaderTitle.TLabel").pack(side="left")
        self.path_var = tk.StringVar(value="No repository selected")
        ttk.Label(header, textvariable=self.path_var, style="HeaderPath.TLabel").pack(side="left", padx=(18, 0))
        ttk.Button(header, text="Open Repository", command=self._open_repository).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Refresh", command=self._refresh).pack(side="right")

        ttk.Separator(self.root).pack(fill="x")
        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)

        sidebar = ttk.Frame(body, style="Sidebar.TFrame", width=190, padding=(8, 18))
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        ttk.Label(sidebar, text="WORKSPACE", style="Sidebar.TLabel", padding=(14, 8)).pack(fill="x")
        for key, label in (("overview", "Home  Overview"), ("changes", "Commit Changes"), ("branches", "Branches"), ("remotes", "Remotes")):
            button = ttk.Button(sidebar, text=label, style="Sidebar.TButton", command=lambda page=key: self._show_page(page))
            button.pack(fill="x", pady=2)
            self.navigation_buttons[key] = button

        self.content = ttk.Frame(body, padding=(28, 24))
        self.content.pack(side="left", fill="both", expand=True)
        self._build_overview()
        self._build_changes()
        self._build_branches()
        self._build_remotes()
        self.message_var = tk.StringVar()
        self.message_label = ttk.Label(self.root, textvariable=self.message_var, style="Status.TLabel", anchor="w", padding=(12, 7))
        self.message_label.pack(fill="x", side="bottom")

    def _build_overview(self) -> None:
        frame = ttk.Frame(self.content)
        self.page_frames["overview"] = frame
        ttk.Label(frame, text="Overview", style="PageTitle.TLabel").pack(anchor="w")
        self.overview_hint = ttk.Label(frame, text="Open a Git repository to inspect its current state.", style="Muted.TLabel")
        self.overview_hint.pack(anchor="w", pady=(4, 20))

        details = ttk.Frame(frame, style="Panel.TFrame", padding=(16, 14, 16, 4))
        details.pack(fill="x")
        self.repository_value = self._detail(details, "Repository", 0, 0)
        self.branch_value = self._detail(details, "Branch", 0, 1)
        self.upstream_value = self._detail(details, "Upstream", 1, 0)
        self.status_value = self._detail(details, "Status", 1, 1)

        self.metric_values: dict[str, ttk.Label] = {}
        metrics = ttk.Frame(frame, style="Panel.TFrame", padding=(16, 14))
        metrics.pack(fill="x", pady=(18, 22))
        for index, (key, label) in enumerate((("ahead", "Ahead"), ("behind", "Behind"), ("staged", "Staged"), ("unstaged", "Unstaged"), ("untracked", "Untracked"), ("conflicts", "Conflicts"))):
            cell = ttk.Frame(metrics, style="Panel.TFrame", padding=(0, 0, 24, 0))
            cell.grid(row=0, column=index, sticky="w")
            value = ttk.Label(cell, text="-", style="MetricValue.TLabel")
            value.pack(anchor="w")
            ttk.Label(cell, text=label, style="MetricLabel.TLabel").pack(anchor="w")
            self.metric_values[key] = value

        ttk.Label(frame, text="Changed Files", style="Section.TLabel").pack(anchor="w", pady=(2, 8))
        self.changes_tree = ttk.Treeview(frame, columns=("status", "path"), show="headings", height=14)
        self.changes_tree.heading("status", text="Status")
        self.changes_tree.heading("path", text="Path")
        self.changes_tree.column("status", width=75, anchor="center", stretch=False)
        self.changes_tree.column("path", width=650, anchor="w")
        self.changes_tree.pack(fill="both", expand=True)

    def _build_changes(self) -> None:
        frame = ttk.Frame(self.content)
        self.page_frames["changes"] = frame
        ttk.Label(frame, text="Commit Changes", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Select changed files to stage or unstage, then describe and create your commit.", style="Muted.TLabel").pack(anchor="w", pady=(4, 18))

        # The fixed-height controls (commit message + command row) are packed to the
        # bottom of the page FIRST, then the file list fills whatever height remains.
        # Packing the expanding tree first would let it consume the whole page and
        # leave the commit-message field unmapped (invisible) in a default-size window.
        commit_row = ttk.Frame(frame)
        commit_row.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(commit_row, text="Create Commit", command=self._create_commit).pack(side="left")
        self.staged_hint = ttk.Label(commit_row, text="", style="Muted.TLabel")
        self.staged_hint.pack(side="left", padx=(12, 0))

        ttk.Label(frame, text="Commit message:", style="Section.TLabel").pack(side="bottom", anchor="w", pady=(18, 8))
        self.commit_message_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.commit_message_var, width=80).pack(side="bottom", fill="x")

        actions = ttk.Frame(frame)
        actions.pack(side="bottom", fill="x", pady=(12, 0))
        ttk.Button(actions, text="Stage Selected", command=self._stage_selected).pack(side="left")
        ttk.Button(actions, text="Unstage Selected", command=self._unstage_selected).pack(side="left", padx=(8, 0))
        self.commit_hint = ttk.Label(actions, text="", style="Muted.TLabel")
        self.commit_hint.pack(side="left", padx=(12, 0))

        # The file list is packed last so it absorbs only the leftover vertical space.
        self.commit_tree = ttk.Treeview(frame, columns=("status", "path"), show="headings", height=13, selectmode="extended")
        self.commit_tree.heading("status", text="Status")
        self.commit_tree.heading("path", text="Path")
        self.commit_tree.column("status", width=75, anchor="center", stretch=False)
        self.commit_tree.column("path", width=650, anchor="w")
        self.commit_tree.pack(fill="both", expand=True)

    def _detail(self, parent: ttk.Frame, label: str, row: int, column: int) -> ttk.Label:
        cell = ttk.Frame(parent, style="Panel.TFrame", padding=(0, 0, 45, 10))
        cell.grid(row=row, column=column, sticky="w")
        ttk.Label(cell, text=label, style="DetailLabel.TLabel").pack(anchor="w")
        value = ttk.Label(cell, text="-", style="DetailValue.TLabel")
        value.pack(anchor="w", pady=(3, 0))
        return value

    def _build_branches(self) -> None:
        frame = ttk.Frame(self.content)
        self.page_frames["branches"] = frame
        ttk.Label(frame, text="Branches", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Create a branch or switch safely to an existing local branch.", style="Muted.TLabel").pack(anchor="w", pady=(4, 18))

        create_row = ttk.Frame(frame)
        create_row.pack(fill="x", pady=(0, 16))
        self.branch_name_var = tk.StringVar()
        entry = ttk.Entry(create_row, textvariable=self.branch_name_var, width=42)
        entry.pack(side="left")
        ttk.Button(create_row, text="Create Branch", command=self._create_branch).pack(side="left", padx=(8, 0))

        self.branches_tree = ttk.Treeview(frame, columns=("current", "name"), show="headings", height=16, selectmode="browse")
        self.branches_tree.heading("current", text="")
        self.branches_tree.heading("name", text="Local branch")
        self.branches_tree.column("current", width=45, anchor="center", stretch=False)
        self.branches_tree.column("name", width=650, anchor="w")
        self.branches_tree.pack(fill="both", expand=True)
        switch_row = ttk.Frame(frame)
        switch_row.pack(fill="x", pady=(12, 0))
        ttk.Button(switch_row, text="Switch to Selected Branch", command=self._switch_branch).pack(side="left")
        self.branch_hint = ttk.Label(switch_row, text="", style="Muted.TLabel")
        self.branch_hint.pack(side="left", padx=(12, 0))

    def _show_page(self, page: str) -> None:
        for frame in self.page_frames.values():
            frame.pack_forget()
        self.page_frames[page].pack(fill="both", expand=True)
        self.current_page = page
        for key, button in self.navigation_buttons.items():
            button.configure(style="SidebarActive.TButton" if key == page else "Sidebar.TButton")

    def _open_repository(self) -> None:
        selected = filedialog.askdirectory(title="Open Git Repository")
        if selected:
            self._load_repository(Path(selected))

    def _load_repository(self, path: Path) -> None:
        try:
            self.repository = Repository(path)
            self.path_var.set(str(self.repository.root))
            self._refresh()
            self._show_page("overview")
            self._set_message(f"Loaded repository: {self.repository.root}", "success")
        except Exception as exc:
            self._handle_error(exc, "Unable to open repository")

    def _refresh(self) -> None:
        if self.repository is None:
            self._set_message("Open a Git repository to begin.")
            return
        try:
            self.state = self.repository.get_state()
            self._render_overview(self.state)
            self._render_changes(self.state)
            self._render_branches()
            self._render_remotes()
            self._set_message("Repository refreshed.")
        except Exception as exc:
            self._handle_error(exc, "Unable to refresh repository")

    def _render_overview(self, state: RepositoryState) -> None:
        self.overview_hint.configure(text="Working tree is clean." if state.is_clean else "Working tree has changes.")
        self.repository_value.configure(text=str(state.root_path or self.repository.root))
        self.branch_value.configure(text=branch_display_name(state))
        self.upstream_value.configure(text=state.branch.upstream or "None")
        self.status_value.configure(text="Clean" if state.is_clean else "Dirty", style="StatusClean.TLabel" if state.is_clean else "StatusDirty.TLabel")
        counts = {
            "ahead": state.branch.ahead,
            "behind": state.branch.behind,
            "staged": len(state.staged_files),
            "unstaged": len(state.unstaged_files),
            "untracked": len(state.untracked_files),
            "conflicts": len(state.conflicted_files),
        }
        for key, value in counts.items():
            self.metric_values[key].configure(text=str(value))
        for item in self.changes_tree.get_children():
            self.changes_tree.delete(item)
        for change in state.all_changes:
            self.changes_tree.insert("", "end", values=(format_change_status(change), change.path))

    def _render_changes(self, state: RepositoryState) -> None:
        for item in self.commit_tree.get_children():
            self.commit_tree.delete(item)
        for change in state.all_changes:
            self.commit_tree.insert("", "end", iid=change.path, values=(format_change_status(change), change.path))
        self.staged_hint.configure(text=f"Staged files: {len(state.staged_files)}")
        self.commit_hint.configure(
            text="Working tree is clean." if state.is_clean else "Select one or more files above."
        )

    def _selected_change_paths(self) -> list[str]:
        return list(self.commit_tree.selection())

    def _stage_selected(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before staging files.", "warning")
            return
        paths = self._selected_change_paths()
        if not paths:
            messagebox.showinfo("Stage Files", "Select one or more changed files first.")
            return
        try:
            staged = self.repository.stage_files(paths)
            self._refresh()
            self._show_page("changes")
            self._set_message(f"Staged {len(staged)} file(s).", "success")
        except Exception as exc:
            self._handle_error(exc, "Unable to stage files")

    def _unstage_selected(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before unstaging files.", "warning")
            return
        paths = self._selected_change_paths()
        if not paths:
            messagebox.showinfo("Unstage Files", "Select one or more changed files first.")
            return
        try:
            unstaged = self.repository.unstage_files(paths)
            self._refresh()
            self._show_page("changes")
            self._set_message(f"Unstaged {len(unstaged)} file(s). Working-tree changes were kept.", "success")
        except Exception as exc:
            self._handle_error(exc, "Unable to unstage files")

    def _create_commit(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before creating a commit.", "warning")
            return
        try:
            commit = self.repository.create_commit(self.commit_message_var.get())
            self.commit_message_var.set("")
            self._refresh()
            self._show_page("changes")
            location = commit.branch or commit.short_oid
            summary = f"Committed to {location}: {commit.subject}"
            self._set_message(summary, "success")
            # The commit itself is a terminal, higher-consequence action, so confirm it
            # with the same modal feedback the error path uses rather than relying only
            # on the status bar (which is easy to miss and gets overwritten on refresh).
            messagebox.showinfo("Commit Created", f"{summary}\n\nCommit: {commit.short_oid}")
        except Exception as exc:
            self._handle_error(exc, "Unable to create commit")

    def _render_branches(self) -> None:
        if self.repository is None:
            return
        try:
            branches = self.repository.list_branches()
        except Exception as exc:
            self._handle_error(exc, "Unable to load branches")
            return
        for item in self.branches_tree.get_children():
            self.branches_tree.delete(item)
        for branch in branches:
            self.branches_tree.insert("", "end", iid=branch.name, values=("*" if branch.is_current else "", branch.name))
        current = next((branch.name for branch in branches if branch.is_current), None)
        self.branch_hint.configure(text=f"Current branch: {current or 'detached HEAD'}")

    def _create_branch(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before creating a branch.", "warning")
            return
        name = self.branch_name_var.get().strip()
        try:
            created = self.repository.create_branch(name)
            self.branch_name_var.set("")
            self._refresh()
            self._show_page("branches")
            self._set_message(f"Created branch '{created.name}'. The current branch was not changed.", "success")
        except Exception as exc:
            self._handle_error(exc, "Unable to create branch")

    def _switch_branch(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before switching branches.", "warning")
            return
        selection = self.branches_tree.selection()
        if not selection:
            messagebox.showinfo("Switch Branch", "Select a local branch first.")
            return
        name = selection[0]
        try:
            switched = self.repository.switch_branch(name)
            self._refresh()
            self._show_page("overview")
            self._set_message(f"Switched to branch '{switched.name}'.", "success")
        except Exception as exc:
            self._handle_error(exc, "Unable to switch branch")

    def _build_remotes(self) -> None:
        frame = ttk.Frame(self.content)
        self.page_frames["remotes"] = frame
        ttk.Label(frame, text="Remotes", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            frame,
            text="Inspect configured remotes and synchronize the current branch.",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(4, 18))

        details = ttk.Frame(frame, style="Panel.TFrame", padding=(16, 14, 16, 4))
        details.pack(fill="x")
        self.remote_branch_value = self._detail(details, "Branch", 0, 0)
        self.remote_upstream_value = self._detail(details, "Upstream", 0, 1)
        self.remote_ahead_value = self._detail(details, "Ahead", 1, 0)
        self.remote_behind_value = self._detail(details, "Behind", 1, 1)

        ttk.Label(frame, text="Configured Remotes", style="Section.TLabel").pack(anchor="w", pady=(18, 8))
        self.remotes_tree = ttk.Treeview(
            frame, columns=("name", "fetch", "push"), show="headings", height=7, selectmode="browse"
        )
        self.remotes_tree.heading("name", text="Name")
        self.remotes_tree.heading("fetch", text="Fetch URL")
        self.remotes_tree.heading("push", text="Push URL")
        self.remotes_tree.column("name", width=140, anchor="w", stretch=False)
        self.remotes_tree.column("fetch", width=340, anchor="w")
        self.remotes_tree.column("push", width=340, anchor="w")
        self.remotes_tree.pack(fill="x")

        ttk.Label(frame, text="Synchronize", style="Section.TLabel").pack(anchor="w", pady=(18, 8))
        sync_row = ttk.Frame(frame)
        sync_row.pack(fill="x")
        ttk.Button(sync_row, text="Fetch", command=self._fetch_remote).pack(side="left")
        ttk.Button(sync_row, text="Pull", command=self._pull_remote).pack(side="left", padx=(8, 0))
        ttk.Button(sync_row, text="Push", command=self._push_remote).pack(side="left", padx=(8, 0))
        self.remote_hint = ttk.Label(sync_row, text="", style="Muted.TLabel")
        self.remote_hint.pack(side="left", padx=(12, 0))

    def _selected_remote_name(self) -> str | None:
        """Return the remote selected in the tree, or None to let the repository decide."""
        selection = self.remotes_tree.selection()
        return selection[0] if selection else None

    def _render_remotes(self) -> None:
        if self.repository is None:
            return
        try:
            remotes = self.repository.list_remotes()
            tracking = self.repository.get_tracking_info()
        except Exception as exc:
            self._handle_error(exc, "Unable to load remote information")
            return

        for item in self.remotes_tree.get_children():
            self.remotes_tree.delete(item)
        for remote in remotes:
            self.remotes_tree.insert(
                "", "end", iid=remote.name,
                values=(remote.name, remote.fetch_url or "", remote.push_url or ""),
            )

        self.remote_branch_value.configure(text=tracking.branch or "(detached)")
        self.remote_upstream_value.configure(text=tracking.upstream or "None")
        self.remote_ahead_value.configure(text=str(tracking.ahead))
        self.remote_behind_value.configure(text=str(tracking.behind))

        if not remotes:
            self.remote_hint.configure(text="No remotes configured.")
        elif tracking.upstream:
            self.remote_hint.configure(
                text=f"Tracking {tracking.upstream} (ahead {tracking.ahead}, behind {tracking.behind})."
            )
        else:
            self.remote_hint.configure(text="No upstream tracking branch configured for this branch.")

    def _confirm_remote_action(self, title: str, message: str) -> bool:
        """Ask for confirmation before a higher-consequence sync operation."""
        return messagebox.askyesno(title, message)

    def _finish_remote_action(self, result: SyncResult, verb: str) -> None:
        self._refresh()
        self._show_page("remotes")
        summary = f"{verb} '{result.remote_name}'."
        if result.upstream:
            summary += f" Ahead {result.ahead}, behind {result.behind}."
        self._set_message(summary, "success")
        messagebox.showinfo(verb.capitalize(), summary)

    def _fetch_remote(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before fetching.", "warning")
            return
        try:
            result = self.repository.fetch(self._selected_remote_name())
            self._finish_remote_action(result, "Fetched from")
        except Exception as exc:
            self._handle_error(exc, "Unable to fetch")

    def _pull_remote(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before pulling.", "warning")
            return
        if not self._confirm_remote_action(
            "Pull",
            "Pull the current branch from its upstream?\n\n"
            "GitPilot only fast-forwards and never discards your local changes.",
        ):
            return
        try:
            result = self.repository.pull(self._selected_remote_name())
            self._finish_remote_action(result, "Pulled from")
        except Exception as exc:
            self._handle_error(exc, "Unable to pull")

    def _push_remote(self) -> None:
        if self.repository is None:
            self._set_message("Open a repository before pushing.", "warning")
            return
        if not self._confirm_remote_action(
            "Push",
            "Push the current branch to the selected remote?\n\n"
            "GitPilot never force-pushes and will not overwrite remote history.",
        ):
            return
        try:
            result = self.repository.push(self._selected_remote_name())
            self._finish_remote_action(result, "Pushed to")
        except Exception as exc:
            self._handle_error(exc, "Unable to push")

    def _handle_error(self, exc: Exception, context: str) -> None:
        if isinstance(exc, GitPilotError):
            message = str(exc)
        elif isinstance(exc, FileNotFoundError):
            message = str(exc)
        else:
            LOGGER.exception("Unexpected GUI error")
            message = "An unexpected error occurred. See the application log for details."
        self._set_message(f"{context}: {message.splitlines()[0]}", "error")
        messagebox.showerror(context, message)

    def _set_message(self, message: str, kind: str = "neutral") -> None:
        """Show feedback using a readable semantic status style."""
        styles = {
            "neutral": "Status.TLabel",
            "success": "SuccessStatus.TLabel",
            "warning": "WarningStatus.TLabel",
            "error": "ErrorStatus.TLabel",
        }
        self.message_var.set(message)
        self.message_label.configure(style=styles.get(kind, styles["neutral"]))


def main() -> None:
    """Launch the GitPilot desktop application."""
    root = tk.Tk()
    GitPilotApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
