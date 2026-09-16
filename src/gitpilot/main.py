from pathlib import Path
import sys

# Ensure src/ is on sys.path if invoked directly as a script
package_root = Path(__file__).resolve().parent.parent
if str(package_root) not in sys.path:
    sys.path.insert(0, str(package_root))

from gitpilot.cli import main

if __name__ == "__main__":
    main()
