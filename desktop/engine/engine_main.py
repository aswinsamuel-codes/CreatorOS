"""Entry point for the bundled engine used by the desktop app (built with PyInstaller)."""

import os
import sys

# A windowed (no-console) build has no stdout/stderr; give logging somewhere harmless to write.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from creatoros.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(["run", "--no-browser"]))
