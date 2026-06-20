"""
Portfolio analytics engine.

This module contains pure computation only: it receives price series and
weights, then produces a normalized portfolio path and risk/return metrics.
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


class PortfolioAnalytics:
    """Computes portfolio performance metrics from price series and weights."""

    RISK_FREE_RATE: float = 0.04  # Annual assumption used by Sharpe and Sortino.

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
        weights : { ticker: allocation fraction 0-1 }, must sum to 1.
        rebalance_period_days : number of trading days between targeted rebalances.
        transaction_cost_rate : fraction of turnover paid as transaction cost.
        """
        self.prices = prices
        self.weights = self._validate_weights(weights)

        # Use common trading dates so all assets are evaluated on the same timeline.
        self.price_df: pd.DataFrame = pd.DataFrame(prices).dropna()
        if len(self.price_df) < 2:
            raise ValueError(
                "At least two common price dates are required to compute portfolio statistics."
            )

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
                    # Buys and sells offset, so traded value is half the absolute drift.
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

    def individual_value(self, ticker: str) -> pd.Series:
        """Return a normalised value series for one ticker, starting at 1.0."""
        series = self.price_df[ticker].dropna()
        return series / series.iloc[0]

    @staticmethod
    def _max_drawdown_period(value_series: pd.Series) -> tuple[float, object, object]:
        """Return max drawdown plus its peak and trough timestamps."""
        rolling_max = value_series.cummax()
        drawdown_series = (value_series - rolling_max) / rolling_max
        trough_idx = drawdown_series.idxmin()
        peak_idx = value_series.loc[:trough_idx].idxmax()
        return float(drawdown_series.min()), peak_idx, trough_idx

    @staticmethod
    def _longest_drawdown_period(value_series: pd.Series) -> Dict:
        """Return the longest calendar-day span spent below a prior high."""
        rolling_max = value_series.cummax()
        underwater = value_series < rolling_max
        longest = 0
        start = None
        longest_start = None
        longest_end = None

        for idx, is_underwater in underwater.items():
            if is_underwater and start is None:
                start = idx
            elif not is_underwater and start is not None:
                days = (idx.date() - start.date()).days
                if days > longest:
                    longest = days
                    longest_start = start
                    longest_end = idx
                start = None

        if start is not None:
            end = value_series.index[-1]
            days = (end.date() - start.date()).days
            if days > longest:
                longest = days
                longest_start = start
                longest_end = end

        return {
            "days": int(longest),
            "start": longest_start.date() if longest_start is not None else None,
            "end": longest_end.date() if longest_end is not None else None,
        }

    @classmethod
    def _return_stats(
        cls,
        value_series: pd.Series,
        risk_free_rate: float,
    ) -> Dict:
        """Compute reusable return/risk statistics for a value series."""
        returns = value_series.pct_change().dropna()
        if len(value_series) < 2 or returns.empty:
            raise ValueError(
                "At least two price dates are required to compute return statistics."
            )

        start_date = value_series.index[0].date()
        end_date = value_series.index[-1].date()
        n_days = (end_date - start_date).days
        n_years = n_days / 365.25

        total_return = value_series.iloc[-1] / value_series.iloc[0] - 1.0
        cagr = (
            (value_series.iloc[-1] / value_series.iloc[0]) ** (1 / n_years) - 1
            if n_years > 0
            else 0.0
        )

        max_dd, peak_idx, trough_idx = cls._max_drawdown_period(value_series)
        rolling_max = value_series.cummax()
        drawdown_series = (value_series - rolling_max) / rolling_max

        volatility = returns.std() * np.sqrt(252)
        # Convert annual risk-free rate to a per-trading-day rate using discrete compounding
        # (more precise than simple division for non-negligible rates).
        daily_rf = (1.0 + risk_free_rate) ** (1.0 / 252.0) - 1.0
        excess = returns - daily_rf
        excess_std = excess.std()
        sharpe = (
            (excess.mean() / excess_std) * np.sqrt(252)
            if excess_std > 0
            else 0.0
        )

        # Sortino: downside deviation computed on excess returns (below daily_rf)
        downside = excess[excess < 0]
        downside_std = downside.std() * np.sqrt(252)
        if not np.isfinite(downside_std):
            downside_std = 0.0
        sortino = (
            ((returns.mean() - daily_rf) * 252.0) / downside_std
            if downside_std > 0
            else 0.0
        )

        best_day_idx = returns.idxmax()
        worst_day_idx = returns.idxmin()
        positive_days = int((returns > 0).sum())
        negative_days = int((returns < 0).sum())
        flat_days = int((returns == 0).sum())

        var_95 = returns.quantile(0.05)
        tail_returns = returns[returns <= var_95]
        cvar_95 = tail_returns.mean() if not tail_returns.empty else var_95
        calmar = cagr / abs(max_dd) if max_dd < 0 else 0.0
        ulcer_index = np.sqrt(np.mean(np.square(drawdown_series * 100)))
        skew = returns.skew()
        kurtosis = returns.kurtosis()
        if not np.isfinite(skew):
            skew = 0.0
        if not np.isfinite(kurtosis):
            kurtosis = 0.0

        longest_drawdown = cls._longest_drawdown_period(value_series)

        return {
            "total_return": float(total_return),
            "cagr": float(cagr),
            "annualized_return": float(returns.mean() * 252),
            "max_drawdown": float(max_dd),
            "drawdown_start": peak_idx.date(),
            "drawdown_end": trough_idx.date(),
            "volatility": float(volatility),
            "downside_volatility": float(downside_std),
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "calmar": float(calmar),
            "best_day": float(returns.loc[best_day_idx]),
            "worst_day": float(returns.loc[worst_day_idx]),
            "best_day_date": best_day_idx.date(),
            "worst_day_date": worst_day_idx.date(),
            "avg_daily_return": float(returns.mean()),
            "median_daily_return": float(returns.median()),
            "win_rate": float(positive_days / len(returns)),
            "positive_days": positive_days,
            "negative_days": negative_days,
            "flat_days": flat_days,
            "var_95": float(var_95),
            "cvar_95": float(cvar_95),
            "skew": float(skew),
            "kurtosis": float(kurtosis),
            "ulcer_index": float(ulcer_index),
            "longest_drawdown_days": longest_drawdown["days"],
            "longest_drawdown_start": longest_drawdown["start"],
            "longest_drawdown_end": longest_drawdown["end"],
            "start_date": start_date,
            "end_date": end_date,
            "n_days": int(n_days),
            "n_trading_days": int(len(returns)),
        }

    def compute_stats(self) -> Dict:
        """Compute and return a dictionary of portfolio statistics."""
        pv = self.portfolio_value
        if len(pv) < 2 or self.portfolio_returns.empty:
            raise ValueError(
                "At least two common price dates are required to compute portfolio statistics."
            )

        result = self._return_stats(pv, self.RISK_FREE_RATE)
        result.update({
            "rebalance_cost": float(self.total_transaction_cost),
            "final_allocations": self.final_allocations,
            "rebalance_period_days": self.rebalance_period_days,
            "transaction_cost_rate": self.transaction_cost_rate,
        })
        return result

    def compute_ticker_stats(self) -> Dict[str, Dict]:
        """Compute the same core statistics for each individual ticker."""
        return {
            ticker: self._return_stats(self.individual_value(ticker), self.RISK_FREE_RATE)
            for ticker in self.price_df.columns
        }

    def markowitz_optimize(
        self,
        num_portfolios: int = 20000,
        seed: Optional[int] = None,
        allow_short: bool = False,
    ) -> Dict:
        """
        Monte-Carlo Markowitz-style optimizer that searches for portfolio weights
        maximizing the Sharpe ratio subject to constraints.

        Notes:
        - When allow_short is False weights are constrained to be non-negative and sum to 1 (no shorting).
        - This implementation uses randomized sampling (Dirichlet for long-only). Results are stochastic;
          pass a fixed seed for reproducible outcomes. For stable/production use a deterministic
          quadratic-programming solver with covariance shrinkage (e.g. Ledoit-Wolf) is recommended.

        Returns:
            dict with keys: weights (ticker->float), expected_annual_return,
            annual_volatility, sharpe, num_portfolios.
        """
        prices_df = self.price_df
        returns = self.returns_df
        tickers = list(prices_df.columns)
        if len(tickers) == 0:
            raise ValueError("No price data available for optimization.")

        n = len(tickers)
        mu_daily = returns.mean()
        mu_ann = mu_daily * 252
        cov_ann = returns.cov() * 252
        rf = float(self.RISK_FREE_RATE)

        rng = np.random.default_rng(seed)

        best_sharpe = -np.inf
        best_weights = None
        best_ret = 0.0
        best_vol = 0.0

        # Sampling loop: Dirichlet for non-negative weights, normal+normalize when shorts allowed
        if allow_short:
            for _ in range(num_portfolios):
                w = rng.normal(size=n)
                # normalize to sum to 1 (may contain negatives)
                s = float(np.sum(w))
                if s == 0:
                    continue
                w = w / s
                ret = float(np.dot(w, mu_ann.values))
                vol = float(np.sqrt(w @ cov_ann.values @ w))
                if vol <= 0 or not np.isfinite(vol):
                    continue
                sharpe = (ret - rf) / vol
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_weights = w.copy()
                    best_ret = ret
                    best_vol = vol
        else:
            for _ in range(num_portfolios):
                w = rng.dirichlet(np.ones(n))
                ret = float(np.dot(w, mu_ann.values))
                vol = float(np.sqrt(w @ cov_ann.values @ w))
                if vol <= 0 or not np.isfinite(vol):
                    continue
                sharpe = (ret - rf) / vol
                if sharpe > best_sharpe:
                    best_sharpe = sharpe
                    best_weights = w.copy()
                    best_ret = ret
                    best_vol = vol

        if best_weights is None:
            raise ValueError("Optimization failed to find a valid portfolio.")

        result_weights = {tickers[i]: float(best_weights[i]) for i in range(n)}
        return {
            "weights": result_weights,
            "expected_annual_return": float(best_ret),
            "annual_volatility": float(best_vol),
            "sharpe": float(best_sharpe),
            "num_portfolios": int(num_portfolios),
        }
