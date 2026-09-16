# Development Status

## Current Milestone
Milestone 1: Repository Explorer

## Current Task
Repository detection & status parser

## Completed
- [x] Define PRD
- [x] Create project structure
- [x] Document architecture (`docs/ARCHITECTURE.md`)
- [x] Implement Git command abstraction and safe process runner (`src/gitpilot/core/git_cli.py`)
- [x] Implement domain exceptions (`src/gitpilot/core/errors.py`)
- [x] Add Git CLI unit test suite (`tests/test_git_cli.py`)

## Next
- [ ] Implement repository data models (`src/gitpilot/core/models.py`)
- [ ] Implement porcelain v2 status parser (`src/gitpilot/core/parser.py`)
- [ ] Implement repository detection & inspection service (`src/gitpilot/core/repository.py`)
- [ ] Add unit and integration tests for parser and repository detection

## Notes
Git CLI execution wrapper completed with 15 passing unit tests. Subprocess calls enforce list arguments, `shell=False`, execution timeouts, and `GIT_TERMINAL_PROMPT=0`.