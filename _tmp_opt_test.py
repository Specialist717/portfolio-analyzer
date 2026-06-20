from analytics import PortfolioAnalytics
import pandas as pd
import numpy as np

np.random.seed(1)
idx = pd.date_range('2020-01-01', periods=120, freq='B')
prices = {
    'AAA': pd.Series(np.cumprod(1 + np.random.normal(0.0006, 0.012, size=len(idx))), index=idx),
    'BBB': pd.Series(np.cumprod(1 + np.random.normal(0.0004, 0.010, size=len(idx))), index=idx),
    'CCC': pd.Series(np.cumprod(1 + np.random.normal(0.0003, 0.015, size=len(idx))), index=idx),
}

pa = PortfolioAnalytics(prices, {'AAA': 0.4, 'BBB': 0.4, 'CCC': 0.2})
res = pa.markowitz_optimize(num_portfolios=2000, seed=42, allow_short=False)
print('sharpe:', res['sharpe'])
print('expected_annual_return:', res['expected_annual_return'])
print('annual_volatility:', res['annual_volatility'])
print('weights:')
for t, w in res['weights'].items():
    print(f"{t}: {w*100:.2f}%")
