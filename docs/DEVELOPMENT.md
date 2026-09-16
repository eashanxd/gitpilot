# Development Status

## Current Milestone
Milestone 1: Repository Explorer
Milestone 2: Repository Operations

## Current Task
Milestone 1 Complete — Ready for Milestone 2
Step 1: Branch Operations Complete — Ready for Step 2: File Staging/Unstaging

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

## Next Milestone
Milestone 2: Repository Operations
- [ ] Branch creation
- [ ] Branch switching
- [ ] File staging
- [ ] File unstaging
- [ ] Commit creation
## Next
- [ ] File staging (`stage_files`)
- [ ] File unstaging (`unstage_files`)
- [ ] Commit creation (`create_commit`)

## Notes
Milestone 1 (Repository Explorer) is fully completed with 59 passing tests across the entire test suite. The CLI provides human-readable repository inspection for local paths with clean error handling, strict separation from core Git logic, and full Windows console encoding compatibility.
## Notes & Architectural Decisions
- Branch creation decision: `create_branch(path, name)` creates the branch pointing at HEAD without switching to it, maintaining single-responsibility and predictable behavior.
- Branch switching decision: `switch_branch(path, name)` uses `git switch <name>` without force flags. If local uncommitted changes conflict, it aborts without discarding user work and raises a structured `DirtyWorkingTreeError`.
- State verification: `switch_branch` verifies the active branch changed to the target before returning success.
- Total test suite count: 76 tests, all passing.

## Desktop GUI

The GitPilot desktop GUI uses Python's standard-library `tkinter` and `ttk`, so no
additional Python package is required. The GUI lives in `src/gitpilot/gui/` and
is a presentation layer over `gitpilot.core.repository.Repository`; it does not
run Git commands, parse status output, or classify Git errors itself.

Current GUI functionality includes opening a local Git repository, refreshing
repository state, viewing overview status and changed files, listing local
branches, creating a branch without switching, and safely switching to an
existing local branch. The command-line interface remains the default launcher.

Launch the GUI from the project root with:

```text
python main.py --gui
```

Known limitations: repository selection is session-only, the GUI supports only
local repositories, and staging, commits, remotes, history, and conflict
resolution are intentionally outside this foundation milestone. Tkinter must
be available in the Python installation (it is included with standard Windows
Python distributions).