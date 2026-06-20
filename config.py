"""Application-wide constants and default settings."""

# Import name -> pip install name.
REQUIRED_PACKAGES: dict[str, str] = {
    "yfinance":   "yfinance",
    "pandas":     "pandas",
    "matplotlib": "matplotlib",
    "numpy":      "numpy",
    "mplcursors": "mplcursors",
}

PALETTE: dict[str, str] = {
    "bg":        "#0f1117",
    "surface":   "#1a1d27",
    "surface2":  "#22263a",
    "accent":    "#4f8ef7",
    "accent2":   "#6ee7b7",
    "warn":      "#f97316",
    "danger":    "#ef4444",
    "text":      "#e8eaf0",
    "text_dim":  "#7c8196",
    "border":    "#2e3148",
    "chart_bg":  "#12141e",
}

# One chart color per ticker line before the cycle repeats.
CHART_COLORS: list[str] = [
    "#4f8ef7", "#6ee7b7", "#f97316",
    "#a78bfa", "#f43f5e", "#fbbf24",
    "#34d399", "#60a5fa",
]

REBALANCE_PERIOD_OPTIONS: list[str] = ["30", "60", "90", "180", "365"]
DEFAULT_REBALANCE_PERIOD: str = "30"
REBALANCE_COST_RATE: float = 0.001  # 0.1% of traded value.

DEFAULT_BENCHMARK: str = "SPY"

DEFAULT_HOLDINGS: list[tuple[str, str]] = [
    ("SPY", "60"),
    ("QQQ", "25"),
    ("GLD", "15"),
]
