"""Ramp datamodels and shared schema constants."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


RAMP_COLUMNS = [
    "ticker",
    "price",
    "current_shares",
    "current_value",
    "ramp_target_weight",
    "target_value_after_contribution",
    "deficit_value",
    "buy_value",
    "buy_shares",
    "post_shares",
    "post_value",
    "post_weight",
]

STEP_COLUMNS = [
    "stage",
    "month",
    "trade_date",
    "contribution",
    "buy_count",
    "portfolio_value_after_buy",
]


@dataclass(frozen=True)
class RampStep:
    year: int
    month: int
    stage: str
    contribution: float

    @property
    def month_key(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True)
class RampProgressionResult:
    progression: pd.DataFrame
    final_shares: dict[str, float]
    total_contributed: float
    final_value: float
    valuation_date: date
