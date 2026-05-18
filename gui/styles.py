"""
gui/styles.py
-------------
Configures all ttk widget styles for the dark theme.
Call `apply_styles()` once after creating the root Tk window.
"""

from tkinter import ttk

from config import PALETTE


def apply_styles() -> None:
    """Apply the application-wide dark ttk theme."""
    s = ttk.Style()
    s.theme_use("clam")

    # Frames
    s.configure("Dark.TFrame",    background=PALETTE["bg"])
    s.configure("Surface.TFrame", background=PALETTE["surface"])

    # Labels
    s.configure(
        "Dark.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        font=("Segoe UI", 11),
    )
    s.configure(
        "Header.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["accent"],
        font=("Segoe UI", 13, "bold"),
    )
    s.configure(
        "Dim.TLabel",
        background=PALETTE["surface"],
        foreground=PALETTE["text_dim"],
        font=("Segoe UI", 10),
    )

    # Entries
    s.configure(
        "Dark.TEntry",
        fieldbackground=PALETTE["surface2"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["accent"],
        background=PALETTE["surface2"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["border"],
        darkcolor=PALETTE["border"],
        relief="flat",
        padding=4,
        font=("Segoe UI", 11),
    )
    s.map(
        "Dark.TEntry",
        fieldbackground=[("focus", PALETTE["surface2"])],
        bordercolor=[("focus", PALETTE["accent"])],
    )
    s.configure(
        "Dark.TCombobox",
        fieldbackground=PALETTE["surface2"],
        background=PALETTE["surface2"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        lightcolor=PALETTE["border"],
        darkcolor=PALETTE["border"],
        arrowcolor=PALETTE["text"],
        relief="flat",
        padding=4,
        font=("Segoe UI", 11),
    )
    s.map(
        "Dark.TCombobox",
        fieldbackground=[("focus", PALETTE["surface2"])],
        bordercolor=[("focus", PALETTE["accent"])],
    )

    s.configure(
        "Dark.TCheckbutton",
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        font=("Segoe UI", 10),
        bordercolor=PALETTE["border"],
        focuscolor=PALETTE["surface"],
        padding=0,
        relief="flat",
    )
    s.map(
        "Dark.TCheckbutton",
        background=[("active", PALETTE["surface"]), ("focus", PALETTE["surface"])],
        foreground=[("active", PALETTE["text"]), ("focus", PALETTE["text"])],
    )

    s.configure(
        "Dark.Vertical.TScrollbar",
        troughcolor=PALETTE["surface2"],
        background=PALETTE["border"],
        arrowcolor=PALETTE["text_dim"],
        bordercolor=PALETTE["surface2"],
        relief="flat",
        width=10,
    )
    s.map(
        "Dark.Vertical.TScrollbar",
        background=[("active", PALETTE["accent"])],
        arrowcolor=[("active", PALETTE["text"])],
    )

    # Buttons
    s.configure(
        "Accent.TButton",
        background=PALETTE["accent"],
        foreground="#ffffff",
        font=("Segoe UI", 11, "bold"),
        padding=(10, 6),
        relief="flat",
        borderwidth=0,
    )
    s.map(
        "Accent.TButton",
        background=[("active", "#3a70d4"), ("pressed", "#2d5ab0")],
    )
    s.configure(
        "Ghost.TButton",
        background=PALETTE["surface2"],
        foreground=PALETTE["text"],
        font=("Segoe UI", 10),
        padding=(8, 5),
        relief="flat",
    )
    s.map(
        "Ghost.TButton",
        background=[("active", PALETTE["border"])],
    )

    # Separators
    s.configure("Dark.TSeparator", background=PALETTE["border"])
