"""Shared CLI default paths."""

from pathlib import Path


DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "portfolio.yaml"
DEFAULT_POSITIONS = Path(__file__).parent.parent.parent / "config" / "positions.yaml"
DEFAULT_DAILY_OUTPUT = Path("output") / "daily"
DEFAULT_COMPARE_OUTPUT = Path("output") / "comparisons"
DEFAULT_RAMP_OUTPUT = Path("output") / "ramp-plans"
DEFAULT_RAMP_BACKTEST_OUTPUT = Path("output") / "ramp-backtests"
