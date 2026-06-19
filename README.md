# Portfolio Analyzer

Academic Python project for analyzing a user-defined investment portfolio with
historical market data from Yahoo Finance.

## Goal

The application lets a user enter tickers, allocation weights, a date range, and
an optional rebalance period. It downloads adjusted daily close prices, aligns
all instruments to common trading dates, simulates the portfolio value, and
shows portfolio-level and ticker-level performance statistics.

## Implemented Analysis

- Total return, CAGR, annualized average return, volatility, and downside volatility.
- Maximum drawdown with peak/trough dates and longest underwater period.
- Sharpe, Sortino, and Calmar ratios.
- Best/worst daily return, win rate, median daily return, skew, and excess kurtosis.
- Historical 95% VaR and CVaR based on aligned daily returns.
- Allocation drift and modeled transaction-cost drag for periodic rebalancing.
- Correlation output for multi-asset portfolios.
- Interactive matplotlib charts for portfolio performance, drawdown, and individual tickers.

## Modeling Assumptions

- Prices are adjusted by Yahoo Finance through `yfinance` with `auto_adjust=True`.
- All statistics use the intersection of available ticker dates so every asset is compared on the same timeline.
- Portfolio value starts at 1.0 and initial holdings are sized from the target weights.
- If rebalancing is enabled, the model rebalances every selected number of trading rows, not calendar days.
- Transaction cost is modeled as 0.1% of traded value during each rebalance.
- Sharpe and Sortino use a fixed 4.0% annual risk-free rate converted to a daily rate.
- Annualization uses 252 trading days for daily return metrics and 365.25 calendar days for CAGR.

## Interface

The Tkinter GUI contains:

- A left control panel for tickers, weights, date range, max-range lookup, and rebalance settings.
- A chart area with tabs for portfolio, statistics, and each individual ticker.
- Validation for duplicate tickers, non-numeric weights, non-positive weights, and allocations that do not sum to 100%.
- Background threads for data downloads so the interface does not freeze during network calls.

## How To Run

```bash
python main.py
```

The bootstrap step checks required packages and installs missing dependencies
into the active environment or the local `_vendor` directory.

## Possible Improvements

- Add unit tests for portfolio simulation, rebalancing costs, and each risk metric.
- Add an export button for the statistics report as CSV or text.
- Add benchmark comparison, for example against SPY or an equal-weight portfolio.
- Add a rolling volatility or rolling Sharpe chart for more advanced time-series analysis.
- Add a small local cache for downloaded ticker data to reduce repeated network calls.
