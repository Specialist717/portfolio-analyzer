"""
config.py
---------
Application-wide constants: package requirements, colour palette,
chart colour cycle, and the default demo portfolio.
"""

# ── Packages required at runtime ─────────────────────────────────────────────
# Keys = importable module name; values = pip install name.
REQUIRED_PACKAGES: dict[str, str] = {
    "yfinance":   "yfinance",
    "pandas":     "pandas",
    "matplotlib": "matplotlib",
    "numpy":      "numpy",
    "mplcursors": "mplcursors",
}

# ── Dark-theme colour palette ─────────────────────────────────────────────────
PALETTE: dict[str, str] = {
    "bg":        "#0f1117",   # near-black background
    "surface":   "#1a1d27",   # card / panel surface
    "surface2":  "#22263a",   # slightly lighter surface
    "accent":    "#4f8ef7",   # vivid blue accent
    "accent2":   "#6ee7b7",   # mint green secondary accent
    "warn":      "#f97316",   # amber warning
    "danger":    "#ef4444",   # red error
    "text":      "#e8eaf0",   # primary text
    "text_dim":  "#7c8196",   # muted text
    "border":    "#2e3148",   # subtle border
    "chart_bg":  "#12141e",   # chart canvas background
}

# matplotlib colour cycle — one colour per ticker line
CHART_COLORS: list[str] = [
    "#4f8ef7", "#6ee7b7", "#f97316",
    "#a78bfa", "#f43f5e", "#fbbf24",
    "#34d399", "#60a5fa",
]

# Default rebalance settings
REBALANCE_PERIOD_OPTIONS: list[str] = ["30", "60", "90", "180", "365"]
DEFAULT_REBALANCE_PERIOD: str = "30"
REBALANCE_COST_RATE: float = 0.001  # 0.1 % per turnover

# Pre-filled demo portfolio shown on first launch
DEFAULT_HOLDINGS: list[tuple[str, str]] = [
    ("SPY", "60"),
    ("QQQ", "25"),
    ("GLD", "15"),
]
