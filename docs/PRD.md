# GitPilot

## Product Requirements Document

**Version:** 0.1
**Status:** Initial Product Definition
**Primary Language:** Python

---

# 1. Product Overview

GitPilot is an intuitive, goal-oriented Git workflow assistant designed to help developers work with Git without requiring them to memorize or manually manage every Git command.

GitPilot sits between the user and Git:

```text
User Intent
    ↓
GitPilot
    ↓
Repository State
    ↓
Recommended Workflow
    ↓
Git Operations
    ↓
Verified Result
```

The application should focus on **helping users accomplish Git-related tasks**, rather than simply exposing Git commands through a graphical interface.

---

# 2. Problem Statement

Git is powerful but can be difficult to use, particularly when users encounter unfamiliar workflows or repository states.

Users may know what they want to accomplish:

* "I want to start working on a feature."
* "I want to upload my changes."
* "I need to update my branch."
* "I accidentally committed something."
* "I have a merge conflict."
* "What should I do next?"

However, they may not know:

* Which Git commands are required.
* Which order those commands should be executed in.
* What state their repository is currently in.
* What the consequences of a particular Git operation are.
* How to recover safely after making a mistake.

GitPilot aims to solve this by translating **user goals into understandable Git workflows**.

---

# 3. Product Vision

The core philosophy of GitPilot is:

> **Human intent → Repository understanding → Guided workflow → Git operations**

GitPilot should make Git feel less like a collection of commands and more like a set of understandable workflows.

The application should explain what is happening rather than blindly executing commands.

---

# 4. Target Users

The initial target users are:

### Primary

Beginner and intermediate developers who understand basic programming but are not completely comfortable with Git workflows.

### Secondary

Developers who know Git but want a faster visual way to inspect repository state and perform common workflows.

GitPilot is not initially intended to replace advanced Git clients for expert users.

---

# 5. Core Product Principles

## 5.1 Goal-oriented

The application should ask:

> "What are you trying to accomplish?"

rather than:

> "Which Git command do you want to run?"

---

## 5.2 Repository-aware

GitPilot should understand the current state of the repository before recommending actions.

---

## 5.3 Explainable

Important Git operations should be understandable to the user.

Where appropriate, GitPilot should show:

* What it is doing.
* Why it is doing it.
* The Git command responsible.

---

## 5.4 Safe

Potentially destructive operations must be clearly identified and confirmed.

Examples include:

* Force push
* Hard reset
* Discarding changes
* Branch deletion
* Rebase

GitPilot should never silently perform dangerous operations.

---

## 5.5 Progressive disclosure

Beginners should see simple explanations first.

Advanced Git information and commands can be revealed when the user wants more detail.

---

## 5.6 Maintainability

The application should use a modular architecture.

UI code should not contain Git implementation logic.

---

# 6. MVP Scope

The first version of GitPilot should be deliberately small.

## MVP Features

### Repository Management

* Select a local directory.
* Detect whether it is a Git repository.
* Display repository information.
* Remember the currently selected repository.

### Repository State

Display:

* Current branch.
* Modified files.
* Staged files.
* Untracked files.
* Basic commit information.
* Local/remote relationship where available.
* Ahead/behind status where available.
* Merge conflict state.

### Basic Git Operations

Users should eventually be able to:

* Create a branch.
* Switch branches.
* Stage files.
* Unstage files.
* Commit changes.
* Fetch.
* Pull.
* Push.

### Guided Workflows

Initial workflows:

1. Start a feature.
2. Fix a bug.
3. Commit changes.
4. Push changes.
5. Synchronize a branch.

---

# 7. Future Features

These are intentionally outside the initial MVP.

## Git Doctor

Analyze repository state and explain potential problems.

Example:

```text
🩺 Git Doctor

Your branch has diverged from origin.

You have:
• 2 local commits
• 3 remote commits

What would you like to do?

[Understand the problem]
[Update my branch]
[Show advanced options]
```

---

## Recovery Assistant

Help users understand and recover from common mistakes.

Examples:

* Accidental commit.
* Wrong branch.
* Accidental merge.
* Unwanted changes.
* Detached HEAD.
* Failed rebase.
* Conflicts.

Recovery actions should prioritize safety.

---

## Workflow Persistence

GitPilot should remember the user's current workflow/task.

Example:

```text
Current Task

Implement login system

Workflow:
Feature Development

Branch:
feature/login

Progress:

✓ Create branch
✓ Make changes
○ Review changes
○ Commit
○ Push
○ Pull Request
```

The task state should persist between application sessions.

---

## Learning Mode

Allow users to see the Git commands behind GitPilot's actions.

Example:

```text
GitPilot created your branch.

Command:

git switch -c feature/login

[Copy command]
[Why did GitPilot do this?]
```

This allows GitPilot to function as both a productivity tool and a Git learning tool.

---

# 8. User Experience

The primary interface should revolve around the repository's current state and the user's available actions.

Example:

```text
GitPilot

Repository
CampusLedger

Branch
feature/expense-tracker

──────────────────────────

Repository Status

🟡 4 modified files
🟢 2 commits ahead
⚪ No conflicts

──────────────────────────

What do you want to do?

🌱 Start a feature
💾 Commit changes
🔄 Sync branch
📤 Push changes
🌿 Manage branches
🆘 Something went wrong
```

The available actions should adapt to the repository state.

For example, if there are no changes, "Commit changes" should not be presented as the primary action.

---

# 9. Workflow Model

Every GitPilot workflow should follow a predictable structure.

```text
1. Understand user intent
        ↓
2. Inspect repository state
        ↓
3. Determine required actions
        ↓
4. Explain the planned workflow
        ↓
5. Ask for confirmation when necessary
        ↓
6. Execute Git operations
        ↓
7. Verify the result
        ↓
8. Update task/workflow state
```

GitPilot should verify the repository after important operations instead of assuming that a command succeeded.

---

# 10. Architecture

The initial architecture should separate concerns.

```text
┌─────────────────────────────┐
│             UI              │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│      Workflow Engine        │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│     Repository State        │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│      Git Abstraction        │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│       Git CLI / System      │
└─────────────────────────────┘
```

The exact architecture may evolve during development.

---

# 11. Python Technology Direction

Python is the primary implementation language.

Potential standard-library components:

* `pathlib` for filesystem operations.
* `subprocess` for Git CLI interaction.
* `os` for operating-system interaction.
* `shutil` for file operations.
* `json` for lightweight persistence/configuration.
* `dataclasses` for structured state.
* `logging` for diagnostics.
* `sqlite3` if persistent structured data becomes necessary.

External dependencies should be introduced only when they provide clear value.

---

# 12. Git Integration

GitPilot should initially interact with Git through the Git CLI.

A dedicated abstraction should prevent Git commands from being scattered throughout the application.

Conceptual example:

```python
class GitRepository:

    def status(self):
        ...

    def current_branch(self):
        ...

    def create_branch(self, name):
        ...

    def switch_branch(self, name):
        ...

    def stage(self, files):
        ...

    def commit(self, message):
        ...

    def push(self):
        ...

    def pull(self):
        ...
```

This is a conceptual design, not a strict implementation requirement.

---

# 13. Repository State

GitPilot should maintain a structured representation of repository state.

Conceptual model:

```python
@dataclass
class RepositoryState:
    branch: str
    modified_files: list
    staged_files: list
    untracked_files: list
    ahead: int
    behind: int
    has_conflicts: bool
```

The model can be expanded as requirements become clearer.

---

# 14. Error Handling

Git errors should not simply be dumped onto the user.

For example, instead of only displaying:

```text
fatal: not possible to fast-forward, aborting.
```

GitPilot should explain the situation:

```text
GitPilot couldn't update your branch automatically.

Your local branch and the remote branch contain
different commits.

You may need to merge or rebase the branches.

[Understand]
[Merge]
[Rebase]
```

Raw Git output may still be available through an advanced/details section.

---

# 15. Safety Requirements

GitPilot must treat destructive Git operations carefully.

Before executing operations such as:

* `git reset --hard`
* `git push --force`
* branch deletion
* discarding uncommitted changes

GitPilot should:

1. Explain what will happen.
2. Identify potentially lost work.
3. Ask for explicit confirmation.
4. Avoid performing the operation if the user cancels.

---

# 16. Testing Strategy

Testing should be part of development rather than something performed only at the end.

Tests should cover:

### Unit Tests

* Git command construction.
* Repository-state parsing.
* Workflow logic.
* Error handling.

### Integration Tests

Use temporary/test repositories to verify actual Git behavior.

Examples:

* Creating branches.
* Making commits.
* Detecting modified files.
* Detecting conflicts.
* Push/pull behavior.

### UI Testing

Where practical, verify that important workflows produce the expected UI state.

---

# 17. Development Methodology

GitPilot should be developed iteratively.

The development cycle is:

```text
Requirement
    ↓
Design
    ↓
Implementation
    ↓
Testing
    ↓
Review
    ↓
Release
    ↓
Feedback
    ↓
Next iteration
```

The project should not attempt to implement every planned feature simultaneously.

---

# 18. Initial Development Milestones

## Milestone 1: Repository Explorer

Goal:

Understand and display a local Git repository.

Tasks:

* Project setup.
* Repository selection.
* Git repository detection.
* Current branch detection.
* Basic status detection.
* Initial UI.

---

## Milestone 2: Repository Operations

Tasks:

* Branch creation.
* Branch switching.
* File staging.
* File unstaging.
* Commit creation.

---

## Milestone 3: Remote Operations

Tasks:

* Remote detection.
* Fetch.
* Pull.
* Push.
* Ahead/behind information.

---

## Milestone 4: Workflow Engine

Tasks:

* Define workflow structure.
* Implement feature workflow.
* Implement bug-fix workflow.
* Implement commit workflow.
* Implement synchronization workflow.

---

## Milestone 5: Task Context

Tasks:

* Persistent current task.
* Workflow progress.
* Task history.
* Resume previous workflow.

---

## Milestone 6: Git Doctor

Tasks:

* Repository diagnostics.
* Explain unusual repository states.
* Suggest appropriate actions.
* Safe recovery workflows.

---

# 19. Project Memory for AI Agents

GitPilot will be developed with AI coding agents.

The project should maintain a small set of documentation files that act as persistent project context.

Suggested structure:

```text
docs/
├── PRD.md
├── ARCHITECTURE.md
├── DEVELOPMENT.md
└── DECISIONS.md
```

### PRD.md

The source of truth for:

* Product vision.
* Requirements.
* Scope.
* User experience.
* Planned features.

### ARCHITECTURE.md

The source of truth for:

* System architecture.
* Modules.
* Interfaces.
* Data models.
* Technical decisions.

### DEVELOPMENT.md

The source of truth for:

* Current milestone.
* Current task.
* Completed work.
* Next tasks.
* Development instructions.

### DECISIONS.md

A record of important architectural decisions and their reasoning.

AI agents should read the relevant documentation before making substantial changes.

Agents should not redefine the product direction without discussion.

---

# 20. AI Agent Rules

AI coding agents working on GitPilot should:

1. Read `PRD.md` before substantial implementation.
2. Read `ARCHITECTURE.md` before modifying architecture.
3. Read `DEVELOPMENT.md` to understand the current task.
4. Inspect existing code before creating new code.
5. Avoid unnecessary rewrites.
6. Avoid unnecessary dependencies.
7. Write tests for important functionality.
8. Explain significant architectural changes.
9. Keep changes focused on the current task.
10. Do not silently expand the project's scope.
11. Do not remove existing functionality without justification.
12. Do not perform destructive Git operations without explicit user confirmation.
13. Update project documentation when a significant decision changes.
14. Prefer small, reviewable changes over massive implementations.

---

# 21. Definition of Done

A feature is considered complete when:

* The implementation works.
* Relevant edge cases have been considered.
* Tests have been added where appropriate.
* Existing functionality still works.
* User-facing errors are understandable.
* The implementation follows the project's architecture.
* Documentation is updated if necessary.
* The feature has been manually verified where appropriate.

---

# 22. Out of Scope for the Initial Version

The initial version should NOT attempt to become:

* A complete GitHub replacement.
* A full-featured code editor.
* A complete IDE.
* An advanced Git hosting platform.
* An autonomous AI developer.
* A replacement for every advanced Git workflow.

GitPilot should first become excellent at its core purpose:

> **Helping users understand their Git repository and complete Git workflows intuitively and safely.**

---

# 23. Success Criteria

The MVP should make it possible for a user to:

1. Open a repository.
2. Understand its current state.
3. Identify what actions are available.
4. Choose a goal-oriented workflow.
5. Follow the workflow without memorizing Git commands.
6. Understand what GitPilot is doing.
7. Safely complete the workflow.
8. See the resulting repository state.

The defining characteristic of GitPilot is:

> **The user thinks in terms of goals. GitPilot thinks in terms of Git workflows.**
