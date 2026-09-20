# Development Status

## Current Milestone
Milestone 4: Workflow Engine (next — not started)

## Completed Milestones
**Milestone 1: Repository Explorer — Complete**
**Milestone 2: Repository Operations — Complete**
**Milestone 3: Remote Operations — Complete**

## Current Task
Milestone 3 verified and complete. Ready to begin Milestone 4: Workflow Engine.

## Completed
- [x] Define PRD
- [x] Create project structure
- [x] Document architecture (`docs/ARCHITECTURE.md`)
- [x] Implement Git command abstraction and safe process runner (`src/gitpilot/core/git_cli.py`)
- [x] Implement domain exceptions (`src/gitpilot/core/errors.py`)
- [x] Add Git CLI unit test suite (`tests/test_git_cli.py`)
- [x] Implement repository data models (`src/gitpilot/core/models.py`)
- [x] Implement porcelain v2 status parser (`src/gitpilot/core/parser.py`)
- [x] Add porcelain v2 parser test suite with 19 canned-output scenarios (`tests/test_parser.py`)
- [x] Implement repository detection & inspection service (`src/gitpilot/core/repository.py`)
- [x] Add integration tests with real temporary Git repositories (`tests/test_repository.py`)
- [x] Implement basic presentation / demonstration CLI harness (`src/gitpilot/cli.py`, `src/gitpilot/main.py`, `main.py`)
- [x] Add CLI harness unit and argument verification tests (`tests/test_cli.py`)
- [x] Milestone 1: Repository Explorer (Repository detection, porcelain v2 status parser, CLI harness)
- [x] Define branch domain exceptions (`BranchNotFoundError`, `BranchAlreadyExistsError`, `InvalidBranchNameError`, `DirtyWorkingTreeError`) in `src/gitpilot/core/errors.py`
- [x] Add typed `LocalBranch` model in `src/gitpilot/core/models.py`
- [x] Implement local branch listing using machine-readable format (`list_branches`) in `src/gitpilot/core/repository.py`
- [x] Implement current branch detection (`get_current_branch`) in `src/gitpilot/core/repository.py`
- [x] Implement local branch creation (`create_branch`) in `src/gitpilot/core/repository.py`
- [x] Implement safe branch switching (`switch_branch`) in `src/gitpilot/core/repository.py`
- [x] Expose branch operations on `Repository` domain abstraction
- [x] Expose minimal non-interactive CLI flags (`--branches`, `--create-branch`, `--switch-branch`) in `src/gitpilot/cli.py`
- [x] Add comprehensive branch operations integration test suite (`tests/test_branches.py`)
- [x] Define staging/commit domain exceptions (`InvalidPathError`, `StageOperationError`, `InvalidCommitMessageError`, `NothingToCommitError`) in `src/gitpilot/core/errors.py`
- [x] Add typed `CommitResult` model in `src/gitpilot/core/models.py`
- [x] Implement file staging (`stage_files`) through `run_git()` in `src/gitpilot/core/repository.py`
- [x] Implement file unstaging (`unstage_files`) using `git restore --staged` (with `git reset --` fallback) in `src/gitpilot/core/repository.py`
- [x] Implement commit creation (`create_commit`) with message validation in `src/gitpilot/core/repository.py`
- [x] Expose staging, unstaging, and commit on the `Repository` domain abstraction
- [x] Wire `--stage`, `--unstage`, and `--commit` CLI flags with domain error handling in `src/gitpilot/cli.py`
- [x] Add Commit Changes page (select/stage/unstage/commit) to the tkinter GUI in `src/gitpilot/gui/app.py`
- [x] Add staging, unstaging, and commit integration test suite (`tests/test_staging.py`)
- [x] Add CLI tests for `--stage`, `--unstage`, `--commit` and their error paths (`tests/test_cli.py`)
- [x] Add end-to-end GUI tests driving the real app against temporary repositories (`tests/test_gui.py`)
- [x] Fix missing success feedback on the GUI commit path (success dialog now matches the error path) and add a regression test for it
- [x] Fix the Commit Changes page layout so the commit-message Entry is actually visible (the expanding file list previously starved it of vertical space) and add regression tests for it
- [x] Milestone 2: Repository Operations fully verified end-to-end (branch, staging, unstaging, commit) across core, CLI, GUI, and tests
- [x] Define remote domain exceptions (`NoRemoteError`, `RemoteNotFoundError`, `NoUpstreamError`, `RemoteOperationError`, `PushRejectedError`, `PullConflictError`) in `src/gitpilot/core/errors.py`
- [x] Add typed `Remote`, `TrackingInfo`, and `SyncResult` models in `src/gitpilot/core/models.py`
- [x] Implement remote detection and inspection (`list_remotes`, `get_remote_names`, `has_remotes`, `resolve_remote_name`) using machine-readable `git remote` output
- [x] Implement upstream/ahead-behind tracking (`get_tracking_info`) reusing the porcelain v2 branch headers
- [x] Implement fetch (`fetch_remote`) through `run_git()` with no working-tree side effects
- [x] Implement fast-forward-only pull (`pull_remote`) with conflict/overwrite detection
- [x] Implement non-forcing push (`push_remote`) with non-fast-forward rejection detection
- [x] Expose all M3 operations on the `Repository` domain abstraction
- [x] Wire `--remotes`, `--fetch`, `--pull`, `--push`, and `--set-upstream` CLI flags with domain error handling
- [x] Add a Remotes page to the tkinter GUI (remote list, upstream/ahead-behind, fetch/pull/push with confirmation)
- [x] Add remote operations integration tests using local bare repositories (`tests/test_remotes.py`)
- [x] Add CLI tests for remote flags and their error paths (`tests/test_cli_remotes.py`)
- [x] Add GUI tests for the Remotes page including push/pull/fetch round-trips (`tests/test_gui_remotes.py`)
- [x] Milestone 3: Remote Operations fully verified end-to-end across core, CLI, GUI, and tests

## Next Milestone
Milestone 4: Workflow Engine (NOT STARTED)
- [ ] Define workflow structure
- [ ] Implement feature workflow
- [ ] Implement bug-fix workflow
- [ ] Implement commit workflow
- [ ] Implement synchronization workflow
## Future Milestones
Milestone 5: Task Context — persistent current task, workflow progress, task history, resume previous workflow.
Milestone 6: Git Doctor — repository diagnostics, explaining unusual states, safe recovery workflows.

## Notes
Milestones 1 (Repository Explorer), 2 (Repository Operations), and 3 (Remote Operations) are complete, with 209 passing tests across the entire test suite. The CLI provides human-readable repository inspection plus branch, staging, unstaging, commit, and remote synchronization operations for local paths, with clean error handling, strict separation from core Git logic, and full Windows console encoding compatibility.

### Milestone 2 Summary
Milestone 2 covers: branch operations (list, detect current, create, switch), staging, unstaging, and commit creation, with CLI support (`--branches`, `--create-branch`, `--switch-branch`, `--stage`, `--unstage`, `--commit`), GUI support (Overview, Commit Changes, and Branches pages), structured domain errors, and dedicated test suites (`tests/test_branches.py`, `tests/test_staging.py`, plus CLI and GUI coverage).

### Milestone 3 Summary
Milestone 3 covers: remote detection and inspection (`list_remotes`, `get_remote_names`, `has_remotes`), remote naming that never assumes `origin`, upstream/ahead-behind tracking (`get_tracking_info`), fetch, fast-forward-only pull, and non-forcing push. CLI support is provided through `--remotes`, `--fetch`, `--pull`, `--push`, and `--set-upstream`; GUI support is provided by the Remotes page. Test suites are `tests/test_remotes.py` (integration against local bare repositories), `tests/test_cli_remotes.py`, and `tests/test_gui_remotes.py`.

## Notes & Architectural Decisions
- Branch creation decision: `create_branch(path, name)` creates the branch pointing at HEAD without switching to it, maintaining single-responsibility and predictable behavior.
- Branch switching decision: `switch_branch(path, name)` uses `git switch <name>` without force flags. If local uncommitted changes conflict, it aborts without discarding user work and raises a structured `DirtyWorkingTreeError`.
- State verification: `switch_branch` verifies the active branch changed to the target before returning success.
- Staging decision: `stage_files(path, files)` accepts a single path or a sequence, normalizes `Path` objects with `as_posix()` for stable separators across platforms, and always passes `--` before paths so filenames resembling options (e.g. `-f`) are never misinterpreted by Git. Failures map to `InvalidPathError` (no usable path), `StageOperationError` (Git rejected the pathspec), or `GitCommandError` (unexpected failure).
- Unstaging decision: `unstage_files` uses `git restore --staged --`, which resets only the index entry to HEAD and never touches the working tree. A `git reset --` fallback runs only when the installed Git is too old for `restore` (Git < 2.23). No destructive flag is ever used.
- Commit decision: `create_commit` validates the message (non-empty, whitespace-only and non-string input rejected with `InvalidCommitMessageError`) before invoking Git. The `--commit` CLI flag uses an explicit `is not None` check rather than truthiness so that an empty message is still routed to validation and reported clearly instead of silently falling through to plain status output.
- Empty-autostage detection: Git reports "nothing to commit" on **stdout**, while genuine failures surface on **stderr**. `create_commit` inspects both streams so the empty-staging case maps to `NothingToCommitError` rather than leaking a raw `GitCommandError`.
- Commit subject reporting: `CommitResult.subject` is derived from the message GitPilot supplied, not from the `git commit` stdout summary line, because Git collapses a multi-line message onto one line (`[main abc1234] subject body`), which would misreport the subject.
- Safety: staging, unstaging, and commit use only non-destructive Git flags; no force, discard, or hard-reset behavior is exposed.
- Commit confirmation: `_create_commit` reports success both in the status bar and via a `Commit Created` dialog. The commit is a terminal, higher-consequence action, so it gets the same visible modal feedback the error path already had; relying on the status bar alone made a successful commit look like a no-op next to the error popups.
- Layout decision: the Commit Changes page packs its fixed-height controls (file-list actions, commit-message label/Entry, and commit row) to the bottom first, then lets the file list fill the remaining space. Packing the expanding tree first let it consume the whole page and left the commit-message Entry unmapped, so the field was invisible in a default-size window.
- Remote abstraction decision: remote names come from `git remote` and URLs from `git remote get-url`, avoiding fragile parsing of the human-formatted `git remote -v` output. Remote names are never assumed to be `origin`; any name is supported.
- Remote resolution decision: an explicitly requested remote must exist. With no explicit request, exactly one configured remote is used implicitly, while zero or several remotes raise a structured error so GitPilot never invents a remote. `resolve_remote_name` centralizes this rule for fetch, pull, and push.
- Fetch decision: `fetch_remote` runs plain `git fetch <remote>` with no merge, rebase, or prune flag, so it updates remote-tracking refs only and cannot touch the working tree.
- Pull decision: `pull_remote` uses `git pull --ff-only`, so a pull either fast-forwards or fails — it never creates a surprise merge. A branch without an upstream raises `NoUpstreamError` **before** Git runs, so GitPilot never invents upstream configuration. Conflict, overwrite, and fast-forward-impossible outcomes are mapped to `PullConflictError` rather than reported as success.
- Push decision: `push_remote` never passes a force flag, so remote history cannot be silently overwritten. A branch without an upstream raises `NoUpstreamError` unless the caller explicitly passes `set_upstream=True`, which is the only path that creates upstream configuration and is always an explicit user choice.
- Ahead/behind decision: tracking information reuses the porcelain v2 `# branch.ab` headers already parsed by `get_state`, rather than introducing a parallel status system.
- Remote safety: GUI fetch/pull/push run through the repository layer only, and pull/push ask for confirmation first. No credentials or tokens are stored anywhere, and every remote test uses a local bare repository so the suite requires no network access.
- Total test suite count: 209 tests, all passing.

## Desktop GUI

The GitPilot desktop GUI uses Python's standard-library `tkinter` and `ttk`, so no
additional Python package is required. The GUI lives in `src/gitpilot/gui/` and
is a presentation layer over `gitpilot.core.repository.Repository`; it does not
run Git commands, parse status output, or classify Git errors itself.

Current GUI functionality includes opening a local Git repository, refreshing
repository state, and viewing overview status and changed files. On the Commit
Changes page, users can select changed files, stage or unstage them, enter a
commit message, and create a commit; successful commits and failures are both
reported with a visible dialog plus status-bar feedback. On the Branches page,
users can list local branches, create a branch without switching, and safely
switch to an existing local branch. On the Remotes page, users can inspect
configured remotes plus upstream/ahead/behind information, and fetch, pull, or
push; pull and push ask for confirmation first, and every outcome is reported
with a visible dialog plus status-bar feedback. The command-line interface
remains the default launcher.

Launch the GUI from the project root with:

```text
python main.py --gui
```

Known limitations: repository selection is session-only, history and conflict
resolution are intentionally outside the completed milestones, and GitPilot
never force-pushes or discards local changes, so diverged branches must be
resolved by the user. Tkinter must be available in the Python installation (it
is included with standard Windows Python distributions).