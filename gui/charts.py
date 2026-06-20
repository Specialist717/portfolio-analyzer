"""
Matplotlib chart drawing helpers.

The functions are stateless: callers pass in analytics data and a Figure, then
call canvas.draw() after the selected chart has been rendered.
"""

from __future__ import annotations

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mplcursors
from matplotlib.figure import Figure

from analytics import PortfolioAnalytics
from config import CHART_COLORS, PALETTE


def style_axes(ax) -> None:
    """Apply the dark theme to a matplotlib Axes object."""
    ax.set_facecolor(PALETTE["chart_bg"])
    ax.tick_params(colors=PALETTE["text_dim"], labelsize=9)
    ax.xaxis.label.set_color(PALETTE["text_dim"])
    ax.yaxis.label.set_color(PALETTE["text_dim"])
    ax.title.set_color(PALETTE["text"])
    for spine in ax.spines.values():
        spine.set_edgecolor(PALETTE["border"])
    ax.grid(
        True,
        linestyle="--",
        linewidth=0.4,
        color=PALETTE["border"],
        alpha=0.7,
    )


def draw_placeholder(fig: Figure) -> None:
    """Show a prompt before any analysis has been run."""
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)
    ax.text(
        0.5, 0.5,
        "Enter your portfolio above\nand click  ▶ RUN ANALYSIS",
        transform=ax.transAxes,
        ha="center",
        va="center",
        fontsize=14,
        color=PALETTE["text_dim"],
        fontfamily="Segoe UI",
        linespacing=2.0,
    )
    ax.set_xticks([])
    ax.set_yticks([])


from typing import Optional
import pandas as pd

def draw_portfolio_chart(
    fig: Figure,
    analytics: PortfolioAnalytics,
    benchmark: Optional[pd.Series] = None,
    benchmark_ticker: Optional[str] = None,
) -> None:
    """
    Plot the combined portfolio value with a drawdown sub-panel.

    Optionally overlay a benchmark series as a dashed, normalized line.
    """
    pv = analytics.portfolio_value
    fig.clear()

    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    for ax in (ax1, ax2):
        style_axes(ax)

    # Portfolio line
    ax1.plot(
        pv.index, pv.values,
        color=PALETTE["accent"],
        linewidth=1.8,
        zorder=3,
    )

    # Optional benchmark (dashed)
    if benchmark is not None and not benchmark.empty:
        try:
            b = benchmark.reindex(pv.index).ffill().bfill()
            if not b.empty and b.isnull().sum() < len(b):
                b_norm = b / b.iloc[0]
                ax1.plot(
                    b_norm.index,
                    b_norm.values,
                    color=PALETTE["accent2"],
                    linewidth=1.4,
                    linestyle="--",
                    zorder=2,
                    label=benchmark_ticker or "Benchmark",
                )
                # Draw legend and ensure text is visible on dark background
                legend = ax1.legend(frameon=False, loc="upper left", fontsize=9)
                try:
                    for text in legend.get_texts():
                        text.set_color(PALETTE["text"])
                except Exception:
                    pass
        except Exception:
            pass

    # Shaded fill above / below the 1.0 baseline
    ax1.fill_between(
        pv.index, 1.0, pv.values,
        where=(pv.values >= 1.0),
        alpha=0.12,
        color=PALETTE["accent"],
        interpolate=True,
    )
    ax1.fill_between(
        pv.index, 1.0, pv.values,
        where=(pv.values < 1.0),
        alpha=0.12,
        color=PALETTE["danger"],
        interpolate=True,
    )

    ax1.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"{(v - 1) * 100:+.0f}%")
    )
    ax1.set_title(
        "Portfolio Performance",
        color=PALETTE["text"],
        fontsize=12,
        fontfamily="Segoe UI",
        pad=14,
    )
    fig.subplots_adjust(left=0.08, right=0.98, top=0.92, bottom=0.12)
    ax1.axhline(1.0, color=PALETTE["border"], linewidth=0.8, zorder=2)
    plt.setp(ax1.get_xticklabels(), visible=False)

    rolling_max = pv.cummax()
    drawdown = (pv - rolling_max) / rolling_max * 100

    ax2.fill_between(drawdown.index, 0, drawdown.values, color=PALETTE["danger"], alpha=0.5)
    ax2.plot(drawdown.index, drawdown.values, color=PALETTE["danger"], linewidth=0.9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.set_ylabel("Drawdown", fontsize=8, color=PALETTE["text_dim"], fontfamily="Segoe UI")

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax2.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax2.get_xticklabels(), rotation=30, ha="right")

    mplcursors.cursor(ax1, hover=True)


def draw_individual_chart(
    fig: Figure,
    analytics: PortfolioAnalytics,
    ticker: str,
) -> None:
    """Plot a single ticker's normalised (starts-at-1) value series."""
    value = analytics.individual_value(ticker)
    ticker_list = list(analytics.prices.keys())
    color = CHART_COLORS[ticker_list.index(ticker) % len(CHART_COLORS)]

    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)

    ax.plot(value.index, value.values, color=color, linewidth=1.8, label=ticker)
    ax.fill_between(value.index, 1.0, value.values, alpha=0.12, color=color, interpolate=True)
    ax.axhline(1.0, color=PALETTE["border"], linewidth=0.8)

    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{(v - 1) * 100:+.0f}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    ax.set_title(
        f"{ticker}  –  Individual Performance",
        color=PALETTE["text"],
        fontsize=12,
        fontfamily="Segoe UI",
        pad=10,
    )

    mplcursors.cursor(ax, hover=True)
