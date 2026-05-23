"""
gui/app.py
----------
PortfolioApp — main tkinter application window.

Layout (left → right)
----------------------
┌──────────────────┬──────────────────────────────────────────────────────┐
│  CONTROL PANEL   │                  CHART AREA                          │
│  tickers & alloc │  (matplotlib FigureCanvasTkAgg)                      │
│  date range      │                                                      │
│  buttons         ├──────────────────────────────────────────────────────┤
│  stats display   │        View-switcher tab bar (top of chart)          │
└──────────────────┴──────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import math
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import tkinter as tk
from tkinter import messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from analytics import PortfolioAnalytics
from config import (
    DEFAULT_HOLDINGS,
    PALETTE,
    REBALANCE_PERIOD_OPTIONS,
    DEFAULT_REBALANCE_PERIOD,
    REBALANCE_COST_RATE,
)
from data_fetcher import DataFetcher
from gui import charts
from gui.styles import apply_styles
from gui.ticker_row import TickerRow


class PortfolioApp:
    """Main application window."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._configure_root()
        apply_styles()
        self._build_layout()
        self._populate_defaults()

        # Runtime state
        self.analytics: Optional[PortfolioAnalytics] = None
        self.current_view: str = "portfolio"
        self.latest_stats: Optional[Dict] = None
        self.latest_ticker_stats: Dict[str, Dict] = {}
        self.inception_date: Optional[date] = None

    # ── Window setup ──────────────────────────────────────────────────────────

    def _configure_root(self) -> None:
        self.root.title("Portfolio Analyzer")
        self.root.configure(bg=PALETTE["bg"])
        self.root.minsize(1050, 680)
        self.root.update_idletasks()
        w, h = 1280, 780
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Layout construction ───────────────────────────────────────────────────

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=0, minsize=290)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._build_control_panel()
        self._build_chart_area()

    def _build_control_panel(self) -> None:
        """Left sidebar: inputs, date range, action buttons, stats."""
        self.ctrl = tk.Frame(self.root, bg=PALETTE["surface"], width=290)
        self.ctrl.grid(row=0, column=0, sticky="nsew")
        self.ctrl.grid_propagate(False)
        self.ctrl.columnconfigure(0, weight=1)

        pad = {"padx": 18}

        # App title
        title_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        title_frame.grid(row=0, column=0, sticky="ew", pady=(22, 4), **pad)
        tk.Label(title_frame, text="PORTFOLIO", bg=PALETTE["surface"],
                 fg=PALETTE["accent"], font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="ANALYZER", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 18)).pack(anchor="w")

        self._hsep(1)

        # Section label
        tk.Label(self.ctrl, text="PORTFOLIO HOLDINGS", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9, "bold"),
                 ).grid(row=2, column=0, sticky="w", **pad, pady=(14, 4))

        # Column headers
        header_row = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        header_row.grid(row=3, column=0, sticky="ew", padx=18)
        tk.Label(header_row, text="TICKER", bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), width=9, anchor="w").grid(row=0, column=0)
        tk.Label(header_row, text="WEIGHT", bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), width=7, anchor="e").grid(row=0, column=1)

        # Ticker rows container
        ticker_region = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        ticker_region.grid(row=4, column=0, sticky="nsew", padx=18)
        self.ctrl.rowconfigure(4, weight=0)
        ticker_region.columnconfigure(0, weight=1)
        ticker_region.rowconfigure(0, weight=0)

        self.ticker_canvas = tk.Canvas(
            ticker_region,
            bg=PALETTE["surface"],
            bd=0,
            highlightthickness=0,
            relief="flat",
            height=1,
        )
        self.ticker_canvas.grid(row=0, column=0, sticky="ew")

        self.ticker_scroll = ttk.Scrollbar(
            ticker_region,
            orient="vertical",
            command=self.ticker_canvas.yview,
            style="Dark.Vertical.TScrollbar",
        )
        self.ticker_scroll.grid(row=0, column=1, sticky="ns")
        self.ticker_canvas.configure(yscrollcommand=self.ticker_scroll.set)

        self.ticker_frame = tk.Frame(self.ticker_canvas, bg=PALETTE["surface"])
        self.ticker_window = self.ticker_canvas.create_window(
            (0, 0), window=self.ticker_frame, anchor="nw"
        )
        self.ticker_rows: List[TickerRow] = []
        self.max_visible_ticker_rows = 3

        def _update_ticker_scrollregion(event: tk.Event) -> None:
            if self.ticker_rows:
                content_height = max(event.height, 1)
                content_width = max(
                    self.ticker_canvas.winfo_width(),
                    event.width,
                    1,
                )
                row_height = max(content_height // len(self.ticker_rows), 1)
                canvas_height = min(
                    content_height,
                    row_height * self.max_visible_ticker_rows,
                )
                self.ticker_canvas.configure(
                    height=canvas_height,
                    scrollregion=(0, 0, content_width, content_height),
                    yscrollincrement=row_height,
                )
                if len(self.ticker_rows) > self.max_visible_ticker_rows:
                    self.ticker_scroll.grid()
                else:
                    self.ticker_scroll.grid_remove()
                    self.ticker_canvas.yview_moveto(0.0)
            else:
                self.ticker_canvas.configure(scrollregion=(0, 0, 0, 0))
        self.ticker_frame.bind("<Configure>", _update_ticker_scrollregion)

        def _resize_ticker_window(event: tk.Event) -> None:
            self.ticker_canvas.itemconfigure(self.ticker_window, width=event.width)
        self.ticker_canvas.bind("<Configure>", _resize_ticker_window)
        self._bind_ticker_mousewheel(self.ticker_canvas)
        self._bind_ticker_mousewheel(self.ticker_frame)

        # Add-ticker button
        tk.Button(
            self.ctrl, text="＋  Add Ticker",
            command=self._add_ticker_row,
            bg=PALETTE["surface2"], fg=PALETTE["accent"],
            activebackground=PALETTE["border"], activeforeground=PALETTE["accent"],
            bd=0, cursor="hand2", font=("Segoe UI", 10), pady=5,
        ).grid(row=5, column=0, sticky="ew", padx=18, pady=(4, 0))

        # Allocation sum indicator
        self.alloc_label = tk.Label(
            self.ctrl, text="Allocation: 0 / 100%",
            bg=PALETTE["surface"], fg=PALETTE["text_dim"],
            font=("Segoe UI", 10), anchor="e",
        )
        self.alloc_label.grid(row=6, column=0, sticky="e", padx=18, pady=(4, 0))

        self._hsep(7)

        # Date range section
        tk.Label(self.ctrl, text="DATE RANGE", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9, "bold"),
                 ).grid(row=8, column=0, sticky="w", **pad, pady=(14, 4))

        date_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        date_frame.grid(row=9, column=0, sticky="ew", padx=18)
        date_frame.columnconfigure(1, weight=1)
        date_frame.columnconfigure(3, weight=1)

        for col, label in enumerate(["From", "To"]):
            tk.Label(date_frame, text=label, bg=PALETTE["surface"],
                     fg=PALETTE["text_dim"], font=("Segoe UI", 9),
                     ).grid(row=0, column=col * 2, sticky="w")

        self.start_var = tk.StringVar(
            value=(date.today() - timedelta(days=365 * 5)).strftime("%Y-%m-%d")
        )
        self.end_var = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))

        ttk.Entry(date_frame, textvariable=self.start_var,
                  width=11, style="Dark.TEntry").grid(row=1, column=0, pady=3, sticky="ew")
        tk.Label(date_frame, text="→", bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 12)).grid(row=1, column=1, padx=4)
        ttk.Entry(date_frame, textvariable=self.end_var,
                  width=11, style="Dark.TEntry").grid(row=1, column=2, pady=3, sticky="ew")

        # Max-range button
        self.max_btn = tk.Button(
            self.ctrl, text="⇤  Max Range",
            command=self._set_max_range,
            bg=PALETTE["surface2"], fg=PALETTE["accent2"],
            activebackground=PALETTE["border"],
            bd=0, cursor="hand2", font=("Segoe UI", 10), pady=5,
        )
        self.max_btn.grid(row=10, column=0, sticky="ew", padx=18, pady=(4, 0))

        self.inception_label = tk.Label(
            self.ctrl, text="Earliest data: —",
            bg=PALETTE["surface"], fg=PALETTE["text_dim"],
            font=("Segoe UI", 9), anchor="e",
        )
        self.inception_label.grid(row=11, column=0, sticky="e", padx=18, pady=(2, 0))

        # Rebalancing controls
        rebalance_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        rebalance_frame.grid(row=12, column=0, sticky="ew", padx=18, pady=(14, 0))
        rebalance_frame.columnconfigure(1, weight=1)

        self.rebalance_var = tk.BooleanVar(value=False)
        self.rebalance_check = ttk.Checkbutton(
            rebalance_frame,
            text="Periodic rebalance",
            variable=self.rebalance_var,
            command=self._on_rebalance_toggle,
            style="Dark.TCheckbutton",
        )
        self.rebalance_check.grid(row=0, column=0, sticky="w")

        period_frame = tk.Frame(rebalance_frame, bg=PALETTE["surface"])
        period_frame.grid(row=0, column=1, sticky="e", padx=(8, 0))
        tk.Label(period_frame, text="every", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9),
                 ).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.rebalance_period_var = tk.StringVar(value=DEFAULT_REBALANCE_PERIOD)
        self.rebalance_period_combo = ttk.Combobox(
            period_frame,
            values=REBALANCE_PERIOD_OPTIONS,
            textvariable=self.rebalance_period_var,
            width=6,
            state="disabled",
            style="Dark.TCombobox",
        )
        self.rebalance_period_combo.grid(row=0, column=1, sticky="e")
        tk.Label(period_frame, text="days", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9),
                 ).grid(row=0, column=2, sticky="w", padx=(4, 0))

        self._hsep(13)

        # Run analysis button
        self.run_btn = tk.Button(
            self.ctrl, text="▶  RUN ANALYSIS",
            command=self._run_analysis,
            bg=PALETTE["accent"], fg="#ffffff",
            activebackground="#3a70d4", activeforeground="#ffffff",
            bd=0, cursor="hand2", font=("Segoe UI", 12, "bold"), pady=10,
        )
        self.run_btn.grid(row=14, column=0, sticky="ew", padx=18, pady=(14, 0))

        # Status label
        self.status_var = tk.StringVar(value="")
        tk.Label(self.ctrl, textvariable=self.status_var,
                 bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), anchor="center",
                 ).grid(row=15, column=0, pady=(4, 0))

        self._hsep(16)


    def _build_chart_area(self) -> None:
        """Right side: tab bar + matplotlib canvas + navigation toolbar."""
        self.chart_outer = tk.Frame(self.root, bg=PALETTE["bg"])
        self.chart_outer.grid(row=0, column=1, sticky="nsew")
        self.chart_outer.columnconfigure(0, weight=1)
        self.chart_outer.rowconfigure(1, weight=1)

        # View-switcher tab bar
        self.tab_bar = tk.Frame(self.chart_outer, bg=PALETTE["bg"], height=44)
        self.tab_bar.grid(row=0, column=0, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tab_buttons: Dict[str, tk.Button] = {}

        # Matplotlib figure
        self.fig = Figure(facecolor=PALETTE["chart_bg"], tight_layout=True)
        self.fig.patch.set_facecolor(PALETTE["chart_bg"])

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_outer)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=1, column=0, sticky="nsew")
        charts.draw_placeholder(self.fig)
        self.canvas.draw()

        self.stats_text = tk.Text(
            self.chart_outer,
            bg=PALETTE["chart_bg"],
            fg=PALETTE["text"],
            insertbackground=PALETTE["text"],
            wrap="none",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 10),
        )
        self.stats_text.grid(row=1, column=0, sticky="nsew")
        self.stats_text.grid_remove()
        self.stats_text.config(state="disabled")

        # Navigation toolbar (zoom, pan, save)
        toolbar_frame = tk.Frame(self.chart_outer, bg=PALETTE["bg"])
        toolbar_frame.grid(row=2, column=0, sticky="ew")
        toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
        toolbar.config(background=PALETTE["bg"])
        for child in toolbar.winfo_children():
            try:
                child.config(background=PALETTE["bg"])
            except Exception:
                pass
        toolbar.update()

    # ── Widget helpers ────────────────────────────────────────────────────────

    def _hsep(self, row: int) -> None:
        """Draw a horizontal separator in the control panel."""
        ttk.Separator(self.ctrl, orient="horizontal", style="Dark.TSeparator").grid(
            row=row, column=0, sticky="ew", padx=12, pady=2
        )


    # ── Ticker-row management ─────────────────────────────────────────────────

    def _bind_ticker_mousewheel(self, widget: tk.Widget) -> None:
        """Route mouse-wheel events over ticker widgets to the ticker canvas."""
        widget.bind("<MouseWheel>", self._on_ticker_mousewheel, add="+")
        widget.bind("<Button-4>", lambda event: self._on_ticker_mousewheel(event, -1), add="+")
        widget.bind("<Button-5>", lambda event: self._on_ticker_mousewheel(event, 1), add="+")

    def _on_ticker_mousewheel(
        self,
        event: tk.Event,
        units: Optional[int] = None,
    ) -> str:
        """Scroll the ticker list by mouse wheel while respecting its limits."""
        if units is None:
            if event.delta == 0:
                return "break"
            units = -1 if event.delta > 0 else 1

        first, last = self.ticker_canvas.yview()
        if first <= 0.0 and units < 0:
            return "break"
        if last >= 1.0 and units > 0:
            return "break"

        self.ticker_canvas.yview_scroll(units, "units")
        return "break"

    def _add_ticker_row(self, ticker: str = "", alloc: str = "0") -> None:
        """Add one TickerRow widget to the input grid."""
        row_idx = len(self.ticker_rows)

        tr = TickerRow(
            self.ticker_frame,
            row_idx,
            on_remove=lambda r=row_idx: self._remove_ticker_row(r),
        )
        tr.ticker_var.set(ticker)
        tr.alloc_var.set(alloc)
        tr.alloc_var.trace_add("write", lambda *_: self._update_alloc_label())
        for widget in tr.widgets():
            self._bind_ticker_mousewheel(widget)

        self.ticker_rows.append(tr)
        self._update_alloc_label()

    def _remove_ticker_row(self, row_idx: int) -> None:
        """Remove a ticker row by index and rebuild the remaining grid."""
        if len(self.ticker_rows) <= 1:
            messagebox.showwarning(
                "Cannot Remove",
                "At least one ticker must remain in the portfolio.",
                parent=self.root,
            )
            return

        self.ticker_rows[row_idx].destroy()
        self.ticker_rows.pop(row_idx)

        # Re-grid surviving rows at their new positions
        for new_idx, tr in enumerate(self.ticker_rows):
            tr.regrid(new_idx)
            tr.remove_btn.config(command=lambda r=new_idx: self._remove_ticker_row(r))

        self._update_alloc_label()

    def _populate_defaults(self) -> None:
        """Pre-fill the demo portfolio."""
        for ticker, alloc in DEFAULT_HOLDINGS:
            self._add_ticker_row(ticker, alloc)

    def _update_alloc_label(self) -> None:
        """Recompute and display the running allocation sum."""
        total = 0.0
        for tr in self.ticker_rows:
            try:
                total += float(tr.alloc_var.get())
            except ValueError:
                pass

        colour = PALETTE["accent2"] if abs(total - 100) < 0.01 else PALETTE["warn"]
        self.alloc_label.config(text=f"Allocation: {total:.1f} / 100%", fg=colour)

    # ── Max-range helpers ─────────────────────────────────────────────────────

    def _set_max_range(self) -> None:
        """Fetch inception dates in a background thread, then update date fields."""
        tickers = [tr.get_values()[0] for tr in self.ticker_rows if tr.get_values()[0]]
        if not tickers:
            messagebox.showwarning("No Tickers", "Enter at least one ticker first.",
                                   parent=self.root)
            return

        self.status_var.set("⏳ Fetching inception dates …")
        self.run_btn.config(state="disabled")
        self.max_btn.config(state="disabled")

        def worker():
            inception = DataFetcher.get_inception_date(tickers)
            self.root.after(0, lambda: self._on_inception_fetched(inception))

        threading.Thread(target=worker, daemon=True).start()

    def _on_inception_fetched(self, inception: Optional[date]) -> None:
        self.run_btn.config(state="normal")
        self.max_btn.config(state="normal")

        if inception is None:
            self.status_var.set("⚠ Could not determine inception date.")
            return

        self.inception_date = inception
        self.start_var.set(inception.strftime("%Y-%m-%d"))
        self.end_var.set(date.today().strftime("%Y-%m-%d"))
        self.inception_label.config(
            text=f"Earliest data: {inception.strftime('%b %d, %Y')}"
        )
        self.status_var.set(
            f"✔ Max range set ({inception.strftime('%Y-%m-%d')} → today)"
        )

    # ── Analysis runner ───────────────────────────────────────────────────────

    def _run_analysis(self) -> None:
        """Validate inputs, then fetch data and run analytics in a background thread."""
        entries = self._parse_entries()
        if entries is None:
            return  # validation already showed an error dialog

        start_dt, end_dt = self._parse_dates()
        if start_dt is None:
            return

        tickers = [t for t, _ in entries]
        weights = {t: w / 100.0 for t, w in entries}
        rebalance_days = self._parse_rebalance_period()
        if self.rebalance_var.get() and rebalance_days is None:
            return

        self.run_btn.config(state="disabled")
        self.max_btn.config(state="disabled")
        self.status_var.set("⏳ Fetching market data …")

        def worker():
            try:
                prices, failed = DataFetcher.fetch_prices(
                    tickers,
                    start=start_dt.strftime("%Y-%m-%d"),
                    end=end_dt.strftime("%Y-%m-%d"),
                )
            except ValueError as exc:
                message = str(exc)
                self.root.after(0, lambda msg=message: self._on_analysis_error(msg))
                return

            # Renormalise weights if some tickers failed
            available_weights = {t: weights[t] for t in prices}
            w_sum = sum(available_weights.values())
            if w_sum == 0:
                self.root.after(0, lambda: self._on_analysis_error(
                    "No valid price data returned."
                ))
                return

            normalised = {t: v / w_sum for t, v in available_weights.items()}
            try:
                analytics = PortfolioAnalytics(
                    prices,
                    normalised,
                    rebalance_period_days=rebalance_days,
                    transaction_cost_rate=REBALANCE_COST_RATE,
                )
                stats = analytics.compute_stats()
                ticker_stats = analytics.compute_ticker_stats()
            except ValueError as exc:
                message = str(exc)
                self.root.after(0, lambda msg=message: self._on_analysis_error(msg))
                return

            self.root.after(
                0, lambda: self._on_analysis_complete(analytics, stats, ticker_stats, failed)
            )

        threading.Thread(target=worker, daemon=True).start()

    def _parse_entries(self) -> Optional[List[Tuple[str, float]]]:
        """
        Read and validate ticker/weight inputs.
        Returns a list of (ticker, weight_float) or None on validation failure.
        """
        entries: List[Tuple[str, float]] = []
        seen_tickers: set[str] = set()
        for tr in self.ticker_rows:
            ticker, alloc_str = tr.get_values()
            if not ticker:
                continue
            if ticker in seen_tickers:
                messagebox.showerror("Duplicate Ticker",
                                     f"'{ticker}' appears more than once.\n"
                                     "Use one row per ticker.",
                                     parent=self.root)
                return None
            seen_tickers.add(ticker)
            try:
                w = float(alloc_str)
            except ValueError:
                messagebox.showerror("Invalid Input",
                                     f"Allocation for '{ticker}' must be a number.",
                                     parent=self.root)
                return None
            if not math.isfinite(w):
                messagebox.showerror("Invalid Input",
                                     f"Allocation for '{ticker}' must be a finite number.",
                                     parent=self.root)
                return None
            if w <= 0:
                messagebox.showerror("Invalid Allocation",
                                     f"Allocation for '{ticker}' must be greater than 0%.",
                                     parent=self.root)
                return None
            entries.append((ticker, w))

        if not entries:
            messagebox.showerror("No Tickers", "Please add at least one ticker.",
                                 parent=self.root)
            return None

        total = sum(w for _, w in entries)
        if abs(total - 100.0) > 0.01:
            messagebox.showerror("Allocation Error",
                                 f"Allocations must sum to exactly 100%.\n"
                                 f"Current total: {total:.2f}%",
                                 parent=self.root)
            return None

        return entries

    def _parse_dates(self) -> Tuple[Optional[date], Optional[date]]:
        """
        Parse and validate the date-range fields.
        Returns (start, end) or (None, None) on failure.
        """
        try:
            start_dt = datetime.strptime(self.start_var.get(), "%Y-%m-%d").date()
            end_dt = datetime.strptime(self.end_var.get(), "%Y-%m-%d").date()
        except ValueError:
            messagebox.showerror("Date Format Error",
                                 "Dates must be in YYYY-MM-DD format.",
                                 parent=self.root)
            return None, None

        if start_dt >= end_dt:
            messagebox.showerror("Date Error", "Start date must be before end date.",
                                 parent=self.root)
            return None, None

        return start_dt, end_dt

    def _on_rebalance_toggle(self) -> None:
        """Enable or disable the rebalance period selector."""
        state = "normal" if self.rebalance_var.get() else "disabled"
        self.rebalance_period_combo.config(state=state)

    def _parse_rebalance_period(self) -> Optional[int]:
        if not self.rebalance_var.get():
            return None

        value = self.rebalance_period_var.get().strip()
        if not value:
            messagebox.showerror(
                "Rebalance Period",
                "Select a rebalance period in days.",
                parent=self.root,
            )
            return None

        try:
            period = int(value)
        except ValueError:
            messagebox.showerror(
                "Rebalance Period",
                "Rebalance period must be a whole number of days.",
                parent=self.root,
            )
            return None

        if period <= 0:
            messagebox.showerror(
                "Rebalance Period",
                "Rebalance period must be a positive number of days.",
                parent=self.root,
            )
            return None

        return period

    # ── Analysis callbacks ────────────────────────────────────────────────────

    def _on_analysis_error(self, message: str) -> None:
        self.run_btn.config(state="normal")
        self.max_btn.config(state="normal")
        self.status_var.set("✖ Analysis failed.")
        messagebox.showerror("Analysis Error", message, parent=self.root)

    def _on_analysis_complete(
        self,
        analytics: PortfolioAnalytics,
        stats: Dict,
        ticker_stats: Dict[str, Dict],
        failed: List[str],
    ) -> None:
        self.analytics = analytics
        self.latest_stats = stats
        self.latest_ticker_stats = ticker_stats
        self.run_btn.config(state="normal")
        self.max_btn.config(state="normal")
        self.status_var.set("✔ Analysis complete")

        if failed:
            messagebox.showwarning(
                "Ticker Warning",
                f"No data found for: {', '.join(failed)}.\n"
                "They have been excluded from the analysis.",
                parent=self.root,
            )

        self._rebuild_tab_bar()
        self._switch_view("portfolio")

    def _render_stats_text_legacy(self) -> None:
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")

        if self.latest_stats is None:
            self.stats_text.insert("end", "Run analysis to view portfolio statistics.")
        else:
            s = self.latest_stats
            lines = [
                "PORTFOLIO STATISTICS",
                "---------------------",
                f"Period: {s['start_date'].strftime('%Y-%m-%d')} → {s['end_date'].strftime('%Y-%m-%d')}",
                f"Total Return: {s['total_return'] * 100:+.2f}%",
                f"CAGR: {s['cagr'] * 100:+.2f}%",
                f"Volatility: {s['volatility'] * 100:+.2f}%",
                f"Sharpe: {s['sharpe']:+.2f}",
                f"Sortino: {s['sortino']:+.2f}",
                f"Max Drawdown: {s['max_drawdown'] * 100:+.2f}%",
                f"Drawdown: {s['drawdown_start'].strftime('%Y-%m-%d')} → {s['drawdown_end'].strftime('%Y-%m-%d')}",
                f"Transaction Cost: {s.get('rebalance_cost', 0.0) * 100:.4f}%",
                "",
                "FINAL ALLOCATIONS",
            ]
            final_allocations = s.get('final_allocations', {})
            for ticker, alloc in sorted(final_allocations.items()):
                lines.append(f"  {ticker}: {alloc * 100:.1f}%")
            lines.extend([
                "",
                "INDIVIDUAL TICKER SUMMARY",
                "------------------------",
            ])
            for ticker, series in self.analytics.prices.items():
                returns = series.pct_change().dropna()
                total_return = series.iloc[-1] / series.iloc[0] - 1
                volatility = returns.std() * np.sqrt(252)
                rolling_max = series.cummax()
                drawdown = (series - rolling_max) / rolling_max
                max_dd = drawdown.min()
                lines.append(
                    f"{ticker}: Return {total_return * 100:+.2f}%, "
                    f"Vol {volatility * 100:+.2f}%, Max DD {max_dd * 100:+.2f}%"
                )
            self.stats_text.insert("end", "\n".join(lines))

        self.stats_text.config(state="disabled")

    # ── View switcher ─────────────────────────────────────────────────────────

    def _render_stats_text(self) -> None:
        """Render the statistics tab as a structured, table-like report."""
        self.stats_text.config(state="normal")
        self.stats_text.delete("1.0", "end")
        self.stats_text.tag_configure("title", foreground=PALETTE["accent"], font=("Consolas", 13, "bold"))
        self.stats_text.tag_configure("section", foreground=PALETTE["accent2"], font=("Consolas", 11, "bold"))
        self.stats_text.tag_configure("dim", foreground=PALETTE["text_dim"])
        self.stats_text.tag_configure("good", foreground=PALETTE["accent2"])
        self.stats_text.tag_configure("bad", foreground=PALETTE["danger"])
        self.stats_text.tag_configure("warn", foreground=PALETTE["warn"])

        if self.latest_stats is None or self.analytics is None:
            self.stats_text.insert("end", "Run analysis to view portfolio statistics.")
            self.stats_text.config(state="disabled")
            return

        s = self.latest_stats

        def pct(value: float, signed: bool = True) -> str:
            sign = "+" if signed else ""
            return f"{value * 100:{sign}.2f}%"

        def num(value: float) -> str:
            return f"{value:+.2f}"

        def value_tag(value: float) -> str:
            if abs(value) < 1e-12:
                return "dim"
            return "good" if value > 0 else "bad"

        def write(text: str = "", tag: Optional[str] = None) -> None:
            self.stats_text.insert("end", text + "\n", tag)

        def section(title: str) -> None:
            write("")
            write(title, "section")
            write("-" * len(title), "dim")

        def metric_table(rows: List[Tuple[str, str, str, Optional[str]]]) -> None:
            label_w = max(len(row[0]) for row in rows)
            value_w = max(len(row[1]) for row in rows)
            for label, value, note, tag in rows:
                self.stats_text.insert("end", f"{label:<{label_w}}  ")
                self.stats_text.insert("end", f"{value:>{value_w}}  ", tag)
                self.stats_text.insert("end", note + "\n", "dim")

        rebalance = s.get("rebalance_period_days")
        rebalance_text = (
            f"Every {rebalance} trading days"
            if rebalance
            else "Buy and hold, no periodic rebalance"
        )
        period = (
            f"{s['start_date'].strftime('%Y-%m-%d')} -> "
            f"{s['end_date'].strftime('%Y-%m-%d')}"
        )

        write("PORTFOLIO STATISTICS", "title")
        write(f"Period: {period}  |  Trading days: {s['n_trading_days']}  |  Calendar days: {s['n_days']}", "dim")
        write(f"Method: {rebalance_text}  |  Risk-free rate: {PortfolioAnalytics.RISK_FREE_RATE * 100:.2f}% annual", "dim")

        section("Return")
        metric_table([
            ("Total return", pct(s["total_return"]), "End value vs starting value", value_tag(s["total_return"])),
            ("CAGR", pct(s["cagr"]), "Geometric annualized return", value_tag(s["cagr"])),
            ("Annualized daily mean", pct(s["annualized_return"]), "Arithmetic mean daily return x 252", value_tag(s["annualized_return"])),
            ("Average daily", pct(s["avg_daily_return"]), "Mean daily return", value_tag(s["avg_daily_return"])),
            ("Median daily", pct(s["median_daily_return"]), "Middle daily return", value_tag(s["median_daily_return"])),
        ])

        section("Risk")
        metric_table([
            ("Volatility", pct(s["volatility"], signed=False), "Annualized standard deviation", "warn"),
            ("Downside volatility", pct(s["downside_volatility"], signed=False), "Annualized negative excess-return deviation", "warn"),
            ("Max drawdown", pct(s["max_drawdown"]), f"{s['drawdown_start']} -> {s['drawdown_end']}", "bad"),
            (
                "Longest underwater",
                f"{s['longest_drawdown_days']} days",
                f"{s['longest_drawdown_start']} -> {s['longest_drawdown_end']}",
                "warn",
            ),
            ("Ulcer index", f"{s['ulcer_index']:.2f}", "Depth and duration of drawdowns", "warn"),
            ("VaR 95%", pct(s["var_95"]), "Daily 5th percentile loss threshold", "bad"),
            ("CVaR 95%", pct(s["cvar_95"]), "Average daily return in the worst 5%", "bad"),
        ])

        section("Risk-Adjusted")
        metric_table([
            ("Sharpe", num(s["sharpe"]), "Excess return per unit of volatility", value_tag(s["sharpe"])),
            ("Sortino", num(s["sortino"]), "Excess return per unit of downside volatility", value_tag(s["sortino"])),
            ("Calmar", num(s["calmar"]), "CAGR divided by absolute max drawdown", value_tag(s["calmar"])),
        ])

        section("Daily Behavior")
        metric_table([
            ("Best day", pct(s["best_day"]), str(s["best_day_date"]), "good"),
            ("Worst day", pct(s["worst_day"]), str(s["worst_day_date"]), "bad"),
            ("Win rate", pct(s["win_rate"], signed=False), f"{s['positive_days']} up / {s['negative_days']} down / {s['flat_days']} flat", value_tag(s["win_rate"] - 0.5)),
            ("Skew", num(s["skew"]), "Positive means larger right-tail returns", value_tag(s["skew"])),
            ("Excess kurtosis", num(s["kurtosis"]), "Higher means fatter daily-return tails", "warn"),
        ])

        section("Allocation Drift")
        write(f"{'Ticker':<10} {'Start':>10} {'Final':>10} {'Drift':>10}", "dim")
        write(f"{'-' * 10:<10} {'-' * 10:>10} {'-' * 10:>10} {'-' * 10:>10}", "dim")
        final_allocations = s.get("final_allocations", {})
        for ticker in self.analytics.price_df.columns:
            start_alloc = self.analytics.weights.get(ticker, 0.0)
            end_alloc = final_allocations.get(ticker, 0.0)
            drift = end_alloc - start_alloc
            write(
                f"{ticker:<10} {pct(start_alloc, signed=False):>10} "
                f"{pct(end_alloc, signed=False):>10} {pct(drift):>10}"
            )
        write(f"Transaction cost drag: {s.get('rebalance_cost', 0.0) * 100:.4f}% of initial portfolio value", "dim")

        section("Ticker Comparison")
        header = (
            f"{'Ticker':<8} {'Return':>10} {'CAGR':>10} {'Vol':>10} "
            f"{'Max DD':>10} {'Sharpe':>8} {'Win':>8} {'VaR95':>9}"
        )
        write(header, "dim")
        write("-" * len(header), "dim")
        for ticker, ts in self.latest_ticker_stats.items():
            write(
                f"{ticker:<8} {pct(ts['total_return']):>10} {pct(ts['cagr']):>10} "
                f"{pct(ts['volatility'], signed=False):>10} {pct(ts['max_drawdown']):>10} "
                f"{num(ts['sharpe']):>8} {pct(ts['win_rate'], signed=False):>8} {pct(ts['var_95']):>9}"
            )

        section("Correctness Notes")
        notes = [
            "Total return and CAGR are calculated from the normalized portfolio value series.",
            "Volatility uses sample standard deviation of daily returns annualized by sqrt(252).",
            "Sharpe and Sortino use a 4.00% annual risk-free rate converted to a daily rate.",
            "Max drawdown is the worst peak-to-trough decline; dates show the peak and trough.",
            "Transaction costs are deducted during simulated rebalances before new target holdings are set.",
        ]
        for note in notes:
            write(f"- {note}", "dim")

        self.stats_text.config(state="disabled")

    def _rebuild_tab_bar(self) -> None:
        """Recreate tab buttons: portfolio, statistics, and one per ticker."""
        for w in self.tab_bar.winfo_children():
            w.destroy()
        self.tab_buttons.clear()

        views = ["portfolio", "statistics"] + list(self.analytics.prices.keys())

        for view in views:
            if view == "portfolio":
                label = "Portfolio"
            elif view == "statistics":
                label = "Statistics"
            else:
                label = view
            btn = tk.Button(
                self.tab_bar, text=label,
                command=lambda v=view: self._switch_view(v),
                bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                activebackground=PALETTE["surface2"], activeforeground=PALETTE["text"],
                bd=0, padx=14, pady=10, cursor="hand2",
                font=("Segoe UI", 10),
            )
            btn.pack(side="left", fill="y")
            self.tab_buttons[view] = btn

    def _switch_view(self, view: str) -> None:
        """Redraw the chart and highlight the active tab."""
        self.current_view = view

        for v, btn in self.tab_buttons.items():
            if v == view:
                btn.config(bg=PALETTE["accent"], fg="#ffffff",
                           font=("Segoe UI", 10, "bold"))
            else:
                btn.config(bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                           font=("Segoe UI", 10))

        if view == "statistics":
            self.canvas_widget.grid_remove()
            self._render_stats_text()
            self.stats_text.grid()
        else:
            self.stats_text.grid_remove()
            self.canvas_widget.grid()
            if view == "portfolio":
                charts.draw_portfolio_chart(self.fig, self.analytics)
            else:
                charts.draw_individual_chart(self.fig, self.analytics, view)
            self.canvas.draw()
