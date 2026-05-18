"""
gui/charts.py
-------------
Pure chart-drawing functions that operate on matplotlib Figure / Axes objects.

All functions are stateless: they receive data, draw to the provided figure,
and return nothing. The caller is responsible for calling canvas.draw().
"""

from __future__ import annotations

from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import mplcursors
import numpy as np
from matplotlib.figure import Figure

from analytics import PortfolioAnalytics
from config import CHART_COLORS, PALETTE


# ── Shared axis styling ───────────────────────────────────────────────────────

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


# ── Chart functions ───────────────────────────────────────────────────────────

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


def draw_stats_page(
    fig: Figure,
    analytics: PortfolioAnalytics,
    stats: Optional[dict],
) -> None:
    """Draw a full-screen statistics page for the portfolio and tickers."""
    fig.clear()
    ax = fig.add_subplot(111)
    style_axes(ax)

    if stats is None:
        ax.text(
            0.5, 0.5,
            "Run analysis to view portfolio statistics.",
            transform=ax.transAxes,
            ha="center",
            va="center",
            fontsize=14,
            color=PALETTE["text_dim"],
            fontfamily="Segoe UI",
        )
        ax.set_xticks([])
        ax.set_yticks([])
        return

    def fmt_pct(value: float) -> str:
        return f"{value * 100:+.2f}%"

    lines = [
        "PORTFOLIO STATISTICS",
        "---------------------",
        f"Period: {stats['start_date'].strftime('%Y-%m-%d')} → {stats['end_date'].strftime('%Y-%m-%d')}",
        f"Total Return: {fmt_pct(stats['total_return'])}",
        f"  (after transaction costs: {stats.get('rebalance_cost', 0.0) * 100:.4f}%)",
        f"CAGR: {fmt_pct(stats['cagr'])}",
        f"Volatility: {fmt_pct(stats['volatility'])}",
        f"Sharpe Ratio: {stats['sharpe']:+.2f}",
        f"Sortino Ratio: {stats['sortino']:+.2f}",
        f"Max Drawdown: {fmt_pct(stats['max_drawdown'])}",
        f"Drawdown period: {stats['drawdown_start'].strftime('%Y-%m-%d')} → {stats['drawdown_end'].strftime('%Y-%m-%d')}",
        "",
        "FINAL ALLOCATIONS",
    ]

    final_allocations = stats.get('final_allocations', {})
    for ticker, alloc in sorted(final_allocations.items()):
        lines.append(f"  {ticker}: {alloc * 100:.1f}%")

    lines.append("")
    lines.append("INDIVIDUAL TICKER SUMMARY")
    lines.append("------------------------")

    for ticker, series in analytics.prices.items():
        returns = series.pct_change().dropna()
        total_return = series.iloc[-1] / series.iloc[0] - 1
        volatility = returns.std() * np.sqrt(252)
        rolling_max = series.cummax()
        drawdown = (series - rolling_max) / rolling_max
        max_dd = drawdown.min()
        lines.append(
            f"{ticker}: Return {fmt_pct(total_return)}, Vol {fmt_pct(volatility)}, "
            f"Max DD {fmt_pct(max_dd)}"
        )

    ax.text(
        0.03, 0.97,
        "\n".join(lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        color=PALETTE["text"],
        fontfamily="Segoe UI",
        linespacing=1.3,
    )
    ax.set_xticks([])
    ax.set_yticks([])


def draw_portfolio_chart(fig: Figure, analytics: PortfolioAnalytics) -> None:
    """
    Plot the combined portfolio value with a drawdown sub-panel.

    Layout: top 75 % = cumulative return line, bottom 25 % = drawdown fill.
    """
    pv = analytics.portfolio_value
    fig.clear()

    # Two-panel layout
    gs = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1], sharex=ax1)

    for ax in (ax1, ax2):
        style_axes(ax)

    # Portfolio value line
    ax1.plot(
        pv.index, pv.values,
        color=PALETTE["accent"],
        linewidth=1.8,
        zorder=3,
    )
    if hasattr(analytics, "real_portfolio_value") and not analytics.real_portfolio_value.empty:
        ax1.plot(
            analytics.real_portfolio_value.index,
            analytics.real_portfolio_value.values,
            color=PALETTE["accent2"],
            linewidth=1.6,
            linestyle="--",
            zorder=3,
        )

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

    # Drawdown panel
    rolling_max = pv.cummax()
    drawdown = (pv - rolling_max) / rolling_max * 100

    ax2.fill_between(drawdown.index, 0, drawdown.values, color=PALETTE["danger"], alpha=0.5)
    ax2.plot(drawdown.index, drawdown.values, color=PALETTE["danger"], linewidth=0.9)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    ax2.set_ylabel("Drawdown", fontsize=8, color=PALETTE["text_dim"], fontfamily="Segoe UI")

    # Date formatting on the shared x-axis
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
