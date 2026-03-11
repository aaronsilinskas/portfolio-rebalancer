"""Configuration data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


DriftMode = Literal["absolute", "relative"]
RebalanceSchedule = Literal["2nd_wednesday"]


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
