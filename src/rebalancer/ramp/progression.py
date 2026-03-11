"""Staged ramp progression simulation."""

from __future__ import annotations

from typing import cast

import pandas as pd

from rebalancer.config import PortfolioConfig
from rebalancer.ramp.models import RampProgressionResult, RampStep, STEP_COLUMNS
from rebalancer.ramp.planning import build_ramp_plan


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
