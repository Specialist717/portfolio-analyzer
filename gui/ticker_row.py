"""
gui/ticker_row.py
-----------------
TickerRow — one row in the portfolio-input grid.

Contains: ticker entry field, allocation entry field, a '%' label,
and a remove button.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Tuple

from config import PALETTE


class TickerRow:
    """One row in the portfolio-input grid."""

    def __init__(
        self,
        parent_frame: tk.Frame,
        row_index: int,
        on_remove: Callable[[], None],
    ) -> None:
        self.parent = parent_frame
        self.row = row_index

        # Ticker entry
        self.ticker_var = tk.StringVar()
        self.ticker_entry = ttk.Entry(
            parent_frame,
            textvariable=self.ticker_var,
            width=9,
            style="Dark.TEntry",
        )
        self.ticker_entry.grid(
            row=row_index, column=0, padx=(0, 6), pady=3, sticky="ew"
        )

        # Allocation entry
        self.alloc_var = tk.StringVar(value="0")
        self.alloc_entry = ttk.Entry(
            parent_frame,
            textvariable=self.alloc_var,
            width=7,
            style="Dark.TEntry",
            justify="right",
        )
        self.alloc_entry.grid(
            row=row_index, column=1, padx=(0, 6), pady=3, sticky="ew"
        )

        # Percentage label
        self.pct_lbl = tk.Label(
            parent_frame,
            text="%",
            bg=PALETTE["surface"],
            fg=PALETTE["text_dim"],
            font=("Segoe UI", 11),
        )
        self.pct_lbl.grid(row=row_index, column=2, padx=(0, 10))

        # Remove button
        self.remove_btn = tk.Button(
            parent_frame,
            text="✕",
            command=on_remove,
            bg=PALETTE["surface"],
            fg=PALETTE["text_dim"],
            activebackground=PALETTE["surface2"],
            activeforeground=PALETTE["danger"],
            bd=0,
            cursor="hand2",
            font=("Segoe UI", 11),
        )
        self.remove_btn.grid(row=row_index, column=3, pady=3)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_values(self) -> Tuple[str, str]:
        """Return (ticker_uppercase, allocation_string)."""
        return self.ticker_var.get().strip().upper(), self.alloc_var.get().strip()

    def widgets(self) -> Tuple[tk.Widget, ...]:
        """Return every widget owned by this row."""
        return (
            self.ticker_entry,
            self.alloc_entry,
            self.pct_lbl,
            self.remove_btn,
        )

    def regrid(self, new_index: int) -> None:
        """Move all widgets to a new grid row after a sibling is removed."""
        self.row = new_index
        self.ticker_entry.grid(row=new_index, column=0, padx=(0, 6), pady=3, sticky="ew")
        self.alloc_entry.grid(row=new_index, column=1, padx=(0, 6), pady=3, sticky="ew")
        self.pct_lbl.grid(row=new_index, column=2, padx=(0, 10))
        self.remove_btn.grid(row=new_index, column=3, pady=3)

    def destroy(self) -> None:
        """Remove all widgets from the grid and destroy them."""
        self.ticker_entry.destroy()
        self.alloc_entry.destroy()
        self.pct_lbl.destroy()
        self.remove_btn.destroy()
