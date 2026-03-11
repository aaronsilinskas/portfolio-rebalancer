"""Buy-only ramp allocation planning."""

from __future__ import annotations

import pandas as pd

from rebalancer.config import PortfolioConfig
from rebalancer.ramp.models import RAMP_COLUMNS
from rebalancer.ramp.parsing import validate_contribution_amount
from rebalancer.ramp.weights import get_ramp_target_weights


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
