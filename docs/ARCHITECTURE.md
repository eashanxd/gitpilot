# GitPilot Architecture

**Version:** 0.1  
**Status:** Approved for Milestone 1  
**Scope:** Milestone 1 (Repository Explorer) & Core Foundations  

---

## 1. Architectural Principles

1. **UI-Agnostic Core:**  
   The domain and repository logic in `gitpilot.core` must never depend on any specific presentation layer (CLI, TUI, or GUI). The presentation layer is strictly a consumer of core data models and service methods. The minimal CLI implemented in Milestone 1 is a demonstration and testing harness, not the permanent interface.

2. **Simplicity & Directness:**  
   Avoid speculative abstractions, over-generalized design patterns, and excessive layers. Every module must correspond directly to a concrete responsibility of the current milestone.

3. **Predictable & Explainable Operations:**  
   Git operations are routed through a centralized command execution layer that can log, explain, and verify actions rather than scattering `subprocess` invocations.

4. **Structured, Strongly Typed State:**  
   Repository inspection returns strongly typed, immutable dataclasses (`RepositoryState`, `FileChange`, `BranchInfo`) rather than raw text dictionaries or ad-hoc tuples.

5. **Zero External Dependency Default:**  
   Core functionality relies exclusively on the Python standard library (`subprocess`, `pathlib`, `dataclasses`, `enum`, `typing`, `logging`, `unittest`).

---

## 2. System Layer Diagram (Milestone 1)

```text
┌────────────────────────────────────────────────────────┐
│               Presentation Layer (Harness)             │
│   src/gitpilot/cli.py / main.py                        │
│   - Accepts target directory argument / cwd            │
│   - Renders formatted status to stdout                 │
└───────────────────────────┬────────────────────────────┘
                            │ Calls
                            ▼
┌────────────────────────────────────────────────────────┐
│                  Git Domain Layer                      │
│   src/gitpilot/core/repository.py                      │
│   - is_git_repository(path) -> bool                    │
│   - get_repository_root(path) -> Path                  │
│   - get_state(path) -> RepositoryState                 │
└─────────────┬────────────────────────────┬─────────────┘
              │ Uses                       │ Returns
              ▼                            ▼
┌───────────────────────────┐  ┌─────────────────────────┐
│     Porcelain Parser      │  │       Data Models       │
│  src/gitpilot/core/       │  │  src/gitpilot/core/     │
│  parser.py                │  │  models.py              │
│  - Parses porcelain v2    │  │  - RepositoryState      │
│    stdout into objects    │  │  - FileChange           │
└─────────────┬─────────────┘  │  - BranchInfo           │
              │                └─────────────────────────┘
              ▼ Uses
┌────────────────────────────────────────────────────────┐
│               Git CLI Execution Layer                  │
│   src/gitpilot/core/git_cli.py                         │
│   - verify_git_installed()                             │
│   - run_git(args, cwd, timeout) -> GitCommandResult    │
│   - Translates return codes to custom errors           │
│   src/gitpilot/core/errors.py                          │
│   - GitPilotError, NotAGitRepositoryError, etc.        │
└───────────────────────────┬────────────────────────────┘
                            │ Executes via subprocess
                            ▼
                 Operating System Git CLI
```

---

## 3. Module Responsibilities for Milestone 1

### 3.1 `src/gitpilot/core/errors.py`
Defines domain-specific exceptions to avoid leaking raw `subprocess.CalledProcessError`:
* `GitPilotError`: Base exception for all GitPilot domain errors.
* `GitNotInstalledError`: Raised when the `git` binary is not located in `PATH`.
* `NotAGitRepositoryError`: Raised when an operation targets a directory that is not inside a Git work tree.
* `GitCommandError`: Raised when a Git command fails, capturing command args, exit code, stdout, and stderr.

### 3.2 `src/gitpilot/core/git_cli.py`
Low-level process execution wrapper:
* Executes `git` commands with argument lists (never `shell=True` to eliminate shell injection vulnerabilities).
* Enforces execution timeouts to prevent hung processes.
* Sets environment variable `GIT_TERMINAL_PROMPT=0` to prevent commands from blocking on terminal credentials.
* Returns a structured `GitCommandResult` (stdout, stderr, exit_code, command).

### 3.3 `src/gitpilot/core/models.py`
Pure dataclasses representing the state of the repository:
* `FileStatus`: Enum representing change type (`MODIFIED`, `ADDED`, `DELETED`, `RENAMED`, `UNTRACKED`, `CONFLICT`).
* `FileChange`: Represents a single file change (`path`, `orig_path`, `staged_status`, `unstaged_status`).
* `BranchInfo`: Information about current branch (`name`, `oid`, `upstream`, `ahead`, `behind`, `is_detached`, `is_initial`).
* `RepositoryState`: Aggregated state (`root_path`, `branch`, `is_clean`, `staged_files`, `unstaged_files`, `untracked_files`, `conflicted_files`).

### 3.4 `src/gitpilot/core/parser.py`
Dedicated parser for `git status --porcelain=v2 --branch`:
* Parses branch metadata headers:
  * `# branch.oid <hash> | (initial)`
  * `# branch.head <branch> | (detached)`
  * `# branch.upstream <upstream>`
  * `# branch.ab +<ahead> -<behind>`
* Parses entry lines:
  * `1 <XY> ... <path>` (ordinary changed entries)
  * `2 <XY> ... <origPath> <path>` (renamed or copied entries)
  * `u <XY> ... <path>` (unmerged entries / conflicts)
  * `? <path>` (untracked files)
* Ignores `!` (ignored files) unless requested.

### 3.5 `src/gitpilot/core/repository.py`
High-level domain entry point for repository queries:
* `is_git_repository(path: Path) -> bool`
* `get_repository_root(path: Path) -> Path`
* `get_state(path: Path) -> RepositoryState`
* Orchestrates calling `git_cli` and feeding output to `parser`.

### 3.6 `src/gitpilot/cli.py` & `main.py`
Minimal presentation/demonstration harness for Milestone 1:
* Accepts an optional path argument (defaults to current working directory).
* Calls `Repository.get_state()`.
* Pretty-prints a summary of the repository status:
  * Repository root path
  * Current branch (or detached/initial indicator)
  * Upstream tracking and ahead/behind counts
  * Counts and file paths of staged, modified, untracked, and conflicting files.
* Displays user-friendly error messages if the directory is not a Git repo or Git is not installed.

---

## 4. Technical Decisions & Rationale

### 4.1 Status Source: `git status --porcelain=v2 --branch`
**Why this format is used:**
1. **Designed for machine consumption:** Unlike standard `git status`, porcelain output is guaranteed to be stable and backward/forward compatible across Git versions.
2. **Ambiguity-free relative to porcelain v1:** V1 has ambiguous whitespace handling and complex rename representation. V2 provides explicit record prefixes (`1`, `2`, `u`, `?`) and distinct octal/SHA/path fields.
3. **Single-command atomicity:** `--branch` provides commit hash, branch name, upstream name, and ahead/behind counts in the exact same call as the working tree status, avoiding multiple subprocess calls.

### 4.2 UI-Agnostic Design
All logic in `gitpilot.core` must return plain data objects or raise domain exceptions. No UI printing or interactive prompts are permitted inside `gitpilot.core`. Future interfaces (web GUI, desktop app, or rich TUI) can plug into `gitpilot.core` without refactoring the domain layer.

### 4.3 Deferred Persistence
Persistent configuration (such as `~/.gitpilot/config.json` to remember active repositories) is deferred until after the basic repository explorer is functional and verified. In Milestone 1, repository paths are supplied directly to the CLI or default to the current directory.

---

## 5. Milestone 1 Edge Cases & Prioritization

| Edge Case | Milestone Priority | Handling Strategy |
| :--- | :--- | :--- |
| Target path is not a Git repo | **Milestone 1 (High)** | `get_repository_root` fails cleanly; raises `NotAGitRepositoryError`. |
| Git binary not in `PATH` | **Milestone 1 (High)** | Check presence on startup; raises `GitNotInstalledError` with installation hint. |
| Fresh repo / initial unborn commit | **Milestone 1 (High)** | `# branch.oid (initial)` handled cleanly in `parser.py`; marked as `is_initial=True`. |
| Detached HEAD state | **Milestone 1 (High)** | `# branch.head (detached)` parsed cleanly; branch name marked as `(detached at <oid>)`. |
| Dirty working tree (staged & unstaged) | **Milestone 1 (High)** | Distinguishes staged vs. unstaged file modifications via the `XY` code. |
| Non-existent directory path | **Milestone 1 (High)** | Validates path existence before invoking Git commands. |
| Merge conflicts present | **Milestone 1 (Medium)** | `u` records parsed into `conflicted_files` list in `RepositoryState`. |
| Quoted paths / spaces in filenames | **Milestone 1 (Medium)** | Strip Git quotes / handle space-delimited paths properly in parser. |
| Remote network hang / prompts | *Milestone 3 (Deferred)* | Set `GIT_TERMINAL_PROMPT=0` proactively, but full remote handling deferred. |
| Mid-merge / mid-rebase state | *Milestone 6 (Deferred)* | Basic conflict flags handled in M1; full recovery workflows deferred. |

---

## 6. Testing Strategy for Milestone 1

1. **Unit Tests (`tests/unit/`):**
   * Mock subprocess tests for `git_cli.py` (verifying arguments, timeout, exit codes, and exceptions).
   * Pure parser tests for `parser.py` using canned porcelain v2 outputs covering clean, dirty, untracked, detached HEAD, initial commit, and merge conflict scenarios.
2. **Integration Tests (`tests/integration/`):**
   * Real Git repository tests using `tempfile.TemporaryDirectory`.
   * Initialize a test repo, create commits, modify files, and verify `repository.get_state()` against actual Git output.

