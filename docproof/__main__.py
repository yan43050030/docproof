"""Allow running as: python -m docproof"""

import multiprocessing

from docproof.app import main

if __name__ == "__main__":
    # Required so multiprocessing works in a PyInstaller-frozen app (otherwise
    # each spawned worker would relaunch the whole GUI).
    multiprocessing.freeze_support()
    main()
