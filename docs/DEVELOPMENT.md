# Development Status

## Current Milestone
Milestone 1: Repository Explorer
Milestone 2: Repository Operations

## Current Task
Milestone 2 Complete — Repository Operations (branch, staging, unstaging, commit)

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

## Next Milestone
Milestone 3: Remote Operations
- [ ] Remote detection
- [ ] Fetch
- [ ] Pull
- [ ] Push
- [ ] Ahead/behind information
## Next
- [ ] Remote detection and `git remote` inspection
- [ ] Fetch, pull, and push operations
- [ ] Ahead/behind tracking against upstream branches

## Notes
Milestone 1 (Repository Explorer) and Milestone 2 (Repository Operations) are complete, with 127 passing tests across the entire test suite. The CLI provides human-readable repository inspection plus branch, staging, unstaging, and commit operations for local paths, with clean error handling, strict separation from core Git logic, and full Windows console encoding compatibility.
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
- Total test suite count: 127 tests, all passing.

## Desktop GUI

The GitPilot desktop GUI uses Python's standard-library `tkinter` and `ttk`, so no
additional Python package is required. The GUI lives in `src/gitpilot/gui/` and
is a presentation layer over `gitpilot.core.repository.Repository`; it does not
run Git commands, parse status output, or classify Git errors itself.

Current GUI functionality includes opening a local Git repository, refreshing
repository state, viewing overview status and changed files, selecting changed
files to stage or unstage, entering a commit message and creating a commit,
listing local branches, creating a branch without switching, and safely
switching to an existing local branch. The command-line interface remains the
default launcher.

Launch the GUI from the project root with:

```text
python main.py --gui
```

Known limitations: repository selection is session-only, the GUI supports only
local repositories, and remotes, history, and conflict resolution are
intentionally outside the current milestone. Tkinter must be available in the
Python installation (it is included with standard Windows Python distributions).