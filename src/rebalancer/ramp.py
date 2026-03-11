"""ramp.py — Build buy-only ramp-up contribution plans."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import cast

import pandas as pd

from rebalancer.config import PortfolioConfig


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

CATEGORY_RAMP_WEIGHTS = {
    "US Large-Cap Equities": {"stage1": 0.24, "stage2": 0.18},
    "US Small/Mid-Cap Equities": {"stage1": 0.08, "stage2": 0.09},
    "Developed ex-US Equities": {"stage1": 0.10, "stage2": 0.10},
    "Emerging Markets Equities": {"stage1": 0.06, "stage2": 0.08},
    "Global Real Estate": {"stage1": 0.05, "stage2": 0.07},
    "Precious Metals/Gold": {"stage1": 0.07, "stage2": 0.09},
    "Broad Commodities": {"stage1": 0.05, "stage2": 0.08},
    "Energy/Resources": {"stage1": 0.05, "stage2": 0.07},
    "Bonds/Fixed Income": {"stage1": 0.18, "stage2": 0.13},
    "Cash/Short-Term": {"stage1": 0.12, "stage2": 0.11},
}


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


STEP_COLUMNS = [
    "stage",
    "month",
    "trade_date",
    "contribution",
    "buy_count",
    "portfolio_value_after_buy",
]


def validate_contribution_amount(
    amount: float | str,
    *,
    field_name: str = "contribution",
) -> float:
    """Validate a positive contribution amount with cent precision."""
    try:
        value = Decimal(str(amount))
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be numeric") from exc

    if value <= 0:
        raise ValueError(f"{field_name} must be positive")

    if value != value.quantize(Decimal("0.01")):
        raise ValueError(f"{field_name} must not include sub-cent precision")

    return float(value)


def infer_ramp_stage(funded_ratio: float) -> str:
    """Infer stage from funded ratio in [0, 1]."""
    if funded_ratio < 0.0 or funded_ratio > 1.0:
        raise ValueError("funded_ratio must be between 0.0 and 1.0")
    if funded_ratio <= 0.30:
        return "stage1"
    if funded_ratio <= 0.70:
        return "stage2"
    return "final"


def parse_ramp_steps(step_specs: list[str] | tuple[str, ...]) -> list[RampStep]:
    """Parse user-provided step specs in the form YYYY-MM:stage:amount."""
    if not step_specs:
        raise ValueError("At least one step is required")

    parsed: list[RampStep] = []

    for spec in step_specs:
        parts = [p.strip() for p in spec.split(":")]
        if len(parts) != 3:
            raise ValueError(
                f"Invalid step '{spec}'. Expected format YYYY-MM:stage:amount"
            )

        month_part, stage_part, amount_part = parts
        stage = stage_part.lower()
        if stage not in {"stage1", "stage2", "final"}:
            raise ValueError(
                f"Invalid stage in '{spec}'. Stage must be one of stage1, stage2, final"
            )

        try:
            year_s, month_s = month_part.split("-")
            year = int(year_s)
            month = int(month_s)
        except ValueError as exc:
            raise ValueError(f"Invalid month in '{spec}'. Expected YYYY-MM") from exc

        if month < 1 or month > 12:
            raise ValueError(f"Invalid month in '{spec}'. Month must be in 01..12")

        try:
            contribution = validate_contribution_amount(
                amount_part,
                field_name=f"Contribution in '{spec}'",
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        parsed.append(
            RampStep(
                year=year,
                month=month,
                stage=stage,
                contribution=contribution,
            )
        )

    parsed = sorted(parsed, key=lambda s: (s.year, s.month))

    seen_months: set[tuple[int, int]] = set()
    for step in parsed:
        key = (step.year, step.month)
        if key in seen_months:
            raise ValueError(f"Duplicate month in step list: {step.month_key}")
        seen_months.add(key)

    return parsed


def _resolve_stage_weight(label: str, stage: str, default_weight: float) -> float:
    label_l = label.lower()
    for category_label, stage_weights in CATEGORY_RAMP_WEIGHTS.items():
        category_l = category_label.lower()
        if category_l in label_l or label_l in category_l:
            return stage_weights[stage]
    # Fallback for custom labels: keep configured target weight.
    return default_weight


def get_ramp_target_weights(config: PortfolioConfig, stage: str) -> dict[str, float]:
    """Get per-ticker ramp target weights for the selected stage."""
    if stage == "final":
        return config.target_weights()

    raw_weights = {
        holding.ticker: _resolve_stage_weight(
            holding.label,
            stage,
            holding.target_weight,
        )
        for holding in config.holdings
    }

    total = sum(raw_weights.values())
    if total <= 0:
        raise ValueError("Ramp stage weights must sum to a positive number")

    # Normalize to exactly 1.0 if fallback labels changed the total.
    return {ticker: weight / total for ticker, weight in raw_weights.items()}


def build_ramp_plan(
    *,
    config: PortfolioConfig,
    shares_by_ticker: dict[str, float],
    prices: dict[str, float],
    contribution: float,
    stage: str,
    round_values: bool = True,
) -> pd.DataFrame:
    """Build a buy-only allocation plan for a new contribution."""
    contribution = validate_contribution_amount(contribution)

    target_weights = get_ramp_target_weights(config, stage)

    current_values = {
        ticker: float(shares_by_ticker.get(ticker, 0.0)) * float(prices[ticker])
        for ticker in config.tickers()
    }
    current_total = sum(current_values.values())
    post_total = current_total + contribution

    target_values = {
        ticker: target_weights[ticker] * post_total for ticker in config.tickers()
    }
    deficits = {
        ticker: max(target_values[ticker] - current_values[ticker], 0.0)
        for ticker in config.tickers()
    }

    total_deficit = sum(deficits.values())
    if total_deficit > 0:
        buy_values = {
            ticker: contribution * (deficits[ticker] / total_deficit)
            for ticker in config.tickers()
        }
    else:
        buy_values = {
            ticker: contribution * target_weights[ticker] for ticker in config.tickers()
        }

    rows: list[dict[str, float | str]] = []

    def _fmt(value: float, digits: int) -> float:
        return round(value, digits) if round_values else float(value)

    for ticker in config.tickers():
        price = float(prices[ticker])
        current_shares = float(shares_by_ticker.get(ticker, 0.0))
        buy_value = buy_values[ticker]
        buy_shares = buy_value / price if price > 0 else 0.0

        post_shares = current_shares + buy_shares
        post_value = current_values[ticker] + buy_value
        post_weight = post_value / post_total if post_total > 0 else 0.0

        rows.append(
            {
                "ticker": ticker,
                "price": _fmt(price, 4),
                "current_shares": _fmt(current_shares, 6),
                "current_value": _fmt(current_values[ticker], 2),
                "ramp_target_weight": _fmt(target_weights[ticker], 6),
                "target_value_after_contribution": _fmt(target_values[ticker], 2),
                "deficit_value": _fmt(deficits[ticker], 2),
                "buy_value": _fmt(buy_value, 2),
                "buy_shares": _fmt(buy_shares, 6),
                "post_shares": _fmt(post_shares, 6),
                "post_value": _fmt(post_value, 2),
                "post_weight": _fmt(post_weight, 6),
            }
        )

    plan = pd.DataFrame(rows, columns=RAMP_COLUMNS)
    return plan.sort_values(by="buy_value", ascending=False).reset_index(drop=True)


def run_ramp_progression(
    *,
    config: PortfolioConfig,
    steps: list[RampStep],
    prices: pd.DataFrame,
    initial_shares: dict[str, float],
) -> RampProgressionResult:
    """Simulate staged monthly contributions and return progression summary."""
    if not steps:
        raise ValueError("At least one step is required")
    if prices.empty:
        raise ValueError("Price data must contain at least one row")

    index = pd.DatetimeIndex(prices.index)
    tickers = config.tickers()
    shares = {ticker: float(initial_shares.get(ticker, 0.0)) for ticker in tickers}

    rows: list[dict[str, float | str]] = []
    total_contributed = 0.0

    for step in steps:
        month_mask = (index.year == step.year) & (index.month == step.month)
        month_prices = prices.loc[month_mask]
        if month_prices.empty:
            raise ValueError(f"No trading days found for step month {step.month_key}")

        trade_ts = pd.Timestamp(month_prices.index[0])
        price_map = {
            ticker: float(cast(float, prices.loc[trade_ts, ticker]))
            for ticker in tickers
        }

        plan = build_ramp_plan(
            config=config,
            shares_by_ticker=shares,
            prices=price_map,
            contribution=step.contribution,
            stage=step.stage,
            round_values=False,
        )

        for _, plan_row in plan.iterrows():
            shares[str(plan_row["ticker"])] += float(plan_row["buy_shares"])

        contribution_used = float(plan["buy_value"].sum())
        total_contributed += contribution_used
        portfolio_value_after_buy = sum(
            shares[ticker] * price_map[ticker] for ticker in tickers
        )

        rows.append(
            {
                "stage": step.stage,
                "month": step.month_key,
                "trade_date": trade_ts.date().isoformat(),
                "contribution": round(contribution_used, 2),
                "buy_count": int((plan["buy_value"] > 0).sum()),
                "portfolio_value_after_buy": round(portfolio_value_after_buy, 2),
            }
        )

    valuation_ts = pd.Timestamp(index[-1])
    valuation_prices = {
        ticker: float(cast(float, prices.loc[valuation_ts, ticker]))
        for ticker in tickers
    }
    final_value = sum(shares[ticker] * valuation_prices[ticker] for ticker in tickers)

    return RampProgressionResult(
        progression=pd.DataFrame(rows, columns=STEP_COLUMNS),
        final_shares=shares,
        total_contributed=round(total_contributed, 2),
        final_value=round(final_value, 2),
        valuation_date=valuation_ts.date(),
    )
