"""Tkinter user interface for entering portfolios and viewing analysis."""

from __future__ import annotations

import math
import threading
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

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
    DEFAULT_BENCHMARK,
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
        # Benchmark settings (optional)
        self.benchmark_prices = None
        self.benchmark_ticker: Optional[str] = None

    def _configure_root(self) -> None:
        self.root.title("Portfolio Analyzer")
        self.root.configure(bg=PALETTE["bg"])
        self.root.minsize(1050, 680)

        self.root.update_idletasks()
        w, h = 1280, 780
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.root.update_idletasks()
        w, h = 1280, 780
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

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

        title_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        title_frame.grid(row=0, column=0, sticky="ew", pady=(22, 4), **pad)
        tk.Label(title_frame, text="PORTFOLIO", bg=PALETTE["surface"],
                 fg=PALETTE["accent"], font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(title_frame, text="ANALYZER", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 18)).pack(anchor="w")

        self._hsep(1)

        tk.Label(self.ctrl, text="PORTFOLIO HOLDINGS", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9, "bold"),
                 ).grid(row=2, column=0, sticky="w", **pad, pady=(14, 4))

        header_row = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        header_row.grid(row=3, column=0, sticky="ew", padx=18)
        tk.Label(header_row, text="TICKER", bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), width=9, anchor="w").grid(row=0, column=0)
        tk.Label(header_row, text="WEIGHT", bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), width=7, anchor="e").grid(row=0, column=1)

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

        tk.Button(
            self.ctrl, text="＋  Add Ticker",
            command=self._add_ticker_row,
            bg=PALETTE["surface2"], fg=PALETTE["accent"],
            activebackground=PALETTE["border"], activeforeground=PALETTE["accent"],
            bd=0, cursor="hand2", font=("Segoe UI", 10), pady=5,
        ).grid(row=5, column=0, sticky="ew", padx=18, pady=(4, 0))

        self.alloc_label = tk.Label(
            self.ctrl, text="Allocation: 0 / 100%",
            bg=PALETTE["surface"], fg=PALETTE["text_dim"],
            font=("Segoe UI", 10), anchor="e",
        )
        self.alloc_label.grid(row=6, column=0, sticky="e", padx=18, pady=(4, 0))

        self._hsep(7)

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

        tk.Label(self.ctrl, text="BENCHMARK", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9, "bold"),
                 ).grid(row=14, column=0, sticky="w", **pad, pady=(8, 4))

        benchmark_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        benchmark_frame.grid(row=15, column=0, sticky="ew", padx=18)
        benchmark_frame.columnconfigure(1, weight=1)

        self.benchmark_var = tk.BooleanVar(value=False)
        self.benchmark_check = ttk.Checkbutton(
            benchmark_frame,
            text="Show benchmark",
            variable=self.benchmark_var,
            command=self._on_benchmark_toggle,
            style="Dark.TCheckbutton",
        )
        self.benchmark_check.grid(row=0, column=0, sticky="w")

        self.benchmark_ticker_var = tk.StringVar(value=DEFAULT_BENCHMARK)
        self.benchmark_entry = ttk.Entry(
            benchmark_frame, textvariable=self.benchmark_ticker_var, width=9, style="Dark.TEntry"
        )
        self.benchmark_entry.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self.benchmark_entry.config(state="disabled")

        tk.Label(self.ctrl, text="ACTIONS", bg=PALETTE["surface"],
                 fg=PALETTE["text_dim"], font=("Segoe UI", 9, "bold"),
                 ).grid(row=16, column=0, sticky="w", **pad, pady=(10, 4))

        actions_frame = tk.Frame(self.ctrl, bg=PALETTE["surface"])
        actions_frame.grid(row=17, column=0, sticky="ew", padx=18)
        actions_frame.columnconfigure(0, weight=1)

        self.optimize_btn = tk.Button(
            actions_frame, text="⚖  OPTIMIZE",
            command=self._run_optimization,
            bg=PALETTE["surface2"], fg=PALETTE["accent2"],
            activebackground=PALETTE["border"], activeforeground=PALETTE["accent2"],
            bd=0, cursor="hand2", font=("Segoe UI", 11), pady=8,
        )
        self.optimize_btn.grid(row=0, column=0, sticky="ew")
        # Ensure optimize button is enabled by default (guard against state leftover from other flows)
        try:
            self.optimize_btn.config(state="normal")
        except Exception:
            pass

        self.run_btn = tk.Button(
            actions_frame, text="▶  RUN ANALYSIS",
            command=self._run_analysis,
            bg=PALETTE["accent"], fg="#ffffff",
            activebackground="#3a70d4", activeforeground="#ffffff",
            bd=0, cursor="hand2", font=("Segoe UI", 12, "bold"), pady=10,
        )
        self.run_btn.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        self.status_var = tk.StringVar(value="")
        tk.Label(self.ctrl, textvariable=self.status_var,
                 bg=PALETTE["surface"], fg=PALETTE["text_dim"],
                 font=("Segoe UI", 9), anchor="center",
                 ).grid(row=18, column=0, pady=(8, 0))

        self._hsep(19)


    def _build_chart_area(self) -> None:
        """Right side: tab bar + matplotlib canvas + navigation toolbar."""
        self.chart_outer = tk.Frame(self.root, bg=PALETTE["bg"])
        self.chart_outer.grid(row=0, column=1, sticky="nsew")
        self.chart_outer.columnconfigure(0, weight=1)
        self.chart_outer.rowconfigure(1, weight=1)

        self.tab_bar = tk.Frame(self.chart_outer, bg=PALETTE["bg"], height=44)
        self.tab_bar.grid(row=0, column=0, sticky="ew")
        self.tab_bar.grid_propagate(False)
        self.tab_buttons: Dict[str, tk.Button] = {}

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

    def _hsep(self, row: int) -> None:
        """Draw a horizontal separator in the control panel."""
        ttk.Separator(self.ctrl, orient="horizontal", style="Dark.TSeparator").grid(
            row=row, column=0, sticky="ew", padx=12, pady=2
        )

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

    def _run_analysis(self) -> None:
        """Validate inputs, then fetch data and run analytics in a background thread."""
        entries = self._parse_entries()
        if entries is None:
            return

        start_dt, end_dt = self._parse_dates()
        if start_dt is None:
            return

        tickers = [t for t, _ in entries]
        weights = {t: w / 100.0 for t, w in entries}
        rebalance_days = self._parse_rebalance_period()
        if self.rebalance_var.get() and rebalance_days is None:
            return

        # Check whether user requested a benchmark
        benchmark_ticker = None
        if getattr(self, "benchmark_var", None) and self.benchmark_var.get():
            benchmark_ticker = self.benchmark_ticker_var.get().strip().upper()
            if not benchmark_ticker:
                benchmark_ticker = None

        # Delegate to the shared worker which handles threading and UI state.
        self._start_analysis_worker(tickers, weights, start_dt, end_dt, rebalance_days, benchmark_ticker)

    def _start_analysis_worker(
        self,
        tickers: List[str],
        weights: Dict[str, float],
        start_dt: date,
        end_dt: date,
        rebalance_days: Optional[int],
        benchmark_ticker: Optional[str],
    ) -> None:
        """Run the analysis worker given explicit tickers/weights and date range.
        This bypasses _parse_entries validation and is used after applying optimized allocations.
        """
        self.run_btn.config(state="disabled")
        self.max_btn.config(state="disabled")
        try:
            self.optimize_btn.config(state="disabled")
        except Exception:
            pass
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

            # Re-normalize weights if Yahoo returns data for only part of the input.
            available_weights = {t: weights.get(t, 0.0) for t in prices}
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

            # Optionally fetch benchmark (if requested and not present in the portfolio prices)
            benchmark_series = None
            bench_failed = []
            if benchmark_ticker:
                if benchmark_ticker in prices:
                    benchmark_series = prices.get(benchmark_ticker)
                else:
                    try:
                        bprices, bfailed = DataFetcher.fetch_prices(
                            [benchmark_ticker],
                            start=start_dt.strftime("%Y-%m-%d"),
                            end=end_dt.strftime("%Y-%m-%d"),
                        )
                        benchmark_series = bprices.get(benchmark_ticker)
                        if not benchmark_series:
                            bench_failed = bfailed
                    except Exception:
                        bench_failed = [benchmark_ticker]
                        benchmark_series = None

            # Pass the actual weights used in the analysis so the UI can reflect them
            self.root.after(
                0, lambda: self._on_analysis_complete(analytics, stats, ticker_stats, failed, benchmark_series, benchmark_ticker, normalised)
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

    def _on_benchmark_toggle(self) -> None:
        """Enable/disable benchmark entry and fetch benchmark if enabled."""
        state = "normal" if self.benchmark_var.get() else "disabled"
        try:
            self.benchmark_entry.config(state=state)
        except Exception:
            pass

        # If disabling, clear stored benchmark and redraw
        if not self.benchmark_var.get():
            self.benchmark_prices = None
            self.benchmark_ticker = None
            if self.analytics is not None:
                self._switch_view("portfolio")
            return

        # If enabling and analytics already exists, fetch benchmark series
        if self.analytics is None:
            return

        self.status_var.set("⏳ Fetching benchmark …")
        self.run_btn.config(state="disabled")
        try:
            self.optimize_btn.config(state="disabled")
        except Exception:
            pass

        benchmark_ticker = self.benchmark_ticker_var.get().strip().upper()

        def worker():
            try:
                prices, failed = DataFetcher.fetch_prices(
                    [benchmark_ticker],
                    start=self.start_var.get(),
                    end=self.end_var.get(),
                )
                series = prices.get(benchmark_ticker)
            except Exception:
                series = None
                failed = [benchmark_ticker]
            self.root.after(0, lambda: self._on_benchmark_fetched(series, benchmark_ticker if series is not None else None, failed))

        threading.Thread(target=worker, daemon=True).start()

    def _on_benchmark_fetched(self, series, ticker, failed):
        self.run_btn.config(state="normal")
        try:
            self.optimize_btn.config(state="normal")
        except Exception:
            pass
        self.max_btn.config(state="normal")
        if series is None:
            self.status_var.set("⚠ Could not fetch benchmark.")
            messagebox.showwarning("Benchmark", f"Could not fetch benchmark data for {ticker}.", parent=self.root)
            self.benchmark_prices = None
            self.benchmark_ticker = None
            return
        self.benchmark_prices = series
        self.benchmark_ticker = ticker
        self.status_var.set("✔ Benchmark loaded")
        self._switch_view("portfolio")

    def _parse_rebalance_period(self) -> Optional[int]:
        """Return the selected rebalance interval, or None when disabled/invalid."""
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
        benchmark_series=None,
        benchmark_ticker: Optional[str] = None,
        used_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.analytics = analytics
        self.latest_stats = stats
        self.latest_ticker_stats = ticker_stats
        self.run_btn.config(state="normal")
        try:
            self.optimize_btn.config(state="normal")
        except Exception:
            pass
        self.max_btn.config(state="normal")
        self.status_var.set("✔ Analysis complete")

        # Reflect the actual date range used by the analysis in the UI date fields.
        # This ensures the left-hand date selectors show the common date window when
        # newly-added tickers shorten the available history.
        try:
            # analytics.price_df index contains pandas.Timestamp values
            actual_start = self.analytics.price_df.index[0].date()
            actual_end = self.analytics.price_df.index[-1].date()
            self.start_var.set(actual_start.strftime("%Y-%m-%d"))
            self.end_var.set(actual_end.strftime("%Y-%m-%d"))
            self.inception_date = actual_start
            self.inception_label.config(text=f"Earliest data: {actual_start.strftime('%b %d, %Y')}")
        except Exception:
            # Do not break the UI if indexing fails for any reason
            pass

        # Store optional benchmark (may be None). If the user has the benchmark checkbox enabled
        # but the run-analysis path did not provide a series, attempt an explicit fetch so the UI
        # reflects the requested benchmark without requiring the user to toggle the checkbox.
        self.benchmark_prices = benchmark_series
        self.benchmark_ticker = benchmark_ticker

        # If the user requested a benchmark and it wasn't provided by the analysis worker,
        # try to fetch it explicitly (or reuse a series included in the portfolio prices).
        if getattr(self, "benchmark_var", None) and self.benchmark_var.get():
            # Prefer the ticker returned by the analysis worker, fall back to the UI entry.
            bt = benchmark_ticker or (self.benchmark_ticker_var.get().strip().upper() or None)
            if bt and self.benchmark_prices is None:
                try:
                    # If the benchmark is one of the portfolio tickers, reuse that series.
                    if bt in self.analytics.prices:
                        self.benchmark_prices = self.analytics.prices.get(bt)
                        self.benchmark_ticker = bt
                        self.status_var.set("✔ Benchmark loaded")
                    else:
                        # Fetch benchmark in the background so the UI doesn't block.
                        self.status_var.set("⏳ Fetching benchmark …")
                        self.run_btn.config(state="disabled")
                        try:
                            self.optimize_btn.config(state="disabled")
                        except Exception:
                            pass

                        def bench_worker():
                            try:
                                bprices, bfailed = DataFetcher.fetch_prices(
                                    [bt],
                                    start=self.start_var.get(),
                                    end=self.end_var.get(),
                                )
                                series = bprices.get(bt)
                                failed_b = bfailed
                            except Exception:
                                series = None
                                failed_b = [bt]
                            self.root.after(0, lambda: self._on_benchmark_fetched(series, bt if series is not None else None, failed_b))

                        threading.Thread(target=bench_worker, daemon=True).start()
                except Exception:
                    # Ensure benchmark-fetch errors don't break analysis UI
                    pass

        # Update UI: if some portfolio tickers failed, remove them and reflect the normalized weights
        if failed:
            # Filter to only portfolio tickers that appear in the current input grid
            current_tickers = [tr.get_values()[0] for tr in self.ticker_rows]
            portfolio_failures = [t for t in failed if t in current_tickers]
            if portfolio_failures:
                # Remove rows for failed tickers (reverse order to avoid reindexing issues)
                indices_to_remove = [i for i, tr in enumerate(self.ticker_rows) if tr.get_values()[0] in portfolio_failures]
                for idx in sorted(indices_to_remove, reverse=True):
                    if len(self.ticker_rows) > 1:
                        self._remove_ticker_row(idx)

                # Reflect the actual weights used in the analysis when available
                if used_weights:
                    # used_weights are allocation fractions summing to 1.0 for available tickers
                    pct_map = {t: round(float(w) * 100.0, 2) for t, w in used_weights.items()}
                    # Correct rounding drift
                    diff = round(100.0 - sum(pct_map.values()), 2)
                    if abs(diff) >= 0.01 and pct_map:
                        largest = max(used_weights.items(), key=lambda x: x[1])[0]
                        pct_map[largest] = round(pct_map.get(largest, 0.0) + diff, 2)

                    for tr in self.ticker_rows:
                        t, _ = tr.get_values()
                        if t in pct_map:
                            tr.alloc_var.set(f"{pct_map[t]:.2f}")
                else:
                    # Fallback: renormalize existing allocations on-screen
                    remaining = [tr.get_values() for tr in self.ticker_rows if tr.get_values()[0]]
                    allocated = []
                    for t, wstr in remaining:
                        try:
                            allocated.append((t, float(wstr)))
                        except Exception:
                            allocated.append((t, 0.0))
                    total = sum(w for _, w in allocated)
                    if total <= 0:
                        n = len(allocated)
                        pct = {t: round(100.0 / n, 2) for t, _ in allocated}
                        rem = round(100.0 - sum(pct.values()), 2)
                        if abs(rem) >= 0.01 and pct:
                            first = allocated[0][0]
                            pct[first] = round(pct[first] + rem, 2)
                    else:
                        normalized = {t: w / total for t, w in allocated}
                        pct = {t: round(v * 100.0, 2) for t, v in normalized.items()}
                        rem = round(100.0 - sum(pct.values()), 2)
                        if abs(rem) >= 0.01:
                            largest = max(normalized.items(), key=lambda x: x[1])[0]
                            pct[largest] = round(pct.get(largest, 0.0) + rem, 2)
                    for tr in self.ticker_rows:
                        t, _ = tr.get_values()
                        if t in pct:
                            tr.alloc_var.set(f"{pct[t]:.2f}")

                self._update_alloc_label()

        # If benchmark fetching failed, do not treat that as a portfolio data failure.
        if benchmark_ticker and benchmark_series is None:
            self.status_var.set(f"⚠ Benchmark {benchmark_ticker} not available; omitted from chart.")

        # Warn about any remaining portfolio data failures
        if failed:
            messagebox.showwarning(
                "Ticker Warning",
                f"No data found for: {', '.join(failed)}.\n"
                "They have been excluded from the analysis.",
                parent=self.root,
            )

        self._rebuild_tab_bar()
        self._switch_view("portfolio")

    def _run_optimization(self) -> None:
        """Fetch data and compute Markowitz-optimal weights (no shorting) in a background thread.

        Optimization gathers tickers from the input grid and ignores the current
        allocation values (they are used only for Run Analysis). This allows having
        0% allocations present while still optimizing the universe of tickers.
        """
        # Gather tickers from input rows (allow zero allocations in the inputs)
        tickers: List[str] = []
        seen_tickers: set[str] = set()
        for tr in self.ticker_rows:
            t, _ = tr.get_values()
            if not t:
                continue
            if t in seen_tickers:
                messagebox.showerror(
                    "Duplicate Ticker",
                    f"'{t}' appears more than once.\nUse one row per ticker.",
                    parent=self.root,
                )
                return
            seen_tickers.add(t)
            tickers.append(t)

        if not tickers:
            messagebox.showwarning("No Tickers", "Enter at least one ticker first.", parent=self.root)
            return

        start_dt, end_dt = self._parse_dates()
        if start_dt is None:
            return

        self.run_btn.config(state="disabled")
        try:
            self.optimize_btn.config(state="disabled")
        except Exception:
            pass
        self.max_btn.config(state="disabled")
        self.status_var.set("⏳ Fetching market data for optimization …")

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

            if not prices:
                self.root.after(0, lambda: self._on_analysis_error("No valid price data returned."))
                return

            try:
                dummy_weights = {t: 1.0 / len(prices) for t in prices}
                analytics = PortfolioAnalytics(prices, dummy_weights)
                result = analytics.markowitz_optimize(num_portfolios=20000, allow_short=False)
            except Exception as exc:
                msg = str(exc)
                self.root.after(0, lambda m=msg: self._on_analysis_error(m))
                return

            self.root.after(0, lambda: self._on_optimization_complete(result, failed))

        threading.Thread(target=worker, daemon=True).start()

    def _on_optimization_complete(self, result: Dict, failed: List[str]) -> None:
        self.run_btn.config(state="normal")
        try:
            self.optimize_btn.config(state="normal")
        except Exception:
            pass
        self.max_btn.config(state="normal")
        self.status_var.set("✔ Optimization complete")

        if failed:
            messagebox.showwarning(
                "Ticker Warning",
                f"No data found for: {', '.join(failed)}.\nThey have been excluded from the optimization.",
                parent=self.root,
            )

        weights = result.get("weights", {})
        if not weights:
            messagebox.showinfo("Optimization Result", "No suggested allocation found.")
            return

        lines = [f"{t}: {weights[t]*100:.2f}%" for t in sorted(weights)]
        message = "Recommended allocations:\n\n" + "\n".join(lines)
        apply = messagebox.askyesno("Optimization Complete", message + "\n\nApply these allocations to the input fields?")
        if apply:
            # Apply suggested allocations. Remove tickers with (near) zero weight.
            zero_threshold = 1e-8
            # Build mapping from current ticker rows to (index,tr)
            mapping = {tr.get_values()[0]: (idx, tr) for idx, tr in enumerate(list(self.ticker_rows))}
            # Suggested weights for tickers present in the grid
            suggested = {t: float(weights.get(t, 0.0)) for t in mapping.keys()}
            # Keep only positive weights
            positive = {t: w for t, w in suggested.items() if w > zero_threshold}
            if not positive:
                messagebox.showinfo("Optimization Result", "Optimization suggests zero allocation for all current tickers. No changes applied.")
            else:
                # Normalize positive weights to sum to 1
                total = sum(positive.values())
                normalized = {t: (w / total) for t, w in positive.items()}
                # Convert to percentages with 2 decimal rounding, adjust largest to fix rounding drift
                pct = {t: round(normalized[t] * 100.0, 2) for t in normalized}
                pct_total = sum(pct.values())
                diff = round(100.0 - pct_total, 2)
                if abs(diff) >= 0.01:
                    largest = max(normalized.items(), key=lambda x: x[1])[0]
                    pct[largest] = round(pct.get(largest, 0.0) + diff, 2)
                # Apply percentages to current rows and mark zero rows for removal
                indices_to_remove: list[int] = []
                for idx, tr in enumerate(list(self.ticker_rows)):
                    t, _ = tr.get_values()
                    # Treat any suggested percentage <= 0.00 as zero and remove the row.
                    if t in pct and pct.get(t, 0.0) > 0.0:
                        tr.alloc_var.set(f"{pct[t]:.2f}")
                    else:
                        # set to 0.00 and schedule removal
                        tr.alloc_var.set("0.00")
                        indices_to_remove.append(idx)
                # Remove zero-weight tickers from highest index to lowest
                for idx in sorted(indices_to_remove, reverse=True):
                    if len(self.ticker_rows) > 1:
                        self._remove_ticker_row(idx)
                # Ensure allocation label updates and start analysis (bypassing strict entry validation)
                self._update_alloc_label()
                # Build tickers and weights from the updated UI grid
                entries = [(tr.get_values()[0], tr.get_values()[1]) for tr in self.ticker_rows if tr.get_values()[0]]
                weights_map: Dict[str, float] = {}
                for t, wstr in entries:
                    try:
                        w = float(wstr)
                    except Exception:
                        w = 0.0
                    if w > 0:
                        weights_map[t] = w / 100.0
                # Validate dates and rebalance settings before starting analysis
                rebalance_days = self._parse_rebalance_period()
                start_dt, end_dt = self._parse_dates()
                if start_dt is None:
                    return
                if self.rebalance_var.get() and rebalance_days is None:
                    return
                # Start the analysis worker with the current, applied allocations
                benchmark_ticker = None
                if getattr(self, "benchmark_var", None) and self.benchmark_var.get():
                    benchmark_ticker = self.benchmark_ticker_var.get().strip().upper() or None
                self._start_analysis_worker(list(weights_map.keys()), weights_map, start_dt, end_dt, rebalance_days, benchmark_ticker)
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
        write("Portfolio return/risk metrics include modeled transaction costs when rebalancing is enabled.", "dim")
        write("* marked statistics are estimates or depend on modeling assumptions.", "dim")

        section("Return")
        metric_table([
            ("Total return", pct(s["total_return"]), "End value vs starting value", value_tag(s["total_return"])),
            ("CAGR*", pct(s["cagr"]), "Geometric annualized return using calendar-year scaling", value_tag(s["cagr"])),
            ("Annualized daily mean*", pct(s["annualized_return"]), "Arithmetic mean daily return x 252 trading days", value_tag(s["annualized_return"])),
            ("Average daily", pct(s["avg_daily_return"]), "Mean daily return", value_tag(s["avg_daily_return"])),
            ("Median daily", pct(s["median_daily_return"]), "Middle daily return", value_tag(s["median_daily_return"])),
        ])

        section("Risk")
        metric_table([
            ("Volatility*", pct(s["volatility"], signed=False), "Daily standard deviation annualized by sqrt(252)", "warn"),
            ("Downside volatility*", pct(s["downside_volatility"], signed=False), "Annualized negative excess-return deviation", "warn"),
            ("Max drawdown", pct(s["max_drawdown"]), f"{s['drawdown_start']} -> {s['drawdown_end']}", "bad"),
            (
                "Longest underwater",
                f"{s['longest_drawdown_days']} days",
                f"{s['longest_drawdown_start']} -> {s['longest_drawdown_end']}",
                "warn",
            ),
            ("Ulcer index", f"{s['ulcer_index']:.2f}", "Depth and duration of drawdowns", "warn"),
            ("VaR 95%*", pct(s["var_95"]), "Historical daily 5th percentile loss threshold", "bad"),
            ("CVaR 95%*", pct(s["cvar_95"]), "Historical average daily return in the worst 5%", "bad"),
        ])

        section("Risk-Adjusted")
        metric_table([
            ("Sharpe*", num(s["sharpe"]), "Excess return per unit of volatility; uses risk-free-rate assumption", value_tag(s["sharpe"])),
            ("Sortino*", num(s["sortino"]), "Excess return per unit of downside volatility; uses risk-free-rate assumption", value_tag(s["sortino"])),
            ("Calmar*", num(s["calmar"]), "CAGR divided by absolute max drawdown", value_tag(s["calmar"])),
        ])

        section("Daily Behavior")
        metric_table([
            ("Best day", pct(s["best_day"]), str(s["best_day_date"]), "good"),
            ("Worst day", pct(s["worst_day"]), str(s["worst_day_date"]), "bad"),
            ("Win rate", pct(s["win_rate"], signed=False), f"{s['positive_days']} up / {s['negative_days']} down / {s['flat_days']} flat", value_tag(s["win_rate"] - 0.5)),
            ("Skew*", num(s["skew"]), "Sample estimate; positive means larger right-tail returns", value_tag(s["skew"])),
            ("Excess kurtosis*", num(s["kurtosis"]), "Sample estimate; higher means fatter daily-return tails", "warn"),
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
        write(
            f"Transaction cost drag*: {s.get('rebalance_cost', 0.0) * 100:.4f}% of initial portfolio value; "
            "portfolio return/risk metrics above are after this modeled cost.",
            "dim",
        )

        section("Stock Comparison")
        label_w = 12
        ret_w = 10
        cagr_w = 10
        vol_w = 10
        maxdd_w = 10
        longest_w = 12
        sharpe_w = 8
        win_w = 8
        var_w = 9
        header = (
            f"{'Ticker':<{label_w}} {'Return':>{ret_w}} {'CAGR*':>{cagr_w}} {'Vol*':>{vol_w}} "
            f"{'Max DD':>{maxdd_w}} {'Longest UW':>{longest_w}} {'Sharpe*':>{sharpe_w}} {'Win':>{win_w}} {'VaR95*':>{var_w}}"
        )
        write(header, "dim")
        write("-" * len(header), "dim")

        # Prepare benchmark stats if a benchmark is selected and it's not one of the portfolio tickers
        tickers = list(self.analytics.price_df.columns)
        bench_stats = None
        bench_ticker = getattr(self, "benchmark_ticker", None)
        if getattr(self, "benchmark_prices", None) is not None and bench_ticker and bench_ticker not in tickers:
            try:
                aligned = self.benchmark_prices.reindex(self.analytics.price_df.index).dropna()
                if len(aligned) >= 2:
                    bench_vs = aligned / aligned.iloc[0]
                    bench_stats = PortfolioAnalytics._return_stats(bench_vs, PortfolioAnalytics.RISK_FREE_RATE)
            except Exception:
                bench_stats = None

        for ticker, ts in self.latest_ticker_stats.items():
            longest_uw = f"{ts.get('longest_drawdown_days', 0)}d"
            write(
                f"{ticker:<{label_w}} {pct(ts['total_return']):>{ret_w}} {pct(ts['cagr']):>{cagr_w}} "
                f"{pct(ts['volatility'], signed=False):>{vol_w}} {pct(ts['max_drawdown']):>{maxdd_w}} {longest_uw:>{longest_w}} "
                f"{num(ts['sharpe']):>{sharpe_w}} {pct(ts['win_rate'], signed=False):>{win_w}} {pct(ts['var_95']):>{var_w}}"
            )

        # If benchmark stats are available and benchmark is external to portfolio, show it once after portfolio tickers
        if bench_stats is not None:
            write("")
            b_longest = f"{bench_stats.get('longest_drawdown_days', 0)}d"
            bench_label = f"{bench_ticker} (bench)"
            write(
                f"{bench_label:<{label_w}} {pct(bench_stats['total_return']):>{ret_w}} {pct(bench_stats['cagr']):>{cagr_w}} "
                f"{pct(bench_stats['volatility'], signed=False):>{vol_w}} {pct(bench_stats['max_drawdown']):>{maxdd_w}} {b_longest:>{longest_w}} "
                f"{num(bench_stats['sharpe']):>{sharpe_w}} {pct(bench_stats['win_rate'], signed=False):>{win_w}} {pct(bench_stats['var_95']):>{var_w}}"
            )

        tickers = list(self.analytics.returns_df.columns)
        if len(tickers) == 2:
            section("Correlation")
            corr = self.analytics.returns_df[tickers[0]].corr(self.analytics.returns_df[tickers[1]])
            write(
                f"{tickers[0]} vs {tickers[1]}: {corr:+.2f}",
                "dim",
            )
            write("Correlation is calculated from aligned daily returns.", "dim")
        elif len(tickers) >= 3:
            section("Correlation Matrix")
            corr = self.analytics.returns_df.corr()
            col_w = max(8, max(len(ticker) for ticker in tickers) + 2)
            write(" " * col_w + "".join(f"{ticker:>{col_w}}" for ticker in tickers), "dim")
            write(" " * col_w + "".join(f"{'-' * min(col_w - 1, 8):>{col_w}}" for _ in tickers), "dim")
            for row_ticker in tickers:
                row = f"{row_ticker:<{col_w}}"
                for col_ticker in tickers:
                    row += f"{corr.loc[row_ticker, col_ticker]:>{col_w}.2f}"
                write(row)
            write("Correlation is calculated from aligned daily returns.", "dim")

        section("Correctness Notes")
        notes = [
            "Statistics marked with * are estimates or rely on assumptions such as annualization, risk-free rate, historical quantiles, or modeled transaction costs.",
            "Total return and CAGR are calculated from the normalized portfolio value series.",
            "Portfolio return/risk metrics include modeled transaction costs when periodic rebalancing is enabled.",
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
                charts.draw_portfolio_chart(self.fig, self.analytics, getattr(self, "benchmark_prices", None), getattr(self, "benchmark_ticker", None))
            else:
                charts.draw_individual_chart(self.fig, self.analytics, view)
            self.canvas.draw()
