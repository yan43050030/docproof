"""Allow running as: python -m docproof [GUI]  or  python -m docproof --batch ...

With no proofreading arguments the GUI launches; --batch/--check run headless.
"""

import multiprocessing
import sys

if __name__ == "__main__":
    # Required so multiprocessing works in a PyInstaller-frozen app (otherwise
    # each spawned worker would relaunch the whole GUI).
    multiprocessing.freeze_support()

    if any(a in ("--batch", "--check") for a in sys.argv[1:]):
        from docproof.cli import run
        sys.exit(run())
    else:
        from docproof.app import main
        main()
