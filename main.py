"""Application entry point."""

# Bootstrap must run BEFORE any third-party import.
from bootstrap import ensure_packages
ensure_packages()

import tkinter as tk
from gui.app import PortfolioApp


def main() -> None:
    root = tk.Tk()
    PortfolioApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
