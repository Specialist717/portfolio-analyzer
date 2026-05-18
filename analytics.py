"""
analytics.py
------------
PortfolioAnalytics — pure computation, no GUI or I/O.

Given a dict of price series and their weights this class:
- Builds a combined portfolio value series (daily rebalanced).
- Computes a comprehensive statistics dictionary.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class PortfolioAnalytics:
    """Computes portfolio performance metrics from price series and weights."""

    RISK_FREE_RATE: float = 0.04  # 4 % annual, used for Sharpe / Sortino

    def __init__(
        self,
        prices: Dict[str, pd.Series],
        weights: Dict[str, float],
        rebalance_period_days: Optional[int] = None,
        transaction_cost_rate: float = 0.0,
    ) -> None:
        """
        Parameters
        ----------
        prices  : { ticker: daily-close price series }
        weights : { ticker: allocation fraction 0–1 }, must sum to 1.
        rebalance_period_days : number of trading days between targeted rebalances.
        transaction_cost_rate : fraction of turnover paid as transaction cost.
        """
        self.prices = prices
        self.weights = self._validate_weights(weights)

        # Aligned price DataFrame (inner join — common dates only)
        self.price_df: pd.DataFrame = pd.DataFrame(prices).dropna()
        if len(self.price_df) < 2:
            raise ValueError(
                "At least two common price dates are required to compute portfolio statistics."
            )

        # Daily returns matrix
        self.returns_df: pd.DataFrame = self.price_df.pct_change().dropna()
        self.rebalance_period_days: Optional[int] = rebalance_period_days
        self.transaction_cost_rate: float = transaction_cost_rate
        self.total_transaction_cost: float = 0.0
        self.final_allocations: Dict[str, float] = {}

        self._simulate_portfolio()

    @staticmethod
    def _validate_weights(weights: Dict[str, float]) -> Dict[str, float]:
        """Return validated portfolio weights as floats."""
        if not weights:
            raise ValueError("At least one portfolio weight is required.")

        validated: Dict[str, float] = {}
        for ticker, weight in weights.items():
            value = float(weight)
            if not np.isfinite(value):
                raise ValueError(f"Weight for '{ticker}' must be a finite number.")
            if value < 0:
                raise ValueError(f"Weight for '{ticker}' cannot be negative.")
            validated[ticker] = value

        total = sum(validated.values())
        if total <= 0:
            raise ValueError("Portfolio weights must sum to a positive value.")
        if not np.isclose(total, 1.0, atol=1e-6):
            raise ValueError(f"Portfolio weights must sum to 1.0; current sum is {total:.6f}.")

        return validated

    def _simulate_portfolio(self) -> None:
        """Build the portfolio value series with optional periodic rebalancing."""
        if self.price_df.empty:
            self.portfolio_value = pd.Series(dtype=float)
            self.portfolio_returns = pd.Series(dtype=float)
            self.total_transaction_cost = 0.0
            self.final_allocations = {}
            return

        tickers = list(self.price_df.columns)
        prices = self.price_df.values
        weight_array = np.array([self.weights.get(t, 0.0) for t in tickers], dtype=float)

        # Initial holdings sized so the initial portfolio value is 1.0.
        holdings = weight_array / prices[0]
        portfolio_values = [1.0]
        total_cost = 0.0

        if self.rebalance_period_days is None or self.rebalance_period_days <= 0:
            for i in range(1, len(prices)):
                portfolio_values.append((holdings * prices[i]).sum())
        else:
            for i in range(1, len(prices)):
                current_prices = prices[i]
                current_values = holdings * current_prices
                total_value = current_values.sum()

                if i % self.rebalance_period_days == 0:
                    target_values = total_value * weight_array
                    turnover = np.sum(np.abs(target_values - current_values)) / 2.0
                    cost = turnover * self.transaction_cost_rate
                    total_cost += cost
                    net_value = total_value - cost
                    target_values = net_value * weight_array
                    holdings = target_values / current_prices
                    total_value = net_value

                portfolio_values.append(total_value)

        self.portfolio_value = pd.Series(portfolio_values, index=self.price_df.index, name="Portfolio")
        self.portfolio_returns = self.portfolio_value.pct_change().dropna()
        self.total_transaction_cost = total_cost

        final_values = holdings * prices[-1]
        final_total = final_values.sum()
        self.final_allocations = {
            tickers[i]: float(final_values[i] / final_total)
            for i in range(len(tickers))
        }

    # ── Per-ticker value series ───────────────────────────────────────────────

    def individual_value(self, ticker: str) -> pd.Series:
        """Return a normalised (starts at 1.0) value series for one ticker."""
        returns = self.price_df[ticker].pct_change().dropna()
        return (1 + returns).cumprod()

    # ── Summary statistics ────────────────────────────────────────────────────

    def compute_stats(self) -> Dict:
        """
        Compute and return a dictionary of portfolio statistics.

        Keys
        ----
        total_return    : float   (e.g. 1.45 means +145 %)
        cagr            : float   annualised compound growth rate
        max_drawdown    : float   (negative, e.g. -0.34)
        drawdown_start  : date    peak date of worst drawdown
        drawdown_end    : date    trough date of worst drawdown
        volatility      : float   annualised std of daily returns
        sharpe          : float
        sortino         : float
        best_day        : float   best single-day return
        worst_day       : float   worst single-day return
        best_day_date   : date
        worst_day_date  : date
        start_date      : date
        end_date        : date
        n_days          : int     calendar days in range
        """
        r = self.portfolio_returns
        pv = self.portfolio_value
        if len(pv) < 2 or r.empty:
            raise ValueError(
                "At least two common price dates are required to compute portfolio statistics."
            )

        # Basic dates
        start_date = pv.index[0].date()
        end_date = pv.index[-1].date()
        n_days = (end_date - start_date).days
        n_years = n_days / 365.25

        # Total return
        total_return = pv.iloc[-1] - 1.0

        # CAGR
        cagr = (pv.iloc[-1] ** (1 / n_years) - 1) if n_years > 0 else 0.0

        # Maximum drawdown
        rolling_max = pv.cummax()
        drawdown_series = (pv - rolling_max) / rolling_max
        max_dd = drawdown_series.min()

        # Drawdown period: trough → trace back to its peak
        trough_idx = drawdown_series.idxmin()
        peak_idx = pv.loc[:trough_idx].idxmax()

        # Annualised volatility
        volatility = r.std() * np.sqrt(252)

        # Sharpe ratio
        daily_rf = self.RISK_FREE_RATE / 252
        excess = r - daily_rf
        sharpe = (
            excess.mean() / excess.std() * np.sqrt(252)
            if excess.std() > 0
            else 0.0
        )

        # Sortino ratio (downside deviation only)
        downside = excess[excess < 0]
        downside_std = downside.std() * np.sqrt(252)
        sortino = (
            (r.mean() - daily_rf) * 252 / downside_std
            if downside_std > 0
            else 0.0
        )

        # Best / worst single day
        best_day_idx = r.idxmax()
        worst_day_idx = r.idxmin()

        result = {
            "total_return":   total_return,
            "cagr":           cagr,
            "max_drawdown":   max_dd,
            "drawdown_start": peak_idx.date(),
            "drawdown_end":   trough_idx.date(),
            "volatility":     volatility,
            "sharpe":         sharpe,
            "sortino":        sortino,
            "best_day":       r[best_day_idx],
            "worst_day":      r[worst_day_idx],
            "best_day_date":  best_day_idx.date(),
            "worst_day_date": worst_day_idx.date(),
            "start_date":     start_date,
            "end_date":       end_date,
            "n_days":         n_days,
            "rebalance_cost": self.total_transaction_cost,
            "final_allocations": self.final_allocations,
        }

        return result
