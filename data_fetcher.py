"""Yahoo Finance data access helpers."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf


class DataFetcher:
    """Fetches market data from Yahoo Finance."""

    @staticmethod
    def fetch_prices(
        tickers: List[str],
        start: str,
        end: str,
    ) -> Tuple[Dict[str, pd.Series], List[str]]:
        """
        Download daily adjusted-close prices for every ticker.

        Parameters
        ----------
        tickers : list of uppercase ticker strings, e.g. ['SPY', 'AAPL']
        start   : ISO date string 'YYYY-MM-DD'
        end     : ISO date string 'YYYY-MM-DD'

        Returns
        -------
        prices : dict { ticker: pd.Series(float, index=DatetimeIndex) }
                 Only tickers with valid data are included.
        failed : list of tickers that returned no data.

        Raises
        ------
        ValueError  if *no* ticker returns any data at all.
        """
        prices: Dict[str, pd.Series] = {}
        failed: List[str] = []

        for ticker in tickers:
            try:
                raw = yf.download(
                    ticker,
                    start=start,
                    end=end,
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if raw.empty or "Close" not in raw.columns:
                    failed.append(ticker)
                    continue

                series = raw["Close"].squeeze().dropna()
                if series.empty:
                    failed.append(ticker)
                else:
                    prices[ticker] = series

            except Exception:
                failed.append(ticker)

        if not prices:
            raise ValueError(f"No valid data returned for any ticker: {tickers}")

        return prices, failed

    @staticmethod
    def get_inception_date(tickers: List[str]) -> Optional[date]:
        """
        Find the earliest date that has data for *all* tickers.

        Downloads history from 1990 and takes the latest first-available
        date so that every ticker in the portfolio has data on the same
        start date. Returns None if the lookup fails for any ticker.
        """
        first_dates: List[date] = []

        for ticker in tickers:
            try:
                raw = yf.download(
                    ticker,
                    start="1990-01-01",
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if raw.empty:
                    return None
                first_dates.append(raw.index[0].date())
            except Exception:
                return None

        if not first_dates:
            return None

        # The common inception date is the latest first-available ticker date.
        return max(first_dates)
