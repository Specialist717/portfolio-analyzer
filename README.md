Portfolio Analyzer — academic project

Overview
--------
Portfolio Analyzer fetches historical prices, computes portfolio statistics (return, risk, drawdown, Sharpe, Sortino), simulates periodic rebalancing, and includes a Markowitz Monte‑Carlo optimizer (long-only). The GUI shows portfolio and benchmark charts and statistics.

Evaluation mapping (for reviewers)
---------------------------------
- Czystość kodu (1-20): follow PEP8, add type hints, run black/isort, reduce duplicate code.
- Złożoność (1-30): use robust estimators (Ledoit‑Wolf), deterministic QP solver for efficient frontier.
- Poprawność (1-20): add unit tests for edge-cases (missing data, zero-weights), CI checks.
- Innowacyjność (1-10): add efficient-frontier visualization, turnover-aware optimization, interactive brushing on charts.
- Opis projektu (1-10): document assumptions, data sources, and methodology.
- Interfejs (1-10): aesthetic layout, keyboard navigation, accessible colors, clearer dialogs.

Recommended improvements (prioritised)
-------------------------------------
1. Replace Monte‑Carlo optimizer with a deterministic QP (scipy.optimize or cvxpy) + Ledoit‑Wolf shrinkage for stability and reproducibility.
2. Add unit tests (pytest) covering DataFetcher, analytics edge-cases, optimizer determinism.
3. Add CI (GitHub Actions): run lint, typecheck (mypy), tests on push/PR.
4. Improve data handling: caching, retry logic, and informative warnings instead of hard failures.
5. Add a "safe apply" workflow: preview of rows slated for deletion before applying optimizer.
6. Add documentation: DESIGN.md explaining algorithms and assumptions; a short user manual for the GUI.
7. Use type hints across modules and add concise docstrings to public functions.
8. Replace ad-hoc rounding fixes with a small allocation util (normalize + deterministic rounding).

What changed in repo
--------------------
- README.md updated with project overview and roadmap.
- Temporary test file (_tmp_opt_test.py) removed if present.

Next steps I can take
---------------------
- Implement deterministic QP optimizer + shrinkage and compare to Monte‑Carlo.
- Add pytest tests and GitHub Actions workflow.
- Run code-style pass (black/isort) and add mypy typing.
- Do focused comment cleanup: remove nonessential comments and add concise docstrings where needed.

If you want me to start, choose: "tests+CI", "QP optimizer", or "comment cleanup".
