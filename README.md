# GitPilot 🚀

**A safe, explainable Git workflow assistant with a desktop GUI and CLI.**

GitPilot is a Python-based Git workflow assistant designed to make common Git operations easier to understand and perform.

Instead of relying entirely on Git commands, GitPilot provides a repository-aware interface for inspecting repositories, managing branches, staging changes, creating commits, and working with remotes.

The project is built around a simple idea:

> **Make Git workflows easier to understand without hiding what Git is actually doing.**

---

## ✨ Features

### 📁 Repository Explorer

* Detect and open local Git repositories
* View repository status
* View changed files
* Inspect the current branch
* Display repository information

### 🌿 Branch Operations

* List local branches
* Detect the current branch
* Create local branches
* Switch between branches safely
* Protect uncommitted work from destructive switching

### 📝 Staging & Commits

* Select files to stage
* Unstage files
* Create commits through the GUI or CLI
* Validate commit messages
* Clear error handling for invalid paths and empty staging areas
* Display commit confirmation and results

### 🌐 Remote Operations

* Detect configured Git remotes
* Inspect fetch and push URLs
* Fetch from remotes
* Pull changes using fast-forward-only behavior
* Push changes without force operations
* Inspect upstream tracking
* Display ahead/behind information
* Handle repositories with multiple remotes without assuming `origin`

### 🖥️ Desktop GUI

GitPilot includes a desktop interface built with Python's standard-library **Tkinter/ttk**.

The GUI provides:

* Repository overview
* Changed-file inspection
* Branch management
* Staging and unstaging
* Commit creation
* Remote inspection
* Fetch, pull and push
* Upstream and ahead/behind information
* Visible success and error feedback
* Confirmation dialogs for higher-consequence remote operations

### 💻 CLI

GitPilot also provides a command-line interface for repository operations.

Examples include:

```bash
python main.py --branches
python main.py --stage file.py
python main.py --unstage file.py
python main.py --commit "Add feature"
python main.py --remotes
python main.py --fetch
python main.py --pull
python main.py --push
```

---

## 🛡️ Safety First

GitPilot is designed to avoid silently destructive Git operations.

The current implementation:

* Does not expose force push
* Does not use `git reset --hard`
* Does not discard working-tree changes during branch switching
* Uses `--ff-only` for pull operations
* Requires explicit confirmation for GUI pull/push operations
* Does not assume `origin` when multiple remotes exist
* Reports Git failures instead of pretending an operation succeeded
* Keeps Git execution centralized in the core Git abstraction

The GUI is a presentation layer and does not execute Git subprocesses directly.

---

## 🏗️ Architecture

GitPilot separates presentation, domain logic, and Git execution.

```text
┌───────────────────────────────┐
│        GUI / CLI              │
│     Presentation Layer        │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│        Repository             │
│       Domain Layer            │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│         Git CLI               │
│  Centralized Git Execution    │
└───────────────┬───────────────┘
                │
                ▼
             Git
```

Core Git operations are centralized through the Git command abstraction, while the GUI and CLI remain separate presentation layers.

---

## 🧪 Testing

GitPilot has an automated test suite covering:

* Git command execution
* Repository detection
* Status parsing
* Branch operations
* Staging and unstaging
* Commit creation
* CLI behavior
* GUI workflows
* Remote operations
* Fetch, pull and push
* Upstream tracking
* Ahead/behind state

The current test suite contains:

**209 tests — 0 failures — 0 errors**

Remote-operation tests use local temporary Git repositories and local bare repositories, so the test suite does not depend on external Git hosting services or internet access.

---

## ⚙️ Requirements

* Python 3
* Git
* Tkinter for the desktop GUI

GitPilot currently uses Python's standard library and does not require additional Python packages for its core functionality.

---

## 🚀 Running GitPilot

Clone the repository:

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd GitPilot
```

Launch the CLI:

```bash
python main.py
```

Launch the desktop GUI:

```bash
python main.py --gui
```

Then open a local Git repository through the application.

---

## 📂 Project Structure

```text
GitPilot/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   └── PRD.md
│
├── src/
│   └── gitpilot/
│       ├── core/
│       │   ├── errors.py
│       │   ├── git_cli.py
│       │   ├── models.py
│       │   ├── parser.py
│       │   └── repository.py
│       │
│       ├── gui/
│       │   └── app.py
│       │
│       ├── cli.py
│       └── main.py
│
├── tests/
├── main.py
└── README.md
```

---

## 🗺️ Current Development

GitPilot currently has the following capabilities implemented:

* Repository exploration
* Branch management
* Staging and unstaging
* Commit creation
* Remote management
* Fetch
* Pull
* Push
* Upstream tracking
* Ahead/behind tracking
* CLI and desktop GUI support

The next planned stage is the **Workflow Engine**, where GitPilot will begin translating higher-level user goals into sequences of repository operations.

---

## 🤝 Contributing

Contributions, ideas, bug reports, and suggestions are welcome.

If you find a problem or have an idea for improving GitPilot, feel free to open an issue or submit a pull request.

---

## 📜 License

Add the project's license information here.

---

**GitPilot**
*Making Git workflows easier to understand and execute.* 🚀
