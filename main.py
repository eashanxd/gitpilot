"""Root entry point for GitPilot."""

from pathlib import Path
import sys

# Ensure src/ is on sys.path when executed directly from repository root
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from gitpilot.cli import main

if __name__ == "__main__":
    main()

