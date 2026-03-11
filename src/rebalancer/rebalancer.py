"""
rebalancer.py — Core rebalancing logic: determine required trades to restore target weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from rebalancer.portfolio import Portfolio


@dataclass
class Trade:
    ticker: str
    action: Literal["BUY", "SELL"]
    shares: float  # positive number
    price: float
    value: float  # shares * price


def compute_trades(portfolio: Portfolio) -> list[Trade]:
    """
    Compute the set of trades needed to restore all holdings to their target weights.

    Sells are executed first (conceptually) to raise cash, which is then used to fund buys.
    Returns an empty list if no rebalancing is needed.
    """
    target_weights = portfolio.config.target_weights()
    total_value = portfolio.total_value

    trades: list[Trade] = []
    for ticker, target_weight in target_weights.items():
        holding = portfolio.holdings[ticker]
        target_value = total_value * target_weight
        delta_value = target_value - holding.market_value

        if abs(delta_value) < 0.01:
            continue  # negligible difference; skip

        shares_delta = delta_value / holding.price
        action = "BUY" if shares_delta > 0 else "SELL"
        trades.append(
            Trade(
                ticker=ticker,
                action=action,
                shares=abs(shares_delta),
                price=holding.price,
                value=abs(delta_value),
            )
        )

    return trades


def apply_trades(portfolio: Portfolio, trades: list[Trade]) -> None:
    """Apply a list of trades to the portfolio, updating share counts in place."""
    for trade in trades:
        holding = portfolio.holdings[trade.ticker]
        if trade.action == "BUY":
            holding.shares += trade.shares
        else:
            holding.shares -= trade.shares


def project_shares_after_trades(
    shares_by_ticker: dict[str, float],
    trades: list[Trade],
) -> dict[str, float]:
    """Return projected share counts after applying the proposed trades."""
    projected = shares_by_ticker.copy()
    for trade in trades:
        signed_shares = trade.shares if trade.action == "BUY" else -trade.shares
        next_shares = projected.get(trade.ticker, 0.0) + signed_shares
        if next_shares < -1e-9:
            raise ValueError(f"Trade would result in a negative share count for {trade.ticker}")
        projected[trade.ticker] = 0.0 if abs(next_shares) < 1e-9 else next_shares
    return projected
