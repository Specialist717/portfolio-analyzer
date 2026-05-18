"""
main.py
-------
Application entry point.

1. Runs the dependency bootstrap (installs any missing packages).
2. Imports and launches the GUI.

Run with:
    python main.py        (standard Python 3.8+)
    uv run main.py        (uv-managed Python)
"""

# Bootstrap must run BEFORE any third-party import.
from bootstrap import ensure_packages
ensure_packages()

# All third-party packages are now guaranteed to be importable.
import tkinter as tk
from gui.app import PortfolioApp


def main() -> None:
    root = tk.Tk()
    PortfolioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
