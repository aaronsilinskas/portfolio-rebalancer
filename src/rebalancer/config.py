"""
config.py — Load and validate the portfolio configuration from a YAML file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class HoldingConfig:
    ticker: str
    label: str
    target_weight: float


@dataclass
class DriftConfig:
    mode: Literal["absolute", "relative"]
    threshold: float


@dataclass
class RebalanceConfig:
    schedule: str
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


def load_config(path: Path | str) -> PortfolioConfig:
    """Load and validate a portfolio configuration from a YAML file."""
    raw = yaml.safe_load(Path(path).read_text())

    portfolio_raw = raw["portfolio"]
    rebalance_raw = raw["rebalance"]
    drift_raw = rebalance_raw["drift"]

    holdings = [
        HoldingConfig(
            ticker=h["ticker"],
            label=h["label"],
            target_weight=float(h["target_weight"]),
        )
        for h in portfolio_raw["holdings"]
    ]

    total_weight = sum(h.target_weight for h in holdings)
    if abs(total_weight - 1.0) >= 1e-6:
        raise ValueError(f"Target weights must sum to 1.0, but got {total_weight:.6f}")

    drift = DriftConfig(
        mode=drift_raw["mode"],
        threshold=float(drift_raw["threshold"]),
    )
    rebalance = RebalanceConfig(
        schedule=rebalance_raw["schedule"],
        min_days_between_rebalances=int(rebalance_raw["min_days_between_rebalances"]),
        drift=drift,
    )

    return PortfolioConfig(
        name=portfolio_raw["name"],
        holdings=holdings,
        rebalance=rebalance,
    )
