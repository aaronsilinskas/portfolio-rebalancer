"""
config.py — Load and validate the portfolio configuration from a YAML file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml


DriftMode = Literal["absolute", "relative"]
RebalanceSchedule = Literal["2nd_wednesday"]

VALID_DRIFT_MODES = {"absolute", "relative"}
VALID_SCHEDULES = {"2nd_wednesday"}


@dataclass
class HoldingConfig:
    ticker: str
    label: str
    target_weight: float


@dataclass
class DriftConfig:
    mode: DriftMode
    threshold: float


@dataclass
class RebalanceConfig:
    schedule: RebalanceSchedule
    min_days_between_rebalances: int
    drift: DriftConfig


@dataclass
class PortfolioConfig:
    name: str
    holdings: list[HoldingConfig]
    rebalance: RebalanceConfig

    def tickers(self) -> list[str]:
        return [h.ticker for h in self.holdings]

    def target_weights(self) -> dict[str, float]:
        return {h.ticker: h.target_weight for h in self.holdings}


def _load_yaml_file(path: Path | str) -> dict:
    raw = yaml.safe_load(Path(path).read_text()) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Expected a YAML mapping in {path}")
    return raw


def load_config(path: Path | str) -> PortfolioConfig:
    """Load and validate a portfolio configuration from a YAML file."""
    raw = _load_yaml_file(path)

    try:
        portfolio_raw = raw["portfolio"]
        rebalance_raw = raw["rebalance"]
        drift_raw = rebalance_raw["drift"]
    except KeyError as exc:
        raise ValueError(f"Missing required config key: {exc.args[0]}") from exc

    holdings_raw = portfolio_raw.get("holdings", [])
    if not holdings_raw:
        raise ValueError("Portfolio must define at least one holding")

    holdings: list[HoldingConfig] = []
    seen_tickers: set[str] = set()
    for holding_raw in holdings_raw:
        ticker = holding_raw["ticker"]
        if ticker in seen_tickers:
            raise ValueError(f"Duplicate ticker in portfolio config: {ticker}")

        target_weight = float(holding_raw["target_weight"])
        if not 0.0 < target_weight <= 1.0:
            raise ValueError(
                f"Target weight for {ticker} must be between 0 and 1, got {target_weight}"
            )

        holdings.append(
            HoldingConfig(
                ticker=ticker,
                label=holding_raw["label"],
                target_weight=target_weight,
            )
        )
        seen_tickers.add(ticker)

    total_weight = sum(h.target_weight for h in holdings)
    if abs(total_weight - 1.0) >= 1e-6:
        raise ValueError(f"Target weights must sum to 1.0, but got {total_weight:.6f}")

    mode = drift_raw["mode"]
    if mode not in VALID_DRIFT_MODES:
        raise ValueError(
            f"Unsupported drift mode: {mode}. Expected one of {sorted(VALID_DRIFT_MODES)}"
        )

    threshold = float(drift_raw["threshold"])
    if threshold <= 0:
        raise ValueError(f"Drift threshold must be positive, got {threshold}")

    schedule = rebalance_raw["schedule"]
    if schedule not in VALID_SCHEDULES:
        raise ValueError(
            f"Unsupported rebalance schedule: {schedule}. Expected one of {sorted(VALID_SCHEDULES)}"
        )

    min_days_between_rebalances = int(rebalance_raw["min_days_between_rebalances"])
    if min_days_between_rebalances < 0:
        raise ValueError(
            "min_days_between_rebalances must be greater than or equal to 0"
        )

    drift = DriftConfig(
        mode=mode,
        threshold=threshold,
    )
    rebalance = RebalanceConfig(
        schedule=schedule,
        min_days_between_rebalances=min_days_between_rebalances,
        drift=drift,
    )

    return PortfolioConfig(
        name=portfolio_raw["name"],
        holdings=holdings,
        rebalance=rebalance,
    )


def load_positions(
    path: Path | str,
    *,
    allowed_tickers: set[str] | None = None,
) -> dict[str, float]:
    """Load current portfolio share counts from a YAML file."""
    raw = _load_yaml_file(path)
    positions_raw = raw.get("positions", [])
    if not positions_raw:
        raise ValueError("Positions file must define at least one position")

    positions: dict[str, float] = {}
    for position_raw in positions_raw:
        ticker = position_raw["ticker"]
        shares = float(position_raw["shares"])
        if shares < 0:
            raise ValueError(f"Position shares for {ticker} must be non-negative")
        if ticker in positions:
            raise ValueError(f"Duplicate ticker in positions file: {ticker}")
        if allowed_tickers is not None and ticker not in allowed_tickers:
            raise ValueError(f"Ticker {ticker} is not defined in the portfolio config")
        positions[ticker] = shares

    return positions
